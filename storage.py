import os
from typing import Optional

import boto3
from botocore.exceptions import ClientError

# Where uploaded files live. main.py only calls save / read / delete, so it doesn't care whether
# the bytes end up on the local disk (development) or in an S3 bucket (AWS).
# save() returns the "location" string that gets stored in File.stored_path and is passed back
# to read() and delete() later.


class LocalStorage:
    def __init__(self, upload_dir: str):
        self.upload_dir = upload_dir
        os.makedirs(upload_dir, exist_ok=True)

    def save(self, name: str, contents: bytes) -> str:
        path = os.path.join(self.upload_dir, name)
        with open(path, "wb") as buffer:
            buffer.write(contents)
        return path

    def read(self, location: str) -> Optional[bytes]:
        if not os.path.exists(location):
            return None
        with open(location, "rb") as f:
            return f.read()

    def delete(self, location: str) -> None:
        if os.path.exists(location):
            os.remove(location)


class S3Storage:
    def __init__(self, bucket: str):
        self.bucket = bucket
        # no access keys here: boto3 finds credentials on its own, and on EC2 that means the
        # temporary credentials of the IAM role attached to the instance
        self.client = boto3.client("s3")

    def save(self, name: str, contents: bytes) -> str:
        key = f"uploads/{name}"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=contents, ServerSideEncryption="AES256")
        return key

    def read(self, location: str) -> Optional[bytes]:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=location)
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise
        return response["Body"].read()

    def delete(self, location: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=location)


def get_storage():
    # setting S3_BUCKET switches the app to S3; without it files stay on the local disk
    bucket = os.getenv("S3_BUCKET")
    if bucket:
        return S3Storage(bucket)
    return LocalStorage(os.getenv("UPLOAD_DIR", "uploads"))
