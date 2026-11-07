"""Create the fictional teaching data. Existing databases are never overwritten."""
import argparse
from pathlib import Path
from lab import BASE, initialize


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path, default=BASE / "data")
    args = p.parse_args()
    directory = args.data_dir.resolve()
    main_db, search_db = directory / "range.db", directory / "training.db"
    if main_db.exists() or search_db.exists():
        raise SystemExit("Database already exists. Use a fresh data directory or the reset command.")
    passwords = initialize(main_db, search_db)
    cred_file = directory / "credentials.txt"
    cred_file.write_text("\n".join(f"{name}: {value}" for name, value in passwords.items()) + "\n", encoding="utf-8")
    print(f"Initialized fictional databases in {directory}")
    print(f"Local demonstration credentials: {cred_file} (do not commit this file)")


if __name__ == "__main__":
    main()
