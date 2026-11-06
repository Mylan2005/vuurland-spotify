"""v205: offline verified-backup, corruption, path traversal and restore safety tests."""
import io
import json
import tarfile
import tempfile
from pathlib import Path

from v205_lifetime_backup import (
    FILES, REQUIRED, FORMAT, MANIFEST, create_snapshot,
    verify_snapshot, stage_restore,
)

SHA = "a" * 40
with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    src, backup, dest = root / "state", root / "safe.tar.gz", root / "restored"
    src.mkdir()
    for name in REQUIRED:
        (src / name).write_text(
            "[]" if name in {"vuurland_live_queue.json", "vuurland_seen.json"}
            else "sample,archived\n" if name.endswith(".csv")
            else '{"data":true}\n', encoding="utf-8")
    (src / "vuurland_live_queue.json").write_text(
        '[{"artist":"Radio","title":"Song","source":"dkfm_edge","_v116_fifo_seq":321}]')
    (src / "vuurland_user_exclusions.json").write_text('{"ids":[],"pairs":[]}')
    (src / ".vuurland_spotify_cache.json").write_text(
        '{"__v51_radio_unmatched":{"radio|||song":{"source":"dkfm_edge"}},'
        '"__spotify_uri_isrc":{},"__v47_failed_tracks":{}}')
    (src / "private.env").write_text("SPOTIFY_REFRESH_TOKEN=secret")
    (src / "vuurland_queue.json").write_text("[]")
    (src / "duyster_archive_import_state.json").write_text('{"cursor":17}')

    manifest = create_snapshot(src, backup, commit=SHA)
    assert manifest["format"] == FORMAT
    assert set(manifest["files"]) <= set(FILES)
    assert REQUIRED <= set(manifest["files"])
    check, members = verify_snapshot(backup)
    assert check == manifest
    assert b"secret" not in backup.read_bytes()
    assert "private.env" not in members
    assert json.loads(members["vuurland_live_queue.json"])[0]["_v116_fifo_seq"] == 321
    stage_restore(backup, dest)
    assert (dest / "vuurland_live_queue.json").read_bytes() == \
           (src / "vuurland_live_queue.json").read_bytes()
    assert not (dest / "private.env").exists()
    try:
        stage_restore(backup, dest)
    except FileExistsError:
        pass
    else:
        raise AssertionError("Existing restore folder was overwritten")
    assert not (src / ".git").exists()

    # Overwriting an existing backup is forbidden, even with another commit.
    try:
        create_snapshot(src, backup, commit=SHA)
    except FileExistsError:
        pass
    else:
        raise AssertionError("Existing backup was overwritten")

    # Missing critical state means the backup job fails, never silently skips.
    (src / "vuurland_live_queue.json").unlink()
    try:
        create_snapshot(src, root / "missing.tar.gz", commit=SHA)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Missing FIFO accepted")

    # Bad JSON, invalid queue items, unexpected types are rejected.
    (src / "vuurland_live_queue.json").write_text('[{"source":"duyster"}]')
    try:
        create_snapshot(src, root / "badqueue.tar.gz", commit=SHA)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid queue accepted")

    # Path traversal and symlink payloads are rejected, never extracted.
    attack = root / "attack.tar.gz"
    with tarfile.open(attack, "w:gz") as tar:
        content = b"unsafe"
        info = tarfile.TarInfo("../evil")
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))
    try:
        stage_restore(attack, root / "attacker-staged")
    except ValueError:
        pass
    else:
        raise AssertionError("Traversal tar accepted")
    assert not (root / "evil").exists()

    # A changed single archive byte must never pass integrity validation.
    tampered = root / "tampered.tar.gz"
    with tarfile.open(backup, "r:gz") as archive, tarfile.open(tampered, "w:gz") as out:
        for info in archive:
            data = archive.extractfile(info).read()
            if info.name == "vuurland_seen.json":
                data = b'[{"forged":1}]'
            info.size = len(data)
            out.addfile(info, io.BytesIO(data))
    try:
        verify_snapshot(tampered)
    except ValueError:
        pass
    else:
        raise AssertionError("Checksum-mismatched tar accepted")

    # Rebuild corrupted source with symlink: fail closed.
    (src / "vuurland_live_queue.json").symlink_to(src / "private.env")
    try:
        create_snapshot(src, root / "symlink.tar.gz", commit=SHA)
    except ValueError:
        pass
    else:
        raise AssertionError("Symlink source was accepted")

print("✅ v205: strong offline checksums, restore staging, FIFO preservation and fail-closed corrupt backup.")
