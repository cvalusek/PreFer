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
| `AmiId` | `` (blank) | Optional override; blank uses the built-in RegionMap for the deploy region. Set an `ami-xxxx` only to pin a specific AMI |
| `KeyName` | — | Existing EC2 key pair (SSH; SSM also enabled) |
| `AllowedCidr` | `0.0.0.0/0` | Narrow this to your IP |
| `RootVolumeGb` | `100` | OS + container image only; models live on NVMe |

## Deploy as plain CloudFormation (no CDK needed)

Grab the template from the **`template-latest`** GitHub release (published by
`build-cdk.yml`), then:

```bash
gh release download template-latest -p prefer-ec2.template.json

aws cloudformation deploy \
  --template-file prefer-ec2.template.json \
  --stack-name prefer-ec2 \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides KeyName=my-key AllowedCidr=1.2.3.4/32
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

`build-cdk.yml` runs the synth in CI, bakes in the current region -> AMI map
(from the build-ami `ami-map` artifact), and publishes the template to the
`template-latest` release — nothing is committed back to the repo.
