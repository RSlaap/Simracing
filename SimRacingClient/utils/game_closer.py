
import psutil
import sys


def close_game(process_name):
    process_name_lower = process_name.lower()  
    found_processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() == process_name_lower:
                found_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    for proc in found_processes:
        try:
            print(f"Terminating process (PID: {proc.pid})...")
            proc.terminate()
            proc.wait(timeout=5)
            print(f"Process {proc.pid} terminated successfully")
        except psutil.TimeoutExpired:
            print(f"Process {proc.pid} didn't terminate gracefully, force killing...")
            proc.kill()
            print(f"Process {proc.pid} killed")
        except psutil.AccessDenied:
            print(f"Access denied to terminate process {proc.pid}. Try running as administrator.")
        except Exception as e:
            print(f"Error terminating process {proc.pid}: {e}")
    return True
