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
from typing import Optional
from utils.networking import get_local_ip, register_mdns_service
from utils.process import terminate_process, is_process_running, is_running_elevated
from utils.monitoring import get_logger, setup_logging
from utils.data_model import MachineConfig
from utils.setup_state import SetupState
from utils.input_blocker import disable_quickedit
from utils.cammus_helper import execute_cammus_configuration
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

# Thread-safe state management
setup_state = SetupState()


def _send_heartbeat():
    """Send periodic status updates to the orchestrator"""
    logger.info("Heartbeat service started")
    while not stop_heartbeat.is_set():
        if ORCHESTRATOR_URL and MACHINE_CONFIG:
            try:
                # Get thread-safe snapshot of current state
                state = setup_state.snapshot()
                actual_game = None

                if state["current_game"]:
                    try:
                        config = GAME_REGISTRY.get(state["current_game"])
                        if is_process_running(config.process_name):
                            actual_game = state["current_game"]
                            # If game is running but state is not "running", update it
                            if state["status"] != "running":
                                logger.info(f"Game {actual_game} is running but state was {state['status']}, updating to running")
                                setup_state.set_status("running")
                        else:
                            # Game process is not running but we have it configured
                            if state["status"] == "running":
                                logger.warning(f"Game {state['current_game']} process not found, resetting state to idle")
                                setup_state.reset()
                    except ValueError as e:
                        # Game not in registry
                        logger.error(f"Game {state['current_game']} not found in registry: {e}")

                # Get fresh snapshot for payload after potential updates
                state = setup_state.snapshot()
                payload = {
                    "name": MACHINE_CONFIG.name,
                    "id": MACHINE_CONFIG.id,
                    "ip": MACHINE_CONFIG.ip,
                    "port": MACHINE_CONFIG.port,
                    "status": state["status"],
                    "current_game": actual_game,
                    "session_id": state["session_id"],
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
    host_ip = data.get('host_ip')

    setup_state.configure(
        game=game,
        session_id=session_id,
        role=role,
        player_count=player_count,
        host_ip=host_ip
    )

    return jsonify({
        "status": "success",
        "message": f"Setup configured for {game} as {role}",
        "state": setup_state.snapshot()
    })


def _launch_game_async(game: str, role: Role, player_count: Optional[int] = None, host_ip: Optional[str] = None):
    """Background thread function to launch game"""
    try:
        # Clear any previous cancellation signal before starting
        cancel_navigation.clear()

        logger.info(f"Background thread: launching {game} as {role} with player_count={player_count}, host_ip={host_ip}")
        success = launch(game, role, cancel_event=cancel_navigation, player_count=player_count, host_ip=host_ip)

        if success:
            setup_state.set_status("running")
            logger.info(f"Background thread: {game} started successfully")
        else:
            logger.error(f"Background thread: Failed to start {game}")
            setup_state.reset()

    except Exception as e:
        logger.error(f"Background thread: Error starting game: {e}")
        setup_state.reset()


@app.route('/api/start', methods=['POST'])
def start_game():
    """Start the configured game"""
    logger.info("Received start game request.")

    # Validate that setup is configured
    if not setup_state.is_configured():
        logger.error(f"Cannot start game: setup is not configured (status: {setup_state.status})")
        return jsonify({
            "status": "error",
            "message": "Setup must be configured before starting game"
        }), 400

    # Get values from state
    game = setup_state.current_game
    role = setup_state.role
    host_ip = setup_state.host_ip
    player_count = setup_state.player_count
    logger.info(f"Starting {game} with role {role}")

    # Update state to starting immediately
    setup_state.set_status("starting")

    # Launch game in background thread to avoid blocking the response
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

    # Get current game info
    game = setup_state.current_game
    current_status = setup_state.status

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
        setup_state.reset()

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
        setup_state.reset()
        return jsonify({
            "status": "error",
            "message": f"Error stopping game: {str(e)}"
        }), 500


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
        success, message = execute_cammus_configuration()

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
    if is_running_elevated():
        logger.info("Admin privileges: YES")
    else:
        logger.warning("Admin privileges: NO - CAMMUS clicks may not work")
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