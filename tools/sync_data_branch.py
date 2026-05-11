from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync data from origin/data into the working tree")
    parser.add_argument("--ref", default="origin/data", help="Git ref to sync from")
    return parser.parse_args()


def run_git(*args: str, check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT_DIR,
        text=True,
        check=check,
        capture_output=capture_output,
    )


def ensure_ref_exists(ref: str) -> None:
    result = run_git("rev-parse", "--verify", "--quiet", ref, check=False, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Missing git ref {ref!r}. Initialize the data branch first, then rerun this sync."
        )


def extract_archive(ref: str) -> Path:
    archive = subprocess.run(
        ["git", "archive", "--format=tar", ref, "data"],
        cwd=ROOT_DIR,
        check=True,
        stdout=subprocess.PIPE,
    )
    temp_dir = Path(tempfile.mkdtemp(prefix="aipulse-data-sync-"))

    with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as tar:
        tar.extractall(temp_dir)

    staged_data = temp_dir / "data"
    if not staged_data.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(f"Git archive from {ref!r} did not contain a data/ directory.")

    return temp_dir


def replace_data_dir(staged_root: Path) -> None:
    staged_data = staged_root / "data"
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    shutil.copytree(staged_data, DATA_DIR)


def main() -> None:
    args = parse_args()
    try:
        run_git("fetch", "--no-write-fetch-head", "origin", "data")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Unable to fetch origin/data. Ensure the remote branch exists and the working tree is writable."
        ) from exc
    ensure_ref_exists(args.ref)
    staged_root = extract_archive(args.ref)
    try:
        replace_data_dir(staged_root)
    finally:
        shutil.rmtree(staged_root, ignore_errors=True)

    print(f"Synced {args.ref} -> {DATA_DIR.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
