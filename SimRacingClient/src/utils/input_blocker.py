"""
Windows input blocking and console utilities.

Provides functions to block keyboard/mouse input during automated
navigation sequences, and console configuration utilities.
"""

import sys
import ctypes
import atexit
import threading
from utils.monitoring import get_logger

logger = get_logger(__name__)


def disable_quickedit():
    """
    Disable QuickEdit mode on Windows console.

    QuickEdit mode causes the process to pause when the user clicks
    on the console window. This is problematic for long-running services
    that should not be interrupted by accidental clicks.

    This function silently does nothing on non-Windows platforms.
    """
    if sys.platform != 'win32':
        return

    try:
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
        pass  # Silently fail if it doesn't work


# Input blocking is Windows-only
if sys.platform != 'win32':
    def block_input():
        """Stub for non-Windows platforms."""
        logger.warning("Input blocking is only available on Windows")

    def unblock_input():
        """Stub for non-Windows platforms."""
        pass

else:
    # Windows-specific imports and implementation
    from ctypes import POINTER, c_int, c_uint, c_long, windll, c_void_p
    from ctypes import wintypes

    user32 = windll.user32
    kernel32 = windll.kernel32

    WH_KEYBOARD_LL = 13
    WH_MOUSE_LL = 14

    HOOKPROC = ctypes.WINFUNCTYPE(c_long, c_int, c_uint, POINTER(c_uint))

    keyboard_hook = None
    mouse_hook = None
    is_blocking = False
    hook_thread = None
    hooks_ready = threading.Event()
    hook_error = None

    keyboard_proc = None
    mouse_proc = None

    def _keyboard_hook_callback(nCode, wParam, lParam):
        if nCode >= 0 and is_blocking:
            return 1
        return user32.CallNextHookEx(keyboard_hook, nCode, wParam, lParam)

    def _mouse_hook_callback(nCode, wParam, lParam):
        if nCode >= 0 and is_blocking:
            return 1
        return user32.CallNextHookEx(mouse_hook, nCode, wParam, lParam)

    def _hook_thread_func():
        global keyboard_hook, mouse_hook, keyboard_proc, mouse_proc, hook_error

        keyboard_proc = HOOKPROC(_keyboard_hook_callback)
        mouse_proc = HOOKPROC(_mouse_hook_callback)

        user32.SetWindowsHookExW.restype = c_void_p

        keyboard_hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            keyboard_proc,
            None,
            0
        )

        if not keyboard_hook:
            error_code = kernel32.GetLastError()
            hook_error = f"Keyboard hook failed with error code: {error_code}"
            hooks_ready.set()
            return

        mouse_hook = user32.SetWindowsHookExW(
            WH_MOUSE_LL,
            mouse_proc,
            None,
            0
        )

        if not mouse_hook:
            error_code = kernel32.GetLastError()
            hook_error = f"Mouse hook failed with error code: {error_code}"
            user32.UnhookWindowsHookEx(keyboard_hook)
            keyboard_hook = None
            hooks_ready.set()
            return

        hooks_ready.set()

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def block_input():
        """Block all keyboard and mouse input using Windows hooks."""
        global is_blocking, hook_thread, hook_error
        logger.info("Blocking input")
        if is_blocking:
            return

        hook_error = None
        hooks_ready.clear()
        hook_thread = threading.Thread(target=_hook_thread_func, daemon=True)
        hook_thread.start()

        hooks_ready.wait(timeout=5)

        if hook_error:
            raise RuntimeError(f"Failed to install input hooks: {hook_error}")

        if not keyboard_hook or not mouse_hook:
            raise RuntimeError("Failed to install input hooks: hooks are NULL")

        is_blocking = True

    def unblock_input():
        """Unblock keyboard and mouse input."""
        global keyboard_hook, mouse_hook, is_blocking, hook_thread

        if not is_blocking:
            return

        is_blocking = False

        if hook_thread and hook_thread.is_alive():
            ctypes.windll.user32.PostThreadMessageW(hook_thread.ident, 0x0012, 0, 0)
            hook_thread.join(timeout=1)

        keyboard_hook = None
        mouse_hook = None
        hook_thread = None

    atexit.register(unblock_input)


if __name__ == "__main__":
    import time

    logger.info("Testing input blocker...")
    logger.info("Blocking input in 3 seconds...")
    time.sleep(3)

    try:
        block_input()
        logger.info("Input blocked! Try moving your mouse or typing.")
        logger.info("Press Ctrl+C in this console to unblock.")
        time.sleep(5)
    except RuntimeError as e:
        logger.error(f"Error: {e}")
    finally:
        logger.info("Unblocking input...")
        unblock_input()
        logger.info("Input unblocked!")
