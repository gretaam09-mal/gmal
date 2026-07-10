variable "aws_region" {
  description = "AWS region. Provision is UK-hosted: must stay eu-west-2 (London)."
  type        = string
  default     = "eu-west-2"

  validation {
    condition     = var.aws_region == "eu-west-2"
    error_message = "Provision data must stay in eu-west-2 (London) for UK hosting."
  }
}

variable "environment" {
  description = "Deployment environment name, e.g. staging, production."
  type        = string
  default     = "development"
}
