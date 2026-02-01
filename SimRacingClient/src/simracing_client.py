import sys
from pathlib import Path

# Ensure src directory is in Python path for local imports
_src_dir = Path(__file__).parent.resolve()
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

import json
import threading
import time
import requests
from flask import Flask, request, jsonify


def disable_quickedit():
    """Disable QuickEdit mode on Windows to prevent console click from pausing the process."""
    if sys.platform != 'win32':
        return

    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32

        # Get handle to stdin
        handle = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE

        # Get current console mode
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))

        # Disable QuickEdit (0x0040) and Insert Mode (0x0020)
        ENABLE_QUICK_EDIT_MODE = 0x0040
        ENABLE_INSERT_MODE = 0x0020
        mode.value &= ~(ENABLE_QUICK_EDIT_MODE | ENABLE_INSERT_MODE)

        # Set new console mode
        kernel32.SetConsoleMode(handle, mode)
    except Exception:
        pass  # Silently fail on non-Windows or if it doesn't work


from typing import Optional
from utils.networking import get_local_ip, register_mdns_service
from utils.process import terminate_process, is_process_running, launch_process
from utils.focus_window import _wait_and_focus_window
from utils.click_navigator import click_template_if_found
from utils.monitoring import get_logger, setup_logging
from utils.data_model import MachineConfig
from game_handling import launch, GAME_REGISTRY, Role

# Initialize logging with file output
log_file = Path(__file__).parent.parent / "scripts" / "simracing_client.log"
setup_logging(log_file=log_file, console=True)
logger = get_logger(__name__)

app = Flask(__name__)

HEARTBEAT_INTERVAL = 5
ORCHESTRATOR_URL = None
heartbeat_thread = None
stop_heartbeat = threading.Event()
SERVICE_PORT = 5000
MACHINE_CONFIG: Optional[MachineConfig] = None

# Cancellation event for stopping running navigation sequences
cancel_navigation = threading.Event()

SETUP_STATE = {
    "status": "idle",
    "current_game": None,
    "session_id": None,
    "role": None,
    "player_count": None,
    "host_ip": None
}

def _send_heartbeat():
    """Send periodic status updates to the orchestrator"""
    logger.info("Heartbeat service started")
    while not stop_heartbeat.is_set():
        if ORCHESTRATOR_URL and MACHINE_CONFIG:
            try:
                # Check if configured game is actually running
                actual_game = None
                if SETUP_STATE["current_game"]:
                    try:
                        config = GAME_REGISTRY.get(SETUP_STATE["current_game"])
                        if is_process_running(config.process_name):
                            actual_game = SETUP_STATE["current_game"]
                            # If game is running but state is not "running", update it
                            if SETUP_STATE["status"] != "running":
                                logger.info(f"Game {actual_game} is running but state was {SETUP_STATE['status']}, updating to running")
                                SETUP_STATE["status"] = "running"
                        else:
                            # Game process is not running but we have it configured
                            if SETUP_STATE["status"] == "running":
                                logger.warning(f"Game {SETUP_STATE['current_game']} process not found, resetting state to idle")
                                SETUP_STATE["status"] = "idle"
                                SETUP_STATE["current_game"] = None
                                SETUP_STATE["session_id"] = None
                                SETUP_STATE["role"] = None
                                SETUP_STATE["player_count"] = None
                    except ValueError as e:
                        # Game not in registry
                        logger.error(f"Game {SETUP_STATE['current_game']} not found in registry: {e}")
                payload = {
                    "name": MACHINE_CONFIG.name,
                    "id": MACHINE_CONFIG.id,
                    "ip": MACHINE_CONFIG.ip,
                    "port": MACHINE_CONFIG.port,
                    "status": SETUP_STATE["status"],
                    "current_game": actual_game,
                    "session_id": SETUP_STATE["session_id"],
                    "timestamp": time.time()
                }
                logger.info(
                    f"Sending heartbeat to {ORCHESTRATOR_URL} | "
                    f"Status: {payload['status']} | "
                    f"Game: {payload['current_game'] or 'None'} | "
                )
                response = requests.post(
                    f"{ORCHESTRATOR_URL}/api/heartbeat",
                    json=payload,
                    timeout=2
                )
                if response.status_code == 200:
                    logger.info(f"Heartbeat acknowledged by orchestrator")
                else:
                    logger.warning(f"Heartbeat failed: HTTP {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Heartbeat error: {e}")
        stop_heartbeat.wait(HEARTBEAT_INTERVAL)
    logger.info("Heartbeat service stopped")

