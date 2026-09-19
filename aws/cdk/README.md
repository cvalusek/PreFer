# PreFer EC2 — CDK app

This CDK app authors the public CloudFormation template for one llama.cpp GPU
instance with `/models` on instance-store NVMe and optional S3 read-through.
Consumers deploy the synthesized template without a Node/CDK toolchain.

## Inputs

| Parameter | Default | Notes |
| --- | --- | --- |
| `InstanceType` | `g7e.2xlarge` | GPU instance with local NVMe |
| `RuntimeHandoffBase64` | required | Release-bound llama.cpp handoff as RFC 4648 base64 JSON |
| `AmiId` | blank | Optional override; otherwise use the release RegionMap |
| `KeyName` | required | Existing EC2 key pair; SSM is also enabled |
| `AllowedCidr` | `0.0.0.0/0` | Narrow for port 8080 and SSH |
| `RootVolumeGb` | `100` | OS and image only; models use NVMe |

There is no `ModelsPreset`, hardware deployment selector, or preset-derived
prestage list. The controller uses the provider hardware catalog and live
resource observations to create the handoff before stack deployment.

User data atomically writes AWS/S3 values, the handoff, and
`LLAMA_ARG_MODELS_MAX=1` to `/opt/prefer/deployment.env`. The boot service waits
for cloud-init and reads that file after immutable AMI defaults. It never starts
the runtime from user data.

## Deploy

```bash
gh release download template-latest -p prefer-ec2.template.json
aws cloudformation deploy \
  --template-file prefer-ec2.template.json \
  --stack-name prefer-ec2 \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    KeyName=my-key \
    RuntimeHandoffBase64="$HANDOFF_BASE64"
```

The S3 bucket is retained on stack deletion. Model weights remain external and
are staged from the handoff at boot.

## Authoring

```bash
cd aws/cdk
npm ci
npm test
npm run synth
```
