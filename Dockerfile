# Knowling API — lean image (core: plan/compile/generate/refine/reteach/quiz-eval).
# FFmpeg is included so the `manim` block can render IF you also install the
# heavy [manim] extra (uncomment below). Playwright-based QA is NOT included
# (qa defaults off in the API); add it only if you need server-side QA.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# core has zero runtime deps
RUN pip install --no-cache-dir .
# heavy 3B1B animation backend (large image; needs cairo/pango/latex for full use):
# RUN apt-get update && apt-get install -y --no-install-recommends libcairo2 libpango-1.0-0 \
#     && pip install --no-cache-dir ".[manim]" && rm -rf /var/lib/apt/lists/*

ENV PORT=8765
# Set a token in production so the public endpoint isn't open:
#   -e KNOWLING_API_TOKEN=...   and pass your GLM key:  -e ZHIPU_API_KEY=...
EXPOSE 8765
CMD ["sh", "-c", "python -m knowling.server --host 0.0.0.0 --port ${PORT}"]
