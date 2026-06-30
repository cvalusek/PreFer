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
  - user-data injecting `S3_BUCKET_NAME` into `/opt/prefer/prefer-boot.env`.

## Parameters

| Parameter | Default | Notes |
| --------- | ------- | ----- |
| `InstanceType` | `g6e.12xlarge` | GPU family with local NVMe instance store |
| `AmiId` | — | PreFer AMI built by `aws/packer` in this region |
| `KeyName` | — | Existing EC2 key pair (SSH; SSM also enabled) |
| `AllowedCidr` | `0.0.0.0/0` | Narrow this to your IP |
| `RootVolumeGb` | `100` | OS + container image only; models live on NVMe |

## Deploy as plain CloudFormation (no CDK needed)

```bash
aws cloudformation deploy \
  --template-file ../cloudformation/prefer-ec2.template.json \
  --stack-name prefer-ec2 \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides AmiId=ami-xxxx KeyName=my-key AllowedCidr=1.2.3.4/32
```

Or upload the template in the CloudFormation console.

## Develop / re-synth (CDK)

```bash
npm install
npm run synth                 # print the template
npm run synth:template        # write ../cloudformation/prefer-ec2.template.json
```

`build-iac.yml` runs the synth in CI and republishes the template so it never
drifts from this source.
