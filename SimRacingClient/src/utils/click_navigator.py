"""
Click-based navigation for pre-launch configuration (e.g., CAMMUS software).

This module provides template matching with mouse clicks instead of keyboard presses.
Unlike screen_navigator.py which checks fixed regions and presses keys, this module:
- Searches the entire screen for templates
- Clicks on them when found
- Useful for configuring external software before game launch
"""

import json
import time

import cv2
import numpy as np
import pyautogui
from typing import List, Optional, Tuple
from pathlib import Path

from utils.monitoring import get_logger

logger = get_logger(__name__)


def find_template_on_screen(
    template_path: str,
    threshold: float = 0.8,
    method: int = cv2.TM_CCOEFF_NORMED
) -> Optional[Tuple[int, int, float]]:
    """
    Search the entire screen for a template and return its location.

    Args:
        template_path: Path to the template image file
        threshold: Minimum match confidence (0.0-1.0)
        method: OpenCV template matching method (default: cv2.TM_CCOEFF_NORMED)

    Returns:
        Tuple of (center_x, center_y, confidence) in absolute pixels if found, None otherwise

    Example:
        result = find_template_on_screen("button.png", threshold=0.85)
        if result:
            x, y, confidence = result
            pyautogui.click(x, y)
    """
    # Load template image
    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if template is None:
        raise ValueError(f"Could not load template image from {template_path}")

    template_height, template_width = template.shape[:2]

    # Capture full screen
    screenshot = pyautogui.screenshot()
    screenshot_np = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    # Perform template matching
    result = cv2.matchTemplate(screenshot_np, template, method)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    # Check if match meets threshold
    if max_val >= threshold:
        # Calculate center of matched region
        match_x, match_y = max_loc
        center_x = match_x + template_width // 2
        center_y = match_y + template_height // 2

        logger.info(f"Found template {Path(template_path).name} at ({center_x}, {center_y}) with confidence {max_val:.3f}")
        return (center_x, center_y, max_val)

    logger.debug(f"Template {Path(template_path).name} not found (best match: {max_val:.3f} < threshold: {threshold})")
    return None


def click_template_if_found(
    template_path: str,
    threshold: float = 0.8,
    click_delay: float = 0.5,
    double_click: bool = False
) -> bool:
    """
    Find a template on screen and click it if found.

    Args:
        template_path: Path to the template image file
        threshold: Minimum match confidence (0.0-1.0)
        click_delay: Delay after clicking in seconds
        double_click: Whether to double-click instead of single-click

    Returns:
        True if template was found and clicked, False otherwise
    """
    result = find_template_on_screen(template_path, threshold)

    if result:
        x, y, confidence = result
        if double_click:
            pyautogui.doubleClick(x, y)
            logger.info(f"Double-clicked at ({x}, {y})")
        else:
            pyautogui.click(x, y)
            logger.info(f"Clicked at ({x}, {y})")

        time.sleep(click_delay)
        return True

    return False


def execute_click_sequence(
    template_dir: str,
    template_files: List[str],
    threshold: float = 0.85,
    max_retries: int = 10,
    retry_delay: float = 1.0,
    click_delay: float = 0.5,
    double_click: bool = False
) -> bool:
    """
    Execute a sequence of template-based clicks.

    Args:
        template_dir: Base directory containing template images
        template_files: List of template filenames to click in sequence
        threshold: Template matching confidence threshold
        max_retries: Maximum retry attempts per template
        retry_delay: Delay between retry attempts in seconds
        click_delay: Delay after each successful click in seconds
        double_click: Whether to double-click instead of single-click

    Returns:
        True if all templates were found and clicked successfully, False otherwise

    Example:
        success = execute_click_sequence(
            template_dir="templates/CAMMUS",
            template_files=["settings_button.png", "wheel_tab.png", "apply_button.png"],
            threshold=0.85,
            max_retries=10
        )
    """
    template_dir_path = Path(template_dir)

    for i, template_file in enumerate(template_files, 1):
        template_path = str(template_dir_path / template_file)
        logger.info(f"Step {i}/{len(template_files)}: Looking for {template_file}...")

        # Retry loop for this template
        clicked = False
        for attempt in range(max_retries):
            if click_template_if_found(template_path, threshold, click_delay, double_click):
                logger.info(f"✓ Step {i}/{len(template_files)} completed")
                clicked = True
                break

            if attempt < max_retries - 1:
                logger.debug(f"Attempt {attempt + 1}/{max_retries} failed, retrying in {retry_delay}s...")
                time.sleep(retry_delay)

        if not clicked:
            logger.error(f"✗ Step {i}/{len(template_files)} failed: Could not find {template_file} after {max_retries} attempts")
            return False

    logger.info(f"✓ All {len(template_files)} steps completed successfully")
    return True


def execute_click_navigation_from_json(
    json_path: str,
    template_base_dir: str,
    threshold: float = 0.85,
    max_retries: int = 10,
    retry_delay: float = 1.0,
    click_delay: float = 0.5
) -> bool:
    """
    Execute click-based navigation from a JSON configuration file.

    JSON format:
    [
        {"template": "button1.png", "double_click": false},
        {"template": "button2.png", "double_click": true},
        {"template": "button3.png"}
    ]

    Args:
        json_path: Path to JSON file containing click sequence
        template_base_dir: Base directory for resolving template paths
        threshold: Template matching confidence threshold
        max_retries: Maximum retry attempts per template
        retry_delay: Delay between retry attempts in seconds
        click_delay: Delay after each successful click in seconds

    Returns:
        True if all steps completed successfully, False otherwise
    """
    json_file = Path(json_path)
    if not json_file.exists():
        logger.error(f"Navigation file not found: {json_path}")
        return False

    with open(json_file, 'r') as f:
        steps = json.load(f)

    logger.info(f"Loaded {len(steps)} click steps from {json_file.name}")

    for i, step in enumerate(steps, 1):
        template_file = step.get("template")
        double_click = step.get("double_click", False)

        if not template_file:
            logger.error(f"Step {i} missing 'template' field")
            return False

        template_path = str(Path(template_base_dir) / template_file)
        logger.info(f"Step {i}/{len(steps)}: Looking for {template_file}...")

        # Retry loop for this step
        clicked = False
        for attempt in range(max_retries):
            if click_template_if_found(template_path, threshold, click_delay, double_click):
                logger.info(f"✓ Step {i}/{len(steps)} completed")
                clicked = True
                break

            if attempt < max_retries - 1:
                logger.debug(f"Attempt {attempt + 1}/{max_retries} failed, retrying in {retry_delay}s...")
                time.sleep(retry_delay)

        if not clicked:
            logger.error(f"✗ Step {i}/{len(steps)} failed: Could not find {template_file} after {max_retries} attempts")
            return False

    logger.info(f"✓ All {len(steps)} click steps completed successfully")
    return True


if __name__ == "__main__":
    # Example usage
    print("Click Navigator Test")
    print("This script searches the entire screen for templates and clicks them")
    print()

    # Example 1: Simple sequence
    success = execute_click_sequence(
        template_dir="C:/path/to/templates/CAMMUS",
        template_files=["settings_button.png", "wheel_tab.png", "apply_button.png"],
        threshold=0.85,
        max_retries=5,
        retry_delay=1.0,
        click_delay=0.5
    )

    if success:
        print("Configuration completed successfully!")
    else:
        print("Configuration failed!")
