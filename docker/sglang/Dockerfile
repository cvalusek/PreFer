ARG SGLANG_BASE_IMAGE=lmsysorg/sglang:nightly-dev-cu13-20260814-c4271c3f@sha256:3a28a37ce6dba5471494781617451eed355308cb7d90347f022df37f5fb212dc
FROM ${SGLANG_BASE_IMAGE}

ARG TARGETARCH
ARG S5CMD_VERSION=2.2.2

USER root
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates curl ffmpeg python3 python3-pip util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir --break-system-packages -U "huggingface_hub[cli]" "comfy-kitchen==0.2.32" \
    && case "$TARGETARCH" in \
         amd64) s5cmd_arch=64bit ;; \
         arm64) s5cmd_arch=arm64 ;; \
         *) echo "unsupported TARGETARCH for s5cmd: $TARGETARCH" >&2; exit 1 ;; \
       esac \
    && curl -fsSL "https://github.com/peak/s5cmd/releases/download/v${S5CMD_VERSION}/s5cmd_${S5CMD_VERSION}_Linux-${s5cmd_arch}.tar.gz" \
       | tar -xz -C /usr/local/bin s5cmd \
    && mkdir -p /models /inputs /outputs /app /server-configs

ENV HF_HOME=/models \
    HF_XET_HIGH_PERFORMANCE=1 \
    PYTHONUNBUFFERED=1

COPY server.generated.json /app/server.json
COPY server.generated.prestage /app/server.prestage
COPY server-configs /server-configs
COPY deployment-inventory.generated.json /deployment-inventory.json
COPY download-artifacts.sh /prefer-download-artifacts.sh
COPY model-downloads.generated.sh /model-downloads.generated.sh
COPY entrypoint.sh /prefer-sglang-entrypoint.sh
COPY video_gateway.py /prefer-sglang-video-gateway.py
RUN sed -i 's/\r$//' /prefer-download-artifacts.sh /model-downloads.generated.sh /prefer-sglang-entrypoint.sh /prefer-sglang-video-gateway.py \
    && chmod +x /prefer-download-artifacts.sh /model-downloads.generated.sh /prefer-sglang-entrypoint.sh /prefer-sglang-video-gateway.py

LABEL io.prefer.runtime="sglang" \
      io.prefer.sglang.backend="cuda13" \
      io.prefer.sglang.source-revision="c4271c3fe1262fc2adbd162c33b25de5255251c5" \
      io.prefer.sglang.image-build-revision="c4271c3fe1262fc2adbd162c33b25de5255251c5" \
      io.prefer.sglang.lineage="official-upstream" \
      io.prefer.deployment-inventory.path="/deployment-inventory.json" \
      io.prefer.deployment-inventory.schema="prefer.sglang-deployment-inventory.v2"

EXPOSE 30000
HEALTHCHECK --interval=30s --timeout=10s --start-period=4h --retries=3 \
  CMD curl -fsS http://127.0.0.1:30000/health || exit 1

ENTRYPOINT ["/prefer-sglang-entrypoint.sh"]
