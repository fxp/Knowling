"""Knowling HTTP API (seam contract §⑤, ROADMAP P4) — stdlib-only, zero-dep.

A thin JSON service over the engine so a host orchestrator (the adaptive-learning
layer) can drive Knowling units over HTTP. No framework dependency: built on
``http.server`` so the core stays stdlib-only.

Run:
    python -m knowling.server --port 8765         # or: knowling api --port 8765

Endpoints (all JSON; POST bodies are JSON objects):
    GET  /v1/health                  → {ok, provider, manim, version}
    GET  /v1/blocks                  → {blocks: [...]}
    POST /v1/knowling/plan           {kp, ground?, allow_manim?}        → {spec}
    POST /v1/knowling/compile        {spec, kp, qa?}                    → {knowling, html}
    POST /v1/knowling/generate       {kp, qa?, allow_manim?, ground?}   → {knowling, html}
    POST /v1/knowling/refine         {spec, kp, instruction}           → {knowling, html, summary, changes}
    POST /v1/knowling/reteach        {spec, kp, quiz}                  → {knowling, html, summary}
    POST /v1/knowling/quiz-eval      {kp_id, quiz, knowling_id?, pass_threshold?} → {mastery}

Common request fields: ``provider`` ("auto"|"zhipu"|"mock"), ``qa`` (bool, default
false — QA is slow + needs a browser/VLM), ``allow_manim`` (bool), ``ground``
(list of grounding snippets).
"""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Tuple

from . import __version__, blocks as _blocks
from .engine import (
    Config, compile_spec, generate_knowling, plan_spec, refine_knowling, reteach_knowling,
)
from .capabilities import manim_render
from .providers import get_provider
from .schema import KnowledgePoint, KnowlingSpec, MasteryResult, QuizOutcome, SourceRef


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# ─────────────────────────── request → engine objects ───────────────────────────


def _cfg(body: Dict[str, Any]) -> Config:
    from .capabilities.qa import QAConfig
    qa = bool(body.get("qa", False))
    return Config(
        provider_name=body.get("provider", "auto"),
        quiet=True,
        allow_manim=bool(body.get("allow_manim", False)),
        qa_enabled=qa,
        qa=QAConfig(sandbox_name=body.get("sandbox", "playwright" if qa else "static")),
    )


def _kp(body: Dict[str, Any]) -> KnowledgePoint:
    d = body.get("kp")
    if not isinstance(d, dict):
        raise ApiError(400, "body.kp (object) is required")
    if not d.get("id") or not d.get("title"):
        raise ApiError(400, "kp.id and kp.title are required")
    kp = KnowledgePoint.from_dict(d)
    ground = body.get("ground")
    if ground:
        kp.source_refs = [SourceRef(id=f"g{i}", snippet=str(s)) for i, s in enumerate(ground)]
    return kp


def _spec(body: Dict[str, Any]) -> KnowlingSpec:
    d = body.get("spec")
    if not isinstance(d, dict):
        raise ApiError(400, "body.spec (object) is required")
    return KnowlingSpec.from_dict(d)


def _knowling_resp(k, **extra) -> Dict[str, Any]:
    return {"knowling": k.to_dict(), "html": getattr(k, "_html", ""), **extra}


# ─────────────────────────── route handlers ───────────────────────────


def h_plan(body):
    kp = _kp(body)
    cfg = _cfg(body)
    spec, _call = plan_spec(kp, cfg)
    return {"spec": spec.to_dict()}


def h_generate(body):
    kp = _kp(body)
    cfg = _cfg(body)
    k = generate_knowling(kp, cfg)
    return _knowling_resp(k)


def h_compile(body):
    kp = _kp(body)
    spec = _spec(body)
    cfg = _cfg(body)
    k = compile_spec(spec, kp, cfg)
    return _knowling_resp(k)


def h_refine(body):
    kp = _kp(body)
    spec = _spec(body)
    instr = body.get("instruction")
    if not instr:
        raise ApiError(400, "body.instruction is required")
    k, summary, changes = refine_knowling(spec, kp, str(instr), _cfg(body))
    return _knowling_resp(k, summary=summary, changes=changes)


