"""Clean only this bot's generated files and dedicated log namespace."""

import fcntl
import subprocess
import sys
import time
from pathlib import Path


def prune_backups(root: Path, now: float) -> int:
    removed = 0
    directory = root / "backups"
    if directory.is_symlink():
        raise ValueError("Backup directory must not be a symlink")
    for path in directory.glob("*.sql.gz"):
        if not path.is_symlink() and path.is_file():
            if path.stat().st_mtime < now - 86400:
                path.unlink()
                removed += 1
    return removed


def main() -> None:
    root = Path(sys.argv[1]).resolve(strict=True)
    with (root / ".deploy.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        count = prune_backups(root, time.time())
        subprocess.run(
            [
                "journalctl",
                "--namespace=portal",
                "--rotate",
                "--vacuum-time=23h58min",
                "--vacuum-size=64M",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        print(f"Expired portal backups removed: {count}")


if __name__ == "__main__":
    main()
