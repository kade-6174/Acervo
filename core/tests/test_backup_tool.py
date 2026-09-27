"""バックアップ補助ツールの失敗時安全性を確認する。"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import tarfile
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

BACKUP_TOOL_PATH = Path(__file__).resolve().parents[2] / "deploy" / "backup" / "acervo_backup.py"
SPEC = importlib.util.spec_from_file_location("acervo_backup_tool", BACKUP_TOOL_PATH)
assert SPEC and SPEC.loader
backup_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup_tool)


class BackupToolTests(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.backups = self.root / "backups"
        self.backups.mkdir()
        self.media = self.root / "media"
        self.media.mkdir()
        self.settings = self.root / ".env.production"
        self.settings.write_text("DJANGO_SECRET_KEY=not-printed\n", encoding="utf-8")
        self.target_media = self.root / "target-media"
        self.target_media.mkdir()
        self.restored_settings = self.root / "restored-settings"
        self.restored_settings.mkdir()
        self.signing_private_key = self.root / "signing-private"
        self.allowed_signers = self.root / "allowed_signers"
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.signing_private_key)],
            check=True,
        )
        public_key = self.signing_private_key.with_suffix(".pub").read_bytes().split()[:2]
        self.allowed_signers.write_bytes(b"acervo-backup " + b" ".join(public_key) + b"\n")
        self.constants = patch.multiple(
            backup_tool,
            BACKUP_ROOT=self.backups,
            SOURCE_MEDIA=self.media,
            SOURCE_SETTINGS=self.settings,
            TARGET_MEDIA=self.target_media,
            RESTORED_SETTINGS=self.restored_settings,
            SIGNING_PRIVATE_KEY=self.signing_private_key,
            ALLOWED_SIGNERS=self.allowed_signers,
        )
        self.constants.start()
        self.addCleanup(self.constants.stop)
        self.addCleanup(self.temporary_directory.cleanup)
        self.environment = patch.dict(
            os.environ,
            {
                "POSTGRES_HOST": "db",
                "POSTGRES_PORT": "5432",
                "POSTGRES_DB": "acervo",
                "POSTGRES_USER": "acervo",
                "POSTGRES_PASSWORD": "database-password-must-not-appear",
                "ACERVO_BACKUP_AGE_RECIPIENTS": "age1recipientone,age1recipienttwo",
                "ACERVO_BACKUP_RETENTION_DAILY": "14",
                "ACERVO_BACKUP_RETENTION_WEEKLY": "8",
                "ACERVO_BACKUP_RETENTION_MONTHLY": "12",
            },
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_recipients_require_one_or_more_distinct_public_keys(self):
        with patch.dict(os.environ, {"ACERVO_BACKUP_AGE_RECIPIENTS": "age1only"}):
            self.assertEqual(backup_tool.recipients(), ["age1only"])
        with patch.dict(os.environ, {"ACERVO_BACKUP_AGE_RECIPIENTS": "age1same,age1same"}):
            with self.assertRaisesRegex(backup_tool.BackupError, "age_recipients_invalid"):
                backup_tool.recipients()
        with patch.dict(os.environ, {"ACERVO_BACKUP_AGE_RECIPIENTS": ""}):
            with self.assertRaisesRegex(backup_tool.BackupError, "age_recipients_invalid"):
                backup_tool.recipients()
        with patch.dict(os.environ, {"ACERVO_BACKUP_AGE_RECIPIENTS": "not-an-age-recipient"}):
            with self.assertRaisesRegex(backup_tool.BackupError, "age_recipients_invalid"):
                backup_tool.recipients()

    def test_missing_database_configuration_fails_without_values(self):
        with patch.dict(os.environ, {"POSTGRES_PASSWORD": ""}):
            with self.assertRaisesRegex(
                backup_tool.BackupError, "database_configuration_missing"
            ) as context:
                backup_tool.postgres_env()
        self.assertNotIn("database-password-must-not-appear", str(context.exception))

    def test_database_backup_failure_is_not_published(self):
        with patch.object(
            backup_tool, "command", side_effect=backup_tool.BackupError("external_command_failed")
        ):
            with self.assertRaisesRegex(backup_tool.BackupError, "database_backup_failed"):
                backup_tool.create_backup()
        self.assertFalse(list(self.backups.glob("acervo-*")))
        self.assertEqual(len(list(self.backups.glob(".failed-acervo-*"))), 1)

    def test_photo_backup_failure_is_not_published(self):
        def fake_command(args, **kwargs):
            if args[0] == "pg_dump":
                Path(args[args.index("--file") + 1]).write_bytes(b"database")
                return ""
            raise backup_tool.BackupError("external_command_failed")

        with patch.object(backup_tool, "command", side_effect=fake_command):
            with self.assertRaisesRegex(backup_tool.BackupError, "photo_backup_failed"):
                backup_tool.create_backup()
        self.assertFalse(list(self.backups.glob("acervo-*")))

    def test_encryption_failure_is_not_published_or_logged_with_secret(self):
        messages = []

        def fake_command(args, **kwargs):
            if args[0] == "pg_dump":
                Path(args[args.index("--file") + 1]).write_bytes(b"database")
            elif args[0] == "tar":
                Path(args[args.index("--file") + 1]).write_bytes(b"archive")
            elif args[0] == "psql":
                return "180006"
            elif args[0] == "age":
                raise backup_tool.BackupError("external_command_failed")
            return ""

        with (
            patch.object(backup_tool, "command", side_effect=fake_command),
            patch.object(
                backup_tool,
                "log",
                side_effect=lambda *args, **kwargs: messages.append((args, kwargs)),
            ),
        ):
            with self.assertRaisesRegex(backup_tool.BackupError, "backup_encryption_failed"):
                backup_tool.create_backup()
        self.assertFalse(list(self.backups.glob("acervo-*")))
        self.assertNotIn("database-password-must-not-appear", repr(messages))

    def test_checksum_mismatch_is_rejected(self):
        archive = self.backups / "acervo-test"
        archive.mkdir()
        (archive / "payload.tar.gz.age").write_bytes(b"payload")
        (archive / "metadata.json").write_text("{}", encoding="utf-8")
        (archive / "checksums.sha256").write_text(
            "0" * 64 + "  payload.tar.gz.age\n" + "0" * 64 + "  metadata.json\n", encoding="ascii"
        )
        with self.assertRaisesRegex(backup_tool.BackupError, "backup_checksum_mismatch"):
            backup_tool.verify_checksums(archive)

    def test_replaced_backup_metadata_and_checksums_fail_authentication(self):
        archive = self.backups / "acervo-test"
        archive.mkdir()
        payload = archive / "payload.tar.gz.age"
        payload.write_bytes(b"original encrypted payload")
        metadata = {
            "backup_id": archive.name,
            "components": [],
            "created_at": "2026-09-27T00:00:00Z",
            "encrypted_payload_sha256": backup_tool.sha256(payload),
            "format_version": backup_tool.BACKUP_FORMAT_VERSION,
            "postgres_major": 18,
        }
        metadata["authentication"] = {
            "algorithm": "ssh-ed25519",
            "signature": backup_tool.sign_metadata(metadata, self.root),
        }
        payload.write_bytes(b"attacker replacement")
        metadata["encrypted_payload_sha256"] = backup_tool.sha256(payload)
        (archive / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        (archive / "checksums.sha256").write_text(
            f"{backup_tool.sha256(payload)}  payload.tar.gz.age\n"
            f"{backup_tool.sha256(archive / 'metadata.json')}  metadata.json\n",
            encoding="ascii",
        )
        with self.assertRaisesRegex(backup_tool.BackupError, "backup_authentication_invalid"):
            backup_tool.verify_metadata_authentication(archive, metadata, self.root)

    def test_signed_metadata_is_accepted(self):
        archive = self.backups / "acervo-test"
        archive.mkdir()
        payload = archive / "payload.tar.gz.age"
        payload.write_bytes(b"signed encrypted payload")
        metadata = {
            "backup_id": archive.name,
            "components": [],
            "created_at": "2026-09-27T00:00:00Z",
            "encrypted_payload_sha256": backup_tool.sha256(payload),
            "format_version": backup_tool.BACKUP_FORMAT_VERSION,
            "postgres_major": 18,
        }
        metadata["authentication"] = {
            "algorithm": "ssh-ed25519",
            "signature": backup_tool.sign_metadata(metadata, self.root),
        }
        backup_tool.verify_metadata_authentication(archive, metadata, self.root)

    def test_unsigned_backup_is_rejected(self):
        archive = self.backups / "acervo-test"
        archive.mkdir()
        payload = archive / "payload.tar.gz.age"
        payload.write_bytes(b"unsigned encrypted payload")
        metadata = {
            "backup_id": archive.name,
            "components": [],
            "created_at": "2026-09-27T00:00:00Z",
            "encrypted_payload_sha256": backup_tool.sha256(payload),
            "format_version": 1,
            "postgres_major": 18,
        }
        with self.assertRaisesRegex(backup_tool.BackupError, "backup_authentication_invalid"):
            backup_tool.verify_metadata_authentication(archive, metadata, self.root)

    def test_invalid_signature_is_rejected(self):
        archive = self.backups / "acervo-test"
        archive.mkdir()
        payload = archive / "payload.tar.gz.age"
        payload.write_bytes(b"signed encrypted payload")
        metadata = {
            "backup_id": archive.name,
            "components": [],
            "created_at": "2026-09-27T00:00:00Z",
            "encrypted_payload_sha256": backup_tool.sha256(payload),
            "format_version": backup_tool.BACKUP_FORMAT_VERSION,
            "postgres_major": 18,
        }
        signature = backup_tool.sign_metadata(metadata, self.root)
        metadata["authentication"] = {
            "algorithm": "ssh-ed25519",
            "signature": f"x{signature[1:]}",
        }
        with self.assertRaisesRegex(backup_tool.BackupError, "backup_authentication_invalid"):
            backup_tool.verify_metadata_authentication(archive, metadata, self.root)

    def test_untrusted_public_key_is_rejected(self):
        archive = self.backups / "acervo-test"
        archive.mkdir()
        payload = archive / "payload.tar.gz.age"
        payload.write_bytes(b"signed encrypted payload")
        metadata = {
            "backup_id": archive.name,
            "components": [],
            "created_at": "2026-09-27T00:00:00Z",
            "encrypted_payload_sha256": backup_tool.sha256(payload),
            "format_version": backup_tool.BACKUP_FORMAT_VERSION,
            "postgres_major": 18,
        }
        metadata["authentication"] = {
            "algorithm": "ssh-ed25519",
            "signature": backup_tool.sign_metadata(metadata, self.root),
        }
        other_private_key = self.root / "other-signing-private"
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(other_private_key)],
            check=True,
        )
        other_public_key = other_private_key.with_suffix(".pub").read_bytes().split()[:2]
        self.allowed_signers.write_bytes(b"acervo-backup " + b" ".join(other_public_key) + b"\n")
        with self.assertRaisesRegex(backup_tool.BackupError, "backup_authentication_invalid"):
            backup_tool.verify_metadata_authentication(archive, metadata, self.root)

    def test_extract_archive_rejects_links(self):
        archive = self.root / "photos.tar"
        with tarfile.open(archive, "w") as output:
            member = tarfile.TarInfo("photo-link")
            member.type = tarfile.SYMTYPE
            member.linkname = "/etc/passwd"
            output.addfile(member)
        with self.assertRaisesRegex(backup_tool.BackupError, "backup_archive_invalid"):
            backup_tool.extract_archive(archive, self.target_media)

    def test_extract_archive_rejects_traversal_and_absolute_paths(self):
        for name in ("../outside", "/outside"):
            archive = self.root / f"{len(name)}.tar"
            with tarfile.open(archive, "w") as output:
                member = tarfile.TarInfo(name)
                member.size = 1
                output.addfile(member, io.BytesIO(b"x"))
            with self.assertRaisesRegex(backup_tool.BackupError, "backup_archive_invalid"):
                backup_tool.extract_archive(archive, self.target_media)

    def test_extract_archive_rejects_hard_links(self):
        archive = self.root / "photos.tar"
        with tarfile.open(archive, "w") as output:
            member = tarfile.TarInfo("photo-link")
            member.type = tarfile.LNKTYPE
            member.linkname = "photo.jpg"
            output.addfile(member)
        with self.assertRaisesRegex(backup_tool.BackupError, "backup_archive_invalid"):
            backup_tool.extract_archive(archive, self.target_media)

    def test_snapshot_prevents_reopen_of_replaced_backup_files(self):
        archive = self.backups / "acervo-test"
        archive.mkdir()
        payload = archive / "payload.tar.gz.age"
        payload.write_bytes(b"original encrypted payload")
        metadata = {
            "backup_id": archive.name,
            "components": [],
            "created_at": "2026-09-27T00:00:00Z",
            "encrypted_payload_sha256": backup_tool.sha256(payload),
            "format_version": backup_tool.BACKUP_FORMAT_VERSION,
            "postgres_major": 18,
        }
        metadata["authentication"] = {
            "algorithm": "ssh-ed25519",
            "signature": backup_tool.sign_metadata(metadata, self.root),
        }
        (archive / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        (archive / "checksums.sha256").write_text(
            f"{backup_tool.sha256(payload)}  payload.tar.gz.age\n"
            f"{backup_tool.sha256(archive / 'metadata.json')}  metadata.json\n",
            encoding="ascii",
        )
        work = self.root / "restore-work"
        work.mkdir()
        snapshot = backup_tool.snapshot_backup(archive, work)
        payload.write_bytes(b"attacker replacement")
        restored_metadata = backup_tool.load_metadata(snapshot)
        backup_tool.verify_metadata_authentication(snapshot, restored_metadata, work)
        self.assertEqual(
            (snapshot / "payload.tar.gz.age").read_bytes(), b"original encrypted payload"
        )

    def test_nonempty_restore_target_is_rejected_before_decryption(self):
        self.target_media.joinpath("existing.jpg").write_bytes(b"existing")
        with patch.object(backup_tool, "command", return_value="0"):
            with self.assertRaisesRegex(backup_tool.BackupError, "restore_target_not_empty"):
                backup_tool.target_is_empty()

    def test_restore_requires_exact_confirmation(self):
        with self.assertRaisesRegex(backup_tool.BackupError, "restore_confirmation_required"):
            backup_tool.restore_backup("acervo-test", self.root / "identity.txt", "RESET")

    def test_retention_keeps_daily_weekly_and_monthly_boundaries(self):
        now = datetime(2026, 9, 18, tzinfo=UTC)
        for offset in range(110):
            created = now - timedelta(days=offset)
            directory = self.backups / f"acervo-{offset:03d}"
            directory.mkdir()
            (directory / "metadata.json").write_text(
                json.dumps(
                    {
                        "backup_id": directory.name,
                        "created_at": created.isoformat().replace("+00:00", "Z"),
                        "format_version": 1,
                        "postgres_major": 18,
                    }
                ),
                encoding="utf-8",
            )
        candidates = backup_tool.retention_candidates()
        self.assertTrue(candidates)
        self.assertNotIn(self.backups / "acervo-000", candidates)
        self.assertIn(self.backups / "acervo-109", candidates)

    def test_invalid_retention_configuration_fails(self):
        with patch.dict(os.environ, {"ACERVO_BACKUP_RETENTION_DAILY": "0"}):
            with self.assertRaisesRegex(backup_tool.BackupError, "retention_configuration_invalid"):
                backup_tool.retention_limits()
