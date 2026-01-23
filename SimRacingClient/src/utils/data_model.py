"""
Unified data models for the SimRacing Client.

This module contains all Pydantic BaseModel classes used throughout the application,
providing centralized data validation and type safety.
"""

from pathlib import Path
from typing import Dict, List, Literal, Optional, Union
import json
from pydantic import BaseModel, Field, validator


# ============================================================================
# Type Definitions
# ============================================================================

Role = Literal['host', 'join', 'singleplayer']


# ============================================================================
# Machine Configuration Model
# ============================================================================

class MachineConfig(BaseModel):
    """
    Configuration for a SimRacing client machine.

    Loaded from machine_configuration.json and augmented with runtime values.

    Attributes:
        id: Unique machine identifier (used for ordering - lowest ID becomes host)
        name: Human-readable machine name (displayed in UI and logs)
        ip: Machine's local IP address (set at runtime)
        port: Service port number (set at runtime)
    """
    id: str = Field(..., description="Unique machine identifier")
    name: str = Field(..., description="Human-readable machine name")
    ip: str = Field(..., description="Machine's local IP address")
    port: str = Field(..., description="Service port number")


# ============================================================================
# Navigation Template Models (from screen_navigator.py)
# ============================================================================

class StepOption(BaseModel):
    """
    A single template matching option within a navigation step.

    Attributes:
        template: Path to template image relative to template_dir
        region: Region coordinates as [x1, y1, x2, y2] in relative coordinates (0.0-1.0)
        key_press: Key(s) to press when template matches (string or list of strings).
                   Optional - if None, template is matched but no key is pressed (wait/polling step)
        press_until_match: Key(s) to press repeatedly until template matches.
                          Mutually exclusive with key_press. Use this for skip intro patterns.
        retry_delay: Override global retry_delay for this step (delay between polling attempts).
        action_delay: Override global action_delay for this step (delay after success and between key presses).
    """
    template: str = Field(..., description="Path to template image relative to template_dir")
    region: List[float] = Field(..., min_length=4, max_length=4, description="Region as [x1, y1, x2, y2] in relative coordinates (0.0-1.0)")
    key_press: Union[str, List[str], None] = Field(default=None, description="Key(s) to press when template matches, or None for wait/polling steps")
    press_until_match: Union[str, List[str], None] = Field(default=None, description="Key(s) to press repeatedly until template matches")
    retry_delay: Optional[float] = Field(default=None, ge=0.0, description="Override global retry_delay for this step (polling interval)")
    action_delay: Optional[float] = Field(default=None, ge=0.0, description="Override global action_delay for this step (post-success wait)")

class Step(BaseModel):
    """
    A navigation step containing one or more template matching options.

    Every step contains a list of StepOption objects. Most steps will have just
    one option (single-option), but steps can have multiple options for handling
    different UI states (multi-option).

    Single-option example:
        Step(options=[
            StepOption(template="menu.png", region=[0.4, 0.3, 0.6, 0.5], key_press="enter")
        ])

    Multi-option example:
        Step(options=[
            StepOption(template="error.png", region=[0.4, 0.5, 0.6, 0.6], key_press="enter"),
            StepOption(template="normal.png", region=[0.4, 0.3, 0.6, 0.5], key_press="enter")
        ])
    """
    options: List[StepOption] = Field(..., min_length=1, description="List of template matching options (usually 1)")


class NavigationSequence(BaseModel):
    """
    A sequence of navigation steps loaded from a JSON file.

    The JSON file contains a flat array of Step objects with no execution parameters.
    Parameters are defined in config.json and wrapped in NavigationConfig.

    Example JSON:
        [
          {"options": [{"template": "menu.png", "region": [0.4, 0.3, 0.6, 0.5], "key_press": "enter"}]},
          {"options": [{"template": "lobby.png", "region": [0.3, 0.4, 0.7, 0.6], "key_press": "down"}]}
        ]

    Attributes:
        steps: Ordered list of Step objects
    """
    steps: List[Step] = Field(..., description="Ordered list of navigation steps")


