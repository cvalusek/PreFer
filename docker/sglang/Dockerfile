ARG SGLANG_BASE_IMAGE=lmsysorg/sglang:v0.5.20@sha256:06e4f2ed21afde4ff513cda65070124e727ba23ccaeff7712b8c40e1097d611f
ARG PREFER_BASE_IMAGE=${SGLANG_BASE_IMAGE}
FROM ${PREFER_BASE_IMAGE}

ARG TARGETARCH
ARG S5CMD_VERSION=2.2.2
ARG SGLANG_CUDA_VARIANT=cuda13
ARG PREFER_RUNTIME_BACKEND=${SGLANG_CUDA_VARIANT}
ARG SGLANG_SOURCE_REVISION=94602c9c2b7cbdb8efd5c52802dac6a1c180089e
ARG SGLANG_IMAGE_VERSION=v0.5.20

USER root
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates curl ffmpeg python3 python3-pip util-linux xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir --break-system-packages -U "huggingface_hub[cli]" "comfy-kitchen==0.2.32" \
    && case "$TARGETARCH" in \
         amd64) s5cmd_arch=64bit ;; \
         arm64) s5cmd_arch=arm64 ;; \
         *) echo "unsupported TARGETARCH for s5cmd: $TARGETARCH" >&2; exit 1 ;; \
       esac \
    && curl -fsSL "https://github.com/peak/s5cmd/releases/download/v${S5CMD_VERSION}/s5cmd_${S5CMD_VERSION}_Linux-${s5cmd_arch}.tar.gz" \
       | tar -xz -C /usr/local/bin s5cmd \
    && mkdir -p /models /inputs /outputs /app

COPY .prefer-tooling/install-prefer-node.sh /tmp/install-prefer-node.sh
RUN sed -i 's/\r$//' /tmp/install-prefer-node.sh \
    && chmod +x /tmp/install-prefer-node.sh \
    && /tmp/install-prefer-node.sh "$TARGETARCH" \
    && rm -f /tmp/install-prefer-node.sh

ENV HF_HOME=/models \
    HF_XET_HIGH_PERFORMANCE=1 \
    PYTHONUNBUFFERED=1

COPY deployment-inventory.generated.json /deployment-inventory.json
COPY download-artifacts.sh /prefer-download-artifacts.sh
COPY model-downloads.generated.sh /model-downloads.generated.sh
COPY generate.py /prefer-catalog/generate.py
COPY runtime.json /prefer-catalog/runtime.json
COPY models /prefer-catalog/models
COPY .prefer-tooling/prefer.mjs /usr/local/bin/prefer
COPY .prefer-tooling/prefer-model-catalog.json /prefer-model-catalog.json
COPY .prefer-tooling/prefer-model-catalog.schema.json /prefer-catalog/schemas/prefer-model-catalog.schema.json
COPY .prefer-tooling/prefer-model-catalog-extension.schema.json /prefer-catalog/schemas/prefer-model-catalog-extension.schema.json
COPY .prefer-tooling/prefer-resource-profile.schema.json /prefer-catalog/schemas/prefer-resource-profile.schema.json
COPY .prefer-tooling/prefer-model-plan.schema.json /prefer-catalog/schemas/prefer-model-plan.schema.json
COPY .prefer-tooling/prefer-runtime-handoff.schema.json /prefer-catalog/schemas/prefer-runtime-handoff.schema.json
COPY .prefer-tooling/prefer-runtime-handoff-download.sh /prefer-runtime-handoff-download.sh
COPY entrypoint.sh /prefer-sglang-entrypoint.sh
RUN sed -i 's/\r$//' /prefer-download-artifacts.sh /prefer-runtime-handoff-download.sh /model-downloads.generated.sh /prefer-sglang-entrypoint.sh /prefer-catalog/generate.py \
    && chmod +x /usr/local/bin/prefer /prefer-download-artifacts.sh /prefer-runtime-handoff-download.sh /model-downloads.generated.sh /prefer-sglang-entrypoint.sh

ENV PREFER_ENGINE=sglang \
    PREFER_MODEL_CATALOG=/prefer-model-catalog.json

LABEL io.prefer.runtime="sglang" \
      io.prefer.sglang.backend="${PREFER_RUNTIME_BACKEND}" \
      io.prefer.sglang.source-revision="${SGLANG_SOURCE_REVISION}" \
      io.prefer.sglang.image-build-revision="${SGLANG_IMAGE_VERSION}" \
      io.prefer.sglang.lineage="official-upstream" \
      io.prefer.deployment-inventory.path="/deployment-inventory.json" \
      io.prefer.deployment-inventory.schema="prefer.sglang-deployment-inventory.v2"

EXPOSE 30000
HEALTHCHECK --interval=30s --timeout=10s --start-period=4h --retries=3 \
  CMD curl -fsS http://127.0.0.1:30000/health || exit 1

ENTRYPOINT ["/prefer-sglang-entrypoint.sh"]
