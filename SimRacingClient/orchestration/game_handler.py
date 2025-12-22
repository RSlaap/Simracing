from client.utils.focus_window import bring_window_to_focus, is_window_in_focus
from client.utils.input_blocker import block_input
from client.utils.game_launcher import launch_game
from client.utils.game_closer import close_game
import time
import json
from pathlib import Path
from SimRacingClient.utils.screen_navigator import load_and_execute_navigation

script_dir = Path(__file__).parent
config_path = script_dir / "config.json"
with open(config_path, 'r') as f:
    config = json.load(f)

def handle_acc(play_time):
    launch_game(config['acc_game_path'])
    time.sleep(play_time)
    close_game(config['acc_process_name'])

if __name__ == "__main__":
    # block_input()
    launch_game(config['f1_22_game_path'])
    time.sleep(5)
    bring_window_to_focus("F1 22")
    is_window_in_focus("F1 22")
    success = load_and_execute_navigation(
        json_path="templates.json",
        template_dir="templates",
        threshold=0.85,
        max_retries=60,
        retry_delay=0.05,
        skip_intro_max_attempts=60
    )