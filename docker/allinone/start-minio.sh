#!/usr/bin/env bash
# MinIO with the per-install root creds from nir-env.sh (-> /data/secrets.env).
set -euo pipefail
# shellcheck disable=SC1091
source /opt/allinone/nir-env.sh
export MINIO_ROOT_USER MINIO_ROOT_PASSWORD
exec minio server /data/minio --address 127.0.0.1:9000 --console-address 127.0.0.1:9001
