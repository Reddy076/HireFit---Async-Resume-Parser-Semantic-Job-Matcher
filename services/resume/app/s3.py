import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

BUCKET = os.getenv("S3_BUCKET", "resumes")


def s3_client():
    # Path-style addressing: required by S3Mock, compatible with MinIO/S3.
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT", "http://s3mock:9090"),
        aws_access_key_id=os.getenv("S3_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.getenv("S3_SECRET_KEY", "minioadmin"),
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )


def ensure_bucket() -> None:
    c = s3_client()
    try:
        c.head_bucket(Bucket=BUCKET)
    except ClientError:
        c.create_bucket(Bucket=BUCKET)


def put_bytes(key: str, data: bytes, content_type: str = "application/pdf") -> None:
    ensure_bucket()
    s3_client().put_object(Bucket=BUCKET, Key=key, Body=data, ContentType=content_type)