def h_reteach(body):
    kp = _kp(body)
    spec = _spec(body)
    quiz = body.get("quiz")
    if not isinstance(quiz, dict):
        raise ApiError(400, "body.quiz (QuizOutcome object) is required")
    k, summary = reteach_knowling(spec, kp, QuizOutcome.from_dict(quiz), _cfg(body))
    return _knowling_resp(k, summary=summary)


def h_quiz_eval(body):
    quiz = body.get("quiz")
    if not isinstance(quiz, dict):
        raise ApiError(400, "body.quiz (QuizOutcome object) is required")
    mr = MasteryResult.from_quiz(
        body.get("kp_id", ""),
        QuizOutcome.from_dict(quiz),
        knowling_id=body.get("knowling_id", ""),
        pass_threshold=float(body.get("pass_threshold", 0.8)),
    )
    return {"mastery": mr.to_dict()}


def h_health(_body):
    return {"ok": True, "version": __version__,
            "provider": "zhipu" if get_provider("auto", quiet=True).name == "zhipu" else "mock",
            "manim": manim_render.available()}


def h_blocks(_body):
    return {"blocks": list(_blocks.IMPLEMENTED)}


POST_ROUTES: Dict[str, Callable[[dict], dict]] = {
    "/v1/knowling/plan": h_plan,
    "/v1/knowling/generate": h_generate,
    "/v1/knowling/compile": h_compile,
    "/v1/knowling/refine": h_refine,
    "/v1/knowling/reteach": h_reteach,
    "/v1/knowling/quiz-eval": h_quiz_eval,
}
GET_ROUTES: Dict[str, Callable[[dict], dict]] = {
    "/v1/health": h_health,
    "/v1/blocks": h_blocks,
}


# ─────────────────────────── http plumbing ───────────────────────────


class Handler(BaseHTTPRequestHandler):
    server_version = "Knowling/" + __version__

    def _send(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _dispatch(self, routes, body):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        fn = routes.get(path) or routes.get(self.path.split("?", 1)[0])
        if fn is None:
            self._send(404, {"error": f"no route {path}"})
            return
        try:
            self._send(200, fn(body))
        except ApiError as e:
            self._send(e.status, {"error": e.message})
        except (KeyError, ValueError) as e:
            self._send(400, {"error": str(e)})
        except Exception as e:  # pragma: no cover - defensive
            self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def _authed(self) -> bool:
        """If KNOWLING_API_TOKEN is set, POST routes require it (Bearer or X-API-Key).
        GET health/blocks stay open. Unset → no auth (local dev)."""
        token = os.environ.get("KNOWLING_API_TOKEN")
        if not token:
            return True
        auth = self.headers.get("Authorization", "")
        given = auth[7:] if auth.startswith("Bearer ") else self.headers.get("X-API-Key", "")
        return given == token

    def do_OPTIONS(self):
        self._send(200, {"ok": True})

    def do_GET(self):
        self._dispatch(GET_ROUTES, {})

    def do_POST(self):
        if not self._authed():
            self._send(401, {"error": "missing or invalid API token"})
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n) if n else b"{}"
            body = json.loads(raw or b"{}")
            if not isinstance(body, dict):
                raise ValueError("request body must be a JSON object")
        except (ValueError, json.JSONDecodeError) as e:
            self._send(400, {"error": f"invalid JSON body: {e}"})
            return
        self._dispatch(POST_ROUTES, body)

    def log_message(self, *args):  # quiet by default
        pass


def serve(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), Handler)
    return httpd


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="knowling-api", description="Knowling HTTP API")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)
    httpd = serve(args.host, args.port)
    prov = "zhipu" if get_provider("auto", quiet=True).name == "zhipu" else "mock(offline)"
    print(f"Knowling API v{__version__} on http://{args.host}:{args.port}  "
          f"(provider: {prov}, manim: {manim_render.available()})")
    print("  POST /v1/knowling/{plan,generate,compile,refine,reteach,quiz-eval} · GET /v1/{health,blocks}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
