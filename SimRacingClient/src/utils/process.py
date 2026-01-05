"""
Process management utilities for launching and terminating game processes.

This module provides:
- launch_process(): Start a game executable as a subprocess
- terminate_process(): Find and kill processes by name
"""

import subprocess
import psutil
from pathlib import Path
from utils.monitoring import get_logger

logger = get_logger(__name__)


def launch_process(executable_path: Path) -> subprocess.Popen:
    """
    Launch a game executable as a subprocess.

    Args:
        executable_path: Absolute path to the executable

    Returns:
        subprocess.Popen object for the launched process

    Raises:
        FileNotFoundError: If executable doesn't exist
        PermissionError: If no permission to execute
        RuntimeError: If launch fails for other reasons
    """
    exe_path = Path(executable_path)

    if not exe_path.exists():
        raise FileNotFoundError(f"Executable not found: {executable_path}")

    if not exe_path.is_file():
        raise ValueError(f"Path is not a file: {executable_path}")

    logger.info(f"Launching: {exe_path.name}")
    logger.info(f"Path: {exe_path.absolute()}")

    try:
        process = subprocess.Popen([str(exe_path)], cwd=exe_path.parent)
        logger.info(f"Process launched (PID: {process.pid})")
        return process
    except PermissionError:
        raise PermissionError(f"No permission to execute: {executable_path}")
    except Exception as e:
        raise RuntimeError(f"Failed to launch: {str(e)}")


def terminate_process(process_name: str) -> bool:
    """
    Find and terminate all processes matching the given name.

    Args:
        process_name: Name of the process to terminate (e.g., 'F1_22.exe')

    Returns:
        bool: True if at least one process was terminated, False otherwise
    """
    logger.info(f"Terminating processes: {process_name}")

    process_name_lower = process_name.lower()
    found_processes = []

    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() == process_name_lower:
                found_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not found_processes:
        logger.warning(f"No running processes found for {process_name}")
        return False

    # Terminate all found processes
    success = True
    for proc in found_processes:
        try:
            logger.info(f"Terminating PID {proc.pid}...")
            proc.terminate()
            proc.wait(timeout=5)
            logger.info(f"Process {proc.pid} terminated")
        except psutil.TimeoutExpired:
            logger.warning(f"Process {proc.pid} didn't terminate gracefully, force killing...")
            try:
                proc.kill()
                logger.info(f"Process {proc.pid} killed")
            except Exception as e:
                logger.error(f"Error killing process {proc.pid}: {e}")
                success = False
        except psutil.AccessDenied:
            logger.error(f"Access denied for PID {proc.pid}. Try running as administrator.")
            success = False
        except Exception as e:
            logger.error(f"Error terminating PID {proc.pid}: {e}")
            success = False

    return success
