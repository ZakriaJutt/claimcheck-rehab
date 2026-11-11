"""Configure the object-store bucket for AD-11 (B2-S02). Idempotent.

Sets the lifecycle rule `expire-import-payloads`: objects under `clinic/` tagged `purpose=import_payload`
expire one day after they are written, as a backstop to the hourly `retention_purge` and the worker's
bucket-wide sweep. If the bucket has versioning, earlier versions expire after one day as well. Refuses a
bucket with a public policy. Locally the MinIO bucket from S3_BUCKET; in production the same script must
be run against the real S3 bucket (a deployment requirement recorded in TRD AD-11).

Usage: python scripts/setup_storage.py [--check]   (--check only verifies and exits 1 if not configured)
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from claimcheck_core.settings import get_settings
from claimcheck_core.storage import make_s3_store

RULE_ID = "expire-import-payloads"


def lifecycle_rule(versioned: bool) -> dict[str, Any]:
    rule: dict[str, Any] = {
        "ID": RULE_ID,
        "Status": "Enabled",
        "Filter": {"And": {"Prefix": "clinic/", "Tags": [{"Key": "purpose", "Value": "import_payload"}]}},
        "Expiration": {"Days": 1},
    }
    if versioned:
        rule["NoncurrentVersionExpiration"] = {"NoncurrentDays": 1}
    return rule


def configured(client: Any, bucket: str) -> bool:
    try:
        rules = client.get_bucket_lifecycle_configuration(Bucket=bucket)["Rules"]
    except client.exceptions.ClientError:
        return False
    return any(r.get("ID") == RULE_ID and r.get("Status") == "Enabled"
               and r.get("Expiration", {}).get("Days") == 1 for r in rules)


def setup(check_only: bool = False) -> bool:
    store = make_s3_store()
    client: Any = store._c  # noqa: SLF001 - the setup script needs the raw client
    bucket = get_settings().s3_bucket
    try:
        client.get_bucket_policy(Bucket=bucket)
        print("refusing: the bucket has a policy; this bucket must stay private", file=sys.stderr)
        return False
    except client.exceptions.ClientError:
        pass  # no policy: private
    if check_only:
        return configured(client, bucket)
    versioned = client.get_bucket_versioning(Bucket=bucket).get("Status") == "Enabled"
    client.put_bucket_lifecycle_configuration(Bucket=bucket,
                                              LifecycleConfiguration={"Rules": [lifecycle_rule(versioned)]})
    return configured(client, bucket)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="setup_storage")
    p.add_argument("--check", action="store_true")
    args = p.parse_args(argv)
    ok = setup(check_only=args.check)
    print(f"bucket {get_settings().s3_bucket}: lifecycle rule {RULE_ID} {'present' if ok else 'MISSING'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
