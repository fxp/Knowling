// Persistent Temml worker: reads one JSON request per line on stdin
//   {"id": N, "latex": "...", "display": bool}
// and writes one JSON response per line on stdout
//   {"id": N, "mathml": "<math>…</math>"}
// Used by knowling/blocks/_temml.py to convert LaTeX → MathML at compile time
// (so cards embed native MathML — no runtime JS or fonts). MIT (Temml).
'use strict';
// Keep stdout pristine — ONLY our JSON responses go there. Route any stray
// console output (e.g. Temml warnings) to stderr so it can't desync the protocol.
console.log = console.error;
console.warn = console.error;
console.info = console.error;
const temml = require('./temml.cjs');

let buf = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  buf += chunk;
  let nl;
  while ((nl = buf.indexOf('\n')) >= 0) {
    const line = buf.slice(0, nl);
    buf = buf.slice(nl + 1);
    if (!line.trim()) continue;
    let req;
    try { req = JSON.parse(line); } catch (e) { continue; }
    let mathml = '';
    try {
      mathml = temml.renderToString(String(req.latex || ''), {
        displayMode: !!req.display,
        throwOnError: false,
        annotate: false,
      });
    } catch (e) { mathml = ''; }
    process.stdout.write(JSON.stringify({ id: req.id, mathml: mathml }) + '\n');
  }
});
process.stdin.on('end', () => process.exit(0));
