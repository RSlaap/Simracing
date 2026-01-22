import cv2
import numpy as np
from mss import mss
import pyautogui
from pathlib import Path
import json
import time
from pynput import keyboard
import tkinter as tk
from datetime import datetime

# Use absolute path relative to this script's location
SCRIPT_DIR = Path(__file__).parent
TEMPLATES_DIR = SCRIPT_DIR / "unclassified_templates"
TEMPLATES_DATA = TEMPLATES_DIR / "templates.json"

class TemplateCapturer:
    on_click_counter = 0
    def __init__(self, game_name):
        self.game_name = game_name
        self.capturing = False
        self.corner1 = None
        self.running = True
        self.show_position = True
        self.crosshair_root = None
        self.crosshair_windows = []
        TEMPLATES_DIR.mkdir(exist_ok=True)
        self.setup_crosshair()
    
    def setup_crosshair(self):
        self.crosshair_root = tk.Tk()
        self.crosshair_root.withdraw()
        
        size = 30
        color = 'lime'
        thickness = 3
        
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
                'color': color,
                'thickness': thickness
            })
        
        self.update_crosshair()
    
    def update_crosshair(self):
        if not self.running or not self.crosshair_root:
            return
        
        try:
            x, y = pyautogui.position()
            
            if len(self.crosshair_windows) >= 2:
                ch = self.crosshair_windows[0]
                size = ch['size']
                thickness = ch['thickness']
                
                ch['window'].geometry(f"{size * 2}x{thickness}+{x - size}+{y - thickness // 2}")
                ch['canvas'].config(width=size * 2, height=thickness)
                ch['canvas'].delete('all')
                ch['canvas'].create_line(0, thickness // 2, size * 2, thickness // 2, 
                                        fill=ch['color'], width=thickness)
                
                ch = self.crosshair_windows[1]
                ch['window'].geometry(f"{thickness}x{size * 2}+{x - thickness // 2}+{y - size}")
                ch['canvas'].config(width=thickness, height=size * 2)
                ch['canvas'].delete('all')
                ch['canvas'].create_line(thickness // 2, 0, thickness // 2, size * 2, 
                                        fill=ch['color'], width=thickness)
            
            if self.crosshair_root:
                self.crosshair_root.after(10, self.update_crosshair)
        except:
            pass
    
    def load_templates_data(self):
        if TEMPLATES_DATA.exists():
            try:
                with open(TEMPLATES_DATA, 'r') as f:
                    content = f.read().strip()
                    if not content:
                        return []
                    return json.loads(content)
            except (json.JSONDecodeError, ValueError):
                print(f"Warning: {TEMPLATES_DATA} contains invalid JSON, starting fresh")
                return []
        return []

    def save_templates_data(self, data):
        with open(TEMPLATES_DATA, 'w') as f:
            json.dump(data, f, indent=2)
    
    def capture_region(self, name, x1, y1, x2, y2):
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        
        time.sleep(0.1)
        
        sct = mss()
        monitor = {
            "top": y1,
            "left": x1,
            "width": x2 - x1,
            "height": y2 - y1
        }
        screenshot = sct.grab(monitor)
        img = np.array(screenshot)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        template_filename = f"{name}.png"
        template_path = TEMPLATES_DIR / template_filename
        cv2.imwrite(str(template_path), img)
        
        screen_w, screen_h = pyautogui.size()
        region_relative = [
            x1 / screen_w,
            y1 / screen_h,
            x2 / screen_w,
            y2 / screen_h
        ]

        templates = self.load_templates_data()
        templates.append({
            "options": [
                {
                    "template": template_filename,
                    "region": region_relative,
                    "key_press": "enter"
                }
            ]
        })
        self.save_templates_data(templates)

        print(f"\n✓ Captured: {name}")
        print(f"  Size: {img.shape[1]}x{img.shape[0]} pixels")
        print(f"  Region: {region_relative}")
        print(f"  Total templates: {len(templates)}")
    
    def on_press(self, key):
        try:
            if key.char == 's':
                if not self.capturing:
                    print("\n\nStarting template capture - Click top-left corner...")
                    self.capturing = True
                    self.corner1 = None
                    self.show_position = False
            elif key.char == 'q':
                print("\n\nExiting...")
                self.running = False
                if self.crosshair_root:
                    try:
                        self.crosshair_root.quit()
                    except:
                        pass
                return False
        except AttributeError:
            pass
    
    def on_click(self, x, y, button, pressed):
        if self.show_position:
            print(f"\rMouse: ({x:4d}, {y:4d})    ", end='', flush=True)

        # Handle template capture clicks
        if self.capturing and pressed:
            if self.corner1 is None:
                self.corner1 = (x, y)
                print(f"\n  Top-left: ({x}, {y})")
                print("  Click bottom-right corner...")
            else:
                print(f"\n  Bottom-right: ({x}, {y})")

                name = f"{self.game_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                self.on_click_counter += 1
                if name:
                    self.capture_region(name, self.corner1[0], self.corner1[1], x, y)
                else:
                    print("  Cancelled (no name provided)")

                self.capturing = False
                self.show_position = True
                print("\nReady - Press 'S' for template, 'Q' to quit")
    
    def start(self):
        from pynput import mouse

        print("=" * 60)
        print("TEMPLATE CAPTURE TOOL - HOTKEY MODE")
        print("=" * 60)
        print("\nInstructions:")
        print("  - Press 'S' to capture a template region")
        print("  - Click top-left corner, then bottom-right corner")
        print("  - Press 'Q' to quit and save")
        print("\nReady - Press 'S' for template, 'Q' to quit")
        print("=" * 60 + "\n")
        
        kb_listener = keyboard.Listener(on_press=self.on_press) # type: ignore
        mouse_listener = mouse.Listener(on_click=self.on_click)
        
        kb_listener.start()
        mouse_listener.start()
        
        if self.crosshair_root:
            try:
                self.crosshair_root.mainloop()
            except:
                pass
        else:
            kb_listener.join()
        
        mouse_listener.stop()
        
        templates = self.load_templates_data()
        print(f"\n✓ Saved {len(templates)} template(s) to {TEMPLATES_DATA}")

def main():
    capturer = TemplateCapturer(game_name="f1_22")
    capturer.start()

if __name__ == "__main__":
    main()