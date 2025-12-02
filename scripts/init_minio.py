#!/usr/bin/env python3
# =============================================================================
# File: scripts/init_minio.py
# Description: Initialize MinIO bucket with public read policy
# =============================================================================
"""
Initialize MinIO storage bucket for WellWon.

Run after starting MinIO container:
    docker run -d --name wellwon-minio -p 9000:9000 -p 9001:9001 \
        -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
        -v minio_data:/data quay.io/minio/minio:RELEASE.2025-10-15T17-29-55Z \
        server /data --console-address ":9001"

Then run:
    python scripts/init_minio.py
"""

import json
import os

import boto3
from botocore.exceptions import ClientError


def main():
    # Configuration from environment or defaults
    endpoint_url = os.getenv("STORAGE_ENDPOINT_URL", "http://localhost:9000")
    access_key = os.getenv("STORAGE_ACCESS_KEY", "minioadmin")
    secret_key = os.getenv("STORAGE_SECRET_KEY", "minioadmin")
    bucket_name = os.getenv("STORAGE_BUCKET_NAME", "wellwon")

    print(f"Connecting to MinIO at {endpoint_url}...")

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )

    # Check if bucket exists
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f"Bucket '{bucket_name}' already exists")
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            # Create bucket
            print(f"Creating bucket '{bucket_name}'...")
            s3.create_bucket(Bucket=bucket_name)
            print(f"Bucket '{bucket_name}' created")
        else:
            raise

    # Set public read policy for all objects
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket_name}/*"],
            }
        ],
    }

    print("Setting public read policy...")
    s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
    print("Policy set successfully")

    print("\nMinIO initialization complete!")
    print(f"  Bucket: {bucket_name}")
    print(f"  Endpoint: {endpoint_url}")
    print(f"  Console: http://localhost:9001")
    print(f"  Public URL: {endpoint_url}/{bucket_name}")


if __name__ == "__main__":
    main()
