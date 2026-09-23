ARG STABLE_DIFFUSION_CPP_BASE_IMAGE=ghcr.io/leejet/stable-diffusion.cpp:master-cuda@sha256:dd71cfb3ed1459c6c227f16037bf98bf34c693930176aa45e98e19477117caac
ARG PREFER_BASE_IMAGE=${STABLE_DIFFUSION_CPP_BASE_IMAGE}
FROM ${PREFER_BASE_IMAGE}

ARG TARGETARCH
ARG PREFER_RUNTIME_BACKEND=cuda12
ARG PREFER_IMAGE_SOURCE_REVISION=137f7409bbfb98c70a350a57d6a135487080db96
USER root
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates curl python3 python3-pip tini util-linux xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir --break-system-packages -U "huggingface_hub[cli]" \
    && mkdir -p /models /app

COPY .prefer-tooling/install-prefer-node.sh /tmp/install-prefer-node.sh
RUN sed -i 's/\r$//' /tmp/install-prefer-node.sh \
    && chmod +x /tmp/install-prefer-node.sh \
    && /tmp/install-prefer-node.sh "$TARGETARCH" \
    && rm -f /tmp/install-prefer-node.sh

COPY server.generated.json /app/server.json
COPY server.generated.prestage /app/server.prestage
COPY deployment-inventory.generated.json /deployment-inventory.json
COPY download-artifacts.sh /prefer-download-artifacts.sh
COPY model-downloads.generated.sh /model-downloads.generated.sh
COPY generate.py /prefer-catalog/generate.py
COPY runtime.json deployment-bundles.json /prefer-catalog/
COPY models /prefer-catalog/models
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
      io.prefer.image.backend="${PREFER_RUNTIME_BACKEND}" \
      io.prefer.image.source-revision="${PREFER_IMAGE_SOURCE_REVISION}" \
      io.prefer.deployment-inventory.path="/deployment-inventory.json" \
      io.prefer.deployment-inventory.schema="prefer.image-deployment-inventory.v1"

ENV HF_HOME=/models/.prefer-cache/huggingface \
    HF_XET_HIGH_PERFORMANCE=1 \
    PYTHONUNBUFFERED=1
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8080/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/prefer-image-entrypoint.sh"]
