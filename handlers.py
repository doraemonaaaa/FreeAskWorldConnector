"""Message decoding helpers for the closed-loop websocket server."""

from __future__ import annotations

import base64
import io
import logging
import os
from typing import Any, Dict, Mapping

import numpy as np
from PIL import Image

from .messages import JsonPacket, RGBDFrame

logger = logging.getLogger(__name__)


def _extract_metadata(data: Mapping[str, Any], exclude: set[str]) -> Dict[str, Any]:
    return {key: value for key, value in data.items() if key not in exclude}


def decode_rgbd(data: Mapping[str, Any], *, persist_dir: str | None = None) -> RGBDFrame:
    """Decode an RGB-D payload into numpy arrays."""

    try:
        color_encoded = data["color"]
        depth_encoded = data["depth"]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise ValueError("RGBD payload missing 'color' or 'depth' fields") from exc

    color_bytes = base64.b64decode(color_encoded)
    depth_bytes = base64.b64decode(depth_encoded)

    with Image.open(io.BytesIO(color_bytes)) as color_img:
        color_array = np.asarray(color_img)
    with Image.open(io.BytesIO(depth_bytes)) as depth_img:
        depth_array = np.asarray(depth_img)

    if persist_dir:
        os.makedirs(persist_dir, exist_ok=True)
        rgb_path = os.path.join(persist_dir, "rgb.png")
        depth_path = os.path.join(persist_dir, "depth.png")
        try:
            with Image.open(io.BytesIO(color_bytes)) as color_img:
                color_img.save(rgb_path)
            with Image.open(io.BytesIO(depth_bytes)) as depth_img:
                depth_img.save(depth_path)
        except Exception as exc:  # pragma: no cover - best-effort logging
            logger.warning("Failed to persist RGBD payload: %s", exc)

    metadata = _extract_metadata(data, {"type", "color", "depth"})
    return RGBDFrame(color=color_array, depth=depth_array, metadata=metadata)


def decode_json(data: Mapping[str, Any]) -> JsonPacket:
    """Decode a JSON payload coming from the simulator."""

    json_type = data.get("json_type")
    if not json_type:
        raise ValueError("JSON payload missing 'json_type'")

    content = data.get("content")
    metadata = _extract_metadata(data, {"type", "json_type", "content"})
    return JsonPacket(json_type=json_type, content=content, metadata=metadata)


def unknown_message_response(message_type: str) -> Dict[str, Any]:
    """Construct a diagnostic packet for unsupported message types."""

    return {
        "type": "error",
        "message": f"Unsupported message type: {message_type}",
    }


__all__ = ["decode_rgbd", "decode_json", "unknown_message_response"]
        