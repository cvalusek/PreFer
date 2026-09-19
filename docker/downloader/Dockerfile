FROM debian:bookworm-slim

ARG TARGETARCH
ARG S5CMD_VERSION=2.2.2

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates curl python3 python3-pip util-linux xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir --break-system-packages -U "huggingface_hub[cli]" \
    && case "$TARGETARCH" in \
         amd64) s5cmd_arch=64bit ;; \
         arm64) s5cmd_arch=arm64 ;; \
         *) echo "unsupported TARGETARCH for s5cmd: $TARGETARCH" >&2; exit 1 ;; \
       esac \
    && curl -fsSL "https://github.com/peak/s5cmd/releases/download/v${S5CMD_VERSION}/s5cmd_${S5CMD_VERSION}_Linux-${s5cmd_arch}.tar.gz" \
       | tar -xz -C /usr/local/bin s5cmd \
    && mkdir -p /models /run/prefer

COPY .prefer-tooling/install-prefer-node.sh /tmp/install-prefer-node.sh
RUN sed -i 's/\r$//' /tmp/install-prefer-node.sh \
    && chmod +x /tmp/install-prefer-node.sh \
    && /tmp/install-prefer-node.sh "$TARGETARCH" \
    && rm -f /tmp/install-prefer-node.sh

COPY .prefer-tooling/prefer.mjs /usr/local/bin/prefer
COPY .prefer-tooling/prefer-model-catalog.json /prefer-model-catalog.json
COPY .prefer-tooling/prefer-download-artifacts.sh /prefer-download-artifacts.sh
COPY .prefer-tooling/prefer-runtime-handoff-download.sh /prefer-runtime-handoff-download.sh
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /prefer-download-artifacts.sh /prefer-runtime-handoff-download.sh /entrypoint.sh \
    && chmod +x /usr/local/bin/prefer /prefer-download-artifacts.sh /prefer-runtime-handoff-download.sh /entrypoint.sh

ENV HF_HOME=/models/.prefer-cache/huggingface \
    HF_XET_HIGH_PERFORMANCE=1 \
    PREFER_MODEL_CATALOG=/prefer-model-catalog.json \
    PREFER_MODELS_DIR=/models \
    PYTHONUNBUFFERED=1

LABEL io.prefer.runtime="artifact-downloader" \
      io.prefer.model-catalog.path="/prefer-model-catalog.json" \
      io.prefer.model-catalog.schema="prefer.model-catalog.v1"

ENTRYPOINT ["/entrypoint.sh"]