@app.route('/api/register_orchestrator', methods=['POST'])
def register_orchestrator():
    """Register the orchestrator URL to send heartbeats to"""
    global ORCHESTRATOR_URL, heartbeat_thread
    orchestrator_url = request.json.get('orchestrator_url')
    if not orchestrator_url:
        return jsonify({"error": "Missing orchestrator_url"}), 400

    # Validate it's not our own IP (prevent self-heartbeat loop)
    my_ip = get_local_ip()
    if my_ip in orchestrator_url:
        logger.warning(f"Orchestrator registration - URL contains our own IP: {orchestrator_url}")

    ORCHESTRATOR_URL = orchestrator_url.rstrip('/')
    logger.info(f"Orchestrator registered: {ORCHESTRATOR_URL}")
    if heartbeat_thread is None or not heartbeat_thread.is_alive():
        stop_heartbeat.clear()
        heartbeat_thread = threading.Thread(target=_send_heartbeat, daemon=True)
        heartbeat_thread.start()
        logger.info(f"Heartbeat thread started (interval: {HEARTBEAT_INTERVAL}s)")
    return jsonify({
        "status": "success",
        "message": f"Orchestrator registered: {ORCHESTRATOR_URL}",
        "heartbeat_interval": HEARTBEAT_INTERVAL
    })

@app.route('/api/configure', methods=['POST'])
def configure():
    """Receive configuration from orchestrator"""
    data = request.json
    game = data.get('game')
    session_id = data.get('session_id')
    role = data.get('role')
    player_count = data.get('player_count')
    host_ip = data.get('host_ip')  # Receive host IP

    SETUP_STATE["current_game"] = game
    SETUP_STATE["session_id"] = session_id
    SETUP_STATE["role"] = role
    SETUP_STATE["player_count"] = player_count
    SETUP_STATE["host_ip"] = host_ip  # Store host IP
    SETUP_STATE["status"] = "configured"

    logger.info(f"Configured: Game={game}, Session={session_id}, Role={role}, PlayerCount={player_count}, HostIP={host_ip}")

    return jsonify({
        "status": "success",
        "message": f"Setup configured for {game} as {role}",
        "state": SETUP_STATE
    })


def _launch_game_async(game: str, role: Role, player_count: Optional[int] = None, host_ip: Optional[str] = None):
    """Background thread function to launch game"""
    try:
        # Clear any previous cancellation signal before starting
        cancel_navigation.clear()

        logger.info(f"Background thread: launching {game} as {role} with player_count={player_count}, host_ip={host_ip}")
        success = launch(game, role, cancel_event=cancel_navigation, player_count=player_count, host_ip=host_ip)

        if success:
            SETUP_STATE["status"] = "running"
            logger.info(f"Background thread: {game} started successfully")
        else:
            logger.error(f"Background thread: Failed to start {game}")
            # Reset state on failure
            SETUP_STATE["status"] = "idle"
            SETUP_STATE["current_game"] = None
            SETUP_STATE["session_id"] = None
            SETUP_STATE["role"] = None
            SETUP_STATE["player_count"] = None

    except Exception as e:
        logger.error(f"Background thread: Error starting game: {e}")
        # Reset state on error
        SETUP_STATE["status"] = "idle"
        SETUP_STATE["current_game"] = None
        SETUP_STATE["session_id"] = None
        SETUP_STATE["role"] = None
        SETUP_STATE["player_count"] = None


