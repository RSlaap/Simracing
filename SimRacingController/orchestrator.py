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
import sys
from pydantic import BaseModel
import logging
import threading


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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('SimRacingOrchestrator')

class Heartbeat(BaseModel):
    name: str
    id: int
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

class Slot(BaseModel):
    """Represents one of the 4 static slots for clients"""
    slot_number: int
    setup: Optional[SetupRegistration] = None

    def is_online(self) -> bool:
        """Check if slot has an online setup"""
        if not self.setup or not self.setup.heartbeat:
            return False
        return (time.time() - self.setup.heartbeat.last_seen) < 15

    def get_setup_id(self) -> Optional[str]:
        """Get the setup ID if connected"""
        if self.setup:
            return f"{self.setup.address}:{self.setup.port}"
        return None


# 4 static slots (slot 1-4)
SLOTS: Dict[int, Slot] = {
    1: Slot(slot_number=1),
    2: Slot(slot_number=2),
    3: Slot(slot_number=3),
    4: Slot(slot_number=4)
}

# Map of setup_id to slot_number for quick lookup
SETUP_TO_SLOT: Dict[str, int] = {}

# Global reference to service listener
service_browser_listener = None

port = 8000


def get_local_ip():
    # Primary: UDP socket method - most reliable for finding the "outbound" IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('192.168.2.1', 80))  # Doesn't actually send packets
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        logger.warning(f"UDP socket method failed: {e}")

    # Fallback: hostname resolution
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if not ip.startswith('127.'):
            return ip
    except Exception as e:
        logger.warning(f"Hostname resolution failed: {e}")

    raise RuntimeError(
        "Could not determine local IP address. "
        "Please check network connection and configuration."
    )


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


def assign_setup_to_slot(setup_id: str, setup: SetupRegistration) -> Optional[int]:
    """
    Assign a setup to a slot based on machine ID.
    Returns the slot number (1-4).
    """
    if not setup.heartbeat:
        logger.warning(f"Cannot assign {setup_id} to slot: no heartbeat data")
        return None

    machine_id = setup.heartbeat.id

    # Map machine ID to slot (1-4)
    # If machine_id is within range 1-4, use it directly
    # Otherwise, find first available slot
    if 1 <= machine_id <= 4:
        slot_num = machine_id
    else:
        # Find first available slot
        slot_num = None
        for i in range(1, 5):
            if SLOTS[i].setup is None or SLOTS[i].get_setup_id() == setup_id:
                slot_num = i
                break
        if slot_num is None:
            logger.warning(f"No available slot for setup {setup_id} (machine_id={machine_id})")
            return None

    # Assign to slot
    SLOTS[slot_num].setup = setup
    SETUP_TO_SLOT[setup_id] = slot_num
    logger.info(f"Assigned {setup_id} (machine_id={machine_id}) to Slot {slot_num}")
    return slot_num


class SetupListener(ServiceListener):
    def __init__(self):
        self.discovered_setups = {}  # Track discovered setups before they have heartbeats

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

            # Store discovered setup temporarily
            self.discovered_setups[setup_id] = SetupRegistration(
                name = name,
                address = address,
                port = setup_port,
                properties = properties
            )

            logger.info(f"[+] Discovered setup: {properties.get('name', 'Unknown')} at {address}:{setup_port}")

            threading.Thread(
                target=auto_register_setup,
                args=(address, setup_port),
                daemon=True
            ).start()

    def remove_service(self, zc, type_, name):
        logger.info(f"[-] Setup disconnected: {name}")

        # Find and remove from slots
        setup_to_remove = None
        for setup_id, setup_info in self.discovered_setups.items():
            if setup_info.name == name:
                setup_to_remove = setup_id
                break

        if setup_to_remove:
            # Remove from slot if assigned
            if setup_to_remove in SETUP_TO_SLOT:
                slot_num = SETUP_TO_SLOT[setup_to_remove]
                SLOTS[slot_num].setup = None
                del SETUP_TO_SLOT[setup_to_remove]
                logger.info(f"Removed {setup_to_remove} from Slot {slot_num}")

            # Remove from discovered setups
            del self.discovered_setups[setup_to_remove]

    def update_service(self, zc, type_, name):
        pass


