"""Optional Temml backend — compile-time LaTeX → MathML (self-contained).

Runs the vendored Temml (knowling/vendor/temml.cjs) inside a persistent Node
worker. The card embeds native MathML, so there's no runtime JS or font payload
— modern browsers (Chrome/Edge/Firefox/Safari) render MathML natively.

Entirely optional: if Node or the vendored Temml is missing, ``available()``
returns False and the caller falls back to the pure-Python renderer in _math.
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import threading
from typing import Optional

_VENDOR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "vendor"))
_WORKER = os.path.join(_VENDOR, "temml_worker.js")
_TEMML = os.path.join(_VENDOR, "temml.cjs")


class _TemmlWorker:
    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._ok: Optional[bool] = None
        self._counter = 0

    def available(self) -> bool:
        if self._ok is None:
            disabled = os.environ.get("KNOWLING_MATH", "auto").lower() == "fallback"
            self._ok = (not disabled and bool(shutil.which("node"))
                        and os.path.exists(_TEMML) and os.path.exists(_WORKER))
        return self._ok

    def _ensure(self) -> bool:
        if self._proc is not None and self._proc.poll() is None:
            return True
        if not self.available():
            return False
        try:
            self._proc = subprocess.Popen(
                ["node", _WORKER], cwd=_VENDOR,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, bufsize=1,
            )
            atexit.register(self.close)
            return True
        except Exception:
            self._ok = False
            return False

    def render(self, latex: str, display: bool = False) -> Optional[str]:
        with self._lock:
            if not self._ensure():
                return None
            self._counter += 1
            rid = self._counter
            try:
                self._proc.stdin.write(
                    json.dumps({"id": rid, "latex": latex, "display": bool(display)}) + "\n")
                self._proc.stdin.flush()
                # drain to the response for THIS id — skips any stray/stale line,
                # so the request/response stream can't permanently desync
                for _ in range(64):
                    line = self._proc.stdout.readline()
                    if not line:
                        self._kill()  # worker died → restart next call
                        return None
                    try:
                        data = json.loads(line)
                    except Exception:
                        continue  # non-JSON noise on stdout; skip
                    if data.get("id") == rid:
                        return data.get("mathml") or None
                return None
            except Exception:
                # transient failure on ONE formula: drop the worker so the next
                # call restarts it; fall back for this formula only (don't disable)
                self._kill()
                return None

    def _kill(self) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None

    def close(self) -> None:
        with self._lock:
            if self._proc is not None:
                try:
                    self._proc.stdin.close()
                except Exception:
                    pass
                self._kill()


_worker = _TemmlWorker()


def available() -> bool:
    return _worker.available()


def render(latex: str, display: bool = False) -> Optional[str]:
    return _worker.render(latex, display)
