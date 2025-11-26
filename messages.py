"""Data models used by the FreeAskWorld connector."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Tuple

import numpy as np


@dataclass
class RGBDFrame:
    """Container for a synchronized RGB-D capture."""

    color: np.ndarray
    depth: np.ndarray
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JsonPacket:
    """Structured JSON payload emitted by the simulator."""

    json_type: str
    content: Any
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NavigationCommand:
    """Navigation command issued back to the simulator."""

    LocalPositionOffset: np.ndarray  # shape (3,)
    LocalRotationOffset: np.ndarray  # shape (4,)
    IsStopped: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "LocalPositionOffset": self.LocalPositionOffset.tolist(),
            "LocalRotationOffset": self.LocalRotationOffset.tolist(),
            "IsStopped": bool(self.IsStopped),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "NavigationCommand":
        return NavigationCommand(
            LocalPositionOffset=np.asarray(data["LocalPositionOffset"], dtype=float),
            LocalRotationOffset=np.asarray(data["LocalRotationOffset"], dtype=float),
            IsStopped=bool(data.get("IsStopped", False)),
        )


@dataclass
class Step:
    """Explicit simulator step toggle."""

    IsStep: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {"IsStep": bool(self.IsStep)}

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "Step":
        return Step(IsStep=bool(data.get("IsStep", True)))


@dataclass
class TransformData:
    """Pose information of the agent inside the simulator."""

    position: Tuple[float, float, float]
    rotation: Tuple[float, float, float, float]

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "TransformData":
        position = tuple(float(v) for v in data["position"])
        rotation = tuple(float(v) for v in data["rotation"])
        return TransformData(position=position, rotation=rotation)


__all__ = [
    "RGBDFrame",
    "JsonPacket",
    "NavigationCommand",
    "Step",
    "TransformData",
]