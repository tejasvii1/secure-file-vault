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

variable "github_subject_prefix" {
  description = "How GitHub identifies the repository allowed to deploy. Includes the owner and repo ids, so it still points at this repo after a rename. Shown by: gh api repos/OWNER/REPO/actions/oidc/customization/sub"
  type        = string
  default     = "repo:tejasvii1@196728462/secure-file-vault@1328013485"
}

variable "instance_type" {
  description = "EC2 instance size for the API server"
  type        = string
  default     = "t3.micro"
}
