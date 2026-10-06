import os
from pathlib import Path

import pytest

from deploy.retention_host import prune_backups


def test_backup_cleanup_preserves_boundary_fresh_files_and_symlink_targets(
    tmp_path,
):
    now = 200000
    backups = tmp_path / "backups"
    backups.mkdir()
    for name, age in (
        ("expired.sql.gz", 86401),
        ("boundary.sql.gz", 86400),
        ("fresh.sql.gz", 1),
        ("seed.json", 100000),
    ):
        path = backups / name
        path.write_text("fixture")
        os.utime(path, (now - age, now - age))
    target = tmp_path / "outside.sql.gz"
    target.write_text("preserved")
    os.utime(target, (1, 1))
    (backups / "linked.sql.gz").symlink_to(target)
    assert prune_backups(tmp_path, now) == 1
    assert {path.name for path in backups.iterdir()} == {
        "boundary.sql.gz",
        "fresh.sql.gz",
        "seed.json",
        "linked.sql.gz",
    }
    assert target.exists()


def test_backup_cleanup_rejects_redirected_directory(tmp_path):
    (tmp_path / "backups").symlink_to(Path("/tmp"))
    with pytest.raises(ValueError):
        prune_backups(tmp_path, 200000)