app = Flask(__name__, static_folder='static')


@app.route('/')
def index():
    """Serve the main HTML interface"""
    return send_from_directory('static', 'index.html')


@app.route('/api/heartbeat', methods=['POST'])
def receive_heartbeat():
    """Receive heartbeat updates from setups and assign to slots"""
    data = request.json

    heartbeat_port = data.get('port', 5000)
    setup_id = f"{data.get('ip')}:{heartbeat_port}"

    # Create or update heartbeat
    heartbeat = Heartbeat(
        name=data.get('name'),
        id=data.get('id'),
        status=data.get('status'),
        current_game=data.get('current_game'),
        session_id=data.get('session_id'),
        last_seen=time.time(),
        timestamp=data.get('timestamp')
    )

    # Find or create setup registration
    slot_num = None
    if setup_id in SETUP_TO_SLOT:
        # Already assigned to a slot, update heartbeat
        slot_num = SETUP_TO_SLOT[setup_id]
        if SLOTS[slot_num].setup is not None:
            SLOTS[slot_num].setup.heartbeat = heartbeat  # type: ignore
    else:
        # New setup or setup without slot assignment
        # Try to find it in discovered setups (from mDNS)
        setup = None
        for listener in [service_browser_listener]:  # We'll need to track this
            if hasattr(listener, 'discovered_setups') and setup_id in listener.discovered_setups:   # type: ignore
                setup = listener.discovered_setups[setup_id]  # type: ignore
                setup.heartbeat = heartbeat
                # Assign to slot based on machine ID
                slot_num = assign_setup_to_slot(setup_id, setup)
                break

        if not setup:
            # Heartbeat from unknown setup (not discovered via mDNS)
            # Create minimal registration
            logger.warning(f"Heartbeat from setup not discovered via mDNS: {setup_id}")
            setup = SetupRegistration(
                name=data.get('name', 'Unknown'),
                address=data.get('ip'),
                port=heartbeat_port,
                properties={'name': data.get('name', 'Unknown')},
                heartbeat=heartbeat
            )
            slot_num = assign_setup_to_slot(setup_id, setup)

    if slot_num:
        logger.info(f"Heartbeat from {setup_id} (Slot {slot_num})")
        return jsonify({"status": "received", "slot": slot_num})
    else:
        logger.warning(f"Could not assign {setup_id} to a slot")
        return jsonify({"status": "no_slot_available"}), 503


@app.route('/api/setups', methods=['GET'])
def get_setups():
    """Get all 4 slots with their current setups"""
    result = {}

    for slot_num, slot in SLOTS.items():
        slot_data = {
            "slot_number": slot_num,
            "online": slot.is_online(),
            "setup": None
        }

        if slot.setup:
            setup = slot.setup
            slot_data["setup"] = {
                "address": setup.address,
                "port": setup.port,
                "name": setup.heartbeat.name if setup.heartbeat else setup.properties.get('name', 'Unknown'),
                "status": setup.heartbeat.status if setup.heartbeat else 'unknown',
                "current_game": setup.heartbeat.current_game if setup.heartbeat else None,
                "session_id": setup.heartbeat.session_id if setup.heartbeat else None,
                "last_seen": setup.heartbeat.last_seen if setup.heartbeat else None
            }

        result[f"slot_{slot_num}"] = slot_data

    logger.info(f"Status request | Slot summary: " +
                " | ".join([f"Slot {i}: {'online' if SLOTS[i].is_online() else 'offline'}" for i in range(1, 5)]))

    return jsonify(result)


