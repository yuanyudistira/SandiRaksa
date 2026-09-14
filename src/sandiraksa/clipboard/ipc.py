"""
Local IPC protocol for the Tier B detection worker process (design 28-32).

Transport is QLocalSocket/QLocalServer (a named pipe on Windows, a Unix domain
socket elsewhere) - local-only, never a TCP interface (design 29).

Security model (design 29):
  * local-only, per-user/session named endpoint;
  * authenticated by a random session token in every message;
  * bounded message size;
  * versioned protocol.

Privacy (design 32): raw clipboard text crosses only GUI -> worker; it is never
persisted, logged, or placed in crash telemetry. Framing here does not write to
disk.

Wire format: a 4-byte big-endian length prefix followed by a UTF-8 JSON object.
The length prefix is validated against MAX_MESSAGE_BYTES before any allocation.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass

PROTOCOL_VERSION = 1

#: Hard cap on a single framed message (design 29). 1 MiB comfortably covers a
#: 512 KiB clipboard payload plus JSON overhead, and bounds hostile input.
MAX_MESSAGE_BYTES = 1_048_576

#: Message kinds.
MSG_SCAN_REQUEST = "scan_request"
MSG_SCAN_RESULT = "scan_result"
MSG_SCAN_FAILURE = "scan_failure"
MSG_HEARTBEAT = "heartbeat"
MSG_HEARTBEAT_ACK = "heartbeat_ack"
MSG_SHUTDOWN = "shutdown"
MSG_READY = "ready"


class ProtocolError(Exception):
    """Raised on malformed, oversized, or unauthenticated messages."""


def generate_session_token() -> str:
    """Return a fresh random session token (design 29)."""
    return secrets.token_hex(16)


def generate_endpoint_name() -> str:
    """
    Build a unique local endpoint name for this session.

    Random component prevents collisions and casual connection by other local
    processes; the token still authenticates each message.
    """
    return f"sandiraksa-clip-{secrets.token_hex(8)}"


# --------------------------------------------------------------------------
# DTOs (design 30, 31). Frozen so they are immutable messages.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ScanRequestDTO:
    request_id: str
    generation: int
    fingerprint: str
    text: str
    created_monotonic: float
    protocol_version: int = PROTOCOL_VERSION


@dataclass(frozen=True)
class ScanResultDTO:
    request_id: str
    generation: int
    source_fingerprint: str
    risk_level: str
    findings: tuple  # tuple of dicts
    safe_text: str
    processing_ms: int
    protocol_version: int = PROTOCOL_VERSION


# --------------------------------------------------------------------------
# Framing + (de)serialization
# --------------------------------------------------------------------------
def encode_message(kind: str, token: str, payload: dict) -> bytes:
    """
    Encode a message to length-prefixed JSON bytes.

    Raises ProtocolError if the encoded body exceeds MAX_MESSAGE_BYTES.
    """
    envelope = {
        "protocol_version": PROTOCOL_VERSION,
        "kind": kind,
        "token": token,
        "payload": payload,
    }
    body = json.dumps(envelope, ensure_ascii=False).encode("utf-8", "surrogatepass")
    if len(body) > MAX_MESSAGE_BYTES:
        raise ProtocolError(f"message too large: {len(body)} bytes")
    prefix = len(body).to_bytes(4, "big")
    return prefix + body


def decode_message(body: bytes, expected_token: str) -> tuple[str, dict]:
    """
    Decode a message body, verifying protocol version and session token.

    Args:
        body: The JSON body (length prefix already stripped by the framer).
        expected_token: The session token this side expects (design 29).

    Returns:
        (kind, payload)

    Raises:
        ProtocolError: malformed JSON, wrong version, or bad/missing token.
    """
    if len(body) > MAX_MESSAGE_BYTES:
        raise ProtocolError("message exceeds maximum size")
    try:
        envelope = json.loads(body.decode("utf-8", "surrogatepass"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProtocolError("invalid JSON") from exc
    if not isinstance(envelope, dict):
        raise ProtocolError("envelope is not an object")
    if envelope.get("protocol_version") != PROTOCOL_VERSION:
        raise ProtocolError("protocol version mismatch")
    # Constant-time token comparison to avoid timing side channels.
    token = envelope.get("token", "")
    if not isinstance(token, str) or not secrets.compare_digest(
        token, expected_token
    ):
        raise ProtocolError("authentication failed")
    kind = envelope.get("kind")
    payload = envelope.get("payload", {})
    if not isinstance(kind, str) or not isinstance(payload, dict):
        raise ProtocolError("malformed envelope fields")
    return kind, payload


class MessageFramer:
    """
    Incremental length-prefixed message framer over a byte stream.

    Feed raw bytes as they arrive; yields complete message bodies. Guards the
    declared length against MAX_MESSAGE_BYTES before buffering to prevent a
    hostile peer from forcing unbounded allocation (design 29).
    """

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        """Append bytes; return any complete message bodies now available."""
        self._buffer.extend(data)
        messages: list[bytes] = []
        while True:
            if len(self._buffer) < 4:
                break
            length = int.from_bytes(self._buffer[:4], "big")
            if length > MAX_MESSAGE_BYTES:
                raise ProtocolError(f"declared length {length} exceeds max")
            if len(self._buffer) < 4 + length:
                break
            body = bytes(self._buffer[4 : 4 + length])
            del self._buffer[: 4 + length]
            messages.append(body)
        return messages


def request_to_dto(request) -> ScanRequestDTO:
    """Convert a clipboard ScanRequest to an IPC ScanRequestDTO."""
    return ScanRequestDTO(
        request_id=request.request_id,
        generation=request.generation,
        fingerprint=request.fingerprint,
        text=request.text,
        created_monotonic=request.created_monotonic,
    )


def result_to_payload(result) -> dict:
    """Serialize a ClipboardProtectionResult's transferable fields."""
    return {
        "request_id": getattr(result, "result_id", ""),
        "generation": result.generation,
        "source_fingerprint": result.source_fingerprint,
        "risk_level": result.risk_level.value,
        "findings": [
            {
                "entity_type": f.entity_type,
                "start": f.start,
                "end": f.end,
                "score": f.score,
                "severity": f.severity,
            }
            for f in result.findings
        ],
        "safe_text": result.safe_text,
        "processing_ms": result.processing_ms,
    }


def dto_asdict(dto) -> dict:
    return asdict(dto)


__all__ = [
    "PROTOCOL_VERSION",
    "MAX_MESSAGE_BYTES",
    "MSG_SCAN_REQUEST",
    "MSG_SCAN_RESULT",
    "MSG_SCAN_FAILURE",
    "MSG_HEARTBEAT",
    "MSG_HEARTBEAT_ACK",
    "MSG_SHUTDOWN",
    "MSG_READY",
    "ProtocolError",
    "ScanRequestDTO",
    "ScanResultDTO",
    "MessageFramer",
    "generate_session_token",
    "generate_endpoint_name",
    "encode_message",
    "decode_message",
    "request_to_dto",
    "result_to_payload",
    "dto_asdict",
]
