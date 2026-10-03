import argparse
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    destination = args.destination.resolve()
    if destination.exists():
        raise SystemExit("Use a new destination to preserve existing work")
    source = Path(__file__).resolve().parents[1]
    destination.mkdir(mode=0o700, parents=True)
    for name in (
        "api",
        "bots",
        "packages",
        "tests",
        "tools",
        "docs",
        "deploy",
        ".github",
        ".gitignore",
        ".dockerignore",
        ".env.example",
        "config.yml.sample",
        "compose.yml",
        "pyproject.toml",
        "LICENSE",
        "README.md",
        "SECURITY.md",
    ):
        path = source / name
        if path.is_dir():
            shutil.copytree(
                path,
                destination / name,
                ignore=shutil.ignore_patterns(
                    "__pycache__",
                    "*.pyc",
                    "*.egg-info",
                    ".venv",
                    "private",
                    "config.yml",
                    ".env",
                    ".env.runtime",
                    "*.log",
                ),
                symlinks=True,
            )
        else:
            shutil.copy2(path, destination / name)
    if any(path.is_symlink() for path in destination.rglob("*")):
        raise SystemExit("Symlink found; review the staged directory")
    print(f"Prepared public source at {destination}; no private environment")


if __name__ == "__main__":
    main()
