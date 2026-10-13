#!/usr/bin/env python3
"""Limpeza: remove todos os objetos do bucket de demo (uso repetido da demo)."""
import argparse
import os
import sys

import boto3
from botocore.config import Config

DEFAULT_ENV = "/home/d50055825/mcp-hwc/.env"


def load_creds(env_file):
    ak, sk = os.environ.get("HWC_AK"), os.environ.get("HWC_SK")
    if (not ak or not sk) and os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("HWC_AK="):
                    ak = ak or line.split("=", 1)[1].strip().strip('"')
                if line.startswith("HWC_SK="):
                    sk = sk or line.split("=", 1)[1].strip().strip('"')
    return ak, sk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", default="onprem-migration-demo-sgp")
    ap.add_argument("--region", default="ap-southeast-3")
    ap.add_argument("--endpoint", default="https://obs.ap-southeast-3.myhuaweicloud.com")
    ap.add_argument("--env-file", default=DEFAULT_ENV)
    args = ap.parse_args()

    ak, sk = load_creds(args.env_file)
    c = boto3.client("s3", endpoint_url=args.endpoint, region_name=args.region,
                     aws_access_key_id=ak, aws_secret_access_key=sk,
                     config=Config(signature_version="s3v4",
                                   s3={"addressing_style": "virtual"},
                                   request_checksum_calculation="when_required",
                                   response_checksum_validation="when_required"))
    total = 0
    while True:
        resp = c.list_objects_v2(Bucket=args.bucket, MaxKeys=1000)
        keys = [{"Key": o["Key"]} for o in resp.get("Contents", [])]
        if not keys:
            break
        c.delete_objects(Bucket=args.bucket, Delete={"Objects": keys, "Quiet": True})
        total += len(keys)
    # aborta multiparts incompletos
    mp = c.list_multipart_uploads(Bucket=args.bucket)
    for u in mp.get("Uploads", []):
        c.abort_multipart_upload(Bucket=args.bucket, Key=u["Key"], UploadId=u["UploadId"])
    print(f"[cleanup] {total} objetos removidos de {args.bucket}")


if __name__ == "__main__":
    main()
