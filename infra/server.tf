# ---- The EC2 server that runs the API container ----

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

# newest Amazon Linux 2023 image, looked up instead of hardcoding an AMI id
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

# the IP ranges CloudFront uses to reach origins, maintained by AWS
data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_security_group" "api" {
  name_prefix = "${var.project}-api-"
  description = "API server: HTTP from CloudFront only, no SSH"
  vpc_id      = data.aws_vpc.default.id

  # the only way in is through CloudFront; the server can't be reached directly from the internet
  ingress {
    description     = "HTTP from CloudFront"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    prefix_list_ids = [data.aws_ec2_managed_prefix_list.cloudfront.id]
  }

  egress {
    description = "Outbound to AWS APIs and VirusTotal"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ---- IAM role: what the server is allowed to do ----

resource "aws_iam_role" "api" {
  name_prefix = "${var.project}-api-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# lets GitHub Actions run the deploy script on the server through SSM, so port 22 never has to be open
resource "aws_iam_role_policy_attachment" "api_ssm" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "api" {
  name = "app-access"
  role = aws_iam_role.api.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "UploadedFiles"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.uploads.arn}/uploads/*"
      },
      {
        Sid      = "EcrLogin"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Sid      = "PullImage"
        Effect   = "Allow"
        Action   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"]
        Resource = aws_ecr_repository.api.arn
      },
      {
        Sid      = "ReadSecrets"
        Effect   = "Allow"
        Action   = "ssm:GetParameter"
        Resource = [aws_ssm_parameter.secret_key.arn, aws_ssm_parameter.vt_api_key.arn]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "api" {
  name_prefix = "${var.project}-api-"
  role        = aws_iam_role.api.name
}

resource "aws_instance" "api" {
  ami                    = nonsensitive(data.aws_ssm_parameter.al2023.value)
  instance_type          = var.instance_type
  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.api.id]
  iam_instance_profile   = aws_iam_instance_profile.api.name

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    region         = var.aws_region
    project        = var.project
    ecr_repo_url   = aws_ecr_repository.api.repository_url
    uploads_bucket = aws_s3_bucket.uploads.bucket
  })

  metadata_options {
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 2          # one extra hop so the container can get the role's credentials
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = 16
    encrypted   = true
  }

  tags = {
    Name = "${var.project}-api"
  }

  lifecycle {
    # a newer Amazon Linux image shouldn't replace the server (and the SQLite database on its disk)
    ignore_changes = [ami, user_data]
  }
}

# a fixed public address, so CloudFront's origin doesn't change if the server is stopped and started
resource "aws_eip" "api" {
  domain   = "vpc"
  instance = aws_instance.api.id
}