# ============================================================================
# Pre-Launch Configuration Models (for CAMMUS, etc.)
# ============================================================================

class ClickStep(BaseModel):
    """
    A single click-based navigation step for pre-launch configuration.

    Attributes:
        template: Template image filename (relative to template directory)
        double_click: Whether to double-click instead of single-click
    """
    template: str = Field(..., description="Template image filename")
    double_click: bool = Field(default=False, description="Whether to double-click")


class PreLaunchConfig(BaseModel):
    """
    Configuration for pre-launch setup (e.g., CAMMUS software configuration).

    This configuration runs BEFORE the game launches to configure external
    software like wheel/pedal/motion sim software.

    Attributes:
        enabled: Whether pre-launch config is enabled for this game
        executable_path: Path to the software executable (optional, if it needs launching)
        process_name: Process name to check if already running
        window_title: Window title to focus (optional)
        template_dir: Directory containing template images for click navigation
        template_threshold: Template matching confidence threshold
        max_retries: Maximum retry attempts per click step
        retry_delay: Delay between retry attempts in seconds
        click_delay: Delay after each successful click in seconds
        click_steps: List of click steps to execute
    """
    enabled: bool = Field(default=False, description="Whether pre-launch config is enabled")
    executable_path: Optional[Path] = Field(default=None, description="Path to software executable")
    process_name: Optional[str] = Field(default=None, description="Process name to check if running")
    window_title: Optional[str] = Field(default=None, description="Window title to focus")
    template_dir: str = Field(..., description="Directory containing template images")
    template_threshold: float = Field(default=0.85, ge=0.0, le=1.0, description="Template matching threshold")
    max_retries: int = Field(default=10, ge=1, description="Maximum retry attempts per step")
    retry_delay: float = Field(default=1.0, ge=0.0, description="Delay between retries in seconds")
    click_delay: float = Field(default=0.5, ge=0.0, description="Delay after each click in seconds")
    click_steps: List[ClickStep] = Field(default_factory=list, description="Click steps to execute")

    class Config:
        arbitrary_types_allowed = True


# ============================================================================
# Game Configuration Models (from registry.py)
# ============================================================================

class NavigationConfig(BaseModel):
    """
    Configuration for executing a navigation sequence.

    Combines execution parameters from config.json with a loaded NavigationSequence.
    Multiple NavigationConfigs can exist per role for different strategies/tracks/modes.

    Supports deferred loading for dynamic paths containing {n} placeholder (resolved at runtime
    based on player_count).

    Attributes:
        template_dir: Directory containing template images (relative to templates base)
        template_threshold: Template matching threshold (0.0-1.0)
        max_retries: Maximum retry attempts per step
        retry_delay: Delay between retry attempts in seconds
        action_delay: Delay between sequential key presses in seconds
        search_margin: Percentage of screen size to add as search margin (0.0-1.0, default 0.05 = 5%)
        matching_method: OpenCV template matching method name (default: "TM_CCOEFF_NORMED")
        navigation_sequence: The loaded sequence of steps to execute (can be None if deferred)
        navigation_sequence_path: Raw path from config (may contain {n} placeholder)
        _template_base: Internal path to template base directory (set by registry for deferred loading)
    """
    template_dir: str = Field(..., description="Directory containing template images (relative to templates base)")
    template_threshold: float = Field(..., ge=0.0, le=1.0, description="Template matching threshold (0.0-1.0)")
    max_retries: int = Field(default=60, ge=1, description="Maximum retry attempts per step")
    retry_delay: float = Field(default=0.05, ge=0.0, description="Delay between retry attempts in seconds")
    action_delay: float = Field(default=0.2, ge=0.0, description="Delay between sequential key presses in seconds")
    search_margin: float = Field(default=0.05, ge=0.0, le=1.0, description="Percentage of screen size to add as search margin (0.05 = 5%)")
    matching_method: str = Field(default="TM_CCOEFF_NORMED", description="OpenCV template matching method")
    navigation_sequence: Optional[NavigationSequence] = Field(default=None, description="The navigation sequence to execute (None if deferred)")
    navigation_sequence_path: Optional[str] = Field(default=None, description="Raw path from config (may contain {n} placeholder)")
    _template_base: Optional[Path] = None  # Set by registry for deferred loading

    class Config:
        underscore_attrs_are_private = True

    def resolve_sequence(self, player_count: Optional[int] = None) -> None:
        """
        Load navigation sequence, resolving {n} placeholder if present.

        Args:
            player_count: Number of players (required if path contains {n})

        Raises:
            ValueError: If path contains {n} but no player_count provided
            FileNotFoundError: If resolved navigation sequence file doesn't exist
        """
        if self.navigation_sequence is not None:
            return  # Already loaded

        if not self.navigation_sequence_path:
            raise ValueError("No navigation_sequence_path to resolve")

        path = self.navigation_sequence_path
        if "{n}" in path:
            if player_count is None:
                raise ValueError(f"Path contains {{n}} but no player_count provided: {path}")
            path = path.replace("{n}", str(player_count))

        if self._template_base is None:
            raise ValueError("_template_base not set - cannot resolve navigation sequence")

        full_path = self._template_base / path
        if not full_path.exists():
            raise FileNotFoundError(f"Navigation sequence file not found: {full_path}")

        with open(full_path, 'r') as f:
            steps_data = json.load(f)

        steps = [Step(**step_data) for step_data in steps_data]
        self.navigation_sequence = NavigationSequence(steps=steps)


