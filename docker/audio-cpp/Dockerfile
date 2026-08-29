ARG AUDIO_CPP_BASE_IMAGE=ghcr.io/0xshug0/audio.cpp:full-cuda12-20260828-6d530f4@sha256:88ec7504877ae0ff427dd15089693b260c1228cc511b22cd4a79b44f0b1ee268
FROM ${AUDIO_CPP_BASE_IMAGE}

USER root
RUN mkdir -p /models /voices \
    && chown ubuntu:ubuntu /models /voices

COPY server.cuda.generated.json /app/server.json
COPY server-configs /server-configs
COPY deployment-inventory.generated.json /deployment-inventory.json
COPY model-downloads.generated.sh /model-downloads.generated.sh
COPY entrypoint.sh /prefer-audio-entrypoint.sh
RUN sed -i 's/\r$//' /model-downloads.generated.sh /prefer-audio-entrypoint.sh \
    && chmod +x /model-downloads.generated.sh /prefer-audio-entrypoint.sh

LABEL io.prefer.runtime="audio.cpp" \
      io.prefer.audio.backend="cuda12" \
      io.prefer.audio.source-revision="6d530f4052ca93b5cd84ef6124406dcf85542a6f" \
      io.prefer.deployment-inventory.path="/deployment-inventory.json" \
      io.prefer.deployment-inventory.schema="prefer.audio-deployment-inventory.v1"

USER ubuntu
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=4h --retries=3 \
  CMD curl -fsS http://127.0.0.1:8080/health || exit 1

ENTRYPOINT ["/prefer-audio-entrypoint.sh"]
