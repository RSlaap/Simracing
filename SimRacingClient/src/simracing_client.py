from flask import Flask, request, jsonify
from typing import Dict
import json
import threading
import time
import requests
from pathlib import Path
from utils.networking import get_local_ip, register_mdns_service
from games import launch
from utils.process import terminate_process, is_process_running
from games.registry import GAME_REGISTRY
from utils.monitoring import get_logger, setup_logging

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
MACHINE_CONFIG: Dict = {}

SETUP_STATE = {
    "status": "idle",
    "current_game": None,
    "session_id": None,
    "role": None
}

def _send_heartbeat():
    """Send periodic status updates to the orchestrator"""
    logger.info("Heartbeat service started")

    while not stop_heartbeat.is_set():
        if ORCHESTRATOR_URL:
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
                    except ValueError as e:
                        # Game not in registry
                        logger.error(f"Game {SETUP_STATE['current_game']} not found in registry: {e}")

                payload = {
                    "name": MACHINE_CONFIG['name'],
                    "id": MACHINE_CONFIG['id'],
                    "ip": get_local_ip(),
                    "port": SERVICE_PORT,
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
    
    data = request.json
    orchestrator_url = data.get('orchestrator_url')
    
    if not orchestrator_url:
        return jsonify({"error": "Missing orchestrator_url"}), 400
    
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

    SETUP_STATE["current_game"] = game
    SETUP_STATE["session_id"] = session_id
    SETUP_STATE["role"] = role
    SETUP_STATE["status"] = "configured"

    logger.info(f"Configured: Game={game}, Session={session_id}, Role={role}")

    return jsonify({
        "status": "success",
        "message": f"Setup configured for {game} as {role}",
        "state": SETUP_STATE
    })

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

    logger.info(f"Starting {game} with role {role}")

    try:
        # Launch the game using the new games module
        success = launch(game, role)

        if success:
            # Update state to running
            SETUP_STATE["status"] = "running"
            logger.info(f"{game} started successfully")
            return jsonify({
                "status": "success",
                "message": f"{game} is starting as {role}",
            })
        else:
            logger.error(f"Failed to start {game}")
            return jsonify({
                "status": "error",
                "message": f"Failed to start {game}"
            }), 500

    except Exception as e:
        logger.error(f"Error starting game: {e}")
        return jsonify({
            "status": "error",
            "message": f"Error starting game: {str(e)}"
        }), 500

@app.route('/api/stop', methods=['POST'])
def stop_game():
    """Stop the currently running game"""
    logger.info("Stop game request received.")

    game = SETUP_STATE["current_game"]

    if not game:
        logger.warning("No game is currently configured")
        return jsonify({
            "status": "error",
            "message": "No game is currently running"
        }), 400

    logger.info(f"Attempting to close {game}")

    try:
        # Get game config to retrieve process name
        config = GAME_REGISTRY.get(game)
        success = terminate_process(config.process_name)

        if success:
            # Reset state to idle
            SETUP_STATE["status"] = "idle"
            SETUP_STATE["current_game"] = None
            SETUP_STATE["session_id"] = None
            SETUP_STATE["role"] = None

            logger.info(f"{game} closed successfully, state reset to idle")
            return jsonify({
                "status": "success",
                "message": f"{game} stopped successfully"
            })
        else:
            logger.error(f"Failed to close {game}")
            return jsonify({
                "status": "error",
                "message": f"Failed to stop {game}"
            }), 500

    except Exception as e:
        logger.error(f"Error stopping game: {e}")
        return jsonify({
            "status": "error",
            "message": f"Error stopping game: {str(e)}"
        }), 500


def _start_server(config):
    global MACHINE_CONFIG
    MACHINE_CONFIG = config

    logger.info(f"Machine Name: {config['name']}")
    logger.info(f"Machine ID: {config['id']}")
    logger.info(f"IP: {get_local_ip()}")
    logger.info(f"Port: {SERVICE_PORT}")
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