# FreeAskWorld Connector

The FreeAskWorld connector provides the websocket bridge between the Unity
simulator (client) and Python baselines hosted inside this repository. The
package translates incoming simulator payloads into structured objects, feeds
them into a pluggable baseline, and streams the resulting navigation commands
back to Unity.

## Highlights
- Unified `ClosedLoopBaseline` protocol for implementing baseline policies.
- Session-scoped state containers that cache RGB-D frames and JSON packets.
- Drop-in smoke-test baseline so you can validate the communication pipeline in isolation.
- Optional Cloudflare tunnel helper for quick NAT/firewall traversal.

## Requirements
- Python 3.10+
- Repository dependencies: `pip install -r requirements.txt`
- Optional: `cloudflared` binary if you plan to expose the server publicly

You can create a dedicated environment first:

```bash
conda create -n freeaskworld python=3.10
conda activate freeaskworld
pip install -r requirements.txt
```

## Running the server

Launch the websocket server and point it to a baseline factory via the
`package.module:create_function` notation:

```bash
python -m closed_loop.freeaskworld_connector.server \
  --host 0.0.0.0 \
  --port 8766 \
  --baseline closed_loop.freeaskworld_connector.simple_baseline:create_baseline
```

From Unity, connect to `ws://<server-ip>:8766`.

### Helper script

`start.bash` wraps both the server and an optional Cloudflare tunnel. Override
defaults through environment variables:

```bash
PORT=8766 \
HOST=0.0.0.0 \
BASELINE_SPEC="closed_loop.freeaskworld_connector.simple_baseline:create_baseline" \
bash start.bash
```

The script prints the generated `*.trycloudflare.com` URL once the tunnel is
ready.

## Optional Cloudflare setup

```bash
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
cloudflared tunnel --url http://localhost:8766
```

## Message flow
1. Unity connects to the websocket endpoint.
2. Unity streams RGB-D frames and JSON packets (`Instruction`, `TransformData`, etc.).
3. The server deserializes messages into `RGBDFrame` or `JsonPacket` instances and updates `SessionState`.
4. The active baseline consumes envelopes and, when ready, emits responses such as `NavigationCommand` + `Step` packets.
5. Unity applies the commands and advances the simulation.

## Implementing a baseline

Create a class that satisfies the `ClosedLoopBaseline` protocol and expose a factory named `create_baseline`:

```python
from closed_loop.freeaskworld_connector.framework import (
    BaselineResponse, BaselineSession, ClosedLoopBaseline, MessageEnvelope,
)


class MyBaseline(ClosedLoopBaseline):
    async def on_session_start(self, session: BaselineSession) -> None:
        ...

    async def on_session_end(self, session: BaselineSession) -> None:
        ...

    async def handle_envelope(
        self, session: BaselineSession, envelope: MessageEnvelope
    ) -> BaselineResponse | None:
        ...


def create_baseline() -> ClosedLoopBaseline:
    return MyBaseline()
```

Run the server with `--baseline my_package.module:create_baseline` (or set the `BASELINE_SPEC` environment variable) to activate your implementation.

## Troubleshooting
- **Connection refused**: ensure Unity targets the host/port configured on the server.
- **No responses**: verify that the baseline only returns a `BaselineResponse` once all necessary inputs (RGB-D, instruction, transform) are available.
- **Cloudflare errors**: make sure the `cloudflared` binary is on the `PATH` and the requested port is free.

## Reference files
- `server.py`: websocket event loop and baseline dispatcher
- `framework.py`: core data structures and interfaces
- `handlers.py`: payload decoding utilities
- `simple_baseline.py`: minimal baseline example
- `start_cloudflared.py`: Cloudflare tunnel launcher
