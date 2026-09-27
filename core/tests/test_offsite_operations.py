"""別ホストの保持処理・容量監視・Discord通知の失敗時安全性を確認する。"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError

OFFSITE_DIRECTORY = Path(__file__).resolve().parents[2] / "deploy" / "offsite"


def load_module(name: str, filename: str):
    specification = importlib.util.spec_from_file_location(name, OFFSITE_DIRECTORY / filename)
    assert specification and specification.loader
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


retention = load_module("acervo_offsite_retention", "acervo_offsite_retention.py")
health = load_module("acervo_offsite_health", "acervo_offsite_health.py")
discord = load_module("acervo_discord_notify", "acervo_discord_notify.py")


class OffsiteRetentionTests(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name) / "incoming"
        self.root.mkdir()
        self.addCleanup(self.temporary_directory.cleanup)

    def backup(self, created_at: datetime) -> Path:
        identifier = created_at.strftime("acervo-%Y%m%dT%H%M%SZ-") + "0" * 12
        path = self.root / identifier
        path.mkdir()
        return path

    def test_daily_weekly_and_monthly_boundaries_are_kept(self):
        now = datetime(2026, 9, 27, tzinfo=UTC)
        for offset in range(400):
            self.backup(now - timedelta(days=offset))

        candidates = retention.retention_candidates(retention.backup_records(self.root))
        candidate_paths = [candidate.path for candidate in candidates]
        newest = self.root / f"acervo-{now:%Y%m%dT%H%M%SZ}-{'0' * 12}"
        old_backup = self.root / f"acervo-20250824T000000Z-{'0' * 12}"

        self.assertTrue(candidates)
        self.assertNotIn(newest, candidate_paths)
        self.assertIn(old_backup, candidate_paths)

    def test_dry_run_does_not_remove_any_backup(self):
        now = datetime(2026, 9, 27, tzinfo=UTC)
        for offset in range(40):
            self.backup(now - timedelta(days=offset))

        retention.run(self.root, apply=False)

        self.assertEqual(len(list(self.root.iterdir())), 40)

    def test_apply_removes_only_retention_candidates(self):
        now = datetime(2026, 9, 27, tzinfo=UTC)
        for offset in range(40):
            self.backup(now - timedelta(days=offset))
        ignored = self.root / ".acervo-unfinished.incoming"
        ignored.mkdir()

        expected = {record.path for record in retention.retention_candidates(retention.backup_records(self.root))}
        retention.run(self.root, apply=True)

        self.assertTrue(all(not candidate.exists() for candidate in expected))
        self.assertTrue(ignored.exists())

    def test_invalid_retention_setting_fails(self):
        with patch.dict(os.environ, {"ACERVO_BACKUP_RETENTION_DAILY": "0"}):
            with self.assertRaisesRegex(retention.RetentionError, "retention_configuration_invalid"):
                retention.retention_limits()


class OffsiteHealthTests(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.addCleanup(self.temporary_directory.cleanup)

    def test_capacity_threshold_rejects_low_free_space(self):
        usage = type("Usage", (), {"total": 100 * 1024**3, "used": 90 * 1024**3, "free": 10 * 1024**3})
        with (
            patch.object(health.shutil, "disk_usage", return_value=usage),
            patch.dict(os.environ, {"ACERVO_OFFSITE_MIN_FREE_GIB": "50"}),
        ):
            with self.assertRaisesRegex(health.HealthError, "capacity_threshold_exceeded"):
                health.inspect_capacity(self.root)

    def test_capacity_check_reports_healthy_space(self):
        usage = type("Usage", (), {"total": 100 * 1024**3, "used": 20 * 1024**3, "free": 80 * 1024**3})
        with patch.object(health.shutil, "disk_usage", return_value=usage):
            self.assertEqual(health.inspect_capacity(self.root), (20, 80))


class DiscordNotificationTests(TestCase):
    def test_notification_uses_verified_user_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            configuration = Path(directory) / "discord-webhook.url"
            configuration.write_text(
                "https://discord.com/api/webhooks/1234567890/test-token", encoding="utf-8"
            )
            with patch.object(discord, "urlopen") as send:
                send.return_value.__enter__.return_value.status = 204
                discord.notify(configuration, "notification-test")

            request = send.call_args.args[0]
            self.assertEqual(request.get_header("User-agent"), "Acervo-Backup/1.0")
            self.assertEqual(request.get_method(), "POST")

    def test_invalid_webhook_is_rejected_without_echoing_value(self):
        with tempfile.TemporaryDirectory() as directory:
            configuration = Path(directory) / "discord-webhook.url"
            configuration.write_text("https://invalid.example/secret-value", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "webhook_configuration_invalid") as context:
                discord.webhook_url(configuration)

            self.assertNotIn("secret-value", str(context.exception))

    def test_http_error_does_not_echo_webhook_url(self):
        with tempfile.TemporaryDirectory() as directory:
            configuration = Path(directory) / "discord-webhook.url"
            url = "https://discord.com/api/webhooks/1234567890/secret-value"
            configuration.write_text(url, encoding="utf-8")
            response = HTTPError(url, 404, "Not Found", hdrs=None, fp=None)

            with patch.object(discord, "urlopen", side_effect=response):
                with self.assertRaisesRegex(ValueError, "webhook_http_404") as context:
                    discord.notify(configuration, "notification-test")

            self.assertNotIn("secret-value", str(context.exception))
