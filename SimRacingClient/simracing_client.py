from flask import Flask, request, jsonify
from zeroconf import ServiceInfo, Zeroconf
import socket
import threading
import time
import logging

from utils.get_local_ip import get_local_ip

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('SimRacingClient')

app = Flask(__name__)

HEARTBEAT_INTERVAL = 5
ORCHESTRATOR_URL = None
heartbeat_thread = None
stop_heartbeat = threading.Event()
SERVICE_PORT = 5000
MACHINE_CONFIG = None

SETUP_STATE = {
    "status": "idle",
    "current_game": None,
    "session_id": None,
    "role": None
}

def register_mdns_service(config, port=5000):
    """Register this setup as discoverable via mDNS"""
    local_ip = get_local_ip()

    service_type = "_simracing._tcp.local."
    service_name = f"{config['name']} SimRacing Setup.{service_type}"

    info = ServiceInfo(
        service_type,
        service_name,
        addresses=[socket.inet_aton(local_ip)],
        port=port,
        properties={
            'name': config['name'],
            'id': str(config['id']),
            'status': 'idle',
            'games': ','.join([])
        }
    )

    zeroconf = Zeroconf()
    zeroconf.register_service(info)
    logger.info(f"mDNS service registered: {service_name}")
    logger.info(f"Discoverable at: {local_ip}:{port}")
    return zeroconf, info

def _send_heartbeat():
    """Send periodic status updates to the orchestrator"""
    import requests
    logger.info("Heartbeat service started")

    while not stop_heartbeat.is_set():
        if ORCHESTRATOR_URL:
            try:
                payload = {
                    "name": MACHINE_CONFIG['name'],
                    "id": MACHINE_CONFIG['id'],
                    "ip": get_local_ip(),
                    "port": SERVICE_PORT,
                    "status": SETUP_STATE["status"],
                    "current_game": SETUP_STATE["current_game"],
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

# @app.route('/api/status', methods=['GET'])
# def get_status():
#     logger.info("Status request received")
#     """Return current setup status"""
#     return jsonify({
#         "status": SETUP_STATE["status"],
#         "current_game": SETUP_STATE["current_game"],
#         "session_id": SETUP_STATE["session_id"],
#         "supported_games": list()
#     })

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
    # TODO: Start game logic
    logger.info("Received start game request.")
    game = ""
    return jsonify({
        "status": "success",
        "message": f"{game} is starting",
    })

@app.route('/api/stop', methods=['POST'])
def stop_game():
    # TODO: Implement stop game logic
    logger.info("Stop game request received.")
    return jsonify({
        "status": "success",
        "message": "Game stopped"
    })

def start_server(config):
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
    import json
    from pathlib import Path

    config_path = Path(__file__).parent / "machine_configuration.json"

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
        start_server(config)

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        exit(1)