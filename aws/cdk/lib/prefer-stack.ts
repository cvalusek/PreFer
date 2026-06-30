import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';

/**
 * PreFer llama.cpp inference on EC2: GPU instance + instance-store NVMe runtime
 * + S3 model cache. Authored in CDK but distributed as the synthesized
 * CloudFormation template, so consumers need no CDK/Node toolchain.
 */
export class PreferStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ---- Parameters (filled in the CloudFormation console / CLI) ----
    const instanceTypeParam = new cdk.CfnParameter(this, 'InstanceType', {
      type: 'String',
      default: 'g6e.12xlarge',
      description:
        'GPU instance type with local NVMe instance store (the models run off NVMe).',
    });

    // No default: the AMI built by aws/packer in THIS region. Once an SSM
    // public parameter is published, this can become
    // type AWS::SSM::Parameter::Value<AWS::EC2::Image::Id> with a default path.
    const amiParam = new cdk.CfnParameter(this, 'AmiId', {
      type: 'AWS::EC2::Image::Id',
      description: 'PreFer AMI id (from aws/packer) in this region.',
    });

    const keyNameParam = new cdk.CfnParameter(this, 'KeyName', {
      type: 'AWS::EC2::KeyPair::KeyName',
      description: 'Existing EC2 key pair for SSH (Session Manager is also enabled).',
    });

    const allowedCidrParam = new cdk.CfnParameter(this, 'AllowedCidr', {
      type: 'String',
      default: '0.0.0.0/0',
      description: 'CIDR allowed to reach the inference port (8080) and SSH (22). Narrow this.',
    });

    const rootVolumeGbParam = new cdk.CfnParameter(this, 'RootVolumeGb', {
      type: 'Number',
      default: 100,
      description: 'Root EBS size (GB). Models do NOT live here — OS + container image only.',
    });

    // ---- Network: single-AZ public VPC, no NAT, free S3 gateway endpoint ----
    // Instance sits in a public subnet (direct IGW egress for HF / GHCR); S3
    // traffic takes the gateway endpoint (free, on-backbone, full bandwidth).
    const vpc = new ec2.Vpc(this, 'Vpc', {
      maxAzs: 1,
      natGateways: 0,
      subnetConfiguration: [
        { name: 'public', subnetType: ec2.SubnetType.PUBLIC, cidrMask: 24 },
      ],
    });
    vpc.addGatewayEndpoint('S3Endpoint', {
      service: ec2.GatewayVpcEndpointAwsService.S3,
    });

    // ---- Model cache bucket (created here; self-populates on first boot) ----
    const bucket = new s3.Bucket(this, 'ModelCache', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      // RETAIN so deleting the stack never destroys staged models. The cache is
      // reproducible from Hugging Face, so DESTROY + autoDeleteObjects is a fine
      // alternative if you'd rather not leave an orphan bucket behind.
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ---- Instance role: scoped S3 cache access + SSM Session Manager ----
    const role = new iam.Role(this, 'InstanceRole', {
      assumedBy: new iam.ServicePrincipal('ec2.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonSSMManagedInstanceCore'),
      ],
    });
    // Grants Get/List/Put on the bucket + objects (sync down, and the
    // self-populating sync up).
    bucket.grantReadWrite(role);

    // ---- Security group ----
    const sg = new ec2.SecurityGroup(this, 'Sg', { vpc, allowAllOutbound: true });
    sg.addIngressRule(
      ec2.Peer.ipv4(allowedCidrParam.valueAsString),
      ec2.Port.tcp(8080),
      'inference API',
    );
    sg.addIngressRule(
      ec2.Peer.ipv4(allowedCidrParam.valueAsString),
      ec2.Port.tcp(22),
      'ssh',
    );

    // ---- User data: inject per-deployment config, then (re)start the unit ----
    // S3_BUCKET_NAME is a write-once value, so first-boot user-data is the right
    // place; the systemd unit re-reads the env file on every later start.
    const userData = ec2.UserData.forLinux();
    userData.addCommands(
      'set -euo pipefail',
      `echo "S3_BUCKET_NAME=${bucket.bucketName}" >> /opt/prefer/prefer-boot.env`,
      'systemctl restart prefer-boot.service',
    );

    // AMI comes from a CFN parameter, so wrap it in a minimal IMachineImage.
    // (userData is supplied via the instance prop below; keep this one empty.)
    const machineImage: ec2.IMachineImage = {
      getImage: () => ({
        imageId: amiParam.valueAsString,
        osType: ec2.OperatingSystemType.LINUX,
        userData: ec2.UserData.forLinux(),
      }),
    };

    const instance = new ec2.Instance(this, 'Instance', {
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      instanceType: new ec2.InstanceType(instanceTypeParam.valueAsString),
      machineImage,
      securityGroup: sg,
      role,
      keyPair: ec2.KeyPair.fromKeyPairName(this, 'KeyPair', keyNameParam.valueAsString),
      userData,
      blockDevices: [
        {
          deviceName: '/dev/sda1',
          volume: ec2.BlockDeviceVolume.ebs(rootVolumeGbParam.valueAsNumber, {
            volumeType: ec2.EbsDeviceVolumeType.GP3,
            deleteOnTermination: true,
          }),
        },
      ],
    });

    // IMDS hop limit = 2 so the bridge-networked container can reach the
    // instance role's credentials (EC2 default of 1 blocks it).
    const cfnInstance = instance.node.defaultChild as ec2.CfnInstance;
    cfnInstance.metadataOptions = {
      httpTokens: 'required',
      httpPutResponseHopLimit: 2,
      httpEndpoint: 'enabled',
    };

    // ---- Outputs ----
    new cdk.CfnOutput(this, 'ApiUrl', {
      value: `http://${instance.instancePublicIp}:8080`,
      description: 'OpenAI-compatible endpoint once the container is serving.',
    });
    new cdk.CfnOutput(this, 'ModelCacheBucket', { value: bucket.bucketName });
    new cdk.CfnOutput(this, 'SsmSession', {
      value: `aws ssm start-session --target ${instance.instanceId}`,
      description: 'Shell in without SSH to watch: docker logs -f prefer',
    });
  }
}
