ARG STABLE_DIFFUSION_CPP_BASE_IMAGE=ghcr.io/leejet/stable-diffusion.cpp:master-cuda@sha256:dcd82f38252a32822dcd0c80672d5948df8e63bb4a3064988e0f7c2bec10c100
FROM ${STABLE_DIFFUSION_CPP_BASE_IMAGE}

ARG TARGETARCH
USER root
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates curl python3 python3-pip tini util-linux xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir --break-system-packages -U "huggingface_hub[cli]" \
    && mkdir -p /models /app /server-configs

COPY .prefer-tooling/install-prefer-node.sh /tmp/install-prefer-node.sh
RUN sed -i 's/\r$//' /tmp/install-prefer-node.sh \
    && chmod +x /tmp/install-prefer-node.sh \
    && /tmp/install-prefer-node.sh "$TARGETARCH" \
    && rm -f /tmp/install-prefer-node.sh

COPY server.generated.json /app/server.json
COPY server.generated.prestage /app/server.prestage
COPY server-configs /server-configs
COPY deployment-inventory.generated.json /deployment-inventory.json
COPY download-artifacts.sh /prefer-download-artifacts.sh
COPY model-downloads.generated.sh /model-downloads.generated.sh
COPY generate.py /prefer-catalog/generate.py
COPY runtime.json deployment-bundles.json /prefer-catalog/
COPY models /prefer-catalog/models
COPY deployment-scenarios /prefer-catalog/deployment-scenarios
COPY .prefer-tooling/prefer.mjs /usr/local/bin/prefer
COPY .prefer-tooling/prefer-model-catalog.json /prefer-model-catalog.json
COPY .prefer-tooling/prefer-model-catalog.schema.json /prefer-catalog/schemas/prefer-model-catalog.schema.json
COPY .prefer-tooling/prefer-model-catalog-extension.schema.json /prefer-catalog/schemas/prefer-model-catalog-extension.schema.json
COPY .prefer-tooling/prefer-resource-profile.schema.json /prefer-catalog/schemas/prefer-resource-profile.schema.json
COPY .prefer-tooling/prefer-model-plan.schema.json /prefer-catalog/schemas/prefer-model-plan.schema.json
COPY .prefer-tooling/prefer-runtime-handoff.schema.json /prefer-catalog/schemas/prefer-runtime-handoff.schema.json
COPY .prefer-tooling/prefer-runtime-handoff-download.sh /prefer-runtime-handoff-download.sh
COPY router.py /app/router.py
COPY entrypoint.sh /prefer-image-entrypoint.sh
RUN sed -i 's/\r$//' /prefer-download-artifacts.sh /prefer-runtime-handoff-download.sh /model-downloads.generated.sh /prefer-image-entrypoint.sh /prefer-catalog/generate.py \
    && chmod +x /usr/local/bin/prefer /prefer-download-artifacts.sh /prefer-runtime-handoff-download.sh /model-downloads.generated.sh /prefer-image-entrypoint.sh /app/router.py

ENV PREFER_ENGINE=stable-diffusion.cpp \
    PREFER_MODEL_CATALOG=/prefer-model-catalog.json

LABEL io.prefer.runtime="stable-diffusion.cpp" \
      io.prefer.image.backend="cuda12" \
      io.prefer.image.source-revision="be0e34480dada95f8ce9a021bbb95c5de85d67c7" \
      io.prefer.deployment-inventory.path="/deployment-inventory.json" \
      io.prefer.deployment-inventory.schema="prefer.image-deployment-inventory.v1"

ENV HF_HOME=/models/.prefer-cache/huggingface \
    HF_XET_HIGH_PERFORMANCE=1 \
    PYTHONUNBUFFERED=1
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8080/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/prefer-image-entrypoint.sh"]
