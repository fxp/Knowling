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

## Behind a shared API gateway (e.g. api.xiaopingfeng.com) ✅

`api.xiaopingfeng.com` is a **unified gateway serving many projects** — Knowling
must mount as *one service under a path*, never claim the whole host. **Do NOT**
`cloudflared tunnel route dns ... api.xiaopingfeng.com` (that hijacks the host).

Mount Knowling under a path so it answers at `…/knowling/v1/*`:
```bash
export KNOWLING_BASE_PATH=/knowling      # server now serves /knowling/v1/health etc.
export KNOWLING_API_TOKEN=...; export ZHIPU_API_KEY=...
python3 -m knowling.server --port 8765
```
`KNOWLING_BASE_PATH` makes Knowling work whether or not the gateway strips the
prefix (it accepts both `/knowling/v1/...` and `/v1/...`).

Then add a route on the **existing gateway** → `http://<knowling-host>:8765`:
- **cloudflared (ingress rules)** — add a path rule to the gateway tunnel's config.yml
  (don't create a second tunnel for the same hostname):
  ```yaml
  ingress:
    - hostname: api.xiaopingfeng.com
      path: ^/knowling/.*           # Knowling
      service: http://localhost:8765
    - hostname: api.xiaopingfeng.com  # ...your other services / catch-all stay below
      service: http://localhost:OTHER
    - service: http_status:404
  ```
- **Cloudflare Worker router** — add `if (url.pathname.startsWith('/knowling/')) return fetch(KNOWLING_ORIGIN + url.pathname, request)`.
- **nginx / Caddy origin** — `location /knowling/ { proxy_pass http://127.0.0.1:8765; }`.

Knowling itself stays a plain backend; the gateway owns hostname + DNS.

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

## Option C — Cloudflare Containers (fully hosted) ✅ chosen

Hosts the container on Cloudflare and attaches a **path-specific Worker Route**
`api.xiaopingfeng.com/knowling/*` — additive at the edge, so it works regardless of
how the rest of the gateway is built and doesn't touch other routes. Needs the
**Workers Paid** plan. Deploy package (repo root): `Dockerfile`, `wrangler.jsonc`,
`worker.js`, `package.json`.

```bash
# 1. (optional) build/run locally to sanity-check
docker build -t knowling-api .
docker run -p 8765:8765 -e KNOWLING_BASE_PATH=/knowling \
  -e ZHIPU_API_KEY=$ZHIPU_API_KEY -e KNOWLING_API_TOKEN=$KNOWLING_API_TOKEN knowling-api
curl -s localhost:8765/knowling/v1/health

# 2. deploy to Cloudflare
npm install
npx wrangler login                       # your Cloudflare account
npx wrangler secret put ZHIPU_API_KEY    # real GLM
npx wrangler secret put KNOWLING_API_TOKEN
npx wrangler deploy                       # builds the image, pushes, wires the route
# → live at https://api.xiaopingfeng.com/knowling/v1/health
```

The Worker (`worker.js`) only forwards `/knowling/*` to the container and injects
`KNOWLING_BASE_PATH=/knowling` + the secrets. Scales to zero (`sleepAfter`).

**Caveat (Containers + heavy features):** the image is lean — core endpoints
(plan/compile/generate/refine/reteach/quiz-eval) only. The `manim` block degrades
to a placeholder (manim/LaTeX too heavy for the lean image) and `qa` stays off
(no Playwright). For 3B1B animations, render offline or use a beefier instance
with the `[manim]` layer (commented in `Dockerfile`).

## Smoke test (any option)
```bash
curl -s https://<your-host>/v1/health
curl -s -X POST https://<your-host>/v1/knowling/generate \
  -H "Authorization: Bearer $KNOWLING_API_TOKEN" -H 'Content-Type: application/json' \
  -d '{"kp":{"id":"math.slope","title":"一次函数的斜率"}}'
```