@app.route('/api/start', methods=['POST'])
def start_game():
    """Start the configured game"""
    logger.info("Received start game request.")

    # Validate that setup is configured
    if SETUP_STATE["status"] != "configured":
        logger.error(f"Cannot start game: setup is not configured (status: {SETUP_STATE['status']})")
        return jsonify({
            "status": "error",
            "message": "Setup must be configured before starting game"
        }), 400

    game = SETUP_STATE["current_game"]
    role = SETUP_STATE["role"]
    host_ip = SETUP_STATE["host_ip"]
    logger.info(f"Starting {game} with role {role}")

    # Update state to starting immediately
    SETUP_STATE["status"] = "starting"

    # Launch game in background thread to avoid blocking the response
    player_count = SETUP_STATE.get("player_count")
    launch_thread = threading.Thread(
        target=_launch_game_async,
        args=(game, role, player_count, host_ip),
        daemon=True
    )
    launch_thread.start()

    logger.info(f"Game launch initiated in background thread")
    return jsonify({
        "status": "success",
        "message": f"{game} is starting as {role}",
    })

@app.route('/api/stop', methods=['POST'])
def stop_game():
    """Stop the currently running game"""
    logger.info("Stop game request received.")

    # Signal any running navigation to stop immediately
    cancel_navigation.set()
    logger.info("Cancellation signal sent to navigation sequence")

    game = SETUP_STATE["current_game"]
    current_status = SETUP_STATE["status"]

    if not game:
        logger.warning("No game is currently configured")
        return jsonify({
            "status": "error",
            "message": "No game is currently running"
        }), 400

    logger.info(f"Attempting to close {game} (status: {current_status})")

    try:
        # Get game config to retrieve process name
        config = GAME_REGISTRY.get(game)
        success = terminate_process(config.process_name)

        # Always reset state when stop is requested
        # Even if process wasn't found (e.g., during "starting" phase)
        SETUP_STATE["status"] = "idle"
        SETUP_STATE["current_game"] = None
        SETUP_STATE["session_id"] = None
        SETUP_STATE["role"] = None
        SETUP_STATE["player_count"] = None

        if success:
            logger.info(f"{game} closed successfully, state reset to idle")
            return jsonify({
                "status": "success",
                "message": f"{game} stopped successfully"
            })
        else:
            # Process not found, but state still reset
            logger.warning(f"Process {config.process_name} not found, but state reset to idle")
            return jsonify({
                "status": "success",
                "message": f"{game} stop requested (process not running), state reset"
            })

    except Exception as e:
        logger.error(f"Error stopping game: {e}")
        # Still reset state on error
        SETUP_STATE["status"] = "idle"
        SETUP_STATE["current_game"] = None
        SETUP_STATE["session_id"] = None
        SETUP_STATE["role"] = None
        SETUP_STATE["player_count"] = None
        return jsonify({
            "status": "error",
            "message": f"Error stopping game: {str(e)}"
        }), 500


# ============================================================================
# Cammus Configuration Endpoint
# ============================================================================

def _load_cammus_config() -> Optional[dict]:
    """Load Cammus configuration from cammus_config.json."""
    config_path = Path(__file__).parent.parent / "cammus_config.json"
    if not config_path.exists():
        logger.error(f"Cammus config not found: {config_path}")
        return None

    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in cammus_config.json: {e}")
        return None


