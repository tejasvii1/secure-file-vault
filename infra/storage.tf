# ---- S3 bucket for uploaded files ----
# Private: nothing reads it except the API server's IAM role (see server.tf).

resource "aws_s3_bucket" "uploads" {
  bucket_prefix = "${var.project}-uploads-"
  force_destroy = true # lets `terraform destroy` remove the bucket even if it still has files in it
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket                  = aws_s3_bucket.uploads.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ---- ECR: the registry the Docker image is pushed to and pulled from ----

resource "aws_ecr_repository" "api" {
  name         = var.project
  force_delete = true

  image_scanning_configuration {
    scan_on_push = true # ECR checks every pushed image for known vulnerabilities
  }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep only the 5 most recent images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

# ---- Secrets in SSM Parameter Store ----
# The server reads these at deploy time, so they are never in the repo, the image, or a file on disk.

resource "random_password" "secret_key" {
  length  = 48
  special = false
}

resource "aws_ssm_parameter" "secret_key" {
  name  = "/${var.project}/SECRET_KEY"
  type  = "SecureString"
  value = random_password.secret_key.result
}

# Created with a placeholder. Set the real key yourself (see infra/README.md); Terraform then leaves it alone.
resource "aws_ssm_parameter" "vt_api_key" {
  name  = "/${var.project}/VT_API_KEY"
  type  = "SecureString"
  value = "replace-me"

  lifecycle {
    ignore_changes = [value]
  }
}
