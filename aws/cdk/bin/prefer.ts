#!/usr/bin/env node
import * as fs from 'fs';
import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import { PreferStack } from '../lib/prefer-stack';

// region -> ami id, baked into the template's RegionMap. CI drops the real
// ami-map.json (produced by the build-ami workflow) here before synth; the
// placeholder keeps local/PR synth working before any AMI has been built.
const amiMapPath = path.join(__dirname, '..', 'ami-map.json');
const amiMap: Record<string, string> = fs.existsSync(amiMapPath)
  ? JSON.parse(fs.readFileSync(amiMapPath, 'utf8'))
  : { 'us-east-1': 'ami-00000000000000000' };

const app = new cdk.App();

new PreferStack(app, 'PreferEc2', {
  amiMap,
  description: 'PreFer llama.cpp inference on EC2 (GPU + NVMe + S3 model cache).',
  // Env-agnostic on purpose: the synthesized template is region-portable and
  // deployable into any account. The AMI is resolved from the baked-in
  // RegionMap; consumers supply only the key pair.
  //
  // No assets in this stack, so drop the bootstrap-version rule — that lets the
  // synthesized template deploy via plain CloudFormation with no `cdk bootstrap`.
  synthesizer: new cdk.DefaultStackSynthesizer({
    generateBootstrapVersionRule: false,
  }),
});

app.synth();
