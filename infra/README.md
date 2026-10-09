# AWS infrastructure

Terraform that runs Secure File Vault on AWS.

```text
Browser ── HTTPS ──▶ CloudFront ──┬── /        ──▶ S3 (React frontend, private bucket)
                                  └── /api/*   ──▶ EC2 (Docker: FastAPI) ──▶ S3 (uploaded files)
                                                        ▲
GitHub Actions ── OIDC ──▶ ECR (image) ── SSM ──────────┘
```

| File | What it creates |
|---|---|
| `storage.tf` | Private S3 bucket for uploads, ECR image registry, secrets in SSM Parameter Store |
| `server.tf` | EC2 server, its security group (HTTP from CloudFront only, no SSH), and its IAM role |
| `cdn.tf` | Frontend bucket and the CloudFront distribution that serves the site over HTTPS |
| `github.tf` | The role GitHub Actions assumes to deploy, limited to this repo's `main` branch |
| `user_data.sh.tftpl` | First-boot script: installs Docker and writes the `deploy-vault` script |

## Create everything

Sign the AWS CLI in first (`aws login`), then:

```bash
cd infra
terraform init
terraform plan     # shows what would be created; changes nothing
terraform apply    # creates it after you type "yes"
```

Then:

1. Copy the outputs into GitHub repository variables so the deploy job can run:

   ```bash
   gh variable set AWS_DEPLOY_ROLE_ARN        --body "$(terraform output -raw deploy_role_arn)"
   gh variable set AWS_REGION                 --body "$(terraform output -raw aws_region)"
   gh variable set ECR_REPOSITORY_URL         --body "$(terraform output -raw ecr_repository_url)"
   gh variable set FRONTEND_BUCKET            --body "$(terraform output -raw frontend_bucket)"
   gh variable set CLOUDFRONT_DISTRIBUTION_ID --body "$(terraform output -raw cloudfront_distribution_id)"
   gh variable set EC2_INSTANCE_ID            --body "$(terraform output -raw instance_id)"
   gh variable set SITE_URL                   --body "$(terraform output -raw site_url)"
   ```

2. Store the real VirusTotal key (Terraform creates the parameter with a placeholder):

   ```bash
   aws ssm put-parameter --name /secure-file-vault/VT_API_KEY --type SecureString --overwrite --value 'your-key'
   ```

3. Push to `main` (or re-run the CI workflow). The `deploy` job builds the image, publishes the frontend, and restarts the API. The app is then live at `terraform output site_url`.

## Delete everything

```bash
terraform destroy
```

This removes every resource, including uploaded files, and stops all charges.

## Known limitations

- The database is SQLite on the server's disk. It survives deploys and restarts, but not replacing the server.
- CloudFront talks to the server over HTTP. Traffic between the browser and CloudFront is HTTPS, and the server only accepts connections from CloudFront, but that last hop is not encrypted.
- Terraform state is kept in a local file (`terraform.tfstate`, gitignored). It contains the generated `SECRET_KEY`, so don't share or commit it.
