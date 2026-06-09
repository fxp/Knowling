# Knowling API container — network-free build (the package is pure stdlib, zero deps).
# Core endpoints (plan/compile/generate/refine/reteach/quiz-eval) need no native libs.
#
# NOTE: the `manim` block (3B1B animations) needs ffmpeg + the [manim] extra, which
# require apt/pip at build time. It's intentionally NOT in this image (too heavy for
# Containers, and apt may be blocked in restricted networks); manim blocks degrade to
# a captioned placeholder. To enable it, build on a machine with open egress and add:
#   RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libcairo2 libpango-1.0-0 \
#       && pip install --no-cache-dir ".[manim]" && rm -rf /var/lib/apt/lists/*
FROM python:3.11-slim

WORKDIR /app
# pure-Python package — just put it on the path; no build/install step (no network).
COPY knowling /app/knowling

ENV PYTHONUNBUFFERED=1
# In production the Worker injects secrets: KNOWLING_API_TOKEN (guards POST routes)
# and ZHIPU_API_KEY (real GLM; omit → offline Mock).
EXPOSE 8765
CMD ["python", "-m", "knowling.server", "--host", "0.0.0.0", "--port", "8765"]
