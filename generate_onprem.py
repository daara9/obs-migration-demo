#!/usr/bin/env python3
"""Fase 1 - Assessment: gera uma origem "on-premises" simulada.

Cria uma arvore de diretorios realista (docs, images, db-dumps, logs),
milhares de arquivos, e um inventory.csv (relpath,size,md5) que serve de
baseline para a verificacao de integridade da migracao.
"""
import argparse
import csv
import hashlib
import os
import random
import time

BASE = os.path.dirname(os.path.abspath(__file__))

CATEGORIES = {
    "docs": (".pdf", ".docx", ".xlsx", ".pptx"),
    "logs": (".log",),
    "images": (".png", ".jpg", ".mp4"),
    "db-dumps": (".sql", ".tar.gz"),
}


def human(n):
    n = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def build_tree(root):
    for d in CATEGORIES:
        os.makedirs(os.path.join(root, d), exist_ok=True)


def write_random(path, size, block, rnd):
    """Escreve 'size' bytes com um cabecalho unico + bloco reproduzido,
    calculando o MD5 incrementalmente."""
    h = hashlib.md5()
    header = rnd.randbytes(256)
    with open(path, "wb") as f:
        if size >= len(header):
            f.write(header)
            h.update(header)
            remaining = size - len(header)
        else:
            data = header[:size]
            f.write(data)
            h.update(data)
            return h.hexdigest()
        while remaining > 0:
            chunk = block if remaining >= len(block) else block[:remaining]
            f.write(chunk)
            h.update(chunk)
            remaining -= len(chunk)
    return h.hexdigest()


def gen(root, args):
    rnd = random.Random(args.seed)
    block = rnd.randbytes(1 << 20)
    rows = []
    started = time.time()

    # arquivos pequenos -> docs/ e logs/
    small_specs = []
    for i in range(args.small):
        if i % 3 == 0:
            cat = "docs"
        else:
            cat = "logs"
        ext = rnd.choice(CATEGORIES[cat])
        name = f"{cat}-{i:05d}{ext}"
        size = rnd.randint(args.small_min_kb * 1024, args.small_max_kb * 1024)
        small_specs.append((cat, name, size))

    # arquivos medios -> images/
    large_specs = []
    for i in range(args.large):
        ext = rnd.choice(CATEGORIES["images"])
        name = f"asset-{i:03d}{ext}"
        size = rnd.randint(args.large_min_mb * 1024 * 1024,
                           args.large_max_mb * 1024 * 1024)
        large_specs.append(("images", name, size))

    # dump grande -> db-dumps/ (opcional)
    dump_specs = []
    if args.dump_mb > 0:
        dump_specs.append(("db-dumps", "prod-dump.sql", args.dump_mb * 1024 * 1024))

    all_specs = small_specs + large_specs + dump_specs
    total_bytes = sum(s for _, _, s in all_specs)
    print(f"[assessment] gerando {len(all_specs)} arquivos "
          f"({human(total_bytes)}) em {root} ...")

    for idx, (cat, name, size) in enumerate(sorted(all_specs, key=lambda x: x[2])):
        path = os.path.join(root, cat, name)
        md5 = write_random(path, size, block, rnd)
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        rows.append((rel, size, md5))
        if (idx + 1) % 500 == 0 or idx + 1 == len(all_specs):
            print(f"[assessment]   {idx + 1}/{len(all_specs)} arquivos escritos")

    inv = os.path.join(args.out_dir, "inventory.csv")
    with open(inv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["relpath", "size", "md5"])
        w.writerows(rows)

    elapsed = time.time() - started
    print("\n[assessment] relatorio")
    print(f"  objetos gerados : {len(rows)}")
    print(f"  volume total    : {human(total_bytes)}")
    by_cat = {}
    for rel, size, _ in rows:
        c = rel.split("/", 1)[0]
        by_cat[c] = by_cat.get(c, 0) + 1
    for c, n in sorted(by_cat.items()):
        print(f"    - {c:<10} {n} objetos")
    print(f"  inventory       : {inv}")
    print(f"  tempo           : {elapsed:.1f}s")

    return inv


def main():
    ap = argparse.ArgumentParser(description="Gera origem on-prem simulada")
    ap.add_argument("--out", default=os.path.join(BASE, "onprem"))
    ap.add_argument("--out-dir", default=BASE)
    ap.add_argument("--small", type=int, default=2500,
                    help="numero de arquivos pequenos")
    ap.add_argument("--small-min-kb", type=int, default=1)
    ap.add_argument("--small-max-kb", type=int, default=200)
    ap.add_argument("--large", type=int, default=3,
                    help="numero de arquivos medios (exercita multipart)")
    ap.add_argument("--large-min-mb", type=int, default=5)
    ap.add_argument("--large-max-mb", type=int, default=20)
    ap.add_argument("--dump-mb", type=int, default=15,
                    help="tamanho do dump unico em MB (0 desativa)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    build_tree(args.out)
    gen(args.out, args)


if __name__ == "__main__":
    main()
