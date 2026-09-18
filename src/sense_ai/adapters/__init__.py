"""Adapters: interface to external platforms (peaqOS, ROS2, etc.)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..model.snapshot import ContextSnapshot

# Re-export for public API surface
__all__ = [
    "AdapterError",
    "BaseAdapter",
    "PeaqAdapter",
    "Ros2Adapter",
]


class AdapterError(Exception):
    """Base exception for adapter errors."""


class BaseAdapter(ABC):
    """
    Abstract base for platform adapters.

    Subclass this to integrate Sense with a specific runtime platform
    (peaqOS, ROS2, custom, etc.).
    """

    @abstractmethod
    def get_current_situation(self) -> ContextSnapshot:
        """
        Retrieve the current Situation from the platform.

        Raises
        ------
        AdapterError
            If the platform cannot be reached or the response is invalid.
        """
        ...

    @abstractmethod
    def submit_result(self, situation_id: str, result: object) -> None:
        """
        Submit an evaluation result back to the platform.

        Parameters
        ----------
        situation_id : str
            The situation identifier this result applies to.
        result : object
            The result payload to submit.
        """
        ...
