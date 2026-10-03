import base64
import hashlib
import sys
from pathlib import Path

path = Path(sys.argv[1])
expected = sys.argv[2]
matched = []
for line in path.read_text().splitlines():
    parts = line.split()
    if len(parts) != 3:
        continue
    fingerprint = "SHA256:" + base64.b64encode(
        hashlib.sha256(base64.b64decode(parts[2])).digest()
    ).decode().rstrip("=")
    if fingerprint == expected:
        matched.append(line)
if not matched:
    raise SystemExit("No SSH key matches the configured pin")
path.write_text("\n".join(matched) + "\n")
