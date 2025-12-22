import cv2
import numpy as np
import pyautogui
from typing import Callable, List, Dict, Any
import json
import time

import ctypes
import time
import ctypes
import time
from typing import List, Dict, Any
import ctypes
import time
from typing import List, Dict, Any

import pydirectinput

def skip_intro_until_screen(
    template_path: str,
    template_dir: str,
    relative_x: float,
    relative_y: float,
    threshold: float = 0.8,
    max_attempts: int = 30,
    retry_delay: float = 0.5
) -> bool:
    print(f"Skipping intro video - pressing escape until screen appears...")
    
    def do_nothing():
        pass
    
    for attempt in range(max_attempts):
        matched = navigate_if_template_matches(
            template_path=f"{template_dir}/{template_path}",
            relative_x=relative_x,
            relative_y=relative_y,
            action=do_nothing,
            threshold=threshold
        )
        
        if matched:
            print(f"✓ Screen detected after {attempt + 1} attempts")
            return True
        
        print(f"Attempt {attempt + 1}: Pressing escape...")
        pydirectinput.press('escape')
        
        time.sleep(retry_delay)
    
    print(f"✗ Failed to detect screen after {max_attempts} attempts")
    return False

def execute_navigation_sequence(
    steps: List[Dict[str, Any]],
    template_dir: str,
    threshold: float = 0.8,
    max_retries: int = 10,
    retry_delay: float = 0.5,
    previous_step_retries: int = 3
) -> bool:
    consecutive_failures = 0
    
    for i, step_data in enumerate(steps):
        template_path = step_data['template']
        region = step_data['region']
        key_press = step_data['key_press']
        
        center_x = (region[0] + region[2]) / 2
        center_y = (region[1] + region[3]) / 2
        
        matched = attempt_step(i, step_data, template_dir, center_x, center_y, 
                              threshold, max_retries, retry_delay)
        
        if not matched:
            print(f"✗ Step {i+1} failed after {max_retries} attempts")
            
            if i > 0:
                print(f"↻ Retrying previous step {i}...")
                prev_step = steps[i-1]
                prev_center_x = (prev_step['region'][0] + prev_step['region'][2]) / 2
                prev_center_y = (prev_step['region'][1] + prev_step['region'][3]) / 2
                
                prev_matched = attempt_step(i-1, prev_step, template_dir, 
                                           prev_center_x, prev_center_y,
                                           threshold, previous_step_retries, retry_delay)
                
                if prev_matched:
                    print(f"✓ Previous step {i} succeeded, retrying step {i+1}...")
                    matched = attempt_step(i, step_data, template_dir, center_x, center_y,
                                         threshold, max_retries, retry_delay)
            
            if not matched:
                consecutive_failures += 1
                print(f"⚠ Step {i+1} still failed, continuing to next step (consecutive failures: {consecutive_failures})")
                
                if consecutive_failures >= 2:
                    print(f"✗ Two consecutive failures detected. Stopping execution.")
                    return False
            else:
                consecutive_failures = 0
                print(f"✓ Step {i+1} succeeded after retry")
        else:
            consecutive_failures = 0
            print(f"✓ Step {i+1} matched - pressed '{key_press}'")
    
    return True


def attempt_step(
    step_index: int,
    step_data: Dict[str, Any],
    template_dir: str,
    center_x: float,
    center_y: float,
    threshold: float,
    max_retries: int,
    retry_delay: float
) -> bool:
    template_path = step_data['template']
    key_press = step_data['key_press']
    
    for attempt in range(max_retries):
        def press_key():
            key_mapping = {
                'space': 'space',
                'enter': 'enter',
                'down_arrow': 'down',
                'up_arrow': 'up',
                'left_arrow': 'left',
                'right_arrow': 'right',
                'escape': 'escape',
                'esc': 'escape'
            }
            key = key_mapping.get(key_press, key_press)
            pydirectinput.press(key)
        
        matched = navigate_if_template_matches(
            template_path=f"{template_dir}/{template_path}",
            relative_x=center_x,
            relative_y=center_y,
            action=press_key,
            threshold=threshold
        )
        
        if matched:
            time.sleep(retry_delay)
            return True
        
        time.sleep(retry_delay)
    
    return False

def navigate_if_template_matches(
    template_path: str,
    relative_x: float,
    relative_y: float,
    action: Callable[[], None],
    threshold: float = 0.8
) -> bool:
    screen_width, screen_height = pyautogui.size()
    
    absolute_x = int(relative_x * screen_width)
    absolute_y = int(relative_y * screen_height)
    
    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if template is None:
        raise ValueError(f"Could not load template image from {template_path}")
    
    template_height, template_width = template.shape[:2]
    
    capture_x = max(0, absolute_x - template_width // 2)
    capture_y = max(0, absolute_y - template_height // 2)
    capture_width = min(template_width, screen_width - capture_x)
    capture_height = min(template_height, screen_height - capture_y)
    
    screenshot = pyautogui.screenshot(region=(capture_x, capture_y, capture_width, capture_height))
    screenshot_np = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    
    if screenshot_np.shape[0] < template_height or screenshot_np.shape[1] < template_width:
        return False
    
    result = cv2.matchTemplate(screenshot_np, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    
    if max_val >= threshold:
        print(f"Matched {template_path} with accuracy {max_val}")
        action()
        return True
    print(f"Failed to match {template_path}, accuracy = {max_val}")
    return False

def load_and_execute_navigation(
    json_path: str,
    template_dir: str,
    threshold: float = 0.8,
    max_retries: int = 10,
    retry_delay: float = 0.5,
    skip_intro_max_attempts: int = 30,
) -> bool:
    with open(f"{template_dir}/{json_path}", 'r') as f:
        steps = json.load(f)
    
    if not steps:
        print("No navigation steps found")
        return False
    
    first_step = steps[0]
    region = first_step['region']
    center_x = (region[0] + region[2]) / 2
    center_y = (region[1] + region[3]) / 2
    
    if not skip_intro_until_screen(
        template_path=first_step['template'],
        template_dir=template_dir,
        relative_x=center_x,
        relative_y=center_y,
        threshold=threshold,
        max_attempts=skip_intro_max_attempts,
        retry_delay=retry_delay
    ):
        return False
    
    return execute_navigation_sequence(
        steps=steps,
        threshold=threshold,
        max_retries=max_retries,
        retry_delay=retry_delay,
        template_dir=template_dir
    )