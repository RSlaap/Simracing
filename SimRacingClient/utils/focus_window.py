import win32gui
import win32con

def bring_window_to_focus(window_title_substring: str) -> bool:
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if window_title_substring.lower() in title.lower():
                windows.append((hwnd, title))
        return True
    
    windows = []
    win32gui.EnumWindows(callback, windows)
    
    if not windows:
        print(f"No window found with title containing: {window_title_substring}")
        return False
    
    hwnd, title = windows[0]
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    print(f"✓ Window '{title}' brought to focus")
    return True

def is_window_in_focus(window_title_substring: str) -> bool:
    hwnd = win32gui.GetForegroundWindow()
    title = win32gui.GetWindowText(hwnd)
    return window_title_substring.lower() in title.lower()