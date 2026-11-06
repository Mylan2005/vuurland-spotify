#!/usr/bin/env python3
"""v205: versioned verified cold backups for Vuurland state.

Never accesses Spotify, changes queues, or overwrites repository files.
Snapshots are from a clean, specific git checkout on GitHub Actions. Restore
only into a brand-new empty directory after full checksum validation.
"""
import argparse
import hashlib
import io
import json
import os
import re
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

FORMAT = "vuurland-backup-v1"
# Exact allowlist: the critical state plus irreplaceable curated decisions
# and manually managed exclusion/history. No source code or credentials.
FILES = (
    ".vuurland_spotify_cache.json",
    "vuurland_live_queue.json",
    "vuurland_seen.json",
    "spotify_scan_status.json",
    "vuurland_queue.json",
    "vuurland_user_exclusions.json",
    "vuurland_taalbeslissingen.csv",
    "duyster_archive_import_state.json",
    "duyster_archief_uniek.csv",
    "duyster_aflevering_833.csv",
    "duyster_strikte_koppelvoorstellen.csv",
    "duyster_spotify_only_v52_4.csv",
    "duyster_v52_6_556_beslissingen.csv",
    "duyster_v52_7_311_beslissingen.csv",
    "duyster_v52_8_200_definitieve_beslissingen.csv",
    "v62_duyster_playlist_catalog.json",
)
REQUIRED = {
    ".vuurland_spotify_cache.json",
    "vuurland_live_queue.json",
    "vuurland_seen.json",
    "spotify_scan_status.json",
    "vuurland_user_exclusions.json",
    "duyster_archief_uniek.csv",
}
MANIFEST = "_VUURLAND_BACKUP_MANIFEST.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_source_file(name, data):
    if name.endswith(".json"):
        try:
            obj = json.loads(data.decode("utf-8-sig"))
        except (ValueError, UnicodeError) as exc:
            raise ValueError(f"JSON ongeldig: {name}") from exc
        if name in {"vuurland_live_queue.json", "vuurland_seen.json", "vuurland_queue.json"}:
            if not isinstance(obj, list):
                raise ValueError(f"Verwachte JSON-lijst: {name}")
        elif not isinstance(obj, dict):
            raise ValueError(f"Verwacht JSON-object: {name}")
        if name == ".vuurland_spotify_cache.json":
            for key in ("__v51_radio_unmatched", "__v47_failed_tracks", "__spotify_uri_isrc"):
                if key in obj and not isinstance(obj[key], dict):
                    raise ValueError(f"Beschadigde cache-sectie {key}")
        if name == "vuurland_live_queue.json":
            for entry in obj:
                if not isinstance(entry, dict) or not all(
                    isinstance(entry.get(k), str) and entry[k].strip()
                    for k in ("artist", "title", "source")
                ):
                    raise ValueError("Beschadigd FIFO-item")
    elif b"\x00" in data:
        raise ValueError(f"Ongeldig nulbyte in tekstbestand: {name}")


def create_snapshot(root, output, *, commit, generated=None):
    root = Path(root)
    output = Path(output)
    if not re.fullmatch(r"[a-fA-F0-9]{40}", commit):
        raise ValueError("Vereis exacte 40-tekens Git commit voor herleidbaarheid")
    members = {}
    for name in FILES:
        path = root / name
        if path.is_symlink():
            raise ValueError(f"Symbolische link in back-upbron: {name}")
        if not path.is_file():
            if name in REQUIRED:
                raise FileNotFoundError(f"Kritisch back-upbestand ontbreekt: {name}")
            continue
        data = path.read_bytes()
        validate_source_file(name, data)
        members[name] = data
    stamp = generated or datetime.now(timezone.utc).isoformat()
    manifest = {
        "format": FORMAT,
        "created_utc": stamp,
        "git_commit": commit.lower(),
        "files": {name: {"sha256": sha(data), "bytes": len(data)}
                  for name, data in sorted(members.items())},
    }
    if output.exists():
        raise FileExistsError("Back-up bestaat al; nooit overschrijven")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Tar only whitelisted basename files and a manifest. No absolute paths,
    # symlinks, traversal paths, credentials or arbitrary repository blobs.
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".tmp", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with tarfile.open(tmp_path, "w:gz") as archive:
            for name, data in sorted(members.items()):
                info = tarfile.TarInfo(name)
                info.mode = 0o600
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            meta = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n").encode("utf-8")
            info = tarfile.TarInfo(MANIFEST)
            info.mode = 0o600
            info.size = len(meta)
            archive.addfile(info, io.BytesIO(meta))
        # Verify independently before publishing the artifact.
        verify_snapshot(tmp_path)
        os.replace(tmp_path, output)
    finally:
        tmp_path.unlink(missing_ok=True)
    return manifest


