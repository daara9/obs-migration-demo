#!/usr/bin/env python3
"""Fase 2 - Transferencia: migra a origem on-prem para o OBS (S3-compativel).

Motor de upload paralelo com multipart, retomada (--resume) e retries, com
dashboard de progresso ao vivo (rich) mostrando objetos, MB/s, ETA e eventos.
"""
import argparse
import csv
import os
import sys
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

DEFAULT_ENV = "/home/d50055825/mcp-hwc/.env"
BASE = os.path.dirname(os.path.abspath(__file__))
MB = 1024 * 1024


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
    cfg = Config(
        signature_version="s3v4",
        s3={"addressing_style": "virtual"},
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
        retries={"max_attempts": 1},
        max_pool_connections=args.workers * 2,
        connect_timeout=20,
        read_timeout=120,
    )
    return boto3.client(
        "s3",
        endpoint_url=args.endpoint,
        region_name=args.region,
        aws_access_key_id=ak,
        aws_secret_access_key=sk,
        config=cfg,
    )


def load_inventory(path):
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            rows.append((r["relpath"], int(r["size"]), r["md5"]))
    return rows


# --------------------------------------------------------------------------
# Estado do dashboard (thread-safe)
# --------------------------------------------------------------------------
class State:
    def __init__(self, rows):
        self.lock = threading.Lock()
        self.total_files = len(rows)
        self.total_bytes = sum(r[1] for r in rows)
        self.done_files = 0
        self.failed = 0
        self.retries = 0
        self.skipped = 0
        self.done_bytes = 0
        self.start = time.time()
        self.samples = deque(maxlen=240)
        self.events = deque(maxlen=9)
        self.active = {}

    def add_bytes(self, n):
        with self.lock:
            self.done_bytes += n
            self.samples.append((time.time(), self.done_bytes))

    def set_active(self, name, detail):
        with self.lock:
            self.active[name] = detail

    def finish_file(self, name, ok, detail, was_retry=False):
        with self.lock:
            self.active.pop(name, None)
            if ok:
                self.done_files += 1
            else:
                self.failed += 1
            mark = "[green]OK [/]" if ok else "[red]ERR[/]"
            self.events.append((mark, name, detail))

    def add_retry(self, name, detail):
        with self.lock:
            self.retries += 1
            self.events.append(("[yellow]RTY[/]", name, detail))

    def add_skip(self, name, detail):
        with self.lock:
            self.skipped += 1
            self.done_files += 1
            self.events.append(("[cyan]SKP[/]", name, detail))

    def snapshot(self):
        with self.lock:
            return dict(
                total_files=self.total_files,
                total_bytes=self.total_bytes,
                done_files=self.done_files,
                failed=self.failed,
                retries=self.retries,
                skipped=self.skipped,
                done_bytes=self.done_bytes,
                elapsed=time.time() - self.start,
                samples=list(self.samples),
                events=list(self.events),
                active=dict(self.active),
            )


def speed_eta(snap):
    now = time.time()
    win = [(t, b) for (t, b) in snap["samples"] if now - t <= 5.0]
    if len(win) >= 2:
        dt = win[-1][0] - win[0][0]
        speed = (win[-1][1] - win[0][1]) / dt if dt > 0 else 0.0
    else:
        speed = snap["done_bytes"] / snap["elapsed"] if snap["elapsed"] > 0 else 0.0
    remaining = max(snap["total_bytes"] - snap["done_bytes"], 0)
    eta = remaining / speed if speed > 0 else 0.0
    avg = snap["done_bytes"] / snap["elapsed"] if snap["elapsed"] > 0 else 0.0
    return speed, avg, eta


