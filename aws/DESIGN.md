# PreFer on AWS EC2 — design and operations

Goal: make launching the PreFer container on EC2 with GPU support close to
one click, and shareable with other accounts. IaC is **CDK**, but the
distributed artifact is the **synthesized CloudFormation template**, so the
public can deploy with no CDK/Node toolchain.

This documents the implemented AMI, boot, S3-cache, and CDK architecture plus
the rationale behind the operational choices.

## TL;DR of the decisions

- **Public AMI** is the shareable artifact (the only thing AWS lets you share
  cross-account; launch templates are account-scoped and can't be "published").
- AMI carries **software + boot logic only — never the models.** Baking models
  would turn the AMI root into a snapshot and reintroduce the EBS snapshot
  lazy-load penalty.
- Models live in a **regional S3 bucket** acting as the model cache. **All
  model-fetching stays inside the container's `download-models.sh`** (not the
  host): **parallel filtered sync from S3 → marker validation → `hf download`
  for stale/missing data → sync up to S3**, gated on a `S3_BUCKET_NAME` env var
  so local/RunPod behavior is unchanged when it's unset. S3 has no single-volume
  throughput ceiling (unlike gp3's 1 GB/s cap), so on a high-bandwidth GPU
  instance the pull is NIC-bound at multiple GB/s.
- **Instance-store NVMe** is the runtime `/models` mount, repopulated on
  **every start** (NVMe is wiped on stop). This is what makes router model swaps
  (`models-max`) fast.
- **No persistent EBS data volume** — just the AMI root + ephemeral NVMe. No
  AZ-lock, no throughput to provision/pay for.
- Per-boot host work runs from a **systemd unit**, not user-data (user-data runs
  once per instance lifetime, but we stop/start and NVMe must be rebuilt every
  start). The host job shrinks to **prep NVMe + `docker run`** — all S3 logic
  lives in the image.
- First boot is explicitly ordered: cloud-init writes a separate deployment
  environment, exits, and only then may systemd launch PreFer. User-data never
  starts or restarts the service.
- The container is **pulled at boot**, not frozen into the AMI, so the
  container build and the AMI build stay fully decoupled in CI.

## Why this shape (recap of the reasoning)

- **Boot time is paid GPU-idle time.** At ~$3.36/hr ($0.056/min) the model copy
  is a real per-start cost, not just a wait. So the source is chosen for *copy
  speed*, and that's where S3 beats a persistent EBS volume.
- **Single EBS volume = hard throughput ceiling; S3 = NIC-bound parallel.** gp3
  maxes at 1 GB/s (and costs ~$40/mo to reach it). `s5cmd` against S3 saturates
  the instance NIC (multiple GB/s on these boxes) — measured to be *way* faster
  in practice. S3 also costs ~$2.30/mo per 100GB at rest vs $8+throughput for
  gp3, and is regional/replicable rather than AZ-locked.
- **gp3 was slow before because of snapshot lazy-load + the mmap IOPS wall**,
  not raw throughput — but even at its best, gp3's 1 GB/s ceiling loses to S3
  here, so S3 is the source and NVMe is the fast runtime mount.
- **Stop/start, not terminate**, for cost control. Only NVMe needs rebuilding
  each start; nothing persistent to reattach.
- **NVMe wins for swap-heavy use** (`models-max = 2`): each swap past the
  resident set reads a GGUF fresh from disk. From NVMe that's seconds. All
  swappable models must therefore be staged on NVMe.

## Repo layout

```text
aws/                          all EC2 deployment lives here (parallels docker/)
  DESIGN.md                  this file
  packer/
    prefer-ami.pkr.hcl       Packer template; base = DLAMI Base GPU (Ubuntu 24.04) via SSM
    provision.sh             installs boot scripts + systemd unit; warm-pulls image
  boot/
    prefer-boot.service      systemd unit, runs every boot
    10-prep-nvme.sh          ensure instance-store NVMe at /opt/dlami/nvme (dlami-nvme + fallback)
    20-run-container.sh      docker pull (pinned tag) + docker run with /models on NVMe
    prefer-boot.env          immutable AMI defaults (image, paths, router limit)
  cdk/                       thin wrapper: instance + IAM + IMDS + S3/endpoint wiring
docker/prefer/
  preset-catalog.json        model/artifact/revision source of truth
  preset-scenarios/aws.json  AWS deployment shapes
  generate-presets.py        emits presets, prestage sidecars, downloader cases
  download-models.sh         S3 sync + preset-aware catalog downloads
.github/workflows/
  build-prefer.yml           container image -> GHCR  [docker/prefer/** only]
  build-aws.yml              ami job (Packer, path-gated) -> cdk job (synth + release) [aws/**]
```

The synthesized CloudFormation template is not committed — `build-aws.yml`'s
`cdk` job publishes it to the `template-latest` GitHub release for non-CDK users.

## What goes in the AMI (baked)

- **Base**: AWS **Deep Learning Base GPU AMI (Ubuntu 24.04, x86_64)**, resolved
  via AWS's public SSM parameter
  `/aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-24.04/latest/ami-id`
  (no name filters to drift). It ships NVIDIA driver (595.x), CUDA, **Docker**,
  **nvidia-container-toolkit (1.19.x)**, default user `ubuntu`, supports G6e/**G7e**
  — so AWS owns driver/Docker staleness. It also runs a **`dlami-nvme` service**
  that auto-formats/mounts the instance store at `/opt/dlami/nvme` every boot.
- `aws/boot/*` installed under `/opt/prefer/`, systemd unit enabled. The
  host needs **no S3 tooling** — `s5cmd`/aws-cli live in the container image,
  since the container does the fetching.
- A **warm pull** of the pinned container tag as an *offline fallback only*
  (boot still does a fresh `docker pull`).
- **No models.** AMI changes only when software/boot logic changes — rarely.

Build with **Packer** (committed template) so anyone distrusting the public AMI
(security/air-gapped/compliance) can rebuild it byte-for-byte in their own
account. The build is public and copied to **us-east-1 + us-east-2** (Packer
`ami_regions`, `ami_groups=["all"]`). The `ami` job emits the resulting
region -> AMI-id map as an **`ami-map` artifact**; the `cdk` job bakes it into
the template's **RegionMap** so a deploy picks the right AMI by region with no
lookup — and no cross-account SSM dependency (Parameter Store can't be shared
publicly, so an SSM "latest" pointer would only resolve inside the build
account).

## Boot sequence (systemd, every start)

Host side — `prefer-boot.service` (`After=cloud-final.service` and
`docker.service`, `WantedBy=cloud-init.target`):

`cloud-final.service` itself is ordered after `multi-user.target` on the DLAMI.
Enabling PreFer under `multi-user.target` would therefore create the cycle
`multi-user → prefer-boot → cloud-final → multi-user`; systemd breaks that
cycle by dropping the PreFer start job. Enabling it under `cloud-init.target`
keeps cloud-init as the boot owner and starts PreFer after the final stage
without a user-data `systemctl start` race.

0. **Resolve deployment configuration**: first-boot cloud-init writes
   `/opt/prefer/deployment.env` and exits. The unit reads immutable
   `/opt/prefer/prefer-boot.env` first and the optional deployment file second,
   so deployment values override defaults without editing or appending to the
   baked file. `LLAMA_ARG_MODELS_MAX=1` is a safe default in both the AMI and
   generated deployment configuration.

1. **Prep NVMe** (`10-prep-nvme.sh`): the DLAMI's `dlami-nvme` service already
   formats/mounts the instance store at `/opt/dlami/nvme` each boot (the unit
   orders us `After=dlami-nvme.service`), so this is normally just
   `mkdir -p /opt/dlami/nvme/models`. A detect/format/mount **fallback** (match
   model string `Instance Storage`, never the EBS root; RAID0 only if multiple
   devices) covers non-DLAMI bases or a disabled service.
2. **Run container** (`20-run-container.sh`): `docker pull` the pinned tag, then
   `docker run --gpus all -p 8080:8080 -v /opt/dlami/nvme/models:/models -e
   S3_BUCKET_NAME=$BUCKET ...`.

Container side — existing `entrypoint.sh` → `detect-preset.sh` →
`download-models.sh`, with `download-models.sh` gaining an S3 block when
`S3_BUCKET_NAME` is set:

1. Fetch each model key's small completion marker, then stage only the catalog's
   include patterns from `s3://$BUCKET/<hf-repo>/` to `/models`. Independent
   model keys run concurrently (four jobs by default) and join before startup.
2. A marker whose catalog fingerprint, bucket, age, artifact list, and observed
   byte sizes all match skips `hf download`. Missing/invalid markers fall back
   to Hugging Face; markers expire after seven days by default so moving repos
   are periodically checked again.
3. Sync exact catalog artifacts back to S3 **in the background**, then publish
   the completion marker last. Hugging Face `.cache`, locks, and xet data are
   never uploaded and are removed locally after the foreground jobs join.

When `S3_BUCKET_NAME` is unset (local / RunPod), `download-models.sh` behaves
exactly as today — HF only.

## S3 model cache

- **Regional bucket** in the same region as the instances → S3↔EC2 transfer is
  **free**, and an **S3 gateway VPC endpoint** (free) keeps traffic on the AWS
  backbone with no NAT charge and full bandwidth. Both are required to hit the
  NIC-bound speeds and avoid surprise transfer/NAT costs.
- **Self-populating, inside the container**: `download-models.sh` tries S3
  first, falls back to HF on miss, then uploads — so the bucket warms itself on
  first use without a separate staging job, and the same script serves local,
  RunPod, and EC2. (This is the regional-S3-pre-download pattern from the
  original entrypoint idea, kept in one place.)
- **Credentials via instance profile, no static keys** — the container reads
  IMDS for the role's creds. **Requires IMDS hop limit = 2** (EC2 default is 1,
  which blocks bridge-networked containers from reaching IMDS); the IaC must set
  `HttpPutResponseHopLimit: 2`.
- Layout mirrors the container's `/models/<hf-org>/<hf-repo>/...` so objects map
  1:1 to on-disk paths and multiple presets share one bucket.
- Completion markers live at
  `.prefer-cache/downloads-v1/<model-key>.complete`. Set
  `MODEL_CACHE_RECHECK_DAYS=0` for an every-launch recheck, or delete one marker
  to force only that model key through Hugging Face on its next launch.
- At rest ~$2.30/mo per 100GB (S3 Standard). Replicate cross-region with bucket
  replication if the shareable artifact needs to launch elsewhere.

## IaC layer (CDK, distributed as CloudFormation)

Inputs (CFN parameters): instance type, generated model preset path, optional
prestage override, key pair, allowed ingress CIDR, and an *optional* AMI id
override (blank uses the baked-in RegionMap). Outputs the instance + IAM
profile + S3 gateway endpoint.

**Distribution**: CDK is the authoring tool, but the *public artifact* is the
**synthesized CloudFormation template** (`cdk synth`), published to the
`template-latest` GitHub release. Consumers need no CDK, Node, or `cdk bootstrap`
— they deploy the template via the Console (incl. a "Launch Stack" quick-create
URL) or `aws cloudformation deploy`. The CDK source stays in-repo for anyone who
wants to customize in code; `build-aws.yml`'s `cdk` job re-synths (baking the
current region -> AMI RegionMap from the `ami-map` artifact) and publishes the
template release. Nothing is committed back to the repo.

Because we stop/start one long-lived instance rather than churning instances,
the stack primarily **provisions once** (instance + profile + endpoint). It can
also emit a launch template for anyone who *does* want to relaunch fresh.

**Per-deployment config** (region, bucket name, selected preset, router limit,
and optional prestage override) is *not* baked into the AMI. The AMI ships
immutable `/opt/prefer/prefer-boot.env` defaults. First-boot user-data writes a
complete `/opt/prefer/deployment.env` with mode `0600`; it never edits the baked
file and never controls the service. `prefer-boot.service` requires a successful
`cloud-final.service`, then loads the deployment file after the defaults and
launches exactly once. A cloud-init failure therefore blocks PreFer instead of
silently launching the auto-detected preset. An empty `PRESTAGE_MODELS` lets
the selected preset's sibling `.prestage` manifest choose exact catalog
artifacts. Both files persist on the root volume and are re-read on later
starts.

For a direct EC2 launch outside CDK, ordinary shell user-data is sufficient on
an AMI containing this boot contract:

```bash
#!/bin/bash
set -eu
umask 077

cat > /opt/prefer/deployment.env.tmp <<'PREFER_DEPLOYMENT_ENV'
AWS_REGION=us-east-2
S3_BUCKET_NAME=YOUR_BUCKET_NAME
LLAMA_ARG_MODELS_PRESET=/presets/aws/g6/xlarge/general.ini
LLAMA_ARG_MODELS_MAX=1
PRESTAGE_MODELS=
PREFER_DEPLOYMENT_ENV
chmod 0600 /opt/prefer/deployment.env.tmp
mv /opt/prefer/deployment.env.tmp /opt/prefer/deployment.env
```

Do not add `systemctl start` or `systemctl restart` to that script. The service
is already enabled, waits for cloud-init to finish, and owns the only container
launch. A missing deployment file intentionally falls back to the baked
auto-detection behavior.

**IAM**: instance profile needs `s3:GetObject`/`s3:ListBucket` (and
`s3:PutObject` for the self-populating upload) scoped to the cache bucket, and
optionally CloudWatch Logs. No persistent-volume wiring. The IaC must also set
**IMDS `HttpPutResponseHopLimit: 2`** so the container can reach the instance
role's credentials (see S3 cache section).

## CI isolation (builds scoped to what changed)

The hard requirement: a change in one area must not trigger unrelated builds.

| Workflow | Triggers on | Produces |
| -------- | ----------- | -------- |
| `build-prefer.yml` (existing) | `docker/prefer/**` | container image → GHCR |
| `build-aws.yml` (new) | `aws/**`, self | public AMI (us-east-1 + us-east-2) and/or `template-latest` release |

The key decoupler: **the container is pulled at boot, not baked**, so the
container build and the AMI build never need to trigger each other — that's why
the container stays in its own workflow.

Within `build-aws.yml`, the AMI and template *are* coupled (the template embeds
the AMI ids), so they're **ordered jobs** rather than separate workflows: a
paths-filter (`ami` = `aws/packer/**` + `aws/boot/**`) gates the costly AMI job,
and the `cdk` job `needs:` it. This expresses the dependency natively — no
cross-run `workflow_run`/artifact-polling — while still skipping the AMI build
for CDK-only edits.

- Edit a preset / Dockerfile → `build-prefer.yml` only → new image in GHCR →
  picked up on the next instance **start** (no AMI rebuild).
- Edit boot scripts / Packer → `build-aws.yml`: `ami` job builds, then `cdk` job
  re-releases the template with the new AMI ids.
- Edit IaC → `build-aws.yml`: `ami` job skipped, `cdk` job re-synths and
  re-releases, reusing the AMI map from the last release.

The baked image in the AMI is a stale-but-present offline fallback; it never
gates correctness, so the two image-producing pipelines stay independent.

## Resolved (was open)

- **Base AMI**: AWS DLAMI Base GPU Ubuntu 24.04 via public SSM parameter (above).
  Confirmed it ships Docker + nvidia-container-toolkit + driver and supports G7e.
- **NVMe handling**: delegated to the DLAMI `dlami-nvme` service (mounts
  `/opt/dlami/nvme`); our script is a thin fallback. RAID/device-count handling
  is AWS's problem on that path.

## Open questions before scaffolding

- **Bucket bootstrap**: warm the cache lazily on first boot (HF→S3 fallback
  path) vs a one-time explicit upload job. Lazy is simpler and self-healing.
- **Region set** for AMI publication + whether S3 cross-region replication is
  needed for the shareable artifact.
- **Instance NIC bandwidth** of the chosen GPU family — sets the real S3 pull
  ceiling (and confirms how little the first-model-priority optimization buys).
