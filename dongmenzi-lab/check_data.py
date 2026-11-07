"""Read-only business-data summary for classroom evidence."""
import argparse
import json
from pathlib import Path
from lab import BASE, connect, seed_digest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path, default=BASE / "data")
    args = p.parse_args()
    path = args.data_dir.resolve() / "range.db"
    if not path.is_file():
        raise SystemExit("Business database is missing")
    db = connect(path, readonly=True)
    try:
        out = {
            "business_digest": seed_digest(db),
            "devices": db.execute("SELECT COUNT(*) FROM devices").fetchone()[0],
            "records": db.execute("SELECT COUNT(*) FROM records").fetchone()[0],
            "audit_events": db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
