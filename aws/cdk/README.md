# PreFer EC2 — CDK app

Provisions a GPU EC2 instance that runs the PreFer container with `/models` on
local NVMe and a self-populating S3 model cache.

CDK is the **authoring** tool. The **distributed** artifact is the synthesized
CloudFormation template, so the public can deploy with no CDK/Node toolchain.

## What it creates

- A minimal single-AZ public VPC (no NAT) with a **free S3 gateway endpoint**.
- An **S3 model-cache bucket** (`RETAIN` on stack delete — models survive).
- An **IAM instance profile** scoped to that bucket, plus SSM Session Manager.
- A **GPU EC2 instance** from the PreFer AMI, with:
  - **IMDS hop limit = 2** (so the container can read the role's creds),
  - user-data atomically writing `S3_BUCKET_NAME`,
    `LLAMA_ARG_MODELS_PRESET`, `LLAMA_ARG_MODELS_MAX=1`, and any explicit
    prestage override to `/opt/prefer/deployment.env`.

The AMI's systemd unit waits for `cloud-final.service`, then reads the
deployment file after its baked defaults. User-data never starts or restarts
PreFer, so first boot cannot briefly launch the auto-detected preset before the
deployment settings exist.

## Parameters

| Parameter | Default | Notes |
| --------- | ------- | ----- |
| `InstanceType` | `g7e.2xlarge` | GPU instance type with local NVMe instance store |
| `ModelsPreset` | `/presets/aws/g7e/2xlarge/general.ini` | Must match the intended generated AWS scenario |
| `PrestageModels` | `` (blank) | Blank uses the preset's sibling `.prestage`; nonblank is an explicit override |
| `AmiId` | `` (blank) | Optional override; blank uses the built-in RegionMap for the deploy region. Set an `ami-xxxx` only to pin a specific AMI |
| `KeyName` | — | Existing EC2 key pair (SSH; SSM also enabled) |
| `AllowedCidr` | `0.0.0.0/0` | Narrow this to your IP |
| `RootVolumeGb` | `100` | OS + container image only; models live on NVMe |

## AWS scenario matrix

Deploy one stack per independently managed model-family host, overriding both
`InstanceType` and `ModelsPreset` together:

| Instance | vCPU | Local NVMe | Preset |
| -------- | ---: | ---------- | ------ |
| `g6.xlarge` | 4 | 250 GB | `/presets/aws/g6/xlarge/general.ini` |
| `g6e.xlarge` | 4 | 250 GB | `/presets/aws/g6e/xlarge/gemma.ini` |
| `g7e.2xlarge` | 8 | 1.9 TB | `/presets/aws/g7e/2xlarge/general.ini` |
| `g7e.12xlarge` | 48 | 3.8 TB | `/presets/aws/g7e/12xlarge/deepseek-v4-flash-0731.ini` |

The original complete set consumes exactly 64 vCPUs while all four instances
are running. Family bundles can be replaced by a dedicated one-model preset on
the same instance type without changing its vCPU or NVMe shape:

| Instance | Alternative presets |
| -------- | ------------------- |
| `g6.xlarge` | `/presets/aws/g6/xlarge/gemma-e2b.ini`, `gemma-e4b.ini`, `gemma-12b.ini`, `qwen-9b.ini`, `muse.ini` |
| `g6e.xlarge` | `/presets/aws/g6e/xlarge/gemma-26b-a4b.ini`, `gemma-31b.ini`, `muse.ini` |
| `g7e.2xlarge` | `/presets/aws/g7e/2xlarge/qwen.ini`, `qwen-35b-a3b.ini`, `qwen-27b.ini`, `glm-4.7-flash.ini`, `muse.ini` |

The abbreviated names after the first absolute path are siblings in that same
directory. Dedicated presets stage one catalog key and load it at startup;
bundles remain available for flexible hosts. Pending, stopping, stopped, and
hibernated On-Demand instances do not count toward the running On-Demand vCPU
quota; unused Capacity Reservations do. NeurOn can therefore stop inactive
family hosts without changing their selected preset or S3 inventory.

The three `muse.ini` alternatives are supported by the pinned b10362 image,
whose source contains llama.cpp PR #26841. The shapes are Q4/128K×1 on
`g6.xlarge`, Q6/128K×2 on `g6e.xlarge`, and Q6/256K×4 on `g7e.2xlarge`; each
stages only its target, DFlash companion, and quantized projector. Treat their
first launch as a fit, contract, DFlash, projector, and concurrency gate before
production use.

## Deploy as plain CloudFormation (no CDK needed)

Grab the template from the **`template-latest`** GitHub release (published by
`build-aws.yml`), then:

```bash
gh release download template-latest -p prefer-ec2.template.json

aws cloudformation deploy \
  --template-file prefer-ec2.template.json \
  --stack-name prefer-ec2 \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides KeyName=my-key AllowedCidr=1.2.3.4/32
```

For example, a DeepSeek stack adds:

```bash
--parameter-overrides \
  InstanceType=g7e.12xlarge \
  ModelsPreset=/presets/aws/g7e/12xlarge/deepseek-v4-flash-0731.ini
```

`AmiId` is optional — leave it blank and the template's built-in RegionMap
resolves the right public PreFer AMI for whichever region (us-east-1 / us-east-2)
you deploy into. Pass `AmiId=ami-xxxx` only to pin a specific AMI.

Or upload the template in the CloudFormation console.

## Develop / re-synth (CDK)

```bash
npm install
npm run synth                 # print the template
```

`build-aws.yml`'s `cdk` job runs the synth in CI, bakes in the current
region -> AMI map (from the `ami` job's `ami-map` artifact, or the last release
on a CDK-only change), and publishes the template to the `template-latest`
release — nothing is committed back to the repo.
