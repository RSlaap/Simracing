"""
Windows window focus management utilities.

This module provides functions to find and focus windows by title.
Windows-only: uses win32gui and ctypes for window manipulation.
"""

import sys
import time

if sys.platform != 'win32':
    raise ImportError("focus_window module is only available on Windows")

import ctypes
import win32gui
import win32con
import win32process
import pywintypes

from utils.monitoring import get_logger

logger = get_logger(__name__)

# Windows constants
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
VK_MENU = 0x12  # Alt key

def bring_window_to_focus(window_title_substring: str) -> bool:
    """
    Find a window by title substring and bring it to focus.

    Args:
        window_title_substring: Partial window title to search for (case-insensitive).

    Returns:
        True if window was found and focused, False otherwise.
    """
    def callback(hwnd: int, windows: list) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if window_title_substring.lower() in title.lower():
                windows.append((hwnd, title))
        return True

    windows: list = []
    win32gui.EnumWindows(callback, windows)

    if not windows:
        logger.debug(f"No window found with title containing: {window_title_substring}")
        return False

    hwnd, title = windows[0]

    try:
        # Restore window if minimized
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        # Make sure window is visible
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        # Simulate Alt key press/release to allow SetForegroundWindow
        # This is the most reliable way for background processes to gain focus permission
        ctypes.windll.user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)

        # Now we have permission to set foreground
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
        win32gui.SetActiveWindow(hwnd)

        logger.info(f"Window '{title}' brought to focus")
        return True

    except pywintypes.error as e:
        # Enhanced fallback: try thread attachment method
        try:
            logger.debug(f"Primary method failed, trying thread attachment...")

            # Get the thread IDs
            foreground_thread = ctypes.windll.user32.GetWindowThreadProcessId(
                ctypes.windll.user32.GetForegroundWindow(), None
            )
            app_thread = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)

            # Attach to the foreground window's thread
            if foreground_thread != app_thread:
                ctypes.windll.user32.AttachThreadInput(app_thread, foreground_thread, True)

            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)

            # Detach from foreground thread
            if foreground_thread != app_thread:
                ctypes.windll.user32.AttachThreadInput(app_thread, foreground_thread, False)

            logger.info(f"Window '{title}' brought to focus")
            return True

        except Exception as fallback_error:
            logger.warning(f"Could not bring window '{title}' to foreground. Error: {e}, Fallback error: {fallback_error}")
            return False


def _wait_and_focus_window(window_title: str, max_attempts: int = 10) -> bool:
    """
    Wait for a window to appear and bring it to focus.

    Retries every 2 seconds until the window is found or max attempts reached.

    Args:
        window_title: Partial window title to search for.
        max_attempts: Maximum number of attempts (default: 10).

    Returns:
        True if window was found and focused, False if max attempts exceeded.
    """
    logger.info(f"Waiting for '{window_title}' window to appear...")

    for attempt in range(max_attempts):
        time.sleep(2)
        if bring_window_to_focus(window_title):
            logger.info(f"Window focused (attempt {attempt + 1}/{max_attempts})")
            return True
        else:
            logger.debug(f"Window not found yet (attempt {attempt + 1}/{max_attempts})")

    return False
