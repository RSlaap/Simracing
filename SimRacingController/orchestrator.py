"""
SimRacing Orchestrator - Web Interface Only
Refactored version without global variables - all state encapsulated in classes
"""
from typing import Dict, Optional, List
from flask import Flask, request, jsonify, send_from_directory
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
import requests
import time
import socket
from pydantic import BaseModel
import logging
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('SimRacingOrchestrator')

class Heartbeat(BaseModel):
    hostname: str
    status: str
    session_id: Optional[str]
    current_game: Optional[str]
    last_seen: float
    timestamp: float

class SetupRegistration(BaseModel):
    name: str
    address: str
    port: int
    properties: Dict
    heartbeat: Optional[Heartbeat] = None


REGISTERED_SETUPS: Dict[str, SetupRegistration] = {}
port = 8000


def get_local_ip():
    """Get the local IP address of this machine"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def auto_register_setup(address, setup_port):
    """Automatically register with a discovered setup"""
    orchestrator_url = f"http://{get_local_ip()}:{port}"
    setup_url = f"http://{address}:{setup_port}"
    
    try:
        logger.info(f"Auto-registering with setup at {setup_url}")
        response = requests.post(
            f"{setup_url}/api/register_orchestrator",
            json={"orchestrator_url": orchestrator_url},
            timeout=5
        )
        response.raise_for_status()
        logger.info(f"Successfully registered with {setup_url}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to auto-register with {setup_url}: {e}")


def get_online_setups() -> List[tuple]:
    """Get list of online setups in order (left to right as they appear)"""
    online_setups = []
    for setup_id, setup in REGISTERED_SETUPS.items():
        if setup.heartbeat and setup.heartbeat.last_seen:
            is_online = (time.time() - setup.heartbeat.last_seen) < 15
            if is_online:
                online_setups.append((setup_id, setup))
    return online_setups


class SetupListener(ServiceListener):
    def __init__(self):
        pass
    
    def add_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name)
        if info:
            address = socket.inet_ntoa(info.addresses[0])
            setup_port = info.port
            if not setup_port:
                raise ValueError(f"Could not find a port in {info}")
            properties = {}
            for key, value in info.properties.items():
                if value:
                    properties[key.decode('utf-8')] = value.decode('utf-8')
            
            setup_id = f"{address}:{setup_port}"
            REGISTERED_SETUPS[setup_id] = SetupRegistration(
                name = name,
                address = address,
                port = setup_port,
                properties = properties
            )

            logger.info(f"[+] Found setup: {properties.get('hostname', 'Unknown')} at {address}:{setup_port}")
            
            threading.Thread(
                target=auto_register_setup, 
                args=(address, setup_port), 
                daemon=True
            ).start()
    
    def remove_service(self, zc, type_, name):
        logger.info(f"[-] Setup disconnected: {name}")
        
        setup_to_remove = None
        for setup_id, setup_info in REGISTERED_SETUPS.items():
            if setup_info.name == name:
                setup_to_remove = setup_id
                break
        
        if setup_to_remove:
            del REGISTERED_SETUPS[setup_to_remove]
            logger.info(f"Removed {setup_to_remove} from discovered setups")
    
    def update_service(self, zc, type_, name):
        pass


app = Flask(__name__, static_folder='static')


@app.route('/')
def index():
    """Serve the main HTML interface"""
    return send_from_directory('static', 'index.html')


@app.route('/api/heartbeat', methods=['POST'])
def receive_heartbeat():
    """Receive heartbeat updates from setups"""
    data = request.json
    
    heartbeat_port = data.get('port', 5000)
    setup_id = f"{data.get('ip')}:{heartbeat_port}"
    
    if setup_id not in REGISTERED_SETUPS:
        logger.warning(f"Received heartbeat from unknown setup: {setup_id}")
        return jsonify({"status": "unknown_setup", "message": f"Setup {setup_id} not found in registry"}), 404
    
    REGISTERED_SETUPS[setup_id].heartbeat = Heartbeat(
        hostname=data.get('hostname'),
        status=data.get('status'),
        current_game= data.get('current_game'),
        session_id= data.get('session_id'),
        last_seen=time.time(),
        timestamp=data.get('timestamp')
    )
    logger.info(f"Received heartbeat from {setup_id}")
    return jsonify({"status": "received"})


@app.route('/api/setups', methods=['GET'])
def get_setups():
    """Get all setups (both discovered and connected)"""
    result = {}
    setup_summary = []
    
    for setup_id, setup in REGISTERED_SETUPS.items():
        if setup.heartbeat:
            is_online = (time.time() - setup.heartbeat.last_seen) < 15
            result[setup_id] = {
                **setup.model_dump(),
                "connected": True,
                "online": is_online
            }
            status_str = f"{setup.heartbeat.hostname}: {setup.heartbeat.status} ({'online' if is_online else 'offline'})"
            setup_summary.append(status_str)
        else:
            result[setup_id] = {
                **setup.model_dump(),
                "connected": False,
                "online": False
            }
            hostname = setup.properties.get('hostname', 'Unknown')
            setup_summary.append(f"{hostname}: discovered (not connected)")
    
    if setup_summary:
        logger.info(f"Status request | Found {len(result)} setups | {' | '.join(setup_summary)}")
    else:
        logger.info("Status request | No setups found")
    
    return jsonify(result)


@app.route('/api/start_all', methods=['POST'])
def start_all():
    """Start game on N setups where N is the number of players"""
    data = request.json
    game = data.get('game')
    num_players = data.get('num_players', 1)
    
    if not game:
        logger.warning("Start request failed: Missing game")
        return jsonify({"error": "Missing required field: game"}), 400
    
    online_setups = get_online_setups()
    
    if len(online_setups) < num_players:
        logger.warning(f"Start request failed: Not enough online setups. Need {num_players}, have {len(online_setups)}")
        return jsonify({
            "error": f"Not enough online setups. Need {num_players} players, but only {len(online_setups)} setups are online",
            "online_setups": len(online_setups),
            "required_players": num_players
        }), 400
    
    session_id = f"session-{int(time.time())}"
    results = []
    
    for i in range(num_players):
        setup_id, setup = online_setups[i]
        player_id = i + 1
        
        try:
            logger.info(f"Configuring setup {setup_id} for {game} as Player {player_id}")
            
            config_response = requests.post(
                f"http://{setup_id}/api/configure",
                json={
                    "game": game,
                    "session_id": session_id,
                    "player_id": player_id
                },
                timeout=5
            )
            
            if not config_response.ok:
                logger.error(f"Failed to configure {setup_id}: {config_response.text}")
                results.append({
                    "setup_id": setup_id,
                    "hostname": setup.heartbeat.hostname,
                    "player_id": player_id,
                    "status": "failed_configure",
                    "error": config_response.text
                })
                continue
            
            logger.info(f"Starting game on setup {setup_id}")
            start_response = requests.post(
                f"http://{setup_id}/api/start",
                timeout=5
            )
            
            if start_response.ok:
                logger.info(f"Successfully started game on {setup_id}")
                results.append({
                    "setup_id": setup_id,
                    "hostname": setup.heartbeat.hostname,
                    "player_id": player_id,
                    "status": "success"
                })
            else:
                logger.error(f"Failed to start game on {setup_id}: {start_response.text}")
                results.append({
                    "setup_id": setup_id,
                    "hostname": setup.heartbeat.hostname,
                    "player_id": player_id,
                    "status": "failed_start",
                    "error": start_response.text
                })
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with {setup_id}: {e}")
            results.append({
                "setup_id": setup_id,
                "hostname": setup.heartbeat.hostname,
                "player_id": player_id,
                "status": "error",
                "error": str(e)
            })
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    
    return jsonify({
        "game": game,
        "session_id": session_id,
        "num_players": num_players,
        "success_count": success_count,
        "results": results
    })


@app.route('/api/stop_all', methods=['POST'])
def stop_all():
    """Stop game on N setups where N is the number of players"""
    data = request.json
    num_players = data.get('num_players', 1)
    
    online_setups = get_online_setups()
    
    if len(online_setups) < num_players:
        logger.warning(f"Stop request: Only {len(online_setups)} setups online, requested to stop {num_players}")
        num_players = len(online_setups)
    
    results = []
    
    for i in range(num_players):
        setup_id, setup = online_setups[i]
        
        try:
            logger.info(f"Stopping game on setup {setup_id}")
            
            stop_response = requests.post(
                f"http://{setup_id}/api/stop",
                timeout=5
            )
            
            if stop_response.ok:
                logger.info(f"Successfully stopped game on {setup_id}")
                results.append({
                    "setup_id": setup_id,
                    "hostname": setup.heartbeat.hostname,
                    "status": "success"
                })
            else:
                logger.error(f"Failed to stop game on {setup_id}: {stop_response.text}")
                results.append({
                    "setup_id": setup_id,
                    "hostname": setup.heartbeat.hostname,
                    "status": "failed",
                    "error": stop_response.text
                })
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with {setup_id}: {e}")
            results.append({
                "setup_id": setup_id,
                "hostname": setup.heartbeat.hostname,
                "status": "error",
                "error": str(e)
            })
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    
    return jsonify({
        "num_players": num_players,
        "success_count": success_count,
        "results": results
    })


@app.route('/api/register_setup', methods=['POST'])
def register_setup():
    """Manually register a specific setup for heartbeats"""
    data = request.json
    setup_id = data.get('setup_id')
    
    if not setup_id:
        return jsonify({"error": "Missing setup_id"}), 400
    
    orchestrator_url = f"http://{request.host.split(':')[0]}:{port}"
    
    try:
        response = requests.post(
            f"http://{setup_id}/api/register_orchestrator",
            json={"orchestrator_url": orchestrator_url},
            timeout=5
        )
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

def main():
    zeroconf = Zeroconf()
    browser = ServiceBrowser(
        zeroconf,
        "_simracing._tcp.local.",
        SetupListener()
        )
    logger.info("="*60)
    logger.info("SimRacing Orchestrator - Web Interface")
    logger.info("="*60)
    
    """Start the Flask web server"""
    local_ip = get_local_ip()
    web_url = f"http://{local_ip}:{port}"
    
    logger.info(f"Discovering setups on the network...")
    logger.info(f"Auto-registration enabled")
    logger.info(f"Web interface starting...")
    logger.info("="*60)
    logger.info("OPEN YOUR BROWSER:")
    logger.info(f"  {web_url}")
    logger.info("="*60)
    logger.info("Press Ctrl+C to stop the server")
    
    try:
        app.run(host='0.0.0.0', port=port, debug=False)
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    finally:
        zeroconf.close()
        logger.info("Service stopped")

if __name__ == '__main__':
    main()