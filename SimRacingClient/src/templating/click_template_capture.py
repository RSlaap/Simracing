"""
Click-based template capture tool for UI automation.

This tool captures full-screen templates for click-based navigation (e.g., CAMMUS software).
Unlike template_capture.py which captures regions for keyboard navigation, this tool:
- Captures the area around where you click (full-screen search compatible)
- Outputs in ClickStep format for use with click_navigator.py
- Supports double-click marking

Usage:
    python click_template_capture.py [config_name]

    config_name: Name for this configuration (default: "cammus")
                 Templates saved to: templates/{config_name}/
                 Config saved to: {config_name}_config.json

Controls:
    S - Start capture mode (click to capture template at that location)
    D - Toggle double-click for next capture
    Q - Quit and save

Output format (click_steps.json):
    [
        {"template": "step_001.png", "double_click": false},
        {"template": "step_002.png", "double_click": true}
    ]
"""

import cv2
import numpy as np
from mss import mss
import pyautogui
from pathlib import Path
import json
import sys
from pynput import keyboard
import tkinter as tk
from datetime import datetime


class ClickTemplateCapturer:
    """Captures templates for click-based UI automation."""

    # Size of the region to capture around the click point
    CAPTURE_SIZE = 80  # pixels on each side of click point (160x160 total)

    def __init__(self, config_name: str = "cammus"):
        self.config_name = config_name
        self.capturing = False
        self.double_click_next = False
        self.running = True
        self.click_count = 0
        self.click_steps = []

        # Setup directories
        self.script_dir = Path(__file__).parent
        self.project_root = self.script_dir.parent.parent
        self.templates_dir = self.project_root / "templates" / config_name.upper()
        self.config_path = self.project_root / f"{config_name}_config.json"

        # Create templates directory
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # Crosshair overlay
        self.crosshair_root = None
        self.crosshair_windows = []
        self.setup_crosshair()

    def setup_crosshair(self):
        """Create crosshair overlay windows."""
        self.crosshair_root = tk.Tk()
        self.crosshair_root.withdraw()

        size = 40
        thickness = 2

        # Create horizontal and vertical crosshair lines
        for _ in range(2):
            window = tk.Toplevel(self.crosshair_root)
            window.overrideredirect(True)
            window.attributes('-topmost', True)
            window.attributes('-transparentcolor', 'white')
            window.config(bg='white')

            canvas = tk.Canvas(window, bg='white', highlightthickness=0)
            canvas.pack()

            self.crosshair_windows.append({
                'window': window,
                'canvas': canvas,
                'size': size,
                'thickness': thickness
            })

        self.update_crosshair()

    def update_crosshair(self):
        """Update crosshair position to follow mouse."""
        if not self.running or not self.crosshair_root:
            return

        try:
            x, y = pyautogui.position()

            # Color based on mode
            if self.capturing:
                color = 'red' if self.double_click_next else 'lime'
            else:
                color = 'gray'

            if len(self.crosshair_windows) >= 2:
                # Horizontal line
                ch = self.crosshair_windows[0]
                size = ch['size']
                thickness = ch['thickness']

                ch['window'].geometry(f"{size * 2}x{thickness}+{x - size}+{y - thickness // 2}")
                ch['canvas'].config(width=size * 2, height=thickness)
                ch['canvas'].delete('all')
                ch['canvas'].create_line(0, thickness // 2, size * 2, thickness // 2,
                                        fill=color, width=thickness)

                # Vertical line
                ch = self.crosshair_windows[1]
                ch['window'].geometry(f"{thickness}x{size * 2}+{x - thickness // 2}+{y - size}")
                ch['canvas'].config(width=thickness, height=size * 2)
                ch['canvas'].delete('all')
                ch['canvas'].create_line(thickness // 2, 0, thickness // 2, size * 2,
                                        fill=color, width=thickness)

            if self.crosshair_root:
                self.crosshair_root.after(10, self.update_crosshair)
        except Exception:
            pass

    def capture_at_click(self, x: int, y: int) -> str:
        """
        Capture a template region centered on the click position.

        Args:
            x: Click X coordinate (absolute pixels)
            y: Click Y coordinate (absolute pixels)

        Returns:
            Filename of saved template
        """
        # Calculate capture region
        half_size = self.CAPTURE_SIZE
        screen_w, screen_h = pyautogui.size()

        left = max(0, x - half_size)
        top = max(0, y - half_size)
        right = min(screen_w, x + half_size)
        bottom = min(screen_h, y + half_size)

        width = right - left
        height = bottom - top

        # Small delay to let any UI changes settle
        import time
        time.sleep(0.05)

        # Capture screenshot
        sct = mss()
        monitor = {
            "top": top,
            "left": left,
            "width": width,
            "height": height
        }
        screenshot = sct.grab(monitor)
        img = np.array(screenshot)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        # Save template
        self.click_count += 1
        filename = f"step_{self.click_count:03d}.png"
        template_path = self.templates_dir / filename
        cv2.imwrite(str(template_path), img)

        return filename

    def on_press(self, key):
        """Handle keyboard events."""
        try:
            if key.char == 's':
                if not self.capturing:
                    self.capturing = True
                    mode = "DOUBLE-CLICK" if self.double_click_next else "SINGLE-CLICK"
                    print(f"\n[CAPTURE MODE: {mode}] Click on the UI element to capture...")
                else:
                    self.capturing = False
                    print("\n[STANDBY] Press 'S' to capture, 'D' to toggle double-click, 'Q' to quit")

            elif key.char == 'd':
                self.double_click_next = not self.double_click_next
                mode = "DOUBLE-CLICK" if self.double_click_next else "SINGLE-CLICK"
                print(f"\n[{mode} MODE] Next capture will be marked as {mode.lower()}")

            elif key.char == 'q':
                print("\n\nSaving and exiting...")
                self.running = False
                if self.crosshair_root:
                    try:
                        self.crosshair_root.quit()
                    except Exception:
                        pass
                return False

        except AttributeError:
            pass

    def on_click(self, x, y, button, pressed):
        """Handle mouse click events."""
        if self.capturing and pressed:
            # Capture template at click location
            filename = self.capture_at_click(x, y)

            # Record step
            step = {
                "template": filename,
                "double_click": self.double_click_next
            }
            self.click_steps.append(step)

            click_type = "double-click" if self.double_click_next else "click"
            print(f"  Step {len(self.click_steps)}: Captured {filename} ({click_type}) at ({x}, {y})")

            # Reset double-click flag after capture
            self.double_click_next = False

            # Stay in capture mode for next click
            print(f"\n[CAPTURE MODE] Click next element, or press 'S' to pause, 'D' for double-click")

    def save_config(self):
        """Save click steps to JSON file."""
        # Save click steps
        click_steps_path = self.templates_dir / "click_steps.json"
        with open(click_steps_path, 'w') as f:
            json.dump(self.click_steps, f, indent=2)

        # Create/update main config file
        config = {
            "enabled": True,
            "executable_path": "",
            "process_name": "",
            "window_title": "",
            "template_dir": self.config_name.upper(),
            "template_threshold": 0.85,
            "startup_delay": 5.0,
            "max_retries": 10,
            "retry_delay": 1.0,
            "click_delay": 0.5,
            "click_steps_file": "click_steps.json"
        }

        # Load existing config if present
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    existing = json.load(f)
                    # Preserve user-configured values
                    for key in ['executable_path', 'process_name', 'window_title',
                               'startup_delay', 'max_retries', 'retry_delay', 'click_delay']:
                        if key in existing and existing[key]:
                            config[key] = existing[key]
            except Exception:
                pass

        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)

        return click_steps_path, self.config_path

    def start(self):
        """Start the template capture tool."""
        from pynput import mouse

        print("=" * 60)
        print("CLICK TEMPLATE CAPTURE TOOL")
        print("=" * 60)
        print(f"\nConfiguration: {self.config_name}")
        print(f"Templates will be saved to: {self.templates_dir}")
        print(f"Config will be saved to: {self.config_path}")
        print("\nControls:")
        print("  S - Start/pause capture mode")
        print("  D - Toggle double-click for next capture")
        print("  Q - Quit and save")
        print("\nCrosshair colors:")
        print("  Gray  = Standby (not capturing)")
        print("  Green = Capture mode (single-click)")
        print("  Red   = Capture mode (double-click)")
        print("\n" + "=" * 60)
        print("\n[STANDBY] Press 'S' to start capturing")

        # Start listeners
        kb_listener = keyboard.Listener(on_press=self.on_press)
        mouse_listener = mouse.Listener(on_click=self.on_click)

        kb_listener.start()
        mouse_listener.start()

        # Run crosshair update loop
        if self.crosshair_root:
            try:
                self.crosshair_root.mainloop()
            except Exception:
                pass
        else:
            kb_listener.join()

        mouse_listener.stop()

        # Save results
        if self.click_steps:
            steps_path, config_path = self.save_config()
            print(f"\nSaved {len(self.click_steps)} step(s):")
            print(f"  Click steps: {steps_path}")
            print(f"  Config: {config_path}")
            print("\nNext steps:")
            print(f"  1. Edit {config_path.name} to set executable_path, process_name, window_title")
            print(f"  2. Adjust startup_delay if needed (time to wait for software to load)")
            print(f"  3. Call /api/configure_cammus endpoint to test")
        else:
            print("\nNo templates captured.")


def main():
    config_name = sys.argv[1] if len(sys.argv) > 1 else "cammus"
    capturer = ClickTemplateCapturer(config_name=config_name)
    capturer.start()


if __name__ == "__main__":
    main()
