"""
Detection worker supervisor (Tier B) - design 33, 34, 35, 36.

Owns the local IPC server and the worker PROCESS, and applies the resilience
policy from :mod:`sandiraksa.clipboard.resilience`:

  * start the worker, wait for MSG_READY (design 33);
  * heartbeat every 2 s; mark unhealthy after 6 s (design 34);
  * on crash/unresponsive, restart with backoff 1/2/5/15 s, then open the
    circuit (design 35);
  * circuit breaker on repeated scan failures/crashes -> ERROR, automatic
    scanning paused, main app stays alive (design 36).

If the worker crashes: worker dies -> GUI stays alive -> guard goes DEGRADED
-> supervisor restarts -> health check -> READY (design 6.2). This provides the
native-crash isolation that Tier A's QThread cannot (design 38).
"""

from __future__ import annotations

import logging
import sys
import time

from PySide6.QtCore import QObject, QProcess, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from sandiraksa.clipboard import ipc
from sandiraksa.clipboard.resilience import (
    HEARTBEAT_INTERVAL_S,
    CircuitBreaker,
    HeartbeatHealth,
    backoff_for_attempt,
    heartbeat_health,
)

logger = logging.getLogger("sandiraksa.clipboard")


class DetectionWorkerSupervisor(QObject):
    """Supervises the out-of-process detector with health + restart policy."""

    #: Emitted with a scan result payload dict.
    resultReady = Signal(object)
    #: Emitted with a sanitized failure payload dict.
    scanFailed = Signal(object)
    #: Emitted when the guard enters DEGRADED (worker down, restarting).
    degraded = Signal()
    #: Emitted when the worker becomes READY again.
    ready = Signal()
    #: Emitted when the circuit opens (ERROR; automatic scanning paused).
    circuitOpen = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._server: QLocalServer | None = None
        self._conn: QLocalSocket | None = None
        self._process: QProcess | None = None
        self._framer = ipc.MessageFramer()

        self._token = ipc.generate_session_token()
        self._endpoint = ipc.generate_endpoint_name()

        self._breaker = CircuitBreaker()
        self._restart_attempt = 0
        self._last_ack: float | None = None
        self._stopping = False
        self._worker_ready = False

        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(int(HEARTBEAT_INTERVAL_S * 1000))
        self._heartbeat_timer.timeout.connect(self._tick_heartbeat)

        self._restart_timer = QTimer(self)
        self._restart_timer.setSingleShot(True)
        self._restart_timer.timeout.connect(self._spawn_worker)

    # -- lifecycle -------------------------------------------------------
    def start(self) -> bool:
        """Start the IPC server and launch the worker. Returns success."""
        self._stopping = False
        self._server = QLocalServer(self)
        # Remove any stale endpoint, then listen (local-only; design 29).
        QLocalServer.removeServer(self._endpoint)
        if not self._server.listen(self._endpoint):
            logger.warning("clipboard supervisor: failed to listen on endpoint")
            return False
        self._server.newConnection.connect(self._on_new_connection)
        self._spawn_worker()
        return True

    def stop(self) -> None:
        """Ordered shutdown: ask worker to stop, then terminate (design 66)."""
        self._stopping = True
        self._heartbeat_timer.stop()
        self._restart_timer.stop()
        self._send(ipc.MSG_SHUTDOWN, {})
        if self._process is not None:
            if not self._process.waitForFinished(2000):
                self._process.kill()
                self._process.waitForFinished(1000)
            self._process = None
        if self._conn is not None:
            self._conn.disconnectFromServer()
            self._conn = None
        if self._server is not None:
            self._server.close()
            self._server = None

    # -- scanning --------------------------------------------------------
    def submit_scan(self, request) -> bool:
        """Send a scan request DTO to the worker. Returns False if not ready."""
        if self._breaker.is_open or not self._worker_ready:
            return False
        dto = ipc.request_to_dto(request)
        return self._send(ipc.MSG_SCAN_REQUEST, ipc.dto_asdict(dto))

    def retry(self) -> None:
        """Manual recovery from an open circuit (design 36 Retry)."""
        self._breaker.reset()
        self._restart_attempt = 0
        self._spawn_worker()

    # -- worker process --------------------------------------------------
    def _spawn_worker(self) -> None:
        if self._stopping or self._breaker.is_open:
            return
        self._worker_ready = False
        self._process = QProcess(self)
        self._process.setProgram(sys.executable)
        self._process.setArguments(
            [
                "-m",
                "sandiraksa.clipboard.worker_process",
                "--endpoint",
                self._endpoint,
                "--token",
                self._token,
            ]
        )
        self._process.finished.connect(self._on_process_finished)
        self._process.start()
        logger.info("clipboard worker process starting")

    def _on_process_finished(self, exit_code: int, _status) -> None:
        if self._stopping:
            return
        now = time.monotonic()
        self._worker_ready = False
        self.degraded.emit()
        # Count as a crash for the breaker (design 36).
        if self._breaker.record_crash(now):
            logger.warning("clipboard worker: circuit opened (crashes)")
            self.circuitOpen.emit()
            return
        self._schedule_restart()

    def _schedule_restart(self) -> None:
        self._restart_attempt += 1
        delay = backoff_for_attempt(self._restart_attempt)
        if delay is None:
            # Backoff schedule exhausted -> open circuit (design 35).
            self.circuitOpen.emit()
            return
        logger.info(
            "clipboard worker restart #%d in %.0fs", self._restart_attempt, delay
        )
        self._restart_timer.start(int(delay * 1000))

    # -- IPC -------------------------------------------------------------
    def _on_new_connection(self) -> None:
        if self._server is None:
            return
        conn = self._server.nextPendingConnection()
        if conn is None:
            return
        self._conn = conn
        self._conn.readyRead.connect(self._on_ready_read)

    def _on_ready_read(self) -> None:
        if self._conn is None:
            return
        data = bytes(self._conn.readAll().data())
        try:
            bodies = self._framer.feed(data)
        except ipc.ProtocolError:
            self._conn.disconnectFromServer()
            return
        for body in bodies:
            try:
                kind, payload = ipc.decode_message(body, self._token)
            except ipc.ProtocolError:
                # Unauthenticated / malformed -> refuse (design 29).
                self._conn.disconnectFromServer()
                return
            self._dispatch(kind, payload)

    def _dispatch(self, kind: str, payload: dict) -> None:
        now = time.monotonic()
        if kind == ipc.MSG_READY:
            self._worker_ready = True
            self._restart_attempt = 0
            self._last_ack = now
            self._heartbeat_timer.start()
            self.ready.emit()
        elif kind == ipc.MSG_HEARTBEAT_ACK:
            self._last_ack = now
        elif kind == ipc.MSG_SCAN_RESULT:
            self.resultReady.emit(payload)
        elif kind == ipc.MSG_SCAN_FAILURE:
            if self._breaker.record_scan_failure(now):
                logger.warning("clipboard worker: circuit opened (scan failures)")
                self.circuitOpen.emit()
            self.scanFailed.emit(payload)

    def _send(self, kind: str, payload: dict) -> bool:
        if self._conn is None:
            return False
        try:
            self._conn.write(ipc.encode_message(kind, self._token, payload))
            self._conn.flush()
            return True
        except ipc.ProtocolError:
            return False

    # -- heartbeat -------------------------------------------------------
    def _tick_heartbeat(self) -> None:
        now = time.monotonic()
        health = heartbeat_health(self._last_ack, now)
        if health == HeartbeatHealth.UNRESPONSIVE:
            logger.warning("clipboard worker unresponsive; treating as crash")
            # Force a restart cycle; killing the process triggers finished().
            if self._process is not None:
                self._process.kill()
            return
        # Otherwise send a heartbeat ping.
        self._send(ipc.MSG_HEARTBEAT, {"ts": time.time()})


__all__ = ["DetectionWorkerSupervisor"]
