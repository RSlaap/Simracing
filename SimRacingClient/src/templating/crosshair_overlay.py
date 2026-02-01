import tkinter as tk
import pyautogui

class CrosshairOverlay:
    def __init__(self, size=20, color='red', thickness=1):
        self.size = size
        self.color = color
        self.thickness = thickness
        self.running = True
        
        self.root = tk.Tk()
        self.root.withdraw()
        
        self.windows = []
        self.create_crosshair()
        
    def create_crosshair(self):
        for _ in range(4):
            window = tk.Toplevel(self.root)
            window.overrideredirect(True)
            window.attributes('-topmost', True)
            window.attributes('-transparentcolor', 'white')
            window.config(bg='white')
            
            canvas = tk.Canvas(window, bg='white', highlightthickness=0, 
                             width=self.size * 2, height=self.thickness)
            canvas.pack()
            
            self.windows.append({'window': window, 'canvas': canvas})
        
        self.update_position()
    
    def update_position(self):
        if not self.running:
            return
        
        try:
            x, y = pyautogui.position()
            
            self.windows[0]['window'].geometry(f"{self.size * 2}x{self.thickness}+{x - self.size}+{y - self.thickness // 2}")
            self.windows[0]['canvas'].delete('all')
            self.windows[0]['canvas'].create_line(0, self.thickness // 2, self.size * 2, self.thickness // 2, 
                                                  fill=self.color, width=self.thickness)
            
            self.windows[1]['window'].geometry(f"{self.thickness}x{self.size * 2}+{x - self.thickness // 2}+{y - self.size}")
            self.windows[1]['canvas'].config(width=self.thickness, height=self.size * 2)
            self.windows[1]['canvas'].delete('all')
            self.windows[1]['canvas'].create_line(self.thickness // 2, 0, self.thickness // 2, self.size * 2, 
                                                  fill=self.color, width=self.thickness)
            
            self.root.after(10, self.update_position)
        except Exception:
            pass
    
    def stop(self):
        self.running = False
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass

if __name__ == "__main__":
    print("Crosshair Overlay Running")
    print("Press Ctrl+C to exit")
    
    overlay = CrosshairOverlay(size=5, color='lime', thickness=3)
    
    try:
        overlay.root.mainloop()
    except KeyboardInterrupt:
        print("\nExiting...")
        overlay.stop()