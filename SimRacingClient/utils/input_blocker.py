import ctypes
from ctypes import POINTER, c_int, c_uint, c_long, windll, c_void_p
from ctypes import wintypes
import atexit
import threading


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
    global is_blocking, hook_thread, hook_error
    print("Blocking input")
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
    
    print("Testing input blocker...")
    print("Blocking input in 3 seconds...")
    time.sleep(3)
    
    try:
        block_input()
        print("Input blocked! Try moving your mouse or typing.")
        print("Press Ctrl+C in this console to unblock.")
        time.sleep(5)
    except RuntimeError as e:
        print(f"Error: {e}")
    finally:
        print("\nUnblocking input...")
        unblock_input()
        print("Input unblocked!")