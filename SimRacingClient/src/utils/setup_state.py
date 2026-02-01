"""
Thread-safe state management for the SimRacing client setup.

This module provides the SetupState class which encapsulates all state
related to game configuration and execution status.
"""

import threading
from typing import Optional, Literal

from utils.monitoring import get_logger

logger = get_logger(__name__)

# Valid status values
Status = Literal["idle", "configured", "starting", "running"]


class SetupState:
    """
    Thread-safe state management for the SimRacing client.

    Encapsulates all state related to game configuration and execution,
    providing thread-safe access methods for use across multiple threads
    (HTTP handlers, heartbeat thread, game launch thread).

    Attributes:
        status: Current state ("idle", "configured", "starting", "running")
        current_game: Game identifier when configured/running
        session_id: Session identifier from orchestrator
        role: Player role ("host", "join", "singleplayer")
        player_count: Number of players in session
        host_ip: IP address of the host (for join role)

    Example:
        state = SetupState()
        state.configure(game="f1_22", session_id="session-123", role="host")
        print(state.status)  # "configured"
        state.set_status("running")
        state.reset()  # Back to idle
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._status: Status = "idle"
        self._current_game: Optional[str] = None
        self._session_id: Optional[str] = None
        self._role: Optional[str] = None
        self._player_count: Optional[int] = None
        self._host_ip: Optional[str] = None

    # -------------------------------------------------------------------------
    # Thread-safe property access
    # -------------------------------------------------------------------------

    @property
    def status(self) -> Status:
        """Get current status (thread-safe)."""
        with self._lock:
            return self._status

    @property
    def current_game(self) -> Optional[str]:
        """Get current game identifier (thread-safe)."""
        with self._lock:
            return self._current_game

    @property
    def session_id(self) -> Optional[str]:
        """Get current session ID (thread-safe)."""
        with self._lock:
            return self._session_id

    @property
    def role(self) -> Optional[str]:
        """Get current role (thread-safe)."""
        with self._lock:
            return self._role

    @property
    def player_count(self) -> Optional[int]:
        """Get player count (thread-safe)."""
        with self._lock:
            return self._player_count

    @property
    def host_ip(self) -> Optional[str]:
        """Get host IP address (thread-safe)."""
        with self._lock:
            return self._host_ip

    # -------------------------------------------------------------------------
    # State operations
    # -------------------------------------------------------------------------

    def snapshot(self) -> dict:
        """
        Get a thread-safe copy of the complete state.

        Returns:
            Dictionary containing all state fields.
        """
        with self._lock:
            return {
                "status": self._status,
                "current_game": self._current_game,
                "session_id": self._session_id,
                "role": self._role,
                "player_count": self._player_count,
                "host_ip": self._host_ip
            }

    def configure(
        self,
        game: str,
        session_id: str,
        role: str,
        player_count: Optional[int] = None,
        host_ip: Optional[str] = None
    ) -> None:
        """
        Configure the setup for a game session.

        Sets all configuration values and transitions status to "configured".

        Args:
            game: Game identifier (e.g., "f1_22", "acc")
            session_id: Unique session identifier from orchestrator
            role: Player role ("host", "join", "singleplayer")
            player_count: Optional number of players in session
            host_ip: Optional host IP address (required for "join" role)
        """
        with self._lock:
            self._current_game = game
            self._session_id = session_id
            self._role = role
            self._player_count = player_count
            self._host_ip = host_ip
            self._status = "configured"

        logger.info(
            f"State configured: Game={game}, Session={session_id}, "
            f"Role={role}, PlayerCount={player_count}, HostIP={host_ip}"
        )

    def set_status(self, status: Status) -> None:
        """
        Update the status (thread-safe).

        Args:
            status: New status value
        """
        with self._lock:
            old_status = self._status
            self._status = status

        if old_status != status:
            logger.debug(f"State status changed: {old_status} -> {status}")

    def reset(self) -> None:
        """
        Reset state to idle.

        Clears all configuration and sets status back to "idle".
        """
        with self._lock:
            self._status = "idle"
            self._current_game = None
            self._session_id = None
            self._role = None
            self._player_count = None
            self._host_ip = None

        logger.debug("State reset to idle")

    def is_configured(self) -> bool:
        """Check if setup is in configured state (thread-safe)."""
        with self._lock:
            return self._status == "configured"

    def is_running(self) -> bool:
        """Check if a game is currently running (thread-safe)."""
        with self._lock:
            return self._status == "running"

    def is_idle(self) -> bool:
        """Check if setup is idle (thread-safe)."""
        with self._lock:
            return self._status == "idle"

    def __repr__(self) -> str:
        """String representation for debugging."""
        with self._lock:
            return (
                f"SetupState(status={self._status!r}, "
                f"game={self._current_game!r}, role={self._role!r})"
            )