@app.route('/api/start_slot', methods=['POST'])
def start_slot():
    """Start game on a specific slot"""
    data = request.json
    slot_number = data.get('slot')
    game = data.get('game')
    mode = data.get('mode', 'singleplayer')  # 'singleplayer' or 'multiplayer'

    if not slot_number or not game:
        return jsonify({"error": "Missing required fields: slot, game"}), 400

    if slot_number not in SLOTS:
        return jsonify({"error": f"Invalid slot number: {slot_number}. Must be 1-4"}), 400

    slot = SLOTS[slot_number]

    if not slot.is_online():
        return jsonify({"error": f"Slot {slot_number} is not online"}), 400

    setup_id = slot.get_setup_id()
    role = "singleplayer" if mode == "singleplayer" else "host"  # For solo start, assume host
    session_id = f"slot{slot_number}-{int(time.time())}"

    try:
        logger.info(f"Starting {game} ({mode}) on Slot {slot_number}")

        # Phase 1: Configure
        config_response = requests.post(
            f"http://{setup_id}/api/configure",
            json={
                "game": game,
                "session_id": session_id,
                "role": role
            },
            timeout=5
        )

        if not config_response.ok:
            logger.error(f"Failed to configure Slot {slot_number}: {config_response.text}")
            return jsonify({"error": "Configuration failed", "details": config_response.text}), 500

        # Phase 2: Start
        start_response = requests.post(
            f"http://{setup_id}/api/start",
            timeout=5
        )

        if start_response.ok:
            logger.info(f"✓ Successfully started {game} on Slot {slot_number}")
            return jsonify({
                "status": "success",
                "slot": slot_number,
                "game": game,
                "mode": mode
            })
        else:
            logger.error(f"Failed to start game on Slot {slot_number}: {start_response.text}")
            return jsonify({"error": "Failed to start game", "details": start_response.text}), 500

    except requests.exceptions.RequestException as e:
        logger.error(f"Error communicating with Slot {slot_number}: {e}")
        return jsonify({"error": "Communication error", "details": str(e)}), 500


@app.route('/api/stop_slot', methods=['POST'])
def stop_slot():
    """Stop game on a specific slot"""
    data = request.json
    slot_number = data.get('slot')

    if not slot_number:
        return jsonify({"error": "Missing required field: slot"}), 400

    if slot_number not in SLOTS:
        return jsonify({"error": f"Invalid slot number: {slot_number}. Must be 1-4"}), 400

    slot = SLOTS[slot_number]

    if not slot.is_online():
        return jsonify({"error": f"Slot {slot_number} is not online"}), 400

    setup_id = slot.get_setup_id()

    try:
        logger.info(f"Stopping game on Slot {slot_number}")

        stop_response = requests.post(
            f"http://{setup_id}/api/stop",
            timeout=5
        )

        if stop_response.ok:
            logger.info(f"✓ Successfully stopped game on Slot {slot_number}")
            return jsonify({
                "status": "success",
                "slot": slot_number
            })
        else:
            logger.error(f"Failed to stop game on Slot {slot_number}: {stop_response.text}")
            return jsonify({"error": "Failed to stop game", "details": stop_response.text}), 500

    except requests.exceptions.RequestException as e:
        logger.error(f"Error communicating with Slot {slot_number}: {e}")
        return jsonify({"error": "Communication error", "details": str(e)}), 500


