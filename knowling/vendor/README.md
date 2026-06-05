# Vendored: Temml

`temml.cjs` is the [Temml](https://temml.org/) LaTeX→MathML library, **MIT License**
(© Ron Kornbluh and contributors), vendored so Knowling can convert LaTeX to
native MathML at compile time without an `npm install` step.

It is a **build-time tool only** — it never ships inside a generated card. Cards
embed the small MathML output, which modern browsers render natively (no runtime
JS, no web fonts).

- `temml.cjs` — the library (require()-able in Node)
- `temml_worker.js` — a tiny persistent stdin/stdout worker driven by
  `knowling/blocks/_temml.py`

Optional: if Node or `temml.cjs` is absent, Knowling falls back to the pure-Python
renderer in `knowling/blocks/_math.py` (a LaTeX subset). Force the fallback with
`KNOWLING_MATH=fallback`.

To update: `curl -fsSL https://unpkg.com/temml@latest/dist/temml.cjs -o temml.cjs`
