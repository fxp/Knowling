"""Knowling CLI (design §8.1) — dual output: rich (human) / json (agent).

Commands:
  knowling plan    "<title>" [...]          → KnowlingSpec (no compile)
  knowling compile <spec.json>              → Knowling artifact
  knowling gen     "<title>" [...]          → plan + compile + assemble
  knowling blocks                           → list implemented block types

``-f json`` emits a line-delimited JSON event stream (progress / cost / done);
``-f rich`` prints colored human output. Mirrors DeepTutor's agent-native CLI.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from . import __version__, blocks
from .engine import Config, compile_blocks, finalize, generate_knowling, plan_spec
from .schema import KnowledgePoint, KnowlingSpec

# ─────────────────────────── output helpers ───────────────────────────

_C = {
    "reset": "\033[0m", "dim": "\033[2m", "bold": "\033[1m",
    "blue": "\033[34m", "green": "\033[32m", "yellow": "\033[33m",
    "red": "\033[31m", "cyan": "\033[36m",
}


def _supports_color() -> bool:
    return sys.stdout.isatty()


def make_emitter(fmt: str):
    """Return an ``emit(kind, payload)`` sink for the chosen output format."""
    color = _supports_color() and fmt == "rich"

    def c(name: str, s: str) -> str:
        return f"{_C[name]}{s}{_C['reset']}" if color else s

    def emit(kind: str, payload: dict) -> None:
        if fmt == "json":
            sys.stdout.write(json.dumps({"event": kind, **payload}, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            return
        # rich
        if kind == "stage":
            st, status = payload.get("stage"), payload.get("status")
            if status == "start":
                extra = ""
                if st == "compile":
                    extra = f" {payload.get('i')}/{payload.get('n')} " + c("dim", payload.get("type", ""))
                print(c("blue", f"▸ {st}") + extra + c("dim", " …"))
            elif status == "done" and st in ("plan", "assemble"):
                detail = ""
                if st == "plan":
                    detail = c("dim", "  blocks: " + ", ".join(payload.get("blocks", [])))
                if st == "assemble" and payload.get("entry"):
                    detail = c("dim", "  → " + payload["entry"])
                print(c("green", f"  ✓ {st}") + detail)
        elif kind == "warn":
            print(c("yellow", f"  ! {payload.get('stage')} {payload.get('block_id','')}: {payload.get('error','')}"))
        elif kind == "error":
            print(c("red", f"  ✗ {payload.get('msg','')}"))
        elif kind == "done":
            print(
                c("bold", "✓ done ")
                + c("cyan", payload.get("id", ""))
                + c("dim", f"  status={payload.get('status')}  cost=${payload.get('cost_usd')}")
            )
            if payload.get("entry"):
                print(c("dim", "  artifact: ") + payload["entry"])

    return emit


# ─────────────────────────── kp construction ───────────────────────────


def _kp_from_args(args) -> KnowledgePoint:
    kp_id = args.id or _slug(args.title)
    return KnowledgePoint(
        id=kp_id,
        title=args.title,
        description=args.description or "",
        learning_objectives=[o.strip() for o in (args.objectives or "").split(",") if o.strip()],
        difficulty=args.difficulty,
        audience=args.audience,
        prerequisites=[p.strip() for p in (args.prerequisites or "").split(",") if p.strip()],
        followups=[p.strip() for p in (args.followups or "").split(",") if p.strip()],
    )


def _slug(title: str) -> str:
    import re

    s = re.sub(r"\s+", "-", title.strip().lower())
    s = re.sub(r"[^0-9a-z一-鿿\-.]", "", s)
    return s or "kp"


def _cfg_from_args(args, quiet: bool = False) -> Config:
    return Config(
        provider_name=getattr(args, "provider", "auto"),
        model=getattr(args, "model", None),
        render_target=getattr(args, "format_render", "html"),
        approval=getattr(args, "approval", "auto"),
        quiet=quiet,
    )


# ─────────────────────────── commands ───────────────────────────


def cmd_plan(args) -> int:
    emit = make_emitter(args.format)
    cfg = _cfg_from_args(args, quiet=(args.format == "json"))
    kp = _kp_from_args(args)
    spec, _call = plan_spec(kp, cfg, emit)
    spec_json = json.dumps(spec.to_dict(), ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(spec_json)
        emit("info", {"msg": "spec written", "path": args.output})
    else:
        # spec itself goes to stdout (so `knowling plan ... > spec.json` works)
        if args.format == "json":
            emit("info", {"msg": "spec", "spec": spec.to_dict()})
        else:
            print(spec_json)
    return 0


def cmd_compile(args) -> int:
    emit = make_emitter(args.format)
    with open(args.spec, "r", encoding="utf-8") as f:
        spec = KnowlingSpec.from_dict(json.load(f))
    if args.format_render:
        spec.render_target = args.format_render
    cfg = _cfg_from_args(args, quiet=(args.format == "json"))
    cfg.render_target = spec.render_target
    # reconstruct a minimal kp for the compiler context
    kp = KnowledgePoint(id=spec.knowledge_point_id, title=args.title or spec.knowledge_point_id)
    fragments, calls = compile_blocks(spec, kp, cfg, emit)
    knowling = finalize(spec, kp, fragments, calls, cfg, out_path=args.output, emit=emit)
    total = round(sum(c.cost_usd for c in calls), 6)
    emit("done", {"id": knowling.id, "status": knowling.status, "cost_usd": total,
                  "entry": knowling.artifact.entry})
    if not args.output:
        print(knowling._html)  # type: ignore[attr-defined]
    return 0


def cmd_gen(args) -> int:
    emit = make_emitter(args.format)
    cfg = _cfg_from_args(args, quiet=(args.format == "json"))
    kp = _kp_from_args(args)
    out_path = args.output
    if out_path and out_path.endswith("/"):
        out_path = out_path + _slug(args.title) + (".html" if cfg.render_target == "html" else ".tsx")
    knowling = generate_knowling(kp, cfg, out_path=out_path, emit=emit)
    if args.format == "json":
        emit("info", {"msg": "knowling", "knowling": knowling.to_dict()})
    elif not out_path:
        print(knowling._html)  # type: ignore[attr-defined]
    return 0


def cmd_blocks(args) -> int:
    if args.format == "json":
        print(json.dumps({"implemented": list(blocks.IMPLEMENTED),
                          "declared": list(__import__("knowling.schema", fromlist=["BLOCK_TYPES"]).BLOCK_TYPES)},
                         ensure_ascii=False))
    else:
        from .schema import BLOCK_TYPES
        print("implemented (P0):", ", ".join(blocks.IMPLEMENTED))
        print("declared:        ", ", ".join(BLOCK_TYPES))
    return 0


# ─────────────────────────── argparse ───────────────────────────


def _add_common(p: argparse.ArgumentParser, with_kp: bool = True) -> None:
    p.add_argument("-f", "--format", choices=["rich", "json"], default="rich",
                   help="output mode: rich (human) | json (line-delimited events)")
    p.add_argument("--format-render", dest="format_render", choices=["html", "react"],
                   default="html", help="artifact render target")
    p.add_argument("--provider", default="auto", help="auto | zhipu | mock")
    p.add_argument("--model", default=None, help="override model id")
    p.add_argument("-o", "--output", default=None, help="output path (file or dir/)")
    if with_kp:
        p.add_argument("--id", default=None, help="stable knowledge-point id")
        p.add_argument("--description", default=None)
        p.add_argument("--objectives", default=None, help="comma-separated")
        p.add_argument("--difficulty", choices=["intro", "core", "advanced"], default="core")
        p.add_argument("--audience", default=None)
        p.add_argument("--prerequisites", default=None, help="comma-separated kp ids")
        p.add_argument("--followups", default=None, help="comma-separated kp ids")
        p.add_argument("--approval", choices=["auto", "human"], default="auto")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="knowling", description="Generate self-contained interactive learning components.")
    parser.add_argument("-V", "--version", action="version", version=f"knowling {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="knowledge point → KnowlingSpec (no compile)")
    p_plan.add_argument("title")
    _add_common(p_plan)
    p_plan.set_defaults(func=cmd_plan)

    p_comp = sub.add_parser("compile", help="KnowlingSpec → Knowling artifact")
    p_comp.add_argument("spec", help="path to a KnowlingSpec JSON")
    p_comp.add_argument("--title", default=None)
    _add_common(p_comp, with_kp=False)
    p_comp.set_defaults(func=cmd_compile)

    p_gen = sub.add_parser("gen", help="plan + compile + assemble (full P0 loop)")
    p_gen.add_argument("title")
    _add_common(p_gen)
    p_gen.set_defaults(func=cmd_gen)

    p_blk = sub.add_parser("blocks", help="list block types")
    p_blk.add_argument("-f", "--format", choices=["rich", "json"], default="rich")
    p_blk.set_defaults(func=cmd_blocks)

    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        emit = make_emitter(getattr(args, "format", "rich"))
        emit("error", {"msg": f"{type(e).__name__}: {e}"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