class GameConfig(BaseModel):
    """
    Complete metadata for a single game.

    Contains game identification, executable information, and all role-based
    navigation configurations.
    """
    game_id: str = Field(..., description="Unique game identifier (e.g., 'f1_22', 'acc')")
    name: str = Field(..., description="Human-readable game name")
    executable_path: Path = Field(..., description="Path to game executable")
    process_name: str = Field(..., description="Process name for the running game")
    window_title: str = Field(..., description="Window title to search for when focusing")
    navigations: Dict[Role, List[NavigationConfig]] = Field(..., description="Navigation configs by role")
    pre_launch_config: Optional[PreLaunchConfig] = Field(default=None, description="Optional pre-launch configuration")

    class Config:
        arbitrary_types_allowed = True  # Allow Path type

    def get_navigation_configs(self, role: Role, player_count: Optional[int] = None) -> List[NavigationConfig]:
        """
        Get all navigation configurations for the specified role.

        Resolves any deferred configs (those with {n} placeholder) using player_count.

        Args:
            role: Either 'host' or 'join'
            player_count: Number of players (required if any config path contains {n})

        Returns:
            List of NavigationConfig for the specified role

        Raises:
            ValueError: If role is not configured or deferred config cannot be resolved
        """
        if role not in self.navigations:
            available = list(self.navigations.keys())
            raise ValueError(
                f"No navigation configs for role '{role}' in game '{self.game_id}'. "
                f"Available roles: {available}"
            )

        configs = self.navigations[role]

        # Resolve any deferred configs with player_count
        for config in configs:
            if config.navigation_sequence is None and config.navigation_sequence_path:
                config.resolve_sequence(player_count)

        return configs

    def get_navigation_config(self, role: Role, index: int = 0) -> NavigationConfig:
        """
        Get a specific navigation configuration for the specified role.

        Args:
            role: Either 'host' or 'join'
            index: Index of the config to retrieve (default: 0 for first/default config)

        Returns:
            NavigationConfig for the specified role and index

        Raises:
            ValueError: If role is not configured or index is out of range
        """
        configs = self.get_navigation_configs(role)

        if index < 0 or index >= len(configs):
            raise ValueError(
                f"Invalid config index {index} for role '{role}' in game '{self.game_id}'. "
                f"Valid range: 0-{len(configs)-1}"
            )

        return configs[index]
