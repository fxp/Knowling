// Cloudflare Worker fronting the Knowling Python API container.
// Only serves /knowling/* (the gateway owns the rest of api.xiaopingfeng.com).
import { Container, getContainer } from "@cloudflare/containers";

export class KnowlingContainer extends Container {
  defaultPort = 8765;          // the Python server's port
  sleepAfter = "15m";          // scale to zero when idle

  constructor(ctx, env) {
    super(ctx, env);
    // env → container process env. The server reads these:
    //   KNOWLING_BASE_PATH → serve under /knowling/*
    //   ZHIPU_API_KEY (secret) → real GLM (omit → offline Mock)
    //   KNOWLING_API_TOKEN (secret) → require Bearer token on POST routes
    this.envVars = {
      KNOWLING_BASE_PATH: "/knowling",
      ZHIPU_API_KEY: env.ZHIPU_API_KEY ?? "",
      KNOWLING_API_TOKEN: env.KNOWLING_API_TOKEN ?? "",
    };
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith("/knowling/")) {
      return new Response(JSON.stringify({ error: "not found" }), {
        status: 404, headers: { "content-type": "application/json" },
      });
    }
    // single shared instance is fine; use a per-key id to shard if needed.
    const container = getContainer(env.KNOWLING, "default");
    return container.fetch(request);
  },
};
