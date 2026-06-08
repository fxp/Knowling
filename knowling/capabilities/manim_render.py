"""Manim render capability — 3Blue1Brown-style animations (optional ``[manim]``).

A ``manim`` block carries a ManimCommunity ``Scene`` script; at compile time we
render it to MP4 via the manim CLI (FFmpeg under the hood) and inline the result
as a ``data:`` URI so the card stays a single file.

Heavy + offline by design (see docs/seam-contract-draft.md tiering): this is the
one place Knowling shells out to a real renderer. If the toolchain is absent the
caller falls back to a placeholder, so the pipeline never hard-fails.

Resolution order for the manim binary:
  1. ``KNOWLING_MANIM_BIN`` env
  2. ``<repo>/.venv-manim/bin/manim`` (the isolated toolchain venv)
  3. ``manim`` on PATH
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[2]
_QUALITY = {"low": "-ql", "medium": "-qm", "high": "-qh"}


def manim_bin() -> Optional[str]:
    env = os.environ.get("KNOWLING_MANIM_BIN")
    if env and Path(env).exists():
        return env
    venv = _REPO_ROOT / ".venv-manim" / "bin" / "manim"
    if venv.exists():
        return str(venv)
    from shutil import which
    return which("manim")


def available() -> bool:
    return manim_bin() is not None


def render(
    script: str,
    scene: str,
    *,
    quality: str = "low",
    timeout: float = 180.0,
) -> Tuple[Optional[bytes], str]:
    """Render a ManimCE ``Scene`` script → MP4 bytes.

    Returns ``(mp4_bytes, "")`` on success, or ``(None, error_message)``. Never
    raises — the compile path treats a None result as "show a placeholder"."""
    binary = manim_bin()
    if not binary:
        return None, "manim not installed (optional [manim] extra)"
    if not script or not scene:
        return None, "manim block needs both `script` and `scene`"

    qflag = _QUALITY.get(quality, "-ql")
    with tempfile.TemporaryDirectory(prefix="knowling-manim-") as td:
        tdp = Path(td)
        (tdp / "scene.py").write_text(script, encoding="utf-8")
        cmd = [binary, qflag, "--format=mp4", "--media_dir", str(tdp / "media"),
               "--disable_caching", str(tdp / "scene.py"), scene]
        try:
            proc = subprocess.run(cmd, cwd=td, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, f"manim render timed out after {timeout:.0f}s"
        except Exception as e:  # pragma: no cover - environment
            return None, f"manim render failed to start: {e}"
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "")[-600:]
            return None, f"manim exited {proc.returncode}:\n{tail}"
        mp4s = sorted((tdp / "media" / "videos").rglob(f"{scene}.mp4"))
        if not mp4s:
            mp4s = sorted((tdp / "media").rglob("*.mp4"))
        if not mp4s:
            return None, "manim produced no mp4"
        return mp4s[-1].read_bytes(), ""


def render_data_uri(script: str, scene: str, **kw) -> Tuple[Optional[str], str]:
    """Like :func:`render` but returns a ``data:video/mp4;base64,…`` URI."""
    data, err = render(script, scene, **kw)
    if data is None:
        return None, err
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:video/mp4;base64,{b64}", ""


if __name__ == "__main__":  # tiny self-test: python -m knowling.capabilities.manim_render
    demo = (
        "from manim import *\n"
        "class Demo(Scene):\n"
        "    def construct(self):\n"
        "        ax = Axes(x_range=[-3,3,1], y_range=[-1,9,2], x_length=7, y_length=4)\n"
        "        g = ax.plot(lambda x: x*x, color=BLUE)\n"
        "        self.play(Create(ax)); self.play(Create(g)); self.wait(0.2)\n"
    )
    uri, err = render_data_uri(demo, "Demo")
    print("OK", len(uri), "bytes" if uri else "", "| err:", err, file=sys.stderr)
