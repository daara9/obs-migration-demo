#!/usr/bin/env python3
"""Fase 3 - Verificacao: valida integridade origem x destino no OBS.

Compara contagem, tamanho e MD5 (via metadado do objeto) entre o
inventory.csv local e o bucket OBS. Gera um relatorio final.
"""
import argparse
import csv
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.config import Config

DEFAULT_ENV = "/home/d50055825/mcp-hwc/.env"
BASE = os.path.dirname(os.path.abspath(__file__))


def human(n):
    n = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def load_creds(env_file):
    ak, sk = os.environ.get("HWC_AK"), os.environ.get("HWC_SK")
    if (not ak or not sk) and os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k == "HWC_AK" and not ak:
                    ak = v
                if k == "HWC_SK" and not sk:
                    sk = v
    if not ak or not sk:
        sys.exit("[erro] credenciais HWC_AK/HWC_SK nao encontradas")
    return ak, sk


def make_client(args):
    ak, sk = load_creds(args.env_file)
    cfg = Config(signature_version="s3v4", s3={"addressing_style": "virtual"},
                 request_checksum_calculation="when_required",
                 response_checksum_validation="when_required",
                 retries={"max_attempts": 2}, max_pool_connections=16)
    return boto3.client("s3", endpoint_url=args.endpoint, region_name=args.region,
                        aws_access_key_id=ak, aws_secret_access_key=sk, config=cfg)


def list_all(client, bucket, prefix):
    objs = {}
    token = None
    while True:
        kw = dict(Bucket=bucket, Prefix=prefix) if prefix else dict(Bucket=bucket)
        if token:
            kw["ContinuationToken"] = token
        resp = client.list_objects_v2(**kw)
        for o in resp.get("Contents", []):
            objs[o["Key"]] = o["Size"]
        if resp.get("IsTruncated"):
            token = resp.get("NextContinuationToken")
        else:
            break
    return objs


def head_meta(client, bucket, key):
    h = client.head_object(Bucket=bucket, Key=key)
    return h.get("Metadata", {}), h.get("ETag", "").strip('"')


def main():
    ap = argparse.ArgumentParser(description="Verifica integridade da migracao")
    ap.add_argument("--inventory", default=os.path.join(BASE, "inventory.csv"))
    ap.add_argument("--bucket", default="onprem-migration-demo-sgp")
    ap.add_argument("--region", default="ap-southeast-3")
    ap.add_argument("--endpoint", default="https://obs.ap-southeast-3.myhuaweicloud.com")
    ap.add_argument("--prefix", default="")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--report", default=os.path.join(BASE, "verify_report.csv"))
    ap.add_argument("--env-file", default=DEFAULT_ENV)
    args = ap.parse_args()

    rows = []
    with open(args.inventory, newline="") as f:
        for r in csv.DictReader(f):
            rows.append((r["relpath"], int(r["size"]), r["md5"]))

    client = make_client(args)
    remote = list_all(client, args.bucket, args.prefix)

    ok, size_bad, hash_bad, missing = 0, [], [], []
    results = []

    def check(row):
        rel, size, md5 = row
        key = (args.prefix + rel) if args.prefix else rel
        if key not in remote:
            return ("missing", rel, "objeto ausente")
        if remote[key] != size:
            return ("size", rel, f"{remote[key]} != {size}")
        meta, etag = head_meta(client, args.bucket, key)
        remote_md5 = meta.get("md5") or etag
        if remote_md5 != md5:
            return ("hash", rel, f"{remote_md5[:12]}.. != {md5[:12]}..")
        return ("ok", rel, "")

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for status, rel, detail in ex.map(check, rows):
            results.append((status, rel, detail))
            if status == "ok":
                ok += 1
            elif status == "missing":
                missing.append((rel, detail))
            elif status == "size":
                size_bad.append((rel, detail))
            else:
                hash_bad.append((rel, detail))

    with open(args.report, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["status", "relpath", "detail"])
        w.writerows(results)

    total = len(rows)
    pct = 100.0 * ok / total if total else 0
    extra = max(len(remote) - total, 0)
    print()
    print("=" * 60)
    print(" RELATORIO DE INTEGRIDADE  (origem  vs  OBS)")
    print("=" * 60)
    print(f"  origem (inventory) : {total} objetos / {human(sum(r[1] for r in rows))}")
    print(f"  destino (bucket)   : {len(remote)} objetos / {human(sum(remote.values()))}")
    print(f"  integros           : {ok} ({pct:.2f}%)")
    print(f"  ausentes           : {len(missing)}")
    print(f"  tamanho divergente : {len(size_bad)}")
    print(f"  hash divergente    : {len(hash_bad)}")
    if extra:
        print(f"  outros no bucket   : {extra} (nao fazem parte da migracao)")
    print("-" * 60)
    if ok == total:
        print("  RESULTADO: [OK] migracao 100% integra")
    else:
        print("  RESULTADO: [ATENCAO] divergencias encontradas")
        for label, lst in (("ausente", missing), ("tamanho", size_bad), ("hash", hash_bad)):
            for rel, detail in lst[:10]:
                print(f"    - [{label}] {rel}: {detail}")
    print(f"  report: {args.report}")
    print("=" * 60)
    sys.exit(0 if ok == total else 1)


if __name__ == "__main__":
    main()
