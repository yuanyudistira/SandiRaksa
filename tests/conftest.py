"""
Pytest configuration.

Some of our dependencies are native C-extension libraries (spaCy/thinc/blis,
PySide6/Qt, lxml). On Windows these can fault during interpreter shutdown
(STATUS_ACCESS_VIOLATION, 0xC0000005) AFTER the test session has already
finished and reported its result. That turns a fully green run ("1024 passed")
into a non-zero process exit, which fails CI for no real reason.

To make the process exit code reflect the actual test outcome, we flush output
and hard-exit via os._exit() once the session is complete. os._exit() skips the
native/atexit teardown that triggers the shutdown fault, so a passing run exits
0 and a failing run exits non-zero.
"""

import os
import sys


def pytest_sessionfinish(session, exitstatus):
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(int(exitstatus))
