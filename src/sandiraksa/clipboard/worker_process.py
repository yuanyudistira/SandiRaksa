"""
Tier B detection worker process (design 6.2, 28, 32).

Runs the SAME detection pipeline as Tier A, but in a separate process so a
native crash (e.g. in ONNX) cannot take down the GUI (design 6.2, 38). It
connects back to the GUI's QLocalServer, authenticates every message with the
session token, and processes scan requests one at a time (single engine,
design 25/27).

Raw clipboard text lives only in this process's memory for the duration of a
request and is never persisted or logged (design 32).

Launch (by the supervisor):
    python -m sandiraksa.clipboard.worker_process --endpoint <name> --token <tok>
"""

from __future__ import annotations

import argparse
import sys
import time

from sandiraksa.clipboard import ipc
from sandiraksa.clipboard.models import ScanRequest


def _build_engine_and_context():
    from sandiraksa.clipboard.engine_factory import build_context, build_engine

    return build_engine(), build_context()


def run_worker(endpoint: str, token: str) -> int:
    """
    Connect to the GUI server and service detection requests until shutdown.

    Returns a process exit code.
    """
    from PySide6.QtCore import QCoreApplication, QObject
    from PySide6.QtNetwork import QLocalSocket

    from sandiraksa.clipboard.pipeline import OversizedError, run_pipeline

    app = QCoreApplication(sys.argv)

    engine, context = _build_engine_and_context()
    framer = ipc.MessageFramer()

    socket = QLocalSocket()

    def _send(kind: str, payload: dict) -> None:
        try:
            socket.write(ipc.encode_message(kind, token, payload))
            socket.flush()
        except ipc.ProtocolError:
            # Oversized/invalid outbound message; drop silently (no raw text).
            pass

    def _handle_request(payload: dict) -> None:
        # Reconstruct the request; text stays in-process only (design 32).
        try:
            request = ScanRequest(
                request_id=payload["request_id"],
                generation=int(payload["generation"]),
                fingerprint=payload["fingerprint"],
                text=payload["text"],
                created_monotonic=float(payload.get("created_monotonic", 0.0)),
            )
        except (KeyError, TypeError, ValueError):
            return

        started = time.perf_counter()
        try:
            result = run_pipeline(request, engine, context)
            _send(ipc.MSG_SCAN_RESULT, ipc.result_to_payload(result))
        except OversizedError:
            _send(
                ipc.MSG_SCAN_FAILURE,
                {
                    "category": "OversizedError",
                    "message": "payload exceeds hard limit",
                    "generation": request.generation,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                    "oversize": True,
                },
            )
        except Exception as exc:  # sanitized; never raw text (design 60)
            _send(
                ipc.MSG_SCAN_FAILURE,
                {
                    "category": type(exc).__name__,
                    "message": str(exc)[:200],
                    "generation": request.generation,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                    "oversize": False,
                },
            )

    def _on_ready_read() -> None:
        data = bytes(socket.readAll().data())
        try:
            bodies = framer.feed(data)
        except ipc.ProtocolError:
            socket.disconnectFromServer()
            return
        for body in bodies:
            try:
                kind, payload = ipc.decode_message(body, token)
            except ipc.ProtocolError:
                # Bad token / malformed -> refuse and disconnect (design 29).
                socket.disconnectFromServer()
                return
            if kind == ipc.MSG_SCAN_REQUEST:
                _handle_request(payload)
            elif kind == ipc.MSG_HEARTBEAT:
                _send(ipc.MSG_HEARTBEAT_ACK, {"ts": time.time()})
            elif kind == ipc.MSG_SHUTDOWN:
                socket.disconnectFromServer()
                app.quit()

    def _on_connected() -> None:
        _send(ipc.MSG_READY, {"pid": _pid()})

    socket.readyRead.connect(_on_ready_read)
    socket.connected.connect(_on_connected)
    socket.disconnected.connect(app.quit)

    socket.connectToServer(endpoint)
    if not socket.waitForConnected(5000):
        return 2

    return app.exec()


def _pid() -> int:
    import os

    return os.getpid()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SandiRaksa clipboard detector")
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--token", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    return run_worker(args.endpoint, args.token)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["run_worker", "main"]