def _execute_cammus_configuration() -> tuple[bool, str]:
    """
    Execute Cammus software configuration.

    Returns:
        Tuple of (success, message)
    """
    config = _load_cammus_config()
    if not config:
        return False, "Failed to load cammus_config.json"

    if not config.get('enabled', False):
        return False, "Cammus configuration is disabled"

    project_root = Path(__file__).parent.parent
    template_base = project_root / "templates"
    template_dir = template_base / config.get('template_dir', 'CAMMUS')

    # Load click steps
    click_steps_file = config.get('click_steps_file', 'click_steps.json')
    click_steps_path = template_dir / click_steps_file

    if not click_steps_path.exists():
        return False, f"Click steps file not found: {click_steps_path}"

    try:
        with open(click_steps_path, 'r') as f:
            click_steps = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON in click_steps.json: {e}"

    if not click_steps:
        return False, "No click steps configured"

    logger.info(f"Starting Cammus configuration ({len(click_steps)} steps)")

    # Launch software if needed
    executable_path = config.get('executable_path')
    process_name = config.get('process_name')
    window_title = config.get('window_title')
    startup_delay = config.get('startup_delay', 5.0)

    if executable_path and process_name:
        if not is_process_running(process_name):
            logger.info(f"Launching Cammus software: {executable_path}")
            try:
                launch_process(Path(executable_path))
                # Wait for software to load past splash screen
                logger.info(f"Waiting {startup_delay}s for software to load...")
                time.sleep(startup_delay)
            except Exception as e:
                return False, f"Failed to launch Cammus software: {e}"
        else:
            logger.info(f"Cammus software already running: {process_name}")

        # Focus window if specified
        if window_title:
            if not _wait_and_focus_window(window_title, max_attempts=10):
                logger.warning(f"Could not focus window: {window_title}")
    else:
        logger.warning("No executable_path or process_name configured - assuming software is already open")

    # Execute click sequence
    threshold = config.get('template_threshold', 0.85)
    max_retries = config.get('max_retries', 15)
    retry_delay = config.get('retry_delay', 1.0)
    click_delay = config.get('click_delay', 0.5)

    for i, step in enumerate(click_steps, 1):
        template_file = step.get('template')
        double_click = step.get('double_click', False)

        if not template_file:
            logger.error(f"Step {i} missing 'template' field")
            return False, f"Step {i} missing template field"

        template_path = str(template_dir / template_file)
        logger.info(f"Step {i}/{len(click_steps)}: Looking for {template_file}...")

        # Retry loop
        clicked = False
        for attempt in range(max_retries):
            if click_template_if_found(template_path, threshold, click_delay, double_click):
                click_type = "double-clicked" if double_click else "clicked"
                logger.info(f"Step {i}/{len(click_steps)}: {click_type} {template_file}")
                clicked = True
                break

            if attempt < max_retries - 1:
                logger.debug(f"Attempt {attempt + 1}/{max_retries} failed, retrying...")
                time.sleep(retry_delay)

        if not clicked:
            return False, f"Step {i} failed: Could not find {template_file} after {max_retries} attempts"

    logger.info(f"Cammus configuration completed successfully ({len(click_steps)} steps)")
    return True, f"Cammus configuration completed ({len(click_steps)} steps)"


@app.route('/api/configure_cammus', methods=['POST'])
def configure_cammus():
    """
    Configure Cammus wheel software.

    This endpoint triggers the Cammus software configuration sequence,
    which opens the software (if not running) and clicks through the
    required UI elements using template matching.

    Typically called once after PC startup to configure the wheel.
    """
    logger.info("Received Cammus configuration request")

    try:
        success, message = _execute_cammus_configuration()

        if success:
            return jsonify({
                "status": "success",
                "message": message
            })
        else:
            logger.error(f"Cammus configuration failed: {message}")
            return jsonify({
                "status": "error",
                "message": message
            }), 500

    except Exception as e:
        logger.error(f"Cammus configuration error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Cammus configuration error: {str(e)}"
        }), 500


def _start_server(config: dict):
    global MACHINE_CONFIG

    disable_quickedit()

    # Create MachineConfig with values from config file and runtime values
    MACHINE_CONFIG = MachineConfig(
        id=str(config['id']),
        name=config['name'],
        ip=get_local_ip(),
        port=str(SERVICE_PORT)
    )

    logger.info(f"Machine Name: {MACHINE_CONFIG.name}")
    logger.info(f"Machine ID: {MACHINE_CONFIG.id}")
    logger.info(f"IP: {MACHINE_CONFIG.ip}")
    logger.info(f"Port: {MACHINE_CONFIG.port}")
    logger.info("Registering mDNS service...")
    zeroconf, service_info = register_mdns_service(config, SERVICE_PORT)
    try:
        logger.info("REST API server starting...")
        logger.info("Waiting for orchestrator to register for heartbeats...")
        app.run(host='0.0.0.0', port=SERVICE_PORT, debug=False)
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
    finally:
        stop_heartbeat.set()
        if heartbeat_thread and heartbeat_thread.is_alive():
            heartbeat_thread.join(timeout=2)
        zeroconf.unregister_service(service_info)
        zeroconf.close()
        logger.info("Service stopped")


if __name__ == "__main__":
    config_path = Path(__file__).parent.parent / "machine_configuration.json"
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        logger.error("Please create machine_configuration.json with 'name' and 'id' fields")
        exit(1)
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        if 'name' not in config or 'id' not in config:
            logger.error("Configuration must contain 'name' and 'id' fields")
            exit(1)

        logger.info(f"Loaded configuration from {config_path}")
        _start_server(config)

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        exit(1)