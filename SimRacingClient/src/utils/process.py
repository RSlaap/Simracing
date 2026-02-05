"""
Process management utilities for launching and terminating game processes.

This module provides:
- launch_process(): Start a game executable as a subprocess
- launch_process_elevated(): Start a game with admin privileges (UAC prompt)
- terminate_process(): Find and kill processes by name
"""

import subprocess
import sys
import psutil
from pathlib import Path
from typing import Optional
from utils.monitoring import get_logger

logger = get_logger(__name__)

# Windows-specific imports for elevated launch
if sys.platform == 'win32':
    import ctypes
    from ctypes import wintypes

    # ShellExecuteEx structures and constants
    SEE_MASK_NOCLOSEPROCESS = 0x00000040
    SW_SHOWNORMAL = 1

    class SHELLEXECUTEINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", wintypes.ULONG),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR),
            ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIconOrMonitor", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    ShellExecuteEx = ctypes.windll.shell32.ShellExecuteExW
    ShellExecuteEx.restype = wintypes.BOOL


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


def launch_process_elevated(executable_path: Path, parameters: Optional[str] = None, wait: bool = False) -> bool:
    """
    Launch a process with elevated (administrator) privileges using ShellExecuteEx.

    This function triggers a UAC prompt if the current process is not already elevated.
    Use this for applications that require administrator privileges to run.

    Args:
        executable_path: Absolute path to the executable
        parameters: Optional command-line parameters to pass to the executable
        wait: If True, wait for the process to exit before returning.
              When True, the return value reflects the child's exit code
              (True if exit code is 0, False otherwise).

    Returns:
        True if launched successfully (wait=False), or if the process exited
        with code 0 (wait=True).  False on launch failure or non-zero exit.

    Raises:
        FileNotFoundError: If executable doesn't exist
        RuntimeError: On non-Windows platforms or if launch fails

    Note:
        - On Windows, this will show a UAC prompt if the script is not elevated
        - If the user denies the UAC prompt, the function returns False
        - The launched process runs in a separate context, so we cannot get its PID
    """
    if sys.platform != 'win32':
        raise RuntimeError("Elevated launch is only supported on Windows")

    exe_path = Path(executable_path)

    if not exe_path.exists():
        raise FileNotFoundError(f"Executable not found: {executable_path}")

    if not exe_path.is_file():
        raise ValueError(f"Path is not a file: {executable_path}")

    logger.info(f"Launching with elevation: {exe_path.name}")
    logger.info(f"Path: {exe_path.absolute()}")

    try:
        sei = SHELLEXECUTEINFO()
        sei.cbSize = ctypes.sizeof(sei)
        sei.fMask = SEE_MASK_NOCLOSEPROCESS
        sei.hwnd = None
        sei.lpVerb = "runas"  # Request elevation
        sei.lpFile = str(exe_path)
        sei.lpParameters = parameters
        sei.lpDirectory = str(exe_path.parent)
        sei.nShow = SW_SHOWNORMAL
        sei.hInstApp = None
        sei.hProcess = None

        if not ShellExecuteEx(ctypes.byref(sei)):
            error_code = ctypes.get_last_error()
            if error_code == 1223:  # ERROR_CANCELLED - User denied UAC
                logger.warning("User cancelled UAC elevation prompt")
                return False
            logger.error(f"ShellExecuteEx failed with error code: {error_code}")
            return False

        logger.info(f"Process launched with elevation")

        if wait and sei.hProcess:
            ctypes.windll.kernel32.WaitForSingleObject(sei.hProcess, -1)  # INFINITE
            exit_code = wintypes.DWORD()
            ctypes.windll.kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(exit_code))
            ctypes.windll.kernel32.CloseHandle(sei.hProcess)
            return exit_code.value == 0

        return True

    except Exception as e:
        logger.error(f"Failed to launch with elevation: {e}")
        raise RuntimeError(f"Failed to launch with elevation: {str(e)}")


def is_running_elevated() -> bool:
    """
    Check if the current process is running with administrator privileges.

    Returns:
        True if running as admin/elevated, False otherwise.
        Always returns False on non-Windows platforms.
    """
    if sys.platform != 'win32':
        return False

    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def is_process_running(process_name: str) -> bool:
    """
    Check if a process with the given name is currently running.

    Args:
        process_name: Name of the process to check (e.g., 'F1_22.exe')

    Returns:
        bool: True if at least one process with this name is running, False otherwise
    """
    process_name_lower = process_name.lower()

    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'].lower() == process_name_lower:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return False


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
