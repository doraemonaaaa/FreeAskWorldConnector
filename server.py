"""Websocket server that drives closed-loop baselines."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import socket
import sys
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import websockets
from websockets.server import WebSocketServerProtocol

from .framework import (
    BaselineFactory,
    BaselineResponse,
    BaselineSession,
    ClosedLoopBaseline,
    MessageEnvelope,
    load_baseline_factory,
)
from .handlers import decode_json, decode_rgbd, unknown_message_response


logger = logging.getLogger(__name__)


class UnsupportedMessageType(Exception):
    """Raised when we receive a simulator message we cannot decode."""


@dataclass(slots=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8766
    ping_interval: int = 20
    ping_timeout: int = 30
    max_size: int = 30_485_760
    persist_rgbd_dir: Optional[str] = None


class ClosedLoopServer:
    """Callable wrapper passed to :func:`websockets.serve`."""

    def __init__(self, baseline_factory: BaselineFactory, config: ServerConfig) -> None:
        self._baseline_factory = baseline_factory
        self._config = config

    async def __call__(self, websocket: WebSocketServerProtocol) -> None:
        session_id = str(uuid.uuid4())
        baseline = self._baseline_factory()
        session = BaselineSession(session_id=session_id)
        client = websocket.remote_address[0] if websocket.remote_address else "unknown"

        logger.info("🔗 Client connected from %s (session %s)", client, session_id)

        try:
            await baseline.on_session_start(session)
            await websocket.send(
                json.dumps({"type": "system", "message": "Connected to server"})
            )

            async for raw_message in websocket:
                await self._handle_message(websocket, baseline, session, raw_message)
        except Exception as exc:  # pragma: no cover - guardrail for runtime issues
            logger.exception("❌ Error with client %s (%s): %s", client, session_id, exc)
            await websocket.send(
                json.dumps({"type": "error", "message": f"Server error: {exc}"})
            )
        finally:
            await baseline.on_session_end(session)
            logger.info("❎ Client disconnected: %s (session %s)", client, session_id)

    async def _handle_message(
        self,
        websocket: WebSocketServerProtocol,
        baseline: ClosedLoopBaseline,
        session: BaselineSession,
        raw_message: str,
    ) -> None:
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            await websocket.send(
                json.dumps({"type": "error", "message": "Invalid JSON payload"})
            )
            return

        message_type = data.get("type")
        if not message_type:
            await websocket.send(
                json.dumps(
                    {"type": "error", "message": "Message missing 'type' field"}
                )
            )
            return

        try:
            envelope = self._build_envelope(message_type, data, session)
        except UnsupportedMessageType:
            await websocket.send(json.dumps(unknown_message_response(message_type)))
            return
        except ValueError as exc:
            await websocket.send(json.dumps({"type": "error", "message": str(exc)}))
            return

        if envelope.message_type == "json":
            await websocket.send(
                json.dumps(
                    {
                        "type": "ack",
                        "message": f"Received {envelope.payload.json_type}",
                    }
                )
            )

        try:
            response = await baseline.handle_envelope(session, envelope)
        except Exception as exc:  # pragma: no cover - baseline failure guardrail
            logger.exception("Baseline error: %s", exc)
            await websocket.send(
                json.dumps({"type": "error", "message": f"Baseline error: {exc}"})
            )
            return

        if response is None:
            return

        if not isinstance(response, BaselineResponse):
            logger.warning(
                "Baseline returned unsupported payload type: %s",
                type(response).__name__,
            )
            return

        for packet in response.messages:
            await websocket.send(json.dumps(packet))
        if response.reset_state:
            session.state.clear()

    def _build_envelope(
        self, message_type: str, data: Dict[str, Any], session: BaselineSession
    ) -> MessageEnvelope:
        if message_type == "rgbd":
            payload = decode_rgbd(
                data, persist_dir=self._config.persist_rgbd_dir
            )
            session.state.update_rgbd(payload)
            return MessageEnvelope(message_type="rgbd", payload=payload, raw=data)
        if message_type == "json":
            packet = decode_json(data)
            session.state.update_json(packet)
            return MessageEnvelope(message_type="json", payload=packet, raw=data)
        raise UnsupportedMessageType(message_type)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the FreeAskWorld connector")
    parser.add_argument("--host", default="0.0.0.0", help="Websocket bind host")
    parser.add_argument("--port", type=int, default=8766, help="Websocket bind port")
    parser.add_argument(
        "--baseline",
        default=
        "closed_loop.freeaskworld_connector.simple_baseline:create_baseline",
        help="Baseline factory in the form 'pkg.module:function'",
    )
    parser.add_argument(
        "--ping-interval", type=int, default=20, help="Websocket ping interval"
    )
    parser.add_argument(
        "--ping-timeout", type=int, default=30, help="Websocket ping timeout"
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=30_485_760,
        help="Maximum incoming message payload size",
    )
    parser.add_argument(
        "--persist-rgbd",
        default=None,
        help="Optional directory to persist RGBD frames for debugging",
    )
    return parser.parse_args(argv)


async def async_main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    config = ServerConfig(
        host=args.host,
        port=args.port,
        ping_interval=args.ping_interval,
        ping_timeout=args.ping_timeout,
        max_size=args.max_size,
        persist_rgbd_dir=args.persist_rgbd,
    )

    baseline_factory = load_baseline_factory(args.baseline)
    server_handler = ClosedLoopServer(baseline_factory, config)

    async with websockets.serve(
        server_handler,
        config.host,
        config.port,
        ping_interval=config.ping_interval,
        ping_timeout=config.ping_timeout,
        max_size=config.max_size,
    ):
        host_ip = socket.gethostbyname(socket.gethostname())
        logger.info("✅ WebSocket server running:")
        logger.info("  - Local: ws://localhost:%s", config.port)
        logger.info("  - Network: ws://%s:%s", host_ip, config.port)
        logger.info("  - All interfaces: ws://%s:%s", config.host, config.port)
        await asyncio.Future()


def main(argv: Optional[list[str]] = None) -> None:
    logging.basicConfig(level=logging.INFO)
    if sys.version_info >= (3, 7):
        asyncio.run(async_main(argv))
    else:  # pragma: no cover - Python <3.7 support for completeness
        loop = asyncio.get_event_loop()
        loop.run_until_complete(async_main(argv))


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()