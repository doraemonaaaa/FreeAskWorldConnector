"""Utilities for building closed-loop baseline services."""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Protocol, Sequence

from .messages import JsonPacket, RGBDFrame


@dataclass
class SessionState:
    """Aggregated simulator inputs for a single websocket session."""

    latest_rgbd: Optional[RGBDFrame] = None
    json_packets: Dict[str, JsonPacket] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)

    def clear(self) -> None:
        """Reset cached inputs while preserving auxiliary metadata."""

        self.latest_rgbd = None
        self.json_packets.clear()

    def update_rgbd(self, frame: RGBDFrame) -> None:
        self.latest_rgbd = frame

    def update_json(self, packet: JsonPacket) -> None:
        self.json_packets[packet.json_type] = packet


@dataclass
class BaselineSession:
    """Runtime context passed to baseline handlers."""

    session_id: str
    state: SessionState = field(default_factory=SessionState)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MessageEnvelope:
    """Normalized representation of inbound websocket messages."""

    message_type: str
    payload: Any
    raw: Dict[str, Any]


@dataclass
class BaselineResponse:
    """Structured response produced by a baseline after processing input."""

    messages: Sequence[Dict[str, Any]]
    reset_state: bool = False


class ClosedLoopBaseline(Protocol):
    """Interface all baseline implementations must follow."""

    async def on_session_start(self, session: BaselineSession) -> None:
        """Invoked once a websocket client is connected and ready."""

    async def on_session_end(self, session: BaselineSession) -> None:
        """Invoked right before the websocket client disconnects."""

    async def handle_envelope(
        self, session: BaselineSession, envelope: MessageEnvelope
    ) -> Optional[BaselineResponse]:
        """Process an inbound message and optionally produce responses."""


BaselineFactory = Callable[[], ClosedLoopBaseline]


def load_baseline_factory(spec: str) -> BaselineFactory:
    """Resolve ``package.module:callable`` into a baseline factory."""

    if ":" not in spec:
        raise ValueError(
            "Baseline spec must look like 'pkg.module:create_baseline'"
        )

    module_name, attr_name = spec.split(":", maxsplit=1)
    module = importlib.import_module(module_name)

    factory: Any = getattr(module, attr_name)
    if callable(factory):
        return factory  # type: ignore[return-value]
    raise TypeError(
        f"Resolved baseline factory '{spec}' is not callable: {type(factory)!r}"
    )


__all__ = [
    "SessionState",
    "BaselineSession",
    "MessageEnvelope",
    "BaselineResponse",
    "ClosedLoopBaseline",
    "BaselineFactory",
    "load_baseline_factory",
]
