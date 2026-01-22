import cv2
import numpy as np
import pyautogui
from typing import Callable, List, Union, Tuple, Optional
import time
import threading
import pydirectinput
import json
from pathlib import Path
from utils.monitoring import get_logger
from utils.data_model import NavigationConfig, Step, StepOption

logger = get_logger(__name__)

# ============================================================================
# Helper Functions
# ============================================================================

def get_cv2_matching_method(method_name: str) -> int:
    """
    Convert method name string to OpenCV constant.

    Args:
        method_name: String name of the matching method (e.g., "TM_CCOEFF_NORMED")

    Returns:
        int: OpenCV template matching method constant

    Raises:
        ValueError: If method name is not recognized
    """
    method_map = {
        "TM_CCOEFF_NORMED": cv2.TM_CCOEFF_NORMED,
        "TM_CCORR_NORMED": cv2.TM_CCORR_NORMED,
        "TM_SQDIFF_NORMED": cv2.TM_SQDIFF_NORMED,
        "TM_CCOEFF": cv2.TM_CCOEFF,
        "TM_CCORR": cv2.TM_CCORR,
        "TM_SQDIFF": cv2.TM_SQDIFF
    }

    if method_name not in method_map:
        valid_methods = list(method_map.keys())
        raise ValueError(f"Invalid matching method '{method_name}'. Valid methods: {valid_methods}")

    return method_map[method_name]


def calculate_region_center(region: List[float]) -> Tuple[float, float]:
    """Calculate center point of a region defined as [x1, y1, x2, y2]."""
    return (region[0] + region[2]) / 2, (region[1] + region[3]) / 2


def format_key_display(key_press: Union[str, List[str], None]) -> str:
    """Format key press(es) for display in logs."""
    if key_press is None:
        return "(wait/no action)"
    if isinstance(key_press, list):
        return f"[{', '.join(key_press)}]"
    return f"'{key_press}'"




# ============================================================================
# Core Functions
# ============================================================================

