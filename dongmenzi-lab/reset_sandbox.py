"""Local operator reset. This is a privileged VM console action, not a Web identity."""
import argparse
from pathlib import Path
from lab import BASE, connect, reset_business, utcnow, BUILD_ID


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path, default=BASE / "data")
    p.add_argument("--confirm", required=True, help="Must equal RESET")
    args = p.parse_args()
    if args.confirm != "RESET":
        raise SystemExit("Reset not confirmed")
    path = args.data_dir.resolve() / "range.db"
    if not path.is_file():
        raise SystemExit("Database is missing")
    db = connect(path)
    try:
        admin = db.execute("SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
        if not admin:
            raise SystemExit("Admin account is missing")
        before, after = reset_business(db, admin["id"])
        db.execute("INSERT INTO audit_events(at,actor_id,action,target,result,mode,build_id,request_id) VALUES (?,?,?,?,?,?,?,?)",
                   (utcnow(), admin["id"], "reset_cli", "business", "ok", "console", BUILD_ID, "local-console"))
        db.commit()
        print(f"Baseline restored. Before: {before}; after: {after}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
