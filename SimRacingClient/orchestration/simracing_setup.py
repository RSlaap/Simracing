"""
Simple SimRacing Setup Service
Handles service discovery via mDNS and receives configuration from orchestrator
"""

from flask import Flask, request, jsonify
from zeroconf import ServiceInfo, Zeroconf
import socket
import subprocess
import threading
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('SimRacingSetup')

app = Flask(__name__)

HEARTBEAT_INTERVAL = 5
ORCHESTRATOR_URL = None
heartbeat_thread = None
stop_heartbeat = threading.Event()
SERVICE_PORT = 5000

SETUP_STATE = {
    "status": "idle",
    "current_game": None,
    "session_id": None
}

SUPPORTED_GAMES = {
    "F1 22": {
        "executable": "F1_22.exe",
        "telemetry_port": 20777
    },
    "Assetto Corsa Competizione": {
        "executable": "AC2.exe",
        "telemetry_port": 9996
    },
    "Dirt Rally 2": {
        "executable": "dirtrally2.exe",
        "telemetry_port": 20777
    }
}

def send_heartbeat():
    """Send periodic status updates to the orchestrator"""
    import requests
    logger.info("Heartbeat service started")
    
    while not stop_heartbeat.is_set():
        if ORCHESTRATOR_URL:
            try:
                payload = {
                    "hostname": socket.gethostname(),
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


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def register_mdns_service(port=5000):
    """Register this setup as discoverable via mDNS"""
    hostname = socket.gethostname()
    local_ip = get_local_ip()
    
    service_type = "_simracing._tcp.local."
    service_name = f"{hostname} SimRacing Setup.{service_type}"
    
    info = ServiceInfo(
        service_type,
        service_name,
        addresses=[socket.inet_aton(local_ip)],
        port=port,
        properties={
            'hostname': hostname,
            'status': 'idle',
            'games': ','.join(SUPPORTED_GAMES.keys())
        }
    )
    
    zeroconf = Zeroconf()
    zeroconf.register_service(info)
    logger.info(f"mDNS service registered: {service_name}")
    logger.info(f"Discoverable at: {local_ip}:{port}")
    
    return zeroconf, info

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
        heartbeat_thread = threading.Thread(target=send_heartbeat, daemon=True)
        heartbeat_thread.start()
        logger.info(f"Heartbeat thread started (interval: {HEARTBEAT_INTERVAL}s)")
    
    return jsonify({
        "status": "success",
        "message": f"Orchestrator registered: {ORCHESTRATOR_URL}",
        "heartbeat_interval": HEARTBEAT_INTERVAL
    })

@app.route('/api/status', methods=['GET'])
def get_status():
    logger.info("Status request received")
    """Return current setup status"""
    return jsonify({
        "status": SETUP_STATE["status"],
        "current_game": SETUP_STATE["current_game"],
        "session_id": SETUP_STATE["session_id"],
        "supported_games": list(SUPPORTED_GAMES.keys())
    })

@app.route('/api/configure', methods=['POST'])
def configure():
    """Receive configuration from orchestrator"""
    data = request.json
    
    game = data.get('game')
    session_id = data.get('session_id')
    
    if not game:
        logger.warning("Configuration failed: Missing required fields")
        return jsonify({"error": "Missing required fields: game"}), 400
    
    if game not in SUPPORTED_GAMES:
        logger.warning(f"Configuration failed: Unsupported game '{game}'")
        return jsonify({
            "error": f"Unsupported game: {game}",
            "supported_games": list(SUPPORTED_GAMES.keys())
        }), 400
    
    SETUP_STATE["current_game"] = game
    SETUP_STATE["session_id"] = session_id
    SETUP_STATE["status"] = "configured"
    
    logger.info(f"Configured: Game={game}, Session={session_id}")
    
    return jsonify({
        "status": "success",
        "message": f"Setup configured for {game}",
        "state": SETUP_STATE
    })

@app.route('/api/start', methods=['POST'])
def start_game():
    """Start the configured game"""
    if SETUP_STATE["status"] == "idle":
        logger.warning("Cannot start game: Setup not configured")
        return jsonify({"error": "Setup not configured. Call /api/configure first"}), 400
    
    game = SETUP_STATE["current_game"]
    game_info = SUPPORTED_GAMES[game]
    
    logger.info(f"Starting game: {game}")
    
    SETUP_STATE["status"] = "running"
    
    threading.Thread(target=launch_game, args=(game_info,), daemon=True).start()
    
    return jsonify({
        "status": "success",
        "message": f"{game} is starting",
        "telemetry_port": game_info["telemetry_port"]
    })

@app.route('/api/stop', methods=['POST'])
def stop_game():
    """Stop the current game"""
    if SETUP_STATE["status"] != "running":
        logger.warning("Cannot stop: No game is running")
        return jsonify({"error": "No game is running"}), 400
    
    logger.info(f"Stopping game: {SETUP_STATE['current_game']}")
    
    SETUP_STATE["status"] = "idle"
    SETUP_STATE["current_game"] = None
    SETUP_STATE["session_id"] = None
    
    return jsonify({
        "status": "success",
        "message": "Game stopped"
    })

def launch_game(game_info):
    """Launch the game executable (placeholder implementation)"""
    executable = game_info["executable"]
    
    logger.info(f"Game launch initiated: {executable}")
    
    time.sleep(2)
    logger.info(f"{executable} simulation complete")
    
    SETUP_STATE["status"] = "configured"

def main():
    global SERVICE_PORT
    SERVICE_PORT = 5000
    
    logger.info("="*60)
    logger.info("SimRacing Setup Service Starting")
    logger.info("="*60)
    logger.info(f"Hostname: {socket.gethostname()}")
    logger.info(f"IP: {get_local_ip()}")
    logger.info(f"Port: {SERVICE_PORT}")
    logger.info(f"Supported games: {', '.join(SUPPORTED_GAMES.keys())}")
    logger.info(f"Heartbeat interval: {HEARTBEAT_INTERVAL} seconds")
    logger.info("Registering mDNS service...")
    
    zeroconf, service_info = register_mdns_service(SERVICE_PORT)
    
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

if __name__ == '__main__':
    main()