def render(snap, args):
    from rich.console import Group
    from rich.panel import Panel
    from rich.progress_bar import ProgressBar
    from rich.table import Table
    from rich.text import Text

    fbar = ProgressBar(total=max(snap["total_files"], 1), completed=snap["done_files"])
    bbar = ProgressBar(total=max(snap["total_bytes"], 1), completed=snap["done_bytes"])
    speed, avg, eta = speed_eta(snap)

    f_pct = 100 * snap["done_files"] / max(snap["total_files"], 1)
    b_pct = 100 * snap["done_bytes"] / max(snap["total_bytes"], 1)

    head = Table.grid(expand=True)
    head.add_column(justify="left")
    head.add_column(justify="right")
    head.add_row(
        Text(f"OBS Migration  on-prem  ->  {args.region}  [{args.bucket}]", style="bold"),
        Text(time.strftime("%H:%M:%S"), style="dim"),
    )

    body = Table.grid(padding=(0, 2))
    body.add_column(justify="right", style="bold cyan", width=10)
    body.add_column()
    body.add_column(justify="right", width=22)
    body.add_row("Arquivos", fbar, f"{snap['done_files']:,}/{snap['total_files']:,}  {f_pct:4.1f}%")
    body.add_row("Dados", bbar, f"{human(snap['done_bytes'])}/{human(snap['total_bytes'])}  {b_pct:4.1f}%")

    counters = Text()
    counters.append(f"OK {snap['done_files']}  ", style="green")
    counters.append(f"Falhas {snap['failed']}  ", style="red")
    counters.append(f"Retry {snap['retries']}  ", style="yellow")
    counters.append(f"Skip {snap['skipped']}  ", style="cyan")
    counters.append(f"| {human(speed)}/s agora  | media {human(avg)}/s  | ETA {fmt_eta(eta)}  | decorrido {fmt_eta(snap['elapsed'])}")

    active = Table(box=None, show_header=True, header_style="dim", expand=True, pad_edge=False)
    active.add_column("em andamento", overflow="fold")
    active.add_column("progresso", width=24)
    if snap["active"]:
        for name, detail in list(snap["active"].items())[:6]:
            active.add_row(f"[yellow]{name}[/]", detail)
    else:
        active.add_row("[dim]--[/]", "")

    events = Table(box=None, show_header=False, expand=True, pad_edge=False)
    events.add_column(width=5)
    events.add_column(overflow="fold")
    events.add_column(width=12, justify="right")
    for mark, name, detail in reversed(snap["events"]):
        events.add_row(mark, name, detail)

    grid = Table.grid(expand=True)
    grid.add_row(Panel(Group(head, Text(), body, Text(), counters),
                       border_style="blue"))
    grid.add_row(Panel(Group(active, Text("", style="dim"), events),
                       title="eventos", border_style="grey37"))
    return grid


def fmt_eta(sec):
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# --------------------------------------------------------------------------
# Upload
# --------------------------------------------------------------------------
def upload_one(client, args, state, rel, size, md5):
    key = (args.prefix + rel) if args.prefix else rel
    local = os.path.join(args.src, rel)
    name = rel

    if args.resume:
        try:
            h = client.head_object(Bucket=args.bucket, Key=key)
            if h.get("Metadata", {}).get("md5") == md5:
                state.add_bytes(size)
                state.add_skip(name, "ja existente")
                return True
        except ClientError:
            pass

    attempt = 0
    while True:
        attempt += 1
        try:
            if size <= args.threshold * MB:
                state.set_active(name, "single put")
                with open(local, "rb") as f:
                    client.put_object(Bucket=args.bucket, Key=key, Body=f,
                                      Metadata={"md5": md5, "srcpath": rel})
                state.add_bytes(size)
            else:
                _multipart(client, args, state, local, key, rel, size, md5)
            state.finish_file(name, True, human(size))
            return True
        except Exception as e:
            if attempt > args.retries:
                state.finish_file(name, False, f"{type(e).__name__}: {str(e)[:60]}")
                return False
            state.add_retry(name, f"tentativa {attempt}/{args.retries}")
            time.sleep(min(2 ** attempt * 0.5, 4))


