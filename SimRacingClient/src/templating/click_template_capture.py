"""
Click-based template capture tool for UI automation.

This tool captures templates for click-based navigation (e.g., CAMMUS software).
It captures the area around the current mouse position when you press a hotkey,
allowing you to click normally in the target application without interference.

Usage:
    python click_template_capture.py [config_name]

    config_name: Name prefix for saved templates (default: "cammus")
                 Templates saved to: unclassified_templates/

Controls:
    C - Capture template at current mouse position (single-click action)
    V - Capture template at current mouse position (double-click action)
    Q - Quit and save

Workflow:
    1. Open the target application (e.g., CAMMUS)
    2. Run this tool
    3. Position mouse over a button you want to capture
    4. Press 'C' (single-click) or 'V' (double-click) to capture
    5. Click the button normally to navigate to the next screen
    6. Repeat steps 3-5 for each button
    7. Press 'Q' to quit and save

Output:
    - Templates saved as PNG files in unclassified_templates/
    - click_steps.json with the capture sequence
    - User should manually move files to templates/CAMMUS/ and configure cammus_config.json
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

    # Size of the region to capture around the mouse position
    CAPTURE_SIZE = 80  # pixels on each side of mouse (160x160 total)

    def __init__(self, config_name: str = "cammus"):
        self.config_name = config_name
        self.running = True
        self.capture_count = 0
        self.click_steps = []

        # Setup directories - save to unclassified_templates
        self.script_dir = Path(__file__).parent
        self.templates_dir = self.script_dir / "unclassified_templates"

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

            # Always show lime color - crosshair is always ready
            color = 'lime'

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

    def capture_at_position(self, double_click: bool = False) -> str:
        """
        Capture a template region centered on the current mouse position.

        Args:
            double_click: Whether this capture is for a double-click action

        Returns:
            Filename of saved template
        """
        x, y = pyautogui.position()

        # Calculate capture region
        half_size = self.CAPTURE_SIZE
        screen_w, screen_h = pyautogui.size()

        left = max(0, x - half_size)
        top = max(0, y - half_size)
        right = min(screen_w, x + half_size)
        bottom = min(screen_h, y + half_size)

        width = right - left
        height = bottom - top

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

        # Save template with timestamp for uniqueness
        self.capture_count += 1
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.config_name}_step_{self.capture_count:03d}_{timestamp}.png"
        template_path = self.templates_dir / filename
        cv2.imwrite(str(template_path), img)

        # Record step
        step = {
            "template": filename,
            "double_click": double_click
        }
        self.click_steps.append(step)

        click_type = "double-click" if double_click else "single-click"
        print(f"  Step {len(self.click_steps)}: Captured {filename} ({click_type}) at ({x}, {y})")
        print(f"  Now click the button in CAMMUS to continue, then position for next capture")

        return filename

    def on_press(self, key):
        """Handle keyboard events."""
        try:
            if key.char == 'c':
                # Capture for single-click action
                print(f"\n[CAPTURING SINGLE-CLICK TEMPLATE]")
                self.capture_at_position(double_click=False)

            elif key.char == 'v':
                # Capture for double-click action
                print(f"\n[CAPTURING DOUBLE-CLICK TEMPLATE]")
                self.capture_at_position(double_click=True)

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

    def save_click_steps(self):
        """Save click steps to JSON file in unclassified_templates."""
        click_steps_path = self.templates_dir / "click_steps.json"
        with open(click_steps_path, 'w') as f:
            json.dump(self.click_steps, f, indent=2)
        return click_steps_path

    def start(self):
        """Start the template capture tool."""
        print("=" * 60)
        print("CLICK TEMPLATE CAPTURE TOOL")
        print("=" * 60)
        print(f"\nConfiguration: {self.config_name}")
        print(f"Templates will be saved to: {self.templates_dir}")
        print("\nWORKFLOW:")
        print("  1. Position mouse over a button in CAMMUS")
        print("  2. Press 'C' to capture (for single-click buttons)")
        print("     or 'V' to capture (for double-click buttons)")
        print("  3. Click the button in CAMMUS to navigate to next screen")
        print("  4. Repeat for each button")
        print("  5. Press 'Q' when done")
        print("\nControls:")
        print("  C - Capture template at mouse position (single-click)")
        print("  V - Capture template at mouse position (double-click)")
        print("  Q - Quit and save")
        print("\n" + "=" * 60)
        print("\n[READY] Position mouse over first button, then press 'C' or 'V'")

        # Start keyboard listener only (no mouse listener - we don't intercept clicks)
        kb_listener = keyboard.Listener(on_press=self.on_press)
        kb_listener.start()

        # Run crosshair update loop
        if self.crosshair_root:
            try:
                self.crosshair_root.mainloop()
            except Exception:
                pass
        else:
            kb_listener.join()

        # Save results
        if self.click_steps:
            steps_path = self.save_click_steps()
            print(f"\nSaved {len(self.click_steps)} step(s) to: {steps_path}")
            print("\nNext steps:")
            print(f"  1. Move template images from unclassified_templates/ to templates/CAMMUS/")
            print(f"  2. Move click_steps.json to templates/CAMMUS/")
            print(f"  3. Update cammus_config.json with correct paths and settings")
            print(f"  4. See documentation/CAMMUS_SETUP.md for detailed instructions")
        else:
            print("\nNo templates captured.")


def main():
    config_name = sys.argv[1] if len(sys.argv) > 1 else "cammus"
    capturer = ClickTemplateCapturer(config_name=config_name)
    capturer.start()


if __name__ == "__main__":
    main()
