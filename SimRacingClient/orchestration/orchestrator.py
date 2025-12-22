"""
Simple SimRacing Orchestrator
Discovers available setups and sends configuration commands
"""

from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
import requests
import time
import socket

class SetupListener(ServiceListener):
    def __init__(self):
        self.discovered_setups = {}
    
    def add_service(self, zc, service_type, name):
        info = zc.get_service_info(service_type, name)
        if info:
            address = socket.inet_ntoa(info.addresses[0])
            port = info.port
            
            properties = {}
            for key, value in info.properties.items():
                properties[key.decode('utf-8')] = value.decode('utf-8')
            
            setup_id = f"{address}:{port}"
            self.discovered_setups[setup_id] = {
                "name": name,
                "address": address,
                "port": port,
                "properties": properties
            }
            
            print(f"\n[+] Found setup: {properties.get('hostname', 'Unknown')}")
            print(f"    Address: {address}:{port}")
            print(f"    Status: {properties.get('status', 'unknown')}")
            print(f"    Supported games: {properties.get('games', 'unknown')}")
    
    def remove_service(self, zc, service_type, name):
        print(f"\n[-] Setup disconnected: {name}")
    
    def update_service(self, zc, service_type, name):
        pass

class SimRacingOrchestrator:
    def __init__(self):
        self.zeroconf = Zeroconf()
        self.listener = SetupListener()
        self.browser = ServiceBrowser(
            self.zeroconf,
            "_simracing._tcp.local.",
            self.listener
        )
    
    def get_discovered_setups(self):
        return self.listener.discovered_setups
    
    def configure_setup(self, setup_url, game, player_id, session_id):
        """Send configuration to a specific setup"""
        endpoint = f"http://{setup_url}/api/configure"
        
        payload = {
            "game": game,
            "player_id": player_id,
            "session_id": session_id
        }
        
        try:
            response = requests.post(endpoint, json=payload, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def start_game(self, setup_url):
        """Tell setup to start the game"""
        endpoint = f"http://{setup_url}/api/start"
        
        try:
            response = requests.post(endpoint, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def get_setup_status(self, setup_url):
        """Get current status of a setup"""
        endpoint = f"http://{setup_url}/api/status"
        
        try:
            response = requests.get(endpoint, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def stop(self):
        """Clean up resources"""
        self.zeroconf.close()

def print_menu():
    print("\n" + "="*50)
    print("SimRacing Orchestrator")
    print("="*50)
    print("1. List discovered setups")
    print("2. Configure setup")
    print("3. Start game on setup")
    print("4. Check setup status")
    print("5. Exit")
    print("="*50)

def list_setups(orchestrator):
    setups = orchestrator.get_discovered_setups()
    
    if not setups:
        print("\nNo setups discovered yet. Waiting...")
        return None
    
    print("\nDiscovered Setups:")
    setup_list = list(setups.items())
    for i, (setup_id, setup_info) in enumerate(setup_list, 1):
        print(f"{i}. {setup_info['properties'].get('hostname', 'Unknown')}")
        print(f"   Address: {setup_id}")
        print(f"   Status: {setup_info['properties'].get('status', 'unknown')}")
    
    return setup_list

def main():
    print("Starting SimRacing Orchestrator...")
    print("Discovering setups on the network...")
    
    orchestrator = SimRacingOrchestrator()
    
    time.sleep(3)
    
    try:
        while True:
            print_menu()
            choice = input("\nEnter your choice (1-5): ").strip()
            
            if choice == '1':
                list_setups(orchestrator)
            
            elif choice == '2':
                setup_list = list_setups(orchestrator)
                if not setup_list:
                    continue
                
                setup_num = int(input("\nSelect setup number: "))
                if 1 <= setup_num <= len(setup_list):
                    setup_id, _ = setup_list[setup_num - 1]
                    
                    print("\nAvailable games:")
                    games = ["F1 2024", "Assetto Corsa", "iRacing"]
                    for i, game in enumerate(games, 1):
                        print(f"{i}. {game}")
                    
                    game_num = int(input("Select game number: "))
                    if 1 <= game_num <= len(games):
                        game = games[game_num - 1]
                        player_id = input("Enter player ID: ")
                        session_id = input("Enter session ID (optional): ") or "default"
                        
                        result = orchestrator.configure_setup(
                            setup_id, game, player_id, session_id
                        )
                        print(f"\nResult: {result}")
            
            elif choice == '3':
                setup_list = list_setups(orchestrator)
                if not setup_list:
                    continue
                
                setup_num = int(input("\nSelect setup number: "))
                if 1 <= setup_num <= len(setup_list):
                    setup_id, _ = setup_list[setup_num - 1]
                    
                    result = orchestrator.start_game(setup_id)
                    print(f"\nResult: {result}")
            
            elif choice == '4':
                setup_list = list_setups(orchestrator)
                if not setup_list:
                    continue
                
                setup_num = int(input("\nSelect setup number: "))
                if 1 <= setup_num <= len(setup_list):
                    setup_id, _ = setup_list[setup_num - 1]
                    
                    status = orchestrator.get_setup_status(setup_id)
                    print(f"\nSetup Status:")
                    for key, value in status.items():
                        print(f"  {key}: {value}")
            
            elif choice == '5':
                print("\nShutting down...")
                break
            
            else:
                print("Invalid choice. Please try again.")
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        orchestrator.stop()
        print("Goodbye!")

if __name__ == '__main__':
    main()