#!/bin/sh
# Runs automatically once LocalStack's S3 emulation is ready (mounted at
# /etc/localstack/init/ready.d/). Idempotent: safe if the bucket already
# exists from a previous container start against the same volume.
set -e

awslocal s3 mb "s3://${MEDIA_BUCKET_NAME:-deskhive-media}" 2>/dev/null || true