@app.route('/api/start_multiplayer', methods=['POST'])
def start_multiplayer():
    """Start F1 22 multiplayer on selected slots"""
    data = request.json
    slot_numbers = data.get('slots', [])
    game = data.get('game', 'f1_22')

    if not slot_numbers or len(slot_numbers) < 2:
        return jsonify({"error": "Multiplayer requires at least 2 slots"}), 400

    # Validate all slots are online
    for slot_num in slot_numbers:
        if slot_num not in SLOTS:
            return jsonify({"error": f"Invalid slot number: {slot_num}"}), 400
        if not SLOTS[slot_num].is_online():
            return jsonify({"error": f"Slot {slot_num} is not online"}), 400

    session_id = f"multi-{int(time.time())}"
    results = []
    configured_slots = []

    # Get host IP from the first slot (slot 0 will be host)
    host_slot = SLOTS[slot_numbers[0]]
    host_ip = host_slot.setup.address if host_slot.setup else None
    logger.info(f"Host IP for this session: {host_ip}")

    # Phase 1: Configure all slots
    logger.info(f"Phase 1: Configuring {len(slot_numbers)} slots for {game} multiplayer")
    for i, slot_num in enumerate(slot_numbers):
        slot = SLOTS[slot_num]
        setup_id = slot.get_setup_id()
        role = "host" if i == 0 else "join"

        try:
            logger.info(f"Configuring Slot {slot_num} as {role}")

            config_response = requests.post(
                f"http://{setup_id}/api/configure",
                json={
                    "game": game,
                    "session_id": session_id,
                    "role": role,
                    "player_count": len(slot_numbers),
                    "host_ip": host_ip
                },
                timeout=5
            )

            if not config_response.ok:
                logger.error(f"Failed to configure Slot {slot_num}: {config_response.text}")
                results.append({
                    "slot": slot_num,
                    "role": role,
                    "status": "failed_configure",
                    "error": config_response.text
                })
                continue

            logger.info(f"✓ Configuration confirmed for Slot {slot_num}")
            configured_slots.append((slot_num, setup_id, role))

        except requests.exceptions.RequestException as e:
            logger.error(f"Error configuring Slot {slot_num}: {e}")
            results.append({
                "slot": slot_num,
                "role": role,
                "status": "error_configure",
                "error": str(e)
            })

    # Check if all slots were configured
    if len(configured_slots) < len(slot_numbers):
        logger.error(f"Configuration failed: Only {len(configured_slots)}/{len(slot_numbers)} slots configured")
        return jsonify({
            "error": "Not all slots could be configured",
            "configured_count": len(configured_slots),
            "total_slots": len(slot_numbers),
            "results": results
        }), 400

    logger.info(f"✓ All {len(slot_numbers)} slots configured successfully")

    # Phase 2: Start games on all configured slots
    logger.info(f"Phase 2: Starting games on all configured slots")
    for slot_num, setup_id, role in configured_slots:
        try:
            logger.info(f"Starting game on Slot {slot_num}")

            start_response = requests.post(
                f"http://{setup_id}/api/start",
                timeout=5
            )

            if start_response.ok:
                logger.info(f"✓ Successfully started game on Slot {slot_num}")
                results.append({
                    "slot": slot_num,
                    "role": role,
                    "status": "success"
                })
            else:
                logger.error(f"Failed to start game on Slot {slot_num}: {start_response.text}")
                results.append({
                    "slot": slot_num,
                    "role": role,
                    "status": "failed_start",
                    "error": start_response.text
                })

        except requests.exceptions.RequestException as e:
            logger.error(f"Error starting game on Slot {slot_num}: {e}")
            results.append({
                "slot": slot_num,
                "role": role,
                "status": "error_start",
                "error": str(e)
            })

    success_count = sum(1 for r in results if r['status'] == 'success')

    return jsonify({
        "game": game,
        "session_id": session_id,
        "total_slots": len(slot_numbers),
        "success_count": success_count,
        "results": results
    })


@app.route('/api/configure_motion', methods=['POST'])
def configure_motion():
    """Configure motion/wheel software on all online setups"""
    results = []

    for slot_num, slot in SLOTS.items():
        if not slot.is_online():
            continue

        setup_id = slot.get_setup_id()
        setup_name = slot.setup.heartbeat.name if slot.setup and slot.setup.heartbeat else f"Slot {slot_num}"

        try:
            logger.info(f"Configuring motion on {setup_name} ({setup_id})")

            response = requests.post(
                f"http://{setup_id}/api/configure_cammus",
                timeout=60  # Longer timeout as this can take a while
            )

            if response.ok:
                logger.info(f"✓ Motion configured on {setup_name}")
                results.append({
                    "slot": slot_num,
                    "name": setup_name,
                    "status": "success"
                })
            else:
                logger.error(f"Failed to configure motion on {setup_name}: {response.text}")
                results.append({
                    "slot": slot_num,
                    "name": setup_name,
                    "status": "failed",
                    "error": response.json().get('message', response.text)
                })

        except requests.exceptions.RequestException as e:
            logger.error(f"Error configuring motion on {setup_name}: {e}")
            results.append({
                "slot": slot_num,
                "name": setup_name,
                "status": "error",
                "error": str(e)
            })

    success_count = sum(1 for r in results if r['status'] == 'success')
    total_count = len(results)

    if total_count == 0:
        return jsonify({
            "status": "error",
            "message": "No online setups found"
        }), 400

    return jsonify({
        "status": "success" if success_count == total_count else "partial",
        "message": f"Configured {success_count}/{total_count} setups",
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
    global service_browser_listener

    disable_quickedit()

    zeroconf = Zeroconf()
    service_browser_listener = SetupListener()
    browser = ServiceBrowser(
        zeroconf,
        "_simracing._tcp.local.",
        service_browser_listener
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