ARG VLLM_BASE_IMAGE=vllm/vllm-openai:v0.28.0-ubuntu2404@sha256:f8fe15a8039343336945db10494eaad80ef941fe2b2a5fa6649fa38636051a65
FROM ${VLLM_BASE_IMAGE}

ARG TARGETARCH
ARG S5CMD_VERSION=2.2.2

USER root
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
    && mkdir -p /models /app /server-configs

COPY .prefer-tooling/install-prefer-node.sh /tmp/install-prefer-node.sh
RUN sed -i 's/\r$//' /tmp/install-prefer-node.sh \
    && chmod +x /tmp/install-prefer-node.sh \
    && /tmp/install-prefer-node.sh "$TARGETARCH" \
    && rm -f /tmp/install-prefer-node.sh

ENV HF_HOME=/models \
    HF_XET_HIGH_PERFORMANCE=1 \
    PYTHONUNBUFFERED=1

COPY server.generated.json /app/server.json
COPY server.generated.prestage /app/server.prestage
COPY server-configs /server-configs
COPY deployment-inventory.generated.json /deployment-inventory.json
COPY download-artifacts.sh /prefer-download-artifacts.sh
COPY model-downloads.generated.sh /model-downloads.generated.sh
COPY generate.py /prefer-catalog/generate.py
COPY runtime.json /prefer-catalog/runtime.json
COPY models /prefer-catalog/models
COPY deployment-scenarios /prefer-catalog/deployment-scenarios
COPY .prefer-tooling/prefer.mjs /usr/local/bin/prefer
COPY .prefer-tooling/prefer-model-catalog.json /prefer-model-catalog.json
COPY .prefer-tooling/prefer-model-catalog.schema.json /prefer-catalog/schemas/prefer-model-catalog.schema.json
COPY .prefer-tooling/prefer-model-catalog-extension.schema.json /prefer-catalog/schemas/prefer-model-catalog-extension.schema.json
COPY .prefer-tooling/prefer-resource-profile.schema.json /prefer-catalog/schemas/prefer-resource-profile.schema.json
COPY .prefer-tooling/prefer-model-plan.schema.json /prefer-catalog/schemas/prefer-model-plan.schema.json
COPY entrypoint.sh /prefer-vllm-entrypoint.sh
COPY router.py /prefer-vllm-router.py
RUN sed -i 's/\r$//' /prefer-download-artifacts.sh /model-downloads.generated.sh /prefer-vllm-entrypoint.sh /prefer-vllm-router.py /prefer-catalog/generate.py \
    && chmod +x /usr/local/bin/prefer /prefer-download-artifacts.sh /model-downloads.generated.sh /prefer-vllm-entrypoint.sh /prefer-vllm-router.py

ENV PREFER_ENGINE=vllm \
    PREFER_MODEL_CATALOG=/prefer-model-catalog.json

LABEL io.prefer.runtime="vllm" \
      io.prefer.vllm.backend="cuda13" \
      io.prefer.vllm.source-revision="2cf0a6915ce544dc493a0990f2ea38d81601128a" \
      io.prefer.vllm.image-build-revision="v0.28.0" \
      io.prefer.vllm.lineage="official-upstream" \
      io.prefer.deployment-inventory.path="/deployment-inventory.json" \
      io.prefer.deployment-inventory.schema="prefer.vllm-deployment-inventory.v1"

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=4h --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/readyz || exit 1

ENTRYPOINT ["/prefer-vllm-entrypoint.sh"]
