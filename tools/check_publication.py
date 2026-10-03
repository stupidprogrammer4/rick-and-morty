import argparse
import re
import subprocess
from pathlib import Path

PATTERNS = [
    re.compile(rb"\bsk-or-v1-[a-zA-Z0-9]{40,}\b"),
    re.compile(rb"\b(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{30,}\b"),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{60,}\b"),
    re.compile(rb"\b[0-9]{6,12}:[A-Za-z0-9_-]{35}\b"),
    re.compile(rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
]
ARABIC = re.compile(r"[\u0600-\u06ff]")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.directory.resolve()
    files = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "-z"], cwd=root
        )
        .decode()
        .split("\0")
    )
    failures = []
    for filename in filter(None, files):
        path = root / filename
        if path.is_symlink():
            failures.append(f"Symlink requires review: {filename}")
            continue
        if (
            (path.name.startswith(".env") and path.name != ".env.example")
            or filename.startswith(
                ("deploy/private/", ".aws/", ".codex/", ".agents/")
            )
            or path.name in {"config.yml", "AGENTS.md", "WORK.md"}
        ):
            failures.append(f"Private file tracked: {filename}")
        body = path.read_bytes()
        if any(pattern.search(body) for pattern in PATTERNS):
            failures.append(f"Potential credential in: {filename}")
        if path.suffix.lower() == ".md" and ARABIC.search(
            body.decode("utf-8")
        ):
            failures.append(f"Documentation is not English: {filename}")
    exists = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=root,
        capture_output=True,
    )
    history = (
        subprocess.check_output(
            ["git", "log", "--format=%B"], cwd=root
        ).decode()
        if exists.returncode == 0
        else ""
    )
    if ARABIC.search(history):
        failures.append("Commit messages must be English")
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"Reviewed {len(files) - 1} tracked paths and commit messages")


if __name__ == "__main__":
    main()
