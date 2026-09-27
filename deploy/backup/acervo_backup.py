#!/usr/bin/env python3
"""Acervoの暗号化バックアップと空環境への安全な復元を行う。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tarfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

BACKUP_FORMAT_VERSION = 2
BACKUP_ROOT = Path("/backups")
SOURCE_MEDIA = Path("/source-media")
SOURCE_SETTINGS = Path("/source-settings/.env.production")
TARGET_MEDIA = Path("/target-media")
RESTORED_SETTINGS = Path("/restored-settings")
SIGNING_PRIVATE_KEY = Path("/run/acervo-backup-signing/private")
ALLOWED_SIGNERS = Path("/run/acervo-backup-signing/allowed_signers")
SIGNING_NAMESPACE = "acervo-backup"
SIGNING_PRINCIPAL = "acervo-backup"


class BackupError(Exception):
    """秘密値を含めずに処理を中断するための例外。"""


def log(event: str, **values: object) -> None:
    details = " ".join(f"{key}={value}" for key, value in sorted(values.items()))
    print(f"acervo-backup event={event}{' ' + details if details else ''}", flush=True)


def fail(code: str) -> None:
    raise BackupError(code)


def command(args: list[str], *, env: dict[str, str] | None = None, output: bool = False) -> str:
    try:
        result = subprocess.run(
            args,
            check=True,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if output else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise BackupError("external_command_failed") from error
    return result.stdout.strip() if output else ""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def postgres_env() -> dict[str, str]:
    required = (
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    )
    if any(not os.environ.get(name) for name in required):
        fail("database_configuration_missing")
    env = os.environ.copy()
    env["PGPASSWORD"] = env["POSTGRES_PASSWORD"]
    return env


def postgres_arguments() -> list[str]:
    return [
        "--host",
        os.environ["POSTGRES_HOST"],
        "--port",
        os.environ["POSTGRES_PORT"],
        "--username",
        os.environ["POSTGRES_USER"],
        "--dbname",
        os.environ["POSTGRES_DB"],
    ]


def postgres_major() -> int:
    version = command(
        [
            "psql",
            *postgres_arguments(),
            "--tuples-only",
            "--no-align",
            "--command",
            "SHOW server_version_num",
        ],
        env=postgres_env(),
        output=True,
    )
    if not version.isdigit() or len(version) < 4:
        fail("database_version_unavailable")
    return int(version) // 10000


def recipients() -> list[str]:
    raw = os.environ.get("ACERVO_BACKUP_AGE_RECIPIENTS", "")
    values = [value.strip() for value in raw.split(",") if value.strip()]
    if (
        not values
        or len(set(values)) != len(values)
        or any(not value.startswith("age1") for value in values)
    ):
        fail("age_recipients_invalid")
    return values


def write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    path.chmod(0o600)


def canonical_metadata(metadata: dict[str, object]) -> bytes:
    unsigned = {key: value for key, value in metadata.items() if key != "authentication"}
    return json.dumps(unsigned, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def signature_command(args: list[str], *, input_path: Path | None = None) -> None:
    try:
        with input_path.open("rb") if input_path else open(os.devnull, "rb") as stream:
            subprocess.run(
                args,
                check=True,
                stdin=stream,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except (OSError, subprocess.CalledProcessError) as error:
        raise BackupError("backup_authentication_failed") from error


def sign_metadata(metadata: dict[str, object], work: Path) -> str:
    if not SIGNING_PRIVATE_KEY.is_file():
        fail("backup_signing_key_unavailable")
    source = work / "metadata-to-sign"
    signature = source.with_suffix(".sig")
    try:
        source.write_bytes(canonical_metadata(metadata))
        source.chmod(0o600)
        signature_command(
            [
                "ssh-keygen",
                "-Y",
                "sign",
                "-f",
                str(SIGNING_PRIVATE_KEY),
                "-n",
                SIGNING_NAMESPACE,
                str(source),
            ]
        )
        return signature.read_text(encoding="ascii")
    except (OSError, UnicodeError) as error:
        raise BackupError("backup_authentication_failed") from error
    finally:
        source.unlink(missing_ok=True)
        signature.unlink(missing_ok=True)


def verify_metadata_authentication(
    directory: Path, metadata: dict[str, object], work: Path
) -> None:
    authentication = metadata.get("authentication")
    if (
        metadata.get("format_version") != BACKUP_FORMAT_VERSION
        or not isinstance(authentication, dict)
        or authentication.get("algorithm") != "ssh-ed25519"
        or not isinstance(authentication.get("signature"), str)
        or not ALLOWED_SIGNERS.is_file()
    ):
        fail("backup_authentication_invalid")
    expected_payload_hash = metadata.get("encrypted_payload_sha256")
    if (
        not isinstance(expected_payload_hash, str)
        or len(expected_payload_hash) != 64
        or sha256(directory / "payload.tar.gz.age") != expected_payload_hash
    ):
        fail("backup_authentication_invalid")
    source = work / "metadata-to-verify"
    signature = source.with_suffix(".sig")
    try:
        source.write_bytes(canonical_metadata(metadata))
        signature.write_text(authentication["signature"], encoding="ascii")
        source.chmod(0o600)
        signature.chmod(0o600)
        try:
            signature_command(
                [
                    "ssh-keygen",
                    "-Y",
                    "verify",
                    "-f",
                    str(ALLOWED_SIGNERS),
                    "-I",
                    SIGNING_PRINCIPAL,
                    "-n",
                    SIGNING_NAMESPACE,
                    "-s",
                    str(signature),
                ],
                input_path=source,
            )
        except BackupError as error:
            raise BackupError("backup_authentication_invalid") from error
    except (OSError, UnicodeError) as error:
        raise BackupError("backup_authentication_failed") from error
    finally:
        source.unlink(missing_ok=True)
        signature.unlink(missing_ok=True)


def component(path: Path, name: str) -> dict[str, object]:
    return {"name": name, "sha256": sha256(path), "size": path.stat().st_size}


def backup_id() -> tuple[str, str]:
    now = datetime.now(UTC)
    return (
        f"acervo-{now.strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(6)}",
        now.isoformat().replace("+00:00", "Z"),
    )


def create_backup() -> None:
    if not BACKUP_ROOT.is_dir() or not os.access(BACKUP_ROOT, os.W_OK):
        fail("backup_directory_unavailable")
    if not SOURCE_MEDIA.is_dir() or not SOURCE_SETTINGS.is_file():
        fail("backup_source_missing")

    backup_name, created_at = backup_id()
    work = BACKUP_ROOT / f".incomplete-{backup_name}"
    final = BACKUP_ROOT / backup_name
    if final.exists():
        fail("backup_identifier_conflict")
    work.mkdir(mode=0o700)
    try:
        database_dump = work / "database.dump"
        try:
            command(
                ["pg_dump", *postgres_arguments(), "--format=custom", "--file", str(database_dump)],
                env=postgres_env(),
            )
        except BackupError as error:
            raise BackupError("database_backup_failed") from error

        photos = work / "photos.tar"
        try:
            command(
                ["tar", "--create", "--file", str(photos), "--directory", str(SOURCE_MEDIA), "."]
            )
        except BackupError as error:
            raise BackupError("photo_backup_failed") from error

        settings_dir = work / "settings"
        settings_dir.mkdir(mode=0o700)
        settings_copy = settings_dir / ".env.production"
        try:
            shutil.copyfile(SOURCE_SETTINGS, settings_copy)
            settings_copy.chmod(0o600)
        except OSError as error:
            raise BackupError("settings_backup_failed") from error

        manifest = {
            "backup_id": backup_name,
            "components": [
                component(database_dump, "database.dump"),
                component(photos, "photos.tar"),
                component(settings_copy, "settings/.env.production"),
            ],
            "created_at": created_at,
            "format_version": BACKUP_FORMAT_VERSION,
            "postgres_major": postgres_major(),
        }
        write_json(work / "manifest.json", manifest)
        payload = work / "payload.tar.gz"
        command(
            [
                "tar",
                "--create",
                "--gzip",
                "--file",
                str(payload),
                "--directory",
                str(work),
                "database.dump",
                "photos.tar",
                "settings",
                "manifest.json",
            ]
        )

        recipient_file = work / "recipients.txt"
        recipient_file.write_text("\n".join(recipients()) + "\n", encoding="ascii")
        recipient_file.chmod(0o600)
        encrypted = work / "payload.tar.gz.age"
        try:
            command(
                [
                    "age",
                    "--encrypt",
                    "--recipients-file",
                    str(recipient_file),
                    "--output",
                    str(encrypted),
                    str(payload),
                ]
            )
        except BackupError as error:
            raise BackupError("backup_encryption_failed") from error
        payload.unlink()
        recipient_file.unlink()
        database_dump.unlink()
        photos.unlink()
        shutil.rmtree(settings_dir)
        (work / "manifest.json").unlink()

        metadata = {
            "backup_id": backup_name,
            "components": manifest["components"],
            "created_at": created_at,
            "encrypted_payload_sha256": sha256(encrypted),
            "format_version": BACKUP_FORMAT_VERSION,
            "postgres_major": manifest["postgres_major"],
        }
        metadata["authentication"] = {
            "algorithm": "ssh-ed25519",
            "signature": sign_metadata(metadata, work),
        }
        write_json(work / "metadata.json", metadata)
        checksums = work / "checksums.sha256"
        checksums.write_text(
            (
                f"{sha256(encrypted)}  payload.tar.gz.age\n"
                f"{sha256(work / 'metadata.json')}  metadata.json\n"
            ),
            encoding="ascii",
        )
        checksums.chmod(0o600)
        os.replace(work, final)
        log("backup_created", backup_id=backup_name, postgres_major=manifest["postgres_major"])
        apply_retention()
    except Exception:
        if work.exists():
            failed = BACKUP_ROOT / f".failed-{backup_name}"
            os.replace(work, failed)
        raise


def load_metadata(directory: Path) -> dict[str, object]:
    try:
        data = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        if data["format_version"] not in {1, BACKUP_FORMAT_VERSION} or not isinstance(
            data["created_at"], str
        ):
            raise ValueError
        datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        return data
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise BackupError("backup_metadata_invalid") from error


def retention_limits() -> tuple[int, int, int]:
    names = (
        "ACERVO_BACKUP_RETENTION_DAILY",
        "ACERVO_BACKUP_RETENTION_WEEKLY",
        "ACERVO_BACKUP_RETENTION_MONTHLY",
    )
    defaults = (14, 8, 12)
    values: list[int] = []
    for name, default in zip(names, defaults, strict=True):
        raw = os.environ.get(name, str(default))
        try:
            value = int(raw)
        except ValueError as error:
            raise BackupError("retention_configuration_invalid") from error
        if value < 1:
            fail("retention_configuration_invalid")
        values.append(value)
    return tuple(values)  # type: ignore[return-value]


def retention_candidates() -> list[Path]:
    daily_limit, weekly_limit, monthly_limit = retention_limits()
    records: list[tuple[datetime, Path]] = []
    for directory in BACKUP_ROOT.glob("acervo-*"):
        if directory.is_dir():
            metadata = load_metadata(directory)
            created = datetime.fromisoformat(str(metadata["created_at"]).replace("Z", "+00:00"))
            records.append((created, directory))
    records.sort(reverse=True, key=lambda record: record[0])
    keep: set[Path] = set()
    seen_daily: set[object] = set()
    seen_weekly: set[object] = set()
    seen_monthly: set[object] = set()
    for created, directory in records:
        day = created.date()
        week = created.isocalendar()[:2]
        month = (created.year, created.month)
        if day not in seen_daily and len(seen_daily) < daily_limit:
            seen_daily.add(day)
            keep.add(directory)
        if week not in seen_weekly and len(seen_weekly) < weekly_limit:
            seen_weekly.add(week)
            keep.add(directory)
        if month not in seen_monthly and len(seen_monthly) < monthly_limit:
            seen_monthly.add(month)
            keep.add(directory)
    return [directory for _, directory in records if directory not in keep]


def apply_retention(*, dry_run: bool = False) -> None:
    candidates = retention_candidates()
    for directory in candidates:
        log("retention_candidate", backup_id=directory.name)
    if dry_run:
        return
    for directory in candidates:
        try:
            shutil.rmtree(directory)
        except OSError as error:
            raise BackupError("retention_cleanup_failed") from error
    log("retention_completed", deleted=len(candidates))


def verify_checksums(directory: Path) -> None:
    try:
        expected = {}
        for line in (directory / "checksums.sha256").read_text(encoding="ascii").splitlines():
            checksum, filename = line.split("  ", 1)
            expected[filename] = checksum
        if expected.get("payload.tar.gz.age") != sha256(directory / "payload.tar.gz.age"):
            fail("backup_checksum_mismatch")
        if expected.get("metadata.json") != sha256(directory / "metadata.json"):
            fail("backup_checksum_mismatch")
    except (OSError, ValueError):
        fail("backup_checksum_invalid")


def snapshot_backup(directory: Path, work: Path) -> Path:
    snapshot = work / "backup"
    snapshot.mkdir(mode=0o700)
    try:
        for name in ("payload.tar.gz.age", "metadata.json", "checksums.sha256"):
            source = directory / name
            destination = snapshot / name
            if source.is_symlink() or not source.is_file():
                fail("backup_snapshot_invalid")
            with source.open("rb") as input_stream, destination.open("xb") as output_stream:
                shutil.copyfileobj(input_stream, output_stream)
            destination.chmod(0o600)
    except OSError:
        fail("backup_snapshot_invalid")
    return snapshot


def archive_path(name: str) -> Path | None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        fail("backup_archive_invalid")
    parts = tuple(part for part in path.parts if part != ".")
    if not parts:
        return None
    return Path(*parts)


def extract_archive(
    archive: Path,
    destination: Path,
    *,
    expected: dict[str, str] | None = None,
) -> None:
    try:
        with tarfile.open(archive, "r:*") as source:
            members = source.getmembers()
            seen: set[str] = set()
            extracted: list[tuple[tarfile.TarInfo, Path]] = []
            for member in members:
                path = archive_path(member.name)
                if path is None:
                    if not member.isdir():
                        fail("backup_archive_invalid")
                    continue
                name = path.as_posix()
                if name in seen:
                    fail("backup_archive_invalid")
                seen.add(name)
                member_type = "directory" if member.isdir() else "file" if member.isreg() else None
                if member_type is None or (expected and expected.get(name) != member_type):
                    fail("backup_archive_invalid")
                extracted.append((member, path))
            if expected and seen != set(expected):
                fail("backup_archive_invalid")
            for member, path in extracted:
                target = destination / path
                if member.isdir():
                    target.mkdir(mode=0o700, parents=True, exist_ok=False)
                    continue
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                input_stream = source.extractfile(member)
                if input_stream is None:
                    fail("backup_archive_invalid")
                with input_stream, target.open("xb") as output_stream:
                    shutil.copyfileobj(input_stream, output_stream)
                target.chmod(0o600)
    except (OSError, tarfile.TarError):
        fail("backup_archive_invalid")


def target_is_empty() -> None:
    tables = command(
        [
            "psql",
            *postgres_arguments(),
            "--tuples-only",
            "--no-align",
            "--command",
            "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'",
        ],
        env=postgres_env(),
        output=True,
    )
    if tables != "0" or any(TARGET_MEDIA.iterdir()):
        fail("restore_target_not_empty")


def restore_backup(backup_name: str, identity_file: Path, confirmation: str) -> None:
    if confirmation != "RESTORE_EMPTY_TARGET":
        fail("restore_confirmation_required")
    if not identity_file.is_file() or not TARGET_MEDIA.is_dir() or not RESTORED_SETTINGS.is_dir():
        fail("restore_target_unavailable")
    directory = BACKUP_ROOT / backup_name
    if directory.is_symlink() or not directory.is_dir() or not backup_name.startswith("acervo-"):
        fail("backup_not_found")
    work = Path("/tmp") / f"restore-{secrets.token_hex(6)}"
    work.mkdir(mode=0o700)
    try:
        snapshot = snapshot_backup(directory, work)
        metadata = load_metadata(snapshot)
        verify_metadata_authentication(snapshot, metadata, work)
        verify_checksums(snapshot)
        if metadata.get("backup_id") != backup_name:
            fail("backup_metadata_invalid")
        if int(metadata["postgres_major"]) != postgres_major():
            fail("postgres_major_incompatible")
        target_is_empty()
        payload = work / "payload.tar.gz"
        try:
            with payload.open("wb") as output:
                subprocess.run(
                    [
                        "age",
                        "--decrypt",
                        "--identity",
                        str(identity_file),
                        str(snapshot / "payload.tar.gz.age"),
                    ],
                    check=True,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.DEVNULL,
                )
        except (OSError, subprocess.CalledProcessError) as error:
            raise BackupError("backup_decryption_failed") from error
        expected = {
            "database.dump": "file",
            "photos.tar": "file",
            "settings": "directory",
            "settings/.env.production": "file",
            "manifest.json": "file",
        }
        extract_archive(payload, work, expected=expected)
        manifest = json.loads((work / "manifest.json").read_text(encoding="utf-8"))
        if (
            manifest.get("format_version") != BACKUP_FORMAT_VERSION
            or manifest.get("backup_id") != backup_name
        ):
            fail("backup_manifest_invalid")
        components = manifest.get("components")
        if not isinstance(components, list):
            fail("backup_manifest_invalid")
        for entry in components:
            if (
                not isinstance(entry, dict)
                or not isinstance(entry.get("name"), str)
                or not isinstance(entry.get("sha256"), str)
            ):
                fail("backup_manifest_invalid")
            path = work / entry["name"]
            if not path.is_file() or sha256(path) != entry["sha256"]:
                fail("backup_component_checksum_mismatch")
        command(
            [
                "pg_restore",
                *postgres_arguments(),
                "--no-owner",
                "--no-privileges",
                "--single-transaction",
                str(work / "database.dump"),
            ],
            env=postgres_env(),
        )
        extract_archive(work / "photos.tar", TARGET_MEDIA)
        settings_output = RESTORED_SETTINGS / ".env.production"
        if settings_output.exists():
            fail("restore_settings_destination_not_empty")
        shutil.copyfile(work / "settings/.env.production", settings_output)
        settings_output.chmod(0o600)
        log("restore_completed", backup_id=backup_name, postgres_major=metadata["postgres_major"])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Acervoの暗号化バックアップと空環境への復元")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("create")
    retention = subcommands.add_parser("retention")
    retention.add_argument("--dry-run", action="store_true")
    restore = subcommands.add_parser("restore")
    restore.add_argument("--backup-id", required=True)
    restore.add_argument("--identity-file", type=Path, required=True)
    restore.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        if args.command == "create":
            create_backup()
        elif args.command == "retention":
            apply_retention(dry_run=args.dry_run)
        else:
            restore_backup(args.backup_id, args.identity_file, args.confirm)
    except BackupError as error:
        log("failed", reason=str(error))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
