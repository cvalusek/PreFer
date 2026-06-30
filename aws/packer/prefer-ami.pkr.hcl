packer {
  required_plugins {
    amazon = {
      source  = "github.com/hashicorp/amazon"
      version = ">= 1.3.0"
    }
  }
}

variable "region" {
  type        = string
  default     = "us-east-1"
  description = "Region to build the AMI in. Copy to other regions separately (CI matrix)."
}

variable "instance_type" {
  type        = string
  default     = "m7i.large"
  description = "Build instance type. Provisioning only installs scripts + warm-pulls the image (no GPU needed), so a cheap general instance builds fastest; the resulting AMI runs on any supported GPU family."
}

variable "prefer_image" {
  type        = string
  default     = "ghcr.io/cvalusek/prefer:latest"
  description = "Container image + tag to bake as offline fallback and pin in prefer-boot.env."
}

variable "ami_name_prefix" {
  type    = string
  default = "prefer-ec2"
}

# Resolve the base AMI from AWS's public SSM parameter for the Deep Learning
# Base GPU AMI (Ubuntu 24.04, x86_64). This is the authoritative, region-portable
# pointer to the latest build — no name filters to drift. That AMI ships the
# NVIDIA driver, Docker, nvidia-container-toolkit, and a `dlami-nvme` service
# that auto-mounts instance-store NVMe at /opt/dlami/nvme, so AWS owns the
# driver/Docker/NVMe plumbing and we don't.
data "amazon-parameterstore" "dlami" {
  name   = "/aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-24.04/latest/ami-id"
  region = var.region
}

source "amazon-ebs" "prefer" {
  region        = var.region
  instance_type = var.instance_type
  ssh_username  = "ubuntu"
  ami_name      = "${var.ami_name_prefix}-{{timestamp}}"
  source_ami    = data.amazon-parameterstore.dlami.value

  # Roomy root so the warm image pull fits; models never live here.
  launch_block_device_mappings {
    device_name           = "/dev/sda1"
    volume_size           = 100
    volume_type           = "gp3"
    delete_on_termination = true
  }

  tags = {
    Name    = "${var.ami_name_prefix}-{{timestamp}}"
    Project = "PreFer"
  }
}

build {
  sources = ["source.amazon-ebs.prefer"]

  provisioner "file" {
    source      = "../boot/"
    destination = "/tmp/prefer-boot"
  }

  provisioner "shell" {
    environment_vars = ["PREFER_IMAGE=${var.prefer_image}"]
    script           = "provision.sh"
  }
}
