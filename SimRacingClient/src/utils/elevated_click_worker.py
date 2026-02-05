"""
Elevated worker for executing click sequences on admin windows.

Spawned as an elevated subprocess by the main client when click automation
is needed on elevated windows (e.g. CAMMUS).  The caller writes a small JSON
config file, passes its path as the sole command-line argument, and waits for
the process to exit.

Usage:
    python elevated_click_worker.py <config_file_path>

Config file format:
    {
        "template_dir": "/absolute/path/to/template/directory",
        "click_steps": [
            {"template": "button.png", "double_click": false},
            ...
        ],
        "threshold": 0.85,
        "max_retries": 15,
        "retry_delay": 1.0,
        "click_delay": 0.5
    }

Exit codes:
    0 – all steps completed successfully
    1 – config error or a step failed
"""

import sys
from pathlib import Path

# Ensure src directory is in path when spawned as elevated subprocess.
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import time

from utils.click_navigator import click_template_if_found
from utils.monitoring import get_logger

logger = get_logger(__name__)


def main():
    if len(sys.argv) < 2:
        logger.error("Usage: elevated_click_worker.py <config_file_path>")
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load click config from {config_path}: {e}")
        sys.exit(1)

    template_dir = config.get("template_dir")
    click_steps = config.get("click_steps", [])
    threshold = config.get("threshold", 0.85)
    max_retries = config.get("max_retries", 15)
    retry_delay = config.get("retry_delay", 1.0)
    click_delay = config.get("click_delay", 0.5)

    if not template_dir or not click_steps:
        logger.error("Config must contain 'template_dir' and non-empty 'click_steps'")
        sys.exit(1)

    logger.info(f"Elevated click worker starting ({len(click_steps)} steps)")

    for i, step in enumerate(click_steps, 1):
        template_file = step.get("template")
        double_click = step.get("double_click", False)

        if not template_file:
            logger.error(f"Step {i} missing 'template' field")
            sys.exit(1)

        template_path = str(Path(template_dir) / template_file)
        logger.info(f"Step {i}/{len(click_steps)}: Looking for {template_file}...")

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
            logger.error(f"Step {i} failed: Could not find {template_file} after {max_retries} attempts")
            sys.exit(1)

    logger.info(f"All {len(click_steps)} click steps completed successfully")
    sys.exit(0)


if __name__ == "__main__":
    main()
