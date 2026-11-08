"""Start one explicit teaching mode; default is safe."""
import argparse
import ipaddress
import os
from pathlib import Path
from lab import BASE, BUILD_ID, create_app


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("safe", "idor", "sqli", "bp"), default="safe")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--data-dir", type=Path, default=BASE / "data")
    args = p.parse_args()
    try:
        address = ipaddress.ip_address(args.host)
    except ValueError:
        raise SystemExit("--host must be one explicit IP address") from None
    if not (address.is_loopback or address.is_private) or address.is_unspecified or address.is_multicast:
        raise SystemExit("Only loopback or an explicit private VM address is allowed")
    if not address.is_loopback and os.environ.get("LAB_PRIVATE_NETWORK_APPROVED") != "yes":
        raise SystemExit("Private VM binding requires LAB_PRIVATE_NETWORK_APPROVED=yes")
    data_dir = args.data_dir.resolve()
    app = create_app({"LAB_MODE": args.mode, "DB_PATH": str(data_dir / "range.db"), "SEARCH_DB_PATH": str(data_dir / "training.db")})
    print(f"mode={args.mode} build={BUILD_ID} host={args.host} port={args.port}")
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
