output "site_url" {
  description = "Public HTTPS address of the app"
  value       = "https://${aws_cloudfront_distribution.site.domain_name}"
}

# The rest are copied into GitHub repository variables for the deploy job (see infra/README.md).

output "aws_region" {
  value = var.aws_region
}

output "deploy_role_arn" {
  value = aws_iam_role.deploy.arn
}

output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "frontend_bucket" {
  value = aws_s3_bucket.frontend.bucket
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.site.id
}

output "instance_id" {
  value = aws_instance.api.id
}

output "uploads_bucket" {
  value = aws_s3_bucket.uploads.bucket
}
