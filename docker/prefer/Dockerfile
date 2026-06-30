# Pinned (not the rolling `server-cuda` tag) because builds around the
# gemma4-assistant MTP merge (#23398, ~b9549) were unstable. Bump manually
# after confirming a newer build works.
FROM ghcr.io/ggml-org/llama.cpp:server-cuda-b9592

# huggingface-cli is deprecated; the `hf` command (from huggingface_hub) replaces it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-pip curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --break-system-packages -U "huggingface_hub[cli]"

# s5cmd: fast parallel S3 sync for the optional model cache (used by
# download-models.sh only when S3_BUCKET_NAME is set). Single static binary;
# reads AWS creds from the standard chain (env / IMDS instance role). Bump the
# pin as needed.
ARG S5CMD_VERSION=2.2.2
RUN curl -fsSL "https://github.com/peak/s5cmd/releases/download/v${S5CMD_VERSION}/s5cmd_${S5CMD_VERSION}_Linux-64bit.tar.gz" \
    | tar -xz -C /usr/local/bin s5cmd

# Keep HF's staging/cache dir on the same volume as the final model files,
# so downloads don't fill the container's ephemeral filesystem and partial
# downloads survive restarts.
ENV HF_HOME=/models

# Let hf-xet use more network/disk parallelism for large GGUF downloads.
ENV HF_XET_HIGH_PERFORMANCE=1

# Show hf download progress in real time via `docker logs`.
ENV PYTHONUNBUFFERED=1

# If llama-server is ever invoked with -hf directly (e.g. via passthrough
# args), keep its cache on the volume too.
ENV LLAMA_CACHE=/models

# Overriding ENTRYPOINT below drops whatever the base image did to set this
# up for /app/llama-server's bundled shared libs (libllama-common.so etc).
ENV LD_LIBRARY_PATH=/app

COPY presets/ /presets/
COPY detect-preset.sh /detect-preset.sh
COPY download-models.sh /download-models.sh
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /detect-preset.sh /download-models.sh /entrypoint.sh \
    && chmod +x /detect-preset.sh /download-models.sh /entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
