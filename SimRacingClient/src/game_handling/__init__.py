"""
Game management module for SimRacing Client.

This module provides:
- GameRegistry: Centralized game configuration registry
- launch(): Generic game launcher with role-based navigation

Usage:
    from game_handling import launch, GAME_REGISTRY

    # Launch a game
    success = launch('f1_22', 'host')

    # Get game config
    config = GAME_REGISTRY.get('f1_22')
"""

from .registry import GAME_REGISTRY, GameConfig, NavigationConfig
from .launcher import launch

# Expose public API
__all__ = ['GAME_REGISTRY', 'GameConfig', 'NavigationConfig', 'launch']
