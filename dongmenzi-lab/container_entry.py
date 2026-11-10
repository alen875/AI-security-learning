"""Initialize a private container data volume, then start one lab mode."""
import ipaddress
import os
import socket
import sys
from pathlib import Path

from lab import initialize


def main():
    data_dir = Path("/data")
    main_db = data_dir / "range.db"
    search_db = data_dir / "training.db"
    credentials = data_dir / "credentials.txt"
    existing = (main_db.exists(), search_db.exists(), credentials.exists())
    if existing == (False, False, False):
        passwords = initialize(main_db, search_db)
        credentials.write_text(
            "\n".join(f"{name}: {value}" for name, value in passwords.items()) + "\n",
            encoding="utf-8",
        )
        credentials.chmod(0o600)
        print("Created fictional data and local demonstration credentials in /data")
    elif existing != (True, True, True):
        raise SystemExit("Incomplete /data volume; inspect it before restarting")

    # Docker's container address is private; host exposure is controlled by Compose.
    host = socket.gethostbyname(socket.gethostname())
    if not ipaddress.ip_address(host).is_private:
        raise SystemExit("Container must have a private network address")
    mode = os.environ.get("LAB_MODE", "safe")
    os.execv(sys.executable, [sys.executable, "run_range.py", "--mode", mode,
                            "--host", host, "--data-dir", str(data_dir)])


if __name__ == "__main__":
    main()
