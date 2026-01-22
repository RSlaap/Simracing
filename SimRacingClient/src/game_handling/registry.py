"""
Game registry for managing game metadata and launching games.

The GameRegistry provides a centralized way to:
- Load game configurations from config.json
- Validate game metadata
- Launch games with role-based navigation
- Terminate running games
"""

from pathlib import Path
from typing import Dict, List
import json
from pydantic import ValidationError
from utils.monitoring import get_logger
from utils.data_model import Role, GameConfig, NavigationConfig, NavigationSequence, Step

logger = get_logger(__name__)

class GameRegistry:
    """Registry of all configured games."""

    def __init__(self, config_path: Path):
        self._games: Dict[str, GameConfig] = {}
        self._load_config(config_path)

    def _load_config(self, config_path: Path):
        """Load game configurations from JSON file."""
        if not config_path.exists():
            logger.error(f"Game configuration file not found: {config_path}")
            return
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        project_root = config_path.parent
        template_base = project_root / "templates"

        for game_id, game_data in config_data.items():
            try:
                exe_path = Path(game_data['executable_path'])
                if not exe_path.is_absolute():
                    exe_path = project_root / exe_path

                # Parse navigation configs (dict mapping role to array of config objects)
                nav_configs_dict = game_data.get('navigation_config', {})
                navigations: Dict[Role, List[NavigationConfig]] = {}

                for role, config_list in nav_configs_dict.items():
                    if not config_list:
                        logger.warning(f"Empty config list for role '{role}' in game '{game_id}'")
                        continue

                    if not isinstance(config_list, list):
                        logger.error(f"Invalid format for role '{role}' in game '{game_id}': expected array, got {type(config_list)}")
                        continue

                    role_configs = []

                    for config_index, config_data in enumerate(config_list):
                        nav_seq_path = None  # Initialize to avoid stale references from previous iterations
                        try:
                            # Extract parameters from config
                            template_dir = config_data['template_dir']
                            template_threshold = config_data['template_threshold']
                            max_retries = config_data.get('max_retries', 60)
                            retry_delay = config_data.get('retry_delay', 0.05)
                            action_delay = config_data.get('action_delay', 0.2)
                            nav_seq_file = config_data['navigation_sequence_path']

                            # Resolve navigation sequence file path (relative to template_base)
                            nav_seq_path = template_base / nav_seq_file

                            # Load and parse the navigation sequence JSON file
                            if not nav_seq_path.exists():
                                logger.error(f"Navigation sequence file not found: {nav_seq_path}")
                                raise FileNotFoundError
                            with open(nav_seq_path, 'r') as f:
                                steps_data = json.load(f)
                            steps = [Step(**step_data) for step_data in steps_data]
                            nav_sequence = NavigationSequence(steps=steps)

                            # Create NavigationConfig with parameters + sequence
                            nav_config = NavigationConfig(
                                template_dir=template_dir,
                                template_threshold=template_threshold,
                                max_retries=max_retries,
                                retry_delay=retry_delay,
                                action_delay=action_delay,
                                navigation_sequence=nav_sequence
                            )

                            role_configs.append(nav_config)
                            logger.debug(f"  Loaded config {config_index+1} for role '{role}' from {nav_seq_path.name} ({len(steps)} steps)")

                        except KeyError as e:
                            logger.error(f"Missing required field in config {config_index+1} for role '{role}' in game '{game_id}': {e}")
                            continue
                        except json.JSONDecodeError as e:
                            # nav_seq_path is guaranteed to be defined (file was opened on line 76)
                            if nav_seq_path:
                                logger.error(f"Invalid JSON in navigation sequence file {nav_seq_path}: {e}")
                            else:
                                logger.error(f"Invalid JSON in navigation sequence for config {config_index+1}, role '{role}': {e}")
                            continue
                        except ValidationError as e:
                            # nav_seq_path is guaranteed to be defined (JSON was loaded on line 77)
                            if nav_seq_path:
                                logger.error(f"Navigation sequence validation failed for {nav_seq_path}: {e}")
                            else:
                                logger.error(f"Navigation sequence validation failed for config {config_index+1}, role '{role}': {e}")
                            continue
                        except Exception as e:
                            # nav_seq_path might be None if error happened before line 70
                            logger.error(f"Error loading navigation config {config_index+1} for role '{role}': {e}")
                            continue

                    if role_configs:
                        navigations[role] = role_configs
                        logger.debug(f"  Loaded {len(role_configs)} config(s) for role '{role}'")

                # Create GameConfig
                game_config = GameConfig(
                    game_id=game_id,
                    name=game_data['name'],
                    executable_path=exe_path,
                    process_name=game_data['process_name'],
                    window_title=game_data['window_title'],
                    navigations=navigations
                )

                self._games[game_id] = game_config
                logger.debug(f"Registered game: {game_id} ({game_config.name}) with {len(navigations)} navigation(s)")

            except KeyError as e:
                logger.error(f"Missing required field in config for game '{game_id}': {e}")
            except Exception as e:
                logger.error(f"Error loading config for game '{game_id}': {e}")

        logger.info(f"Loaded {len(self._games)} game(s): {list(self._games.keys())}")

    def get(self, game_id: str) -> GameConfig:
        """
        Get game configuration by ID.

        Args:
            game_id: Game identifier (e.g., 'f1_22', 'acc')

        Returns:
            GameConfig for the specified game

        Raises:
            ValueError: If game_id is not registered
        """
        if game_id not in self._games:
            available = list(self._games.keys())
            raise ValueError(
                f"Unknown game: '{game_id}'. "
                f"Available games: {available if available else 'none'}"
            )
        return self._games[game_id]

    def list_games(self) -> list[str]:
        """Get list of registered game IDs."""
        return list(self._games.keys())

    def is_registered(self, game_id: str) -> bool:
        """Check if game is registered."""
        return game_id in self._games


# Global registry instance (initialized on module import)
_config_path = Path(__file__).parent.parent.parent / "config.json"
GAME_REGISTRY = GameRegistry(_config_path)
