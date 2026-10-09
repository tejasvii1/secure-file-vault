variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Name used as a prefix for every resource"
  type        = string
  default     = "secure-file-vault"
}

variable "github_repo" {
  description = "GitHub repository (owner/name) allowed to deploy"
  type        = string
  default     = "tejasvii1/secure-file-vault"
}

variable "instance_type" {
  description = "EC2 instance size for the API server"
  type        = string
  default     = "t3.micro"
}
