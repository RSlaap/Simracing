"""
Cammus wheel software configuration helper.

Provides functions to load configuration and execute the Cammus
software setup sequence using template-based click automation.
"""

import json
import time
from pathlib import Path
from typing import Optional

from utils.process import is_process_running, launch_process_elevated, is_running_elevated
from utils.focus_window import _wait_and_focus_window
from utils.click_navigator import click_template_if_found
from utils.monitoring import get_logger

logger = get_logger(__name__)


def load_cammus_config() -> Optional[dict]:
    """Load Cammus configuration from cammus_config.json.

    Returns:
        Configuration dictionary if successful, None otherwise.
    """
    config_path = Path(__file__).parent.parent.parent / "cammus_config.json"
    if not config_path.exists():
        logger.error(f"Cammus config not found: {config_path}")
        return None

    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in cammus_config.json: {e}")
        return None


def execute_cammus_configuration() -> tuple[bool, str]:
    """
    Execute Cammus software configuration.

    Launches the Cammus software (if not running), focuses its window,
    and executes a click sequence based on template matching.

    Note: This function works best when the script is running with administrator
    privileges. If CAMMUS requires elevation, the script must also be elevated
    to send mouse clicks to it (due to Windows UIPI restrictions).

    Returns:
        Tuple of (success, message)
    """
    # Check if running elevated - warn if not
    if not is_running_elevated():
        logger.warning(
            "Script is NOT running with administrator privileges. "
            "Mouse clicks may not work on elevated windows (CAMMUS). "
            "Consider running the launcher as Administrator."
        )

    config = load_cammus_config()
    if not config:
        return False, "Failed to load cammus_config.json"

    if not config.get('enabled', False):
        return False, "Cammus configuration is disabled"

    project_root = Path(__file__).parent.parent.parent
    template_base = project_root / "templates"
    template_dir = template_base / config.get('template_dir', 'CAMMUS')

    # Load click steps
    click_steps_file = config.get('click_steps_file', 'click_steps.json')
    click_steps_path = template_dir / click_steps_file

    if not click_steps_path.exists():
        return False, f"Click steps file not found: {click_steps_path}"

    try:
        with open(click_steps_path, 'r') as f:
            click_steps = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON in click_steps.json: {e}"

    if not click_steps:
        return False, "No click steps configured"

    logger.info(f"Starting Cammus configuration ({len(click_steps)} steps)")

    # Launch software if needed
    executable_path = config.get('executable_path')
    process_name = config.get('process_name')
    window_title = config.get('window_title')
    startup_delay = config.get('startup_delay', 5.0)

    if executable_path and process_name:
        if not is_process_running(process_name):
            logger.info(f"Launching Cammus software with elevation: {executable_path}")
            try:
                success = launch_process_elevated(Path(executable_path))
                if not success:
                    return False, "Failed to launch Cammus software (user may have denied UAC prompt)"
                # Wait for software to load past splash screen
                logger.info(f"Waiting {startup_delay}s for software to load...")
                time.sleep(startup_delay)
            except Exception as e:
                return False, f"Failed to launch Cammus software: {e}"
        else:
            logger.info(f"Cammus software already running: {process_name}")

        # Focus window if specified
        if window_title:
            if not _wait_and_focus_window(window_title, max_attempts=10):
                logger.warning(f"Could not focus window: {window_title}")
    else:
        logger.warning("No executable_path or process_name configured - assuming software is already open")

    # Execute click sequence
    threshold = config.get('template_threshold', 0.85)
    max_retries = config.get('max_retries', 15)
    retry_delay = config.get('retry_delay', 1.0)
    click_delay = config.get('click_delay', 0.5)

    for i, step in enumerate(click_steps, 1):
        template_file = step.get('template')
        double_click = step.get('double_click', False)

        if not template_file:
            logger.error(f"Step {i} missing 'template' field")
            return False, f"Step {i} missing template field"

        template_path = str(template_dir / template_file)
        logger.info(f"Step {i}/{len(click_steps)}: Looking for {template_file}...")

        # Retry loop
        clicked = False
        for attempt in range(max_retries):
            if click_template_if_found(template_path, threshold, click_delay, double_click):
                click_type = "double-clicked" if double_click else "clicked"
                logger.info(f"Step {i}/{len(click_steps)}: {click_type} {template_file}")
                clicked = True
                break

            if attempt < max_retries - 1:
                logger.debug(f"Attempt {attempt + 1}/{max_retries} failed, retrying...")
                time.sleep(retry_delay)

        if not clicked:
            return False, f"Step {i} failed: Could not find {template_file} after {max_retries} attempts"

    logger.info(f"Cammus configuration completed successfully ({len(click_steps)} steps)")
    return True, f"Cammus configuration completed ({len(click_steps)} steps)"
