"""Knowling Studio — a local web app that wraps a knowledge card with an AI chat.

The card (left) is a fixed, self-contained state. The chat (right) lives OUTSIDE
the card: you tell it "太难了" / "讲深点" / "和导数是什么关系？" and it feeds the
current card's spec + your request to the model, generates a NEW card, and swaps
it in. The API key stays server-side; cards remain self-contained HTML.

Run:  knowling serve "链式法则" --objectives "..." [--port 8799]
"""

from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from .engine import Config, generate_knowling, refine_knowling
from .schema import KnowledgePoint, KnowlingSpec


class StudioState:
    def __init__(self, kp: KnowledgePoint, cfg: Config) -> None:
        self.kp = kp
        self.cfg = cfg
        self.spec: Optional[KnowlingSpec] = None
        self.card_html = ""
        self.version = 0
        self.lock = threading.Lock()
        self.qa = {}
        self.fidelity = {}

    def _store(self, k) -> None:
        self.spec = k.spec
        self.card_html = getattr(k, "_html", "")
        self.version += 1
        self.qa = k.qa.to_dict()
        self.fidelity = getattr(k, "_fidelity", {})

    def generate(self):
        with self.lock:
            k = generate_knowling(self.kp, self.cfg)
            self._store(k)
            return k

    def refine(self, instruction: str):
        with self.lock:
            if self.spec is None:
                self.generate()
            k, summary = refine_knowling(self.spec, self.kp, instruction, self.cfg)
            self._store(k)
            return k, summary


# ─────────────────────────── studio page ───────────────────────────

_PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Knowling Studio · {title}</title>
<style>
:root{{--bg:#0f1117;--panel:#171a21;--fg:#e6e9ef;--muted:#9aa3b2;--accent:#6c8cff;--accent2:#ff8a4c;--border:#262b36;--ok:#3fb950;}}
*{{box-sizing:border-box;}}
html,body{{height:100%;margin:0;}}
body{{background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,"Segoe UI","PingFang SC",sans-serif;display:flex;flex-direction:column;}}
header{{padding:12px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px;}}
header h1{{font-size:17px;margin:0;}}
header h1 .l{{background:linear-gradient(90deg,var(--accent),var(--accent2));-webkit-background-clip:text;background-clip:text;color:transparent;}}
header .kp{{color:var(--muted);font-size:13px;}}
header .qa{{margin-left:auto;color:var(--muted);font-size:12px;}}
.main{{flex:1;display:flex;min-height:0;}}
.card-pane{{flex:1.6;background:#fff;min-width:0;}}
.card-pane iframe{{width:100%;height:100%;border:0;}}
.chat{{flex:1;max-width:440px;min-width:320px;display:flex;flex-direction:column;border-left:1px solid var(--border);background:var(--panel);}}
.msgs{{flex:1;overflow-y:auto;padding:18px;display:flex;flex-direction:column;gap:12px;}}
.msg{{padding:10px 13px;border-radius:12px;max-width:90%;white-space:pre-wrap;}}
.msg.user{{align-self:flex-end;background:var(--accent);color:#fff;border-bottom-right-radius:3px;}}
.msg.bot{{align-self:flex-start;background:#21262d;border:1px solid var(--border);border-bottom-left-radius:3px;}}
.msg.bot.sys{{color:var(--muted);font-size:13px;background:transparent;border:0;}}
.msg.err{{align-self:flex-start;background:#3a1d1d;color:#ffb3b3;border:1px solid #5a2a2a;}}
.chips{{display:flex;flex-wrap:wrap;gap:7px;padding:0 18px 10px;}}
.chip{{font:inherit;font-size:13px;padding:6px 12px;border:1px solid var(--border);border-radius:999px;background:#1c2129;color:var(--fg);cursor:pointer;}}
.chip:hover{{border-color:var(--accent);}}
.inputbar{{display:flex;gap:8px;padding:14px 18px;border-top:1px solid var(--border);}}
.inputbar input{{flex:1;padding:11px 14px;border:1px solid var(--border);border-radius:10px;background:#0f1117;color:var(--fg);font:inherit;}}
.inputbar button{{padding:11px 18px;border:0;border-radius:10px;background:var(--accent);color:#fff;font:inherit;cursor:pointer;}}
.inputbar button:disabled{{opacity:.5;cursor:default;}}
.spin{{display:inline-block;width:13px;height:13px;border:2px solid var(--muted);border-top-color:transparent;border-radius:50%;animation:s .8s linear infinite;vertical-align:-2px;margin-right:6px;}}
@keyframes s{{to{{transform:rotate(360deg);}}}}
</style></head>
<body>
<header>
  <h1>Know<span class="l">ling</span> Studio</h1>
  <span class="kp">{title}</span>
  <span class="qa" id="qa"></span>
</header>
<div class="main">
  <div class="card-pane"><iframe id="card" src="/card?v=0" title="learning card"></iframe></div>
  <div class="chat">
    <div class="msgs" id="msgs">
      <div class="msg bot sys">这是「{title}」的学习卡。在下面告诉我你的想法，我会据此生成一张新的卡片。</div>
    </div>
    <div class="chips">
      <button class="chip">太难了，简单点</button>
      <button class="chip">讲深一点</button>
      <button class="chip">举个具体例子</button>
      <button class="chip">这个和相关知识点是什么关系？</button>
    </div>
    <form class="inputbar" id="form">
      <input id="inp" autocomplete="off" placeholder="例如：太难了 / 讲深点 / 和X的关系…">
      <button id="send" type="submit">发送</button>
    </form>
  </div>
</div>
<script>
var msgs=document.getElementById('msgs'),inp=document.getElementById('inp'),send=document.getElementById('send'),
    card=document.getElementById('card'),qaEl=document.getElementById('qa'),form=document.getElementById('form');
function add(cls,text){{var d=document.createElement('div');d.className='msg '+cls;d.textContent=text;msgs.appendChild(d);msgs.scrollTop=msgs.scrollHeight;return d;}}
function setQa(q){{if(!q||q.score_render==null){{qaEl.textContent='';return;}}qaEl.textContent='质检 渲染'+q.score_render+' / 交互'+q.score_interact+' / 教学'+q.score_peda+(q.passed?' · ready':' · draft');}}
async function refine(text){{
  if(!text.trim())return;
  add('user',text);inp.value='';send.disabled=true;
  var pend=add('bot','');pend.innerHTML='<span class="spin"></span>正在重新生成学习卡…';
  try{{
    var r=await fetch('/api/refine',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{instruction:text}})}});
    var data=await r.json();
    if(data.ok){{pend.className='msg bot';
      var note=(data.fidelity&&data.fidelity.on_topic===false)?'\\n⚠ 注意：检测到可能跑题，已尽量拉回本知识点。':(data.fidelity&&data.fidelity.on_topic?'\\n· 已保持聚焦本知识点 ✓':'');
      pend.textContent='✓ '+data.summary+note;card.src='/card?v='+data.version;setQa(data.qa);}}
    else{{pend.className='msg err';pend.textContent='生成失败：'+(data.error||'未知错误');}}
  }}catch(e){{pend.className='msg err';pend.textContent='请求出错：'+e;}}
  send.disabled=false;inp.focus();
}}
form.addEventListener('submit',function(e){{e.preventDefault();refine(inp.value);}});
document.querySelectorAll('.chip').forEach(function(c){{c.addEventListener('click',function(){{refine(c.textContent);}});}});
</script>
</body></html>"""


def _make_handler(state: StudioState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            return

        def _send(self, code, body, ctype="text/html; charset=utf-8"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._send(200, _PAGE.format(title=state.kp.title))
            elif path == "/card":
                self._send(200, state.card_html or "<p>生成中…</p>")
            else:
                self._send(404, "not found", "text/plain")

        def do_POST(self):
            if self.path != "/api/refine":
                self._send(404, "not found", "text/plain")
                return
            try:
                n = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(n) or b"{}")
                instruction = (payload.get("instruction") or "").strip()
                if not instruction:
                    raise ValueError("empty instruction")
                _k, summary = state.refine(instruction)
                self._send(200, json.dumps(
                    {"ok": True, "summary": summary, "version": state.version,
                     "qa": state.qa, "fidelity": state.fidelity},
                    ensure_ascii=False), "application/json; charset=utf-8")
            except Exception as e:  # noqa: BLE001
                self._send(200, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False),
                           "application/json; charset=utf-8")

    return Handler


def serve(kp: KnowledgePoint, cfg: Config, port: int = 8799, open_browser: bool = True) -> None:
    state = StudioState(kp, cfg)
    print(f"[studio] generating initial card for「{kp.title}」…")
    state.generate()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), _make_handler(state))
    url = f"http://127.0.0.1:{port}/"
    print(f"[studio] ready → {url}  (Ctrl+C to stop)")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[studio] bye")
        httpd.shutdown()
