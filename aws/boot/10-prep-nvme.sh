#!/usr/bin/env bash
# Ensure the ephemeral instance-store NVMe is mounted at $NVME_MOUNT, then make
# the models subdir.
#
# On the AWS DLAMI this is normally a no-op: the platform's `dlami-nvme` service
# already detects, formats, and mounts the instance store at /opt/dlami/nvme on
# every boot (the store is wiped on stop/start, so it re-does it each start).
# The unit orders us After=dlami-nvme.service, so by the time we run it's mounted
# and we just create the subdir.
#
# The detect/format/mount block below is a FALLBACK for non-DLAMI bases or if the
# dlami-nvme service is absent/disabled. It only ever touches devices whose model
# string identifies them as instance store, never the EBS root volume.
set -euo pipefail

NVME_MOUNT="${NVME_MOUNT:-/opt/dlami/nvme}"
MODELS_SUBDIR="${MODELS_SUBDIR:-models}"
FS_TYPE="${NVME_FS:-ext4}"

log() { echo "[prep-nvme] $*"; }

# Preferred path: already mounted (by dlami-nvme, or a prior run this boot).
if mountpoint -q "$NVME_MOUNT"; then
  log "$NVME_MOUNT already mounted (dlami-nvme or prior run); ensuring models subdir"
  mkdir -p "$NVME_MOUNT/$MODELS_SUBDIR"
  exit 0
fi

log "$NVME_MOUNT not mounted; falling back to manual detect/format/mount"

# EBS reports model "Amazon Elastic Block Store"; instance store reports
# "Amazon EC2 NVMe Instance Storage". Match only the latter.
mapfile -t DEVS < <(lsblk -dn -o NAME,MODEL | grep -i "Instance Storage" | awk '{print "/dev/"$1}' || true)

if [ "${#DEVS[@]}" -eq 0 ]; then
  log "ERROR: no instance-store NVMe found — does this instance type have local NVMe?"
  lsblk -dn -o NAME,MODEL >&2 || true
  exit 1
fi

if [ "${#DEVS[@]}" -eq 1 ]; then
  TARGET="${DEVS[0]}"
  log "single instance-store device: $TARGET"
else
  # Rare: some families expose multiple instance-store devices. Stripe them.
  TARGET=/dev/md0
  log "multiple instance-store devices (${DEVS[*]}); building RAID0 at $TARGET"
  mdadm --create --force "$TARGET" --level=0 --raid-devices="${#DEVS[@]}" "${DEVS[@]}"
fi

log "formatting $TARGET as $FS_TYPE"
mkfs -t "$FS_TYPE" -F "$TARGET" >/dev/null

mkdir -p "$NVME_MOUNT"
mount -o noatime "$TARGET" "$NVME_MOUNT"
mkdir -p "$NVME_MOUNT/$MODELS_SUBDIR"
log "mounted $TARGET at $NVME_MOUNT ($(df -h "$NVME_MOUNT" | awk 'NR==2{print $4}') free)"