def verify_snapshot(archive_path):
    members = {}
    with tarfile.open(archive_path, "r:gz") as archive:
        for info in archive:
            if (not info.isfile() or info.name not in (*FILES, MANIFEST)
                    or info.name in members or info.size < 0
                    or info.size > 100_000_000):
                raise ValueError("Onveilig of onbekend back-upbestand")
            stream = archive.extractfile(info)
            if stream is None:
                raise ValueError("Ontbrekende bestandsgegevens")
            data = stream.read()
            if len(data) != info.size:
                raise ValueError("Afgekapt back-upbestand")
            members[info.name] = data
    raw_manifest = members.pop(MANIFEST, None)
    if raw_manifest is None:
        raise ValueError("Manifest ontbreekt")
    try:
        manifest = json.loads(raw_manifest)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Manifest is ongeldig") from exc
    if (not isinstance(manifest, dict)
            or manifest.get("format") != FORMAT
            or not re.fullmatch(r"[a-f0-9]{40}", str(manifest.get("git_commit", "")))
            or not isinstance(manifest.get("files"), dict)
            or set(manifest["files"]) != set(members)
            or not REQUIRED <= set(members)):
        raise ValueError("Manifest of kritische back-upbestanden ontbreken")
    for name, data in members.items():
        meta = manifest["files"][name]
        if (not isinstance(meta, dict) or meta.get("sha256") != sha(data)
                or meta.get("bytes") != len(data)):
            raise ValueError(f"SHA-256-validatie mislukt: {name}")
        validate_source_file(name, data)
    return manifest, members


def stage_restore(archive_path, destination):
    manifest, members = verify_snapshot(archive_path)
    destination = Path(destination)
    # No automatic restore into the live repo; output must be NEW and empty.
    if destination.exists():
        raise FileExistsError("Herstelmap moet nieuw zijn; bestaande state nooit overschrijven")
    if (destination / ".git").exists():
        raise ValueError("Niet herstellen in een Git-repository")
    destination.mkdir(parents=True, exist_ok=False)
    try:
        for name, data in members.items():
            path = destination / name
            with path.open("xb") as handle:
                handle.write(data)
            path.chmod(0o600)
    except Exception:
        # Preserve failure state for manual investigation, never touch live repo.
        raise
    return manifest


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_subparsers(dest="mode", required=True)
    create = modes.add_parser("create", help="maak koude back-up")
    create.add_argument("--data-dir", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--commit", required=True)
    verify = modes.add_parser("verify", help="controleer integriteit, zonder herstel")
    verify.add_argument("--archive", type=Path, required=True)
    restore = modes.add_parser("stage-restore", help="herstel uitsluitend in NIEUWE map")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "create":
        manifest = create_snapshot(args.data_dir, args.output, commit=args.commit)
    elif args.mode == "verify":
        manifest, _ = verify_snapshot(args.archive)
    else:
        manifest = stage_restore(args.archive, args.destination)
    print("✅ Vuurland back-up veilig gecontroleerd: "
          f"{len(manifest['files'])} bestanden, commit {manifest['git_commit'][:12]}; "
          "geen Spotify- of playlistacties.")


if __name__ == "__main__":
    main()
