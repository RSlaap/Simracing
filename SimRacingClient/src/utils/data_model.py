"""
Unified data models for the SimRacing Client.

This module contains all Pydantic BaseModel classes used throughout the application,
providing centralized data validation and type safety.
"""

from pathlib import Path
from typing import Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, validator


# ============================================================================
# Type Definitions
# ============================================================================

Role = Literal['host', 'join', 'singleplayer']


# ============================================================================
# Navigation Template Models (from screen_navigator.py)
# ============================================================================

class Viewport(BaseModel):
    """
    Defines a viewport region for template matching in relative coordinates.

    Used when the game doesn't fill the entire screen (e.g., 16:9 game on ultra-wide monitor).
    Template coordinates are interpreted relative to this viewport rather than the full screen.

    Attributes:
        x1: Left edge of viewport (0.0 = left screen edge, 1.0 = right screen edge)
        y1: Top edge of viewport (0.0 = top screen edge, 1.0 = bottom screen edge)
        x2: Right edge of viewport (0.0 = left screen edge, 1.0 = right screen edge)
        y2: Bottom edge of viewport (0.0 = top screen edge, 1.0 = bottom screen edge)
    """
    x1: float = Field(..., ge=0.0, le=1.0, description="Left edge of viewport (0.0-1.0)")
    y1: float = Field(..., ge=0.0, le=1.0, description="Top edge of viewport (0.0-1.0)")
    x2: float = Field(..., ge=0.0, le=1.0, description="Right edge of viewport (0.0-1.0)")
    y2: float = Field(..., ge=0.0, le=1.0, description="Bottom edge of viewport (0.0-1.0)")

    @validator('x2')
    def x2_must_be_greater_than_x1(cls, v, values):
        if 'x1' in values and v <= values['x1']:
            raise ValueError('x2 must be greater than x1')
        return v

    @validator('y2')
    def y2_must_be_greater_than_y1(cls, v, values):
        if 'y1' in values and v <= values['y1']:
            raise ValueError('y2 must be greater than y1')
        return v


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
    """
    template: str = Field(..., description="Path to template image relative to template_dir")
    region: List[float] = Field(..., min_length=4, max_length=4, description="Region as [x1, y1, x2, y2] in relative coordinates (0.0-1.0)")
    key_press: Union[str, List[str], None] = Field(default=None, description="Key(s) to press when template matches, or None for wait/polling steps")
    press_until_match: Union[str, List[str], None] = Field(default=None, description="Key(s) to press repeatedly until template matches")

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
# Game Configuration Models (from registry.py)
# ============================================================================

class NavigationConfig(BaseModel):
    """
    Configuration for executing a navigation sequence.

    Combines execution parameters from config.json with a loaded NavigationSequence.
    Multiple NavigationConfigs can exist per role for different strategies/tracks/modes.

    Attributes:
        template_dir: Directory containing template images (relative to templates base)
        template_threshold: Template matching threshold (0.0-1.0)
        max_retries: Maximum retry attempts per step
        retry_delay: Delay between retry attempts in seconds
        action_delay: Delay between sequential key presses in seconds
        search_margin: Percentage of screen size to add as search margin (0.0-1.0, default 0.05 = 5%)
        matching_method: OpenCV template matching method name (default: "TM_CCOEFF_NORMED")
        viewport: Optional viewport for coordinate transformation. If None, uses fullscreen.
        navigation_sequence: The loaded sequence of steps to execute
    """
    template_dir: str = Field(..., description="Directory containing template images (relative to templates base)")
    template_threshold: float = Field(..., ge=0.0, le=1.0, description="Template matching threshold (0.0-1.0)")
    max_retries: int = Field(default=60, ge=1, description="Maximum retry attempts per step")
    retry_delay: float = Field(default=0.05, ge=0.0, description="Delay between retry attempts in seconds")
    action_delay: float = Field(default=0.2, ge=0.0, description="Delay between sequential key presses in seconds")
    search_margin: float = Field(default=0.05, ge=0.0, le=1.0, description="Percentage of screen size to add as search margin (0.05 = 5%)")
    matching_method: str = Field(default="TM_CCOEFF_NORMED", description="OpenCV template matching method")
    viewport: Optional[Viewport] = Field(default=None, description="Optional viewport for coordinate transformation. If None, uses fullscreen.")
    navigation_sequence: NavigationSequence = Field(..., description="The navigation sequence to execute")


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

    class Config:
        arbitrary_types_allowed = True  # Allow Path type

    def get_navigation_configs(self, role: Role) -> List[NavigationConfig]:
        """
        Get all navigation configurations for the specified role.

        Args:
            role: Either 'host' or 'join'

        Returns:
            List of NavigationConfig for the specified role

        Raises:
            ValueError: If role is not configured
        """
        if role not in self.navigations:
            available = list(self.navigations.keys())
            raise ValueError(
                f"No navigation configs for role '{role}' in game '{self.game_id}'. "
                f"Available roles: {available}"
            )
        print("*"*70)
        print(self.navigations[role])
        return self.navigations[role]

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