def _multipart(client, args, state, local, key, rel, size, md5):
    part_size = args.part_size * MB
    nparts = (size + part_size - 1) // part_size
    mpu = client.create_multipart_upload(
        Bucket=args.bucket, Key=key,
        Metadata={"md5": md5, "srcpath": rel},
    )
    mpu_id = mpu["UploadId"]
    parts = []
    try:
        with open(local, "rb") as f:
            for i in range(1, nparts + 1):
                chunk = f.read(part_size)
                for pa in range(3):
                    try:
                        resp = client.upload_part(
                            Bucket=args.bucket, Key=key, UploadId=mpu_id,
                            PartNumber=i, Body=chunk,
                        )
                        break
                    except Exception:
                        if pa == 2:
                            raise
                        time.sleep(1.5)
                parts.append({"ETag": resp["ETag"], "PartNumber": i})
                state.add_bytes(len(chunk))
                state.set_active(rel, f"multipart {i}/{nparts}")
        client.complete_multipart_upload(
            Bucket=args.bucket, Key=key, UploadId=mpu_id,
            MultipartUpload={"Parts": parts},
        )
    except Exception:
        try:
            client.abort_multipart_upload(Bucket=args.bucket, Key=key, UploadId=mpu_id)
        except Exception:
            pass
        raise


def run_plain(client, args, state, rows):
    """Modo --plain: barra simples com tqdm (sem painel rich)."""
    from tqdm import tqdm
    from concurrent.futures import as_completed
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(upload_one, client, args, state, r, s, m) for r, s, m in rows]
        with tqdm(total=len(rows), unit="obj", ncols=90) as bar:
            for _ in as_completed(futs):
                bar.update(1)
                sn = state.snapshot()
                bar.set_postfix_str(f"{human(sn['done_bytes'])} enviados")


def main():
    ap = argparse.ArgumentParser(description="Migra on-prem -> OBS")
    ap.add_argument("--src", default=os.path.join(BASE, "onprem"))
    ap.add_argument("--inventory", default=os.path.join(BASE, "inventory.csv"))
    ap.add_argument("--bucket", default="onprem-migration-demo-sgp")
    ap.add_argument("--region", default="ap-southeast-3")
    ap.add_argument("--endpoint", default="https://obs.ap-southeast-3.myhuaweicloud.com")
    ap.add_argument("--prefix", default="")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--part-size", type=int, default=16, help="MB por parte (multipart)")
    ap.add_argument("--threshold", type=int, default=16, help="MB a partir do qual usa multipart")
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--resume", action="store_true", help="pula objetos ja migrados (md5 igual)")
    ap.add_argument("--plain", action="store_true", help="barra simples (tqdm)")
    ap.add_argument("--env-file", default=DEFAULT_ENV)
    args = ap.parse_args()

    rows = load_inventory(args.inventory)
    client = make_client(args)
    state = State(rows)
    t0 = time.time()

    print(f"[migrate] {len(rows)} arquivos | {human(state.total_bytes)} | "
          f"workers={args.workers} part={args.part_size}MB "
          f"multipart>={args.threshold}MB -> {args.bucket} ({args.region})")

    if args.plain:
        run_plain(client, args, state, rows)
    else:
        from rich.live import Live
        with Live(render(state.snapshot(), args), refresh_per_second=10,
                  screen=False) as live:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futs = [ex.submit(upload_one, client, args, state, r, s, m)
                        for r, s, m in rows]
                while any(not f.done() for f in futs):
                    live.update(render(state.snapshot(), args))
                    time.sleep(0.1)
                for f in futs:
                    f.result()
            live.update(render(state.snapshot(), args))
            time.sleep(0.4)

    sn = state.snapshot()
    elapsed = time.time() - t0
    avg = sn["done_bytes"] / elapsed if elapsed else 0
    print()
    print("[migrate] resumo")
    print(f"  enviados : {sn['done_files'] - sn['skipped']}")
    print(f"  pulados  : {sn['skipped']}")
    print(f"  falhas   : {sn['failed']}")
    print(f"  volume   : {human(sn['done_bytes'])}")
    print(f"  tempo    : {fmt_eta(elapsed)}")
    print(f"  throughput medio : {human(avg)}/s")
    sys.exit(1 if sn["failed"] else 0)


if __name__ == "__main__":
    main()
