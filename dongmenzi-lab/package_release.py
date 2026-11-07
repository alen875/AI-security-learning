"""Create a source-only archive. Runtime data and evidence are excluded."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lab import BASE

FILES = [
    ".gitignore", "README.md", "requirements.txt", "lab.py", "init_db.py", "check_data.py",
    "run_range.py", "reset_sandbox.py", "package_release.py",
    "static/index.html", "static/app.js", "static/style.css",
    "scripts/start_safe.ps1", "scripts/run_tests.ps1",
    "tests/test_lab.py", "docs/test-matrix.md", "docs/verification.md", "docs/burp-exercise.md", "docs/实验指导手册.md",
]


def main():
    output = BASE.parent / "dongmenzi-lab-v3-source.zip"
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name in FILES:
            path = BASE / name
            if not path.is_file():
                raise SystemExit(f"Missing release file: {name}")
            archive.write(path, f"dongmenzi-lab-v3/{name}")
    with ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise SystemExit("Archive integrity check failed")
        names = archive.namelist()
        if any("data/" in n or "evidence/" in n or "credentials" in n for n in names):
            raise SystemExit("Runtime data found in archive")
    print(f"Release source archive: {output} ({len(FILES)} files)")


if __name__ == "__main__":
    main()
