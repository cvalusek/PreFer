#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { PreferStack } from '../lib/prefer-stack';

const app = new cdk.App();

new PreferStack(app, 'PreferEc2', {
  description: 'PreFer llama.cpp inference on EC2 (GPU + NVMe + S3 model cache).',
  // Env-agnostic on purpose: the synthesized template is region-portable and
  // deployable into any account. Consumers supply the AMI id / key per region.
  //
  // No assets in this stack, so drop the bootstrap-version rule — that lets the
  // synthesized template deploy via plain CloudFormation with no `cdk bootstrap`.
  synthesizer: new cdk.DefaultStackSynthesizer({
    generateBootstrapVersionRule: false,
  }),
});

app.synth();
