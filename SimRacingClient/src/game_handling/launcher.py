"""
Generic game launcher that orchestrates process launch, window focus, and navigation.

This module provides the launch() function that:
1. Executes pre-launch configuration (if configured)
2. Launches the game executable as a subprocess
3. Waits for and focuses the game window
4. Executes role-based template navigation
"""
# Add src directory to path for direct script execution
import sys
from pathlib import Path
src_dir = Path(__file__).parent.parent
print(src_dir)
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from typing import get_args, Dict, Optional
import threading
from utils.focus_window import _wait_and_focus_window
from utils.monitoring import get_logger
from utils.data_model import Role, PreLaunchConfig
from game_handling.registry import GAME_REGISTRY

logger = get_logger(__name__)


def execute_pre_launch_config(config: PreLaunchConfig, template_base_dir: str) -> bool:
    """
    Execute pre-launch configuration (e.g., CAMMUS software setup).

    Args:
        config: PreLaunchConfig containing executable path, click steps, etc.
        template_base_dir: Base directory for resolving template paths

    Returns:
        True if pre-launch config completed successfully, False otherwise
    """
    from utils.process import launch_process, is_process_running
    from utils.click_navigator import execute_click_sequence
    import time

    # logger.info("Starting pre-launch configuration")

    # Check if software needs to be launched
    if config.executable_path and config.process_name:
        if not is_process_running(config.process_name):
            logger.info(f"Launching {config.executable_path}")
            launch_process(Path(config.executable_path))
            # Give software time to start
            time.sleep(3)

            # Wait for window to appear and focus it
            if config.window_title:
                if not _wait_and_focus_window(config.window_title, max_attempts=10):
                    logger.warning(f"Could not focus {config.window_title} window, continuing anyway...")
        else:
            logger.info(f"{config.process_name} is already running")
            # Focus the window if specified
            if config.window_title:
                _wait_and_focus_window(config.window_title, max_attempts=5)

    # Execute click sequence if steps are configured
    if config.click_steps:
        logger.info(f"Executing {len(config.click_steps)} click steps")
        template_dir = Path(template_base_dir) / config.template_dir

        # Convert ClickStep models to simple template list
        for i, step in enumerate(config.click_steps, 1):
            template_path = str(template_dir / step.template)
            logger.info(f"Click step {i}/{len(config.click_steps)}: Looking for {step.template}...")

            # Import click function
            from utils.click_navigator import click_template_if_found

            # Retry loop for this step
            clicked = False
            for attempt in range(config.max_retries):
                if click_template_if_found(
                    template_path,
                    threshold=config.template_threshold,
                    click_delay=config.click_delay,
                    double_click=step.double_click
                ):
                    logger.info(f"✓ Click step {i}/{len(config.click_steps)} completed")
                    clicked = True
                    break

                if attempt < config.max_retries - 1:
                    logger.debug(f"Attempt {attempt + 1}/{config.max_retries} failed, retrying...")
                    time.sleep(config.retry_delay)

            if not clicked:
                logger.error(f"✗ Click step {i}/{len(config.click_steps)} failed after {config.max_retries} attempts")
                return False

        logger.info(f"✓ Pre-launch configuration completed successfully")
        return True

    logger.info("No click steps configured, skipping")
    return True


def launch(game_id: str, role: Role, cancel_event: Optional[threading.Event] = None,
           player_count: Optional[int] = None, host_ip: Optional[str] = None) -> bool:
    """
    Launch a game and execute role-based navigation.

    Args:
        game_id: Game identifier (e.g., 'f1_22', 'acc')
        role: Either 'host' or 'join'
        cancel_event: Optional threading.Event to signal cancellation
        player_count: Optional player count for resolving dynamic navigation paths

    Returns:
        bool: True if launch and navigation successful, False otherwise

    Raises:
        ValueError: If game_id is unknown or role is invalid
    """
    # Import here to avoid circular imports
    from utils.process import launch_process
    from utils.screen_navigator import load_and_execute_navigation

    # Validate role
    valid_roles = get_args(Role)
    if role not in valid_roles:
        raise ValueError(f"Invalid role: '{role}'. Must be one of {valid_roles}")

    # Get game configuration
    config = GAME_REGISTRY.get(game_id)
    logger.info(f"Launching {config.name} as role: '{role}'")

    # Determine template base directory (from project root)
    project_root = Path(__file__).parent.parent.parent
    template_base_dir = project_root / "templates"

    # Execute pre-launch configuration if enabled
    if config.pre_launch_config and config.pre_launch_config.enabled:
        logger.info(f"Pre-launch configuration is enabled for {config.name}")
        if not execute_pre_launch_config(config.pre_launch_config, str(template_base_dir)):
            logger.error("Pre-launch configuration failed, aborting game launch")
            return False
        logger.info("Pre-launch configuration completed, proceeding with game launch")
    else:
        logger.info("No pre-launch configuration needed")

    # Launch the executable
    process = launch_process(config.executable_path)
    logger.info(f"Process started (PID: {process.pid})")

    # Wait for window to appear and focus it
    if not _wait_and_focus_window(config.window_title, max_attempts=10):
        logger.warning(f"Could not focus {config.name} window, continuing anyway...")

    logger.info(f"Loading navigation configs for role: '{role}' (player_count={player_count})")
    nav_configs = config.get_navigation_configs(role, player_count=player_count)
    logger.info(f"  Found {len(nav_configs)} navigation config(s)")

    # Execute all navigation configs in sequence
    # If any config fails, abort the entire launch
    logger.info(f"Executing {len(nav_configs)} navigation config(s) for role '{role}'")

    for config_index, nav_config in enumerate(nav_configs, 1):
        # Check for cancellation before starting each config
        if cancel_event and cancel_event.is_set():
            logger.info(f"Navigation cancelled before config {config_index}")
            return False

        logger.info(f"Executing config {config_index}/{len(nav_configs)}")
        logger.info(f"  Template dir: {nav_config.template_dir}")
        logger.info(f"  Threshold: {nav_config.template_threshold}, Max retries: {nav_config.max_retries}")
        logger.info(f"  Steps: {len(nav_config.navigation_sequence.steps)}")
        logger.info(f"  Host ip: {host_ip}")

        success = load_and_execute_navigation(
            nav_config=nav_config,
            template_base_dir=str(template_base_dir),
            cancel_event=cancel_event,
            context={"host_ip": host_ip} if host_ip else None
        )

        if not success:
            # Check if failure was due to cancellation
            if cancel_event and cancel_event.is_set():
                logger.info(f"Navigation cancelled during config {config_index}")
            else:
                logger.error(f"[FAILED] Config {config_index}/{len(nav_configs)} failed")
            return False

        logger.info(f"[OK] Config {config_index}/{len(nav_configs)} completed")

    # All configs completed successfully
    
    logger.info(f"[SUCCESS] Launched {config.name} as role '{role}' (all {len(nav_configs)} config(s) completed)")
    return True



if __name__ == "__main__":
    launch("f1_22", "singleplayer")
