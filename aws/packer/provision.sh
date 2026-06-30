#!/usr/bin/env bash
# Packer provisioner: install the PreFer boot scripts + systemd unit into the
# AMI and warm-pull the container image. Runs on the build instance as `ubuntu`.
set -euo pipefail

SRC=/tmp/prefer-boot
DEST=/opt/prefer

# The repo is edited on Windows; strip any CRLF before installing.
sudo sed -i 's/\r$//' "$SRC"/*.sh "$SRC"/*.service "$SRC"/*.env

sudo mkdir -p "$DEST"
sudo cp "$SRC/10-prep-nvme.sh" "$SRC/20-run-container.sh" "$SRC/prefer-boot.env" "$DEST/"
sudo chmod +x "$DEST"/10-prep-nvme.sh "$DEST"/20-run-container.sh

# Pin the container image into the baked env file from the Packer var.
if [ -n "${PREFER_IMAGE:-}" ]; then
  sudo sed -i "s|^PREFER_IMAGE=.*|PREFER_IMAGE=${PREFER_IMAGE}|" "$DEST/prefer-boot.env"
fi

# mdadm is only needed for the rare multi-NVMe instance, but it's cheap to have
# present so 10-prep-nvme.sh works everywhere.
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends mdadm

sudo cp "$SRC/prefer-boot.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable prefer-boot.service

# Warm pull as an offline fallback only; boot still pulls fresh each start.
if [ -n "${PREFER_IMAGE:-}" ]; then
  sudo docker pull "${PREFER_IMAGE}" || echo "[provision] warm pull failed (non-fatal)"
fi

echo "[provision] complete"
