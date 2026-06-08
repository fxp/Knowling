# Deploying the Knowling API on Cloudflare

> **Why not Cloudflare Workers?** The API shells out to **ffmpeg/manim** (subprocess)
> and **Playwright**, and uses socket HTTP. Workers run in V8/Pyodide isolates with
> no subprocess/native deps, so the engine can't run there. The two viable paths
> keep the Python server running and put **Cloudflare in front** of it.

Always set a token so the public endpoint isn't open:
```bash
export KNOWLING_API_TOKEN=$(openssl rand -hex 16)
export ZHIPU_API_KEY=sk-...        # real GLM (omit → offline Mock)
python3 -m knowling.server --port 8765
# clients send:  Authorization: Bearer $KNOWLING_API_TOKEN  (GET /v1/health stays open)
```

## Option A — Quick Tunnel (instant, no account)

Fastest way to get a public Cloudflare URL in front of the local server:
```bash
cloudflared tunnel --url http://localhost:8765
# → prints https://<random>.trycloudflare.com   (ephemeral: dies with the process)
```
Good for demos/sharing. The URL changes each run and lasts only while it's running.

## Option B — Named Tunnel on your domain (persistent, free) ✅ recommended

Runs the server on any always-on box (your Mac, a VPS) and serves it at a stable
hostname on a Cloudflare-managed domain (e.g. `api.xiaopingfeng.com`).
```bash
cloudflared tunnel login                          # browser OAuth (your account)
cloudflared tunnel create knowling-api            # creates a tunnel + credentials json
cloudflared tunnel route dns knowling-api api.xiaopingfeng.com
```
`~/.cloudflared/config.yml`:
```yaml
tunnel: knowling-api
credentials-file: /Users/<you>/.cloudflared/<TUNNEL-ID>.json
ingress:
  - hostname: api.xiaopingfeng.com
    service: http://localhost:8765
  - service: http_status:404
```
Run it (and keep the API running alongside):
```bash
cloudflared tunnel run knowling-api               # or install as a service: cloudflared service install
```
Add **Cloudflare Access** (Zero Trust) on `api.xiaopingfeng.com` for SSO/JWT auth on
top of the API token if you want managed access control.

## Option C — Cloudflare Containers (fully hosted)

Hosts the container on Cloudflare (no always-on box of yours). Needs the **Workers
Paid** plan and `wrangler`.
```bash
docker build -t knowling-api -f deploy/Dockerfile .   # test locally first
docker run -p 8765:8765 -e ZHIPU_API_KEY=... -e KNOWLING_API_TOKEN=... knowling-api
npx wrangler login
# Define a Container in wrangler.jsonc bound to deploy/Dockerfile, then:
npx wrangler deploy
```
Note: the lean image does plan/compile/generate (no manim/QA). The `manim` block
needs the heavy `[manim]` layer (see the commented lines in deploy/Dockerfile);
Playwright-based QA isn't included — keep `qa:false` (the API default).

## Smoke test (any option)
```bash
curl -s https://<your-host>/v1/health
curl -s -X POST https://<your-host>/v1/knowling/generate \
  -H "Authorization: Bearer $KNOWLING_API_TOKEN" -H 'Content-Type: application/json' \
  -d '{"kp":{"id":"math.slope","title":"一次函数的斜率"}}'
```