def match_template_at_position(
    template_path: str,
    relative_x: float,
    relative_y: float,
    search_margin: float = 0.05,
    method: int = cv2.TM_CCOEFF_NORMED
) -> float:
    """
    Performs template matching at a specified screen position with configurable search margin.

    Args:
        template_path: Path to the template image file
        relative_x: Relative X coordinate (0.0-1.0) of region center
        relative_y: Relative Y coordinate (0.0-1.0) of region center
        search_margin: Percentage of screen size to add as search margin (0.0-1.0)
                      e.g., 0.05 = 5% of screen size (~96 pixels on 1920x1080)
        method: OpenCV template matching method (default: cv2.TM_CCOEFF_NORMED)

    Returns:
        float: Maximum correlation value (match confidence score)
               - For TM_CCOEFF_NORMED and TM_CCORR_NORMED: 0.0 to 1.0 (higher = better)
               - For TM_SQDIFF_NORMED: 0.0 to 1.0 (lower = better)

    Raises:
        ValueError: If template image cannot be loaded
    """
    screen_width, screen_height = pyautogui.size()

    # Convert relative coordinates to absolute pixel positions
    absolute_x = int(relative_x * screen_width)
    absolute_y = int(relative_y * screen_height)

    # Load template image
    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if template is None:
        raise ValueError(f"Could not load template image from {template_path}")

    template_height, template_width = template.shape[:2]

    # Calculate search margin in pixels
    margin_x = int(screen_width * search_margin)
    margin_y = int(screen_height * search_margin)

    # Calculate capture region with search margin
    capture_x = max(0, absolute_x - template_width // 2 - margin_x)
    capture_y = max(0, absolute_y - template_height // 2 - margin_y)
    capture_width = min(template_width + 2 * margin_x, screen_width - capture_x)
    capture_height = min(template_height + 2 * margin_y, screen_height - capture_y)

    # Capture screenshot of the region
    screenshot = pyautogui.screenshot(region=(capture_x, capture_y, capture_width, capture_height))
    screenshot_np = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    # Ensure screenshot is large enough for template matching
    if screenshot_np.shape[0] < template_height or screenshot_np.shape[1] < template_width:
        logger.warning(f"Screenshot region too small for template {template_path}")
        return 0.0

    # Perform template matching
    result = cv2.matchTemplate(screenshot_np, template, method)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    return max_val


def execute_key_presses(
    key_press: Union[str, List[str], None],
    action_delay: float = 0.2
) -> None:
    """
    Executes one or more key presses in sequence.

    Args:
        key_press: Either a single key string, a list of key strings to press in sequence, or None for wait/polling steps
        action_delay: Delay in seconds between sequential key presses
    """
    # Handle wait/polling steps (no key press)
    if key_press is None:
        return

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

    # Handle single key press (backward compatible)
    if isinstance(key_press, str):
        key = key_mapping.get(key_press, key_press)
        pydirectinput.press(key)
        # logger.info(f'Pressed single key {key_press}')
    # Handle multiple sequential key presses
    elif isinstance(key_press, list):
        time.sleep(action_delay)
        for i, press in enumerate(key_press):
            key = key_mapping.get(press, press)
            print(key, type(key))
            logger.info(f'Pressed {key}')
            pydirectinput.press(key)
            # Add delay between presses (but not after the last one)
            if i < len(key_press) - 1:
                time.sleep(action_delay)
    else:
        raise ValueError(f"key_press must be string, list, or None, got {type(key_press)}")


def execute_navigation_sequence(
    steps: List[Step],
    template_dir: str,
    threshold: float = 0.8,
    max_retries: int = 10,
    retry_delay: float = 0.5,
    previous_step_retries: int = 3,
    action_delay: float = 0.2,
    search_margin: float = 0.05,
    method: int = cv2.TM_CCOEFF_NORMED,
    cancel_event: Optional[threading.Event] = None
) -> bool:
    """
    Execute a sequence of navigation steps with retry and fallback logic.

    Args:
        steps: List of Step Pydantic model instances
        template_dir: Base directory for template images
        threshold: Template matching confidence threshold
        max_retries: Max retry attempts per step
        retry_delay: Delay between retry attempts
        previous_step_retries: Max retries for previous step fallback
        action_delay: Delay between sequential key presses
        search_margin: Percentage of screen size to add as search margin (default 0.05 = 5%)
        method: OpenCV template matching method (default: cv2.TM_CCOEFF_NORMED)
        cancel_event: Optional threading.Event to signal cancellation

    Returns:
        bool: True if all steps completed successfully, False otherwise
    """
    consecutive_failures = 0

    for i, step in enumerate(steps):
        # Check for cancellation before each step
        if cancel_event and cancel_event.is_set():
            logger.info(f"Navigation cancelled at step {i+1}")
            return False
        # Log if this is a multi-option step
        if len(step.options) > 1:
            logger.info(f"Step {i+1}: Trying {len(step.options)} possible matches...")

        # Attempt the step
        matched = attempt_step_options(
            i, step, template_dir,
            threshold, max_retries, retry_delay, action_delay,
            search_margin, method, cancel_event
        )

        if not matched:
            # Check if failure was due to cancellation
            if cancel_event and cancel_event.is_set():
                logger.info(f"Navigation cancelled during step {i+1}")
                return False

            logger.warning(f"✗ Step {i+1} failed after {max_retries} attempts")

            # Try to recover by retrying previous step
            success, consecutive_failures = handle_step_failure(
                i, step, steps, consecutive_failures,
                template_dir, threshold, max_retries,
                previous_step_retries, retry_delay, action_delay,
                search_margin, method, cancel_event
            )

            if not success:
                logger.warning(f"⚠ Step {i+1} still failed, continuing to next step (consecutive failures: {consecutive_failures})")

                if consecutive_failures >= 2:
                    logger.error(f"✗ Two consecutive failures detected. Stopping execution.")
                    return False
        else:
            consecutive_failures = 0
        # Note: action_delay is now applied inside attempt_step_options() after success

    return True


def handle_step_failure(
    step_index: int,
    step: Step,
    steps: List[Step],
    consecutive_failures: int,
    template_dir: str,
    threshold: float,
    max_retries: int,
    previous_step_retries: int,
    retry_delay: float,
    action_delay: float,
    search_margin: float = 0.05,
    method: int = cv2.TM_CCOEFF_NORMED,
    cancel_event: Optional[threading.Event] = None
) -> Tuple[bool, int]:
    """
    Attempts to recover from step failure by retrying previous step.

    Args:
        step_index: Index of the current (failed) step
        step: The Step model instance that failed
        steps: List of all Step model instances
        consecutive_failures: Current count of consecutive failures
        template_dir: Base directory for template images
        threshold: Template matching confidence threshold
        max_retries: Max retry attempts per step
        previous_step_retries: Max retries for previous step fallback
        retry_delay: Delay between retry attempts
        action_delay: Delay between sequential key presses
        search_margin: Percentage of screen size to add as search margin
        method: OpenCV template matching method
        cancel_event: Optional threading.Event to signal cancellation

    Returns:
        Tuple of (success, consecutive_failures):
        - (True, 0) if recovered successfully
        - (False, failures+1) if recovery failed
    """
    # Can't retry if we're on the first step
    if step_index == 0:
        return False, consecutive_failures + 1

    logger.info(f"↻ Retrying previous step {step_index}...")
    prev_step = steps[step_index - 1]

    # Retry previous step
    prev_matched = attempt_step_options(
        step_index - 1,
        prev_step,
        template_dir,
        threshold,
        previous_step_retries,
        retry_delay,
        action_delay,
        search_margin,
        method,
        cancel_event
    )

    if not prev_matched:
        return False, consecutive_failures + 1

    # Previous step succeeded, retry current step
    logger.info(f"✓ Previous step {step_index} succeeded, retrying step {step_index+1}...")
    matched = attempt_step_options(
        step_index,
        step,
        template_dir,
        threshold,
        max_retries,
        retry_delay,
        action_delay,
        search_margin,
        method,
        cancel_event
    )

    if matched:
        logger.info(f"✓ Step {step_index+1} succeeded after retry")
        return True, 0
    else:
        return False, consecutive_failures + 1


def attempt_step_options(
    step_index: int,
    step: Step,
    template_dir: str,
    threshold: float,
    max_retries: int,
    retry_delay: float,
    action_delay: float = 0.2,
    search_margin: float = 0.05,
    method: int = cv2.TM_CCOEFF_NORMED,
    cancel_event: Optional[threading.Event] = None
) -> bool:
    """
    Attempt matching template(s) at this step.
    Handles both single-option (1 element) and multi-option (multiple elements) steps.

    Args:
        step_index: The index of this step in the sequence
        step: Step Pydantic model instance with step.options (list of StepOption)
        template_dir: Base directory for template images
        threshold: Matching threshold for template matching
        max_retries: Maximum number of retry attempts
        retry_delay: Global delay between retry attempts (can be overridden per-step)
        action_delay: Global delay after success and between key presses (can be overridden per-step)
        search_margin: Percentage of screen size to add as search margin
        method: OpenCV template matching method
        cancel_event: Optional threading.Event to signal cancellation

    Returns:
        True if any option matched and action was executed, False otherwise
    """
    options = step.options
    is_multi_option = len(options) > 1

    for attempt in range(max_retries):
        # Check for cancellation at start of each retry attempt
        if cancel_event and cancel_event.is_set():
            logger.info(f"Step {step_index+1} cancelled during attempt {attempt+1}")
            return False
        # Try each option in order
        for option_index, option in enumerate(options):
            template_path = option.template
            region = option.region
            center_x, center_y = calculate_region_center(region)
            full_template_path = f"{template_dir}/{template_path}"

            # Calculate effective delays (step-level override or global)
            effective_retry_delay = option.retry_delay if option.retry_delay is not None else retry_delay
            effective_action_delay = option.action_delay if option.action_delay is not None else action_delay

            # BRANCH 1: Press-until-match pattern (press BEFORE check)
            if option.press_until_match is not None:
                matched = navigate_press_until_match(
                    template_path=full_template_path,
                    relative_x=center_x,
                    relative_y=center_y,
                    key_press=option.press_until_match,
                    threshold=threshold,
                    action_delay=effective_action_delay,
                    search_margin=search_margin,
                    method=method
                )

                if matched:
                    key_display = format_key_display(option.press_until_match)
                    if is_multi_option:
                        logger.info(f"✓ Step {step_index+1} matched option {option_index+1}/{len(options)} after pressing {key_display}")
                    else:
                        logger.info(f"✓ Step {step_index+1} matched after pressing {key_display}")
                    # Apply action_delay after success (for transitions to next screen)
                    time.sleep(effective_action_delay)
                    return True

            # BRANCH 2: Match-then-press pattern (check THEN press - existing behavior)
            else:
                matched = navigate_if_template_matches(
                    template_path=full_template_path,
                    relative_x=center_x,
                    relative_y=center_y,
                    action=lambda kp=option.key_press, ad=effective_action_delay: execute_key_presses(kp, ad),
                    threshold=threshold,
                    search_margin=search_margin,
                    method=method
                )

                if matched:
                    key_display = format_key_display(option.key_press)
                    if is_multi_option:
                        logger.info(f"✓ Step {step_index+1} matched option {option_index+1}/{len(options)} - pressed {key_display}")
                    else:
                        logger.info(f"✓ Step {step_index+1} matched - pressed {key_display}")
                    # Apply action_delay after success (for transitions to next screen)
                    time.sleep(effective_action_delay)
                    return True

        # No options matched in this attempt - apply retry_delay before next attempt
        if attempt < max_retries - 1:
            # Use retry_delay from first option if set, otherwise global
            effective_retry = options[0].retry_delay if options[0].retry_delay is not None else retry_delay
            time.sleep(effective_retry)

    return False

def navigate_if_template_matches(
    template_path: str,
    relative_x: float,
    relative_y: float,
    action: Callable[[], None],
    threshold: float = 0.8,
    search_margin: float = 0.05,
    method: int = cv2.TM_CCOEFF_NORMED
) -> bool:
    """
    Checks if template matches at position, executes action if match found.

    Args:
        template_path: Path to the template image file
        relative_x: Relative X coordinate (0.0-1.0) of region center
        relative_y: Relative Y coordinate (0.0-1.0) of region center
        action: Callable to execute if template matches
        threshold: Minimum match confidence (0.0-1.0)
        search_margin: Percentage of screen size to add as search margin
        method: OpenCV template matching method

    Returns:
        bool: True if template matched and action was executed, False otherwise
    """
    max_val = match_template_at_position(
        template_path=template_path,
        relative_x=relative_x,
        relative_y=relative_y,
        search_margin=search_margin,
        method=method
    )

    if max_val >= threshold:
        logger.info(f"Matched {template_path} with accuracy {max_val}")
        action()
        return True
    logger.info(f"Failed to match {template_path}, accuracy = {max_val}")
    return False


def navigate_press_until_match(
    template_path: str,
    relative_x: float,
    relative_y: float,
    key_press: Union[str, List[str]],
    threshold: float,
    action_delay: float,
    search_margin: float = 0.05,
    method: int = cv2.TM_CCOEFF_NORMED
) -> bool:
    """
    Press key(s) repeatedly until template matches (press-before-check pattern).

    This is the inverse of navigate_if_template_matches. Instead of checking first
    and pressing when matched, this presses first and checks if the result matches.

    Args:
        template_path: Path to template image
        relative_x: Relative X coordinate (0.0-1.0) of region center
        relative_y: Relative Y coordinate (0.0-1.0) of region center
        key_press: Key(s) to press before checking (string or list of strings)
        threshold: Template matching confidence threshold
        action_delay: Delay between key presses and after pressing
        search_margin: Percentage of screen size to add as search margin
        method: OpenCV template matching method

    Returns:
        True if template matched after pressing (stop pressing), False otherwise
    """
    # logger.info("Starting navigate_press_until_match")
    # First press the key(s)
    execute_key_presses(key_press, action_delay)

    # Wait for UI to update after key press
    time.sleep(action_delay)

    # Now check if template matches using the helper function
    max_val = match_template_at_position(
        template_path=template_path,
        relative_x=relative_x,
        relative_y=relative_y,
        search_margin=search_margin,
        method=method
    )

    if max_val >= threshold:
        logger.info(f"Matched {template_path} with accuracy {max_val} after pressing keys")
        return True  # Stop pressing, template found

    logger.info(f"Failed to match {template_path} after pressing, accuracy = {max_val}")
    return False  # Keep trying

def load_and_execute_navigation(
    nav_config: NavigationConfig,
    template_base_dir: str,
    cancel_event: Optional[threading.Event] = None
) -> bool:
    """
    Main entry point for template-based navigation.
    Executes a navigation configuration with its sequence of steps.

    Args:
        nav_config: NavigationConfig containing parameters and sequence
        template_base_dir: Base directory for resolving relative template paths
        cancel_event: Optional threading.Event to signal cancellation

    Returns:
        bool: True if navigation completed successfully, False otherwise

    Note:
        NavigationConfig contains:
        - template_dir: Directory containing templates (relative to template_base_dir)
        - template_threshold: Matching confidence threshold
        - max_retries: Max retry attempts per step
        - retry_delay: Delay between retry attempts
        - action_delay: Delay between sequential key presses
        - navigation_sequence: The sequence of steps to execute

    Example (single-option step):
        nav_config = NavigationConfig(
            template_dir="F1_22",
            template_threshold=0.85,
            max_retries=60,
            retry_delay=0.05,
            action_delay=0.2,
            navigation_sequence=NavigationSequence(steps=[
                Step(options=[
                    StepOption(template="skip.png", region=[0.4, 0.3, 0.6, 0.5], key_press="escape")
                ])
            ])
        )
        success = load_and_execute_navigation(nav_config, "/path/to/templates")

    Example (multi-option step):
        nav_config = NavigationConfig(
            template_dir="F1_22",
            template_threshold=0.80,
            navigation_sequence=NavigationSequence(steps=[
                Step(options=[
                    StepOption(template="error.png", region=[0.4, 0.5, 0.6, 0.6], key_press="enter"),
                    StepOption(template="normal.png", region=[0.4, 0.3, 0.6, 0.5], key_press="enter")
                ])
            ])
        )
        success = load_and_execute_navigation(nav_config, "/path/to/templates")
    """
    sequence = nav_config.navigation_sequence

    if not sequence.steps:
        logger.error("No navigation steps provided")
        return False

    # Resolve template directory (relative to template_base_dir)
    from pathlib import Path
    template_dir = str(Path(template_base_dir) / nav_config.template_dir)

    # Convert method name to cv2 constant
    matching_method = get_cv2_matching_method(nav_config.matching_method)

    logger.info(f"Starting navigation ({len(sequence.steps)} steps)")
    logger.debug(f"  Template dir: {template_dir}")
    logger.debug(f"  Threshold: {nav_config.template_threshold}, Max retries: {nav_config.max_retries}")
    logger.debug(f"  Search margin: {nav_config.search_margin}, Method: {nav_config.matching_method}")

    success = execute_navigation_sequence(
        steps=sequence.steps,
        template_dir=template_dir,
        threshold=nav_config.template_threshold,
        max_retries=nav_config.max_retries,
        retry_delay=nav_config.retry_delay,
        action_delay=nav_config.action_delay,
        search_margin=nav_config.search_margin,
        method=matching_method,
        cancel_event=cancel_event
    )

    if not success:
        logger.error(f"✗ Navigation failed")
        return False

    logger.info(f"✓ Navigation completed successfully")
    return True