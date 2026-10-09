"""Operational commands.

python -m app.cli import-ppd path/to/pp-2024.csv [--max-rows N]
python -m app.cli make-admin user@example.com
python -m app.cli extract-ppd-sample source.csv out.csv --districts M14,LS6
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models import User
from app.services.imports import ppd


def cmd_import_ppd(args) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1
    start = time.perf_counter()
    with SessionLocal() as db:
        try:
            rec = ppd.import_price_paid(db, path, path.name, max_rows=args.max_rows, allow_duplicate=args.force)
        except ppd.DuplicateImportError as e:
            print(f"Already imported as {e.existing.id}; pass --force to re-import.", file=sys.stderr)
            return 2
    print(
        f"{rec.status}: {rec.rows_imported:,} imported, {rec.rows_rejected:,} rejected of {rec.rows_total:,} "
        f"rows in {time.perf_counter() - start:.1f}s (transactions {rec.data_from} to {rec.data_to})"
    )
    for err in rec.errors[:10]:
        print("  ", err)
    return 0 if rec.status != "failed" else 1


def cmd_make_admin(args) -> int:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == args.email.lower()))
        if not user:
            print("No user with that email; register first.", file=sys.stderr)
            return 1
        user.is_admin = True
        db.commit()
    print(f"{args.email} is now an administrator.")
    return 0


def cmd_extract_sample(args) -> int:
    """Write a subset of a PPD file (selected postcode districts) in official no-header format."""
    import pandas as pd

    districts = {d.strip().upper() for d in args.districts.split(",") if d.strip()}
    header = ppd._has_header(Path(args.source))
    df = pd.read_csv(
        args.source, header=None, names=ppd.COLUMNS, skiprows=1 if header else 0, dtype=str, keep_default_na=False
    )
    mask = df["postcode"].str.split(" ").str[0].isin(districts)
    out = df[mask]
    out.to_csv(args.out, header=False, index=False)
    print(f"Wrote {len(out):,} rows for {len(districts)} districts to {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(required=True)
    p = sub.add_parser("import-ppd", help="Import HM Land Registry Price Paid Data CSV")
    p.add_argument("path")
    p.add_argument("--max-rows", type=int, default=None)
    p.add_argument("--force", action="store_true", help="Re-import a file that was already imported")
    p.set_defaults(func=cmd_import_ppd)
    p = sub.add_parser("make-admin", help="Grant administrator rights to a registered user")
    p.add_argument("email")
    p.set_defaults(func=cmd_make_admin)
    p = sub.add_parser("extract-ppd-sample", help="Extract selected postcode districts from a PPD file")
    p.add_argument("source")
    p.add_argument("out")
    p.add_argument("--districts", required=True)
    p.set_defaults(func=cmd_extract_sample)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
