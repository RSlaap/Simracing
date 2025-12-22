import subprocess
import sys
from pathlib import Path


def launch_game(executable_path):
    exe_path = Path(executable_path)
    
    if not exe_path.exists():
        raise FileNotFoundError(f"Game executable not found: {executable_path}")
    
    if not exe_path.is_file():
        raise ValueError(f"Path is not a file: {executable_path}")
    
    print(f"Launching game: {exe_path.name}")
    print(f"Path: {exe_path.absolute()}")
    
    try:
        process = subprocess.Popen([str(exe_path)], cwd=exe_path.parent)
        print(f"Game launched successfully (PID: {process.pid})")
        return process
    
    except PermissionError:
        raise PermissionError(f"No permission to execute: {executable_path}")
    except Exception as e:
        raise RuntimeError(f"Failed to launch game: {str(e)}")


if __name__ == "__main__":
    game_path = "D:\Steam\steamapps\common\Assetto Corsa Competizione\\acc.exe"
    try:
        game_process = launch_game(game_path)
        print("\nGame is running. Press Ctrl+C to exit this script.")
        print("(Note: Closing this script won't close the game)")
        
        game_process.wait()
        print(f"\nGame exited with code: {game_process.returncode}")
    
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user.")
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)