"""Sprint 6 tests: Tier B IPC protocol (framing, auth, bounds, DTOs)."""

from __future__ import annotations

import pytest

from sandiraksa.clipboard import ipc


class TestTokens:
    def test_session_token_random(self):
        assert ipc.generate_session_token() != ipc.generate_session_token()

    def test_endpoint_name_random_and_prefixed(self):
        name = ipc.generate_endpoint_name()
        assert name.startswith("sandiraksa-clip-")
        assert name != ipc.generate_endpoint_name()


class TestEncodeDecode:
    def test_roundtrip(self):
        token = "tok"
        raw = ipc.encode_message(ipc.MSG_SCAN_REQUEST, token, {"text": "hi"})
        # Strip the 4-byte length prefix for decode.
        body = raw[4:]
        kind, payload = ipc.decode_message(body, expected_token=token)
        assert kind == ipc.MSG_SCAN_REQUEST
        assert payload == {"text": "hi"}

    def test_length_prefix_matches_body(self):
        raw = ipc.encode_message(ipc.MSG_HEARTBEAT, "t", {})
        length = int.from_bytes(raw[:4], "big")
        assert length == len(raw) - 4

    def test_wrong_token_rejected(self):
        raw = ipc.encode_message(ipc.MSG_SCAN_REQUEST, "correct", {"a": 1})
        with pytest.raises(ipc.ProtocolError):
            ipc.decode_message(raw[4:], expected_token="wrong")

    def test_bad_json_rejected(self):
        with pytest.raises(ipc.ProtocolError):
            ipc.decode_message(b"not json", expected_token="t")

    def test_non_object_envelope_rejected(self):
        import json

        body = json.dumps([1, 2, 3]).encode("utf-8")
        with pytest.raises(ipc.ProtocolError):
            ipc.decode_message(body, expected_token="t")

    def test_version_mismatch_rejected(self):
        import json

        body = json.dumps(
            {"protocol_version": 999, "kind": "x", "token": "t", "payload": {}}
        ).encode("utf-8")
        with pytest.raises(ipc.ProtocolError):
            ipc.decode_message(body, expected_token="t")

    def test_encode_oversized_rejected(self):
        huge = "a" * (ipc.MAX_MESSAGE_BYTES + 1000)
        with pytest.raises(ipc.ProtocolError):
            ipc.encode_message(ipc.MSG_SCAN_REQUEST, "t", {"text": huge})


class TestFramer:
    def test_single_message(self):
        raw = ipc.encode_message(ipc.MSG_HEARTBEAT, "t", {"n": 1})
        framer = ipc.MessageFramer()
        bodies = framer.feed(raw)
        assert len(bodies) == 1
        kind, payload = ipc.decode_message(bodies[0], "t")
        assert kind == ipc.MSG_HEARTBEAT
        assert payload == {"n": 1}

    def test_split_across_chunks(self):
        raw = ipc.encode_message(ipc.MSG_HEARTBEAT, "t", {"n": 2})
        framer = ipc.MessageFramer()
        # Feed byte-by-byte; only the final feed completes the message.
        out = []
        for i in range(len(raw)):
            out += framer.feed(raw[i : i + 1])
        assert len(out) == 1

    def test_multiple_messages_in_one_chunk(self):
        a = ipc.encode_message(ipc.MSG_HEARTBEAT, "t", {"i": 1})
        b = ipc.encode_message(ipc.MSG_HEARTBEAT, "t", {"i": 2})
        framer = ipc.MessageFramer()
        bodies = framer.feed(a + b)
        assert len(bodies) == 2

    def test_declared_length_over_max_rejected(self):
        # Forge a length prefix exceeding the max without allocating the body.
        prefix = (ipc.MAX_MESSAGE_BYTES + 1).to_bytes(4, "big")
        framer = ipc.MessageFramer()
        with pytest.raises(ipc.ProtocolError):
            framer.feed(prefix + b"\x00\x00")


class TestDTOs:
    def test_scan_request_dto_defaults_version(self):
        dto = ipc.ScanRequestDTO(
            request_id="q",
            generation=1,
            fingerprint="fp",
            text="hi",
            created_monotonic=0.0,
        )
        assert dto.protocol_version == ipc.PROTOCOL_VERSION

    def test_request_to_dto(self):
        from sandiraksa.clipboard.models import ScanRequest

        req = ScanRequest(
            request_id="q",
            generation=7,
            fingerprint="fp",
            text="secret",
            created_monotonic=1.0,
        )
        dto = ipc.request_to_dto(req)
        assert dto.generation == 7
        assert dto.text == "secret"

    def test_result_to_payload(self):
        from sandiraksa.clipboard.models import (
            ClipboardProtectionResult,
            ClipboardRiskLevel,
            Finding,
        )

        result = ClipboardProtectionResult(
            result_id="r",
            generation=2,
            source_fingerprint="fp",
            created_monotonic=0.0,
            expires_monotonic=30.0,
            risk_level=ClipboardRiskLevel.HIGH,
            findings=(Finding("ID_NIK", 0, 3, 0.9, "high", "abc"),),
            safe_text="[NIK_REDACTED]",
            processing_ms=42,
        )
        payload = ipc.result_to_payload(result)
        assert payload["risk_level"] == "high"
        assert payload["safe_text"] == "[NIK_REDACTED]"
        assert payload["processing_ms"] == 42
        assert payload["findings"][0]["entity_type"] == "ID_NIK"
