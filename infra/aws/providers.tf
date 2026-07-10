terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Stub — configure a real backend (S3 + DynamoDB lock table) before
  # any environment is actually provisioned.
  backend "local" {}
}

provider "aws" {
  region = var.aws_region
}
