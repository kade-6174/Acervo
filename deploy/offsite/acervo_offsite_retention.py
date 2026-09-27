#!/usr/bin/env python3
"""別ホストへ確定保存したAcervoバックアップの保持処理。"""

from __future__ import annotations

import argparse
import os
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_ROOT = Path("/srv/acervo-backup/sftp/incoming")
BACKUP_ID_PATTERN = re.compile(r"acervo-(\d{8}T\d{6}Z)-[0-9a-f]{12}")


class RetentionError(Exception):
    """安全に保持処理を完了できない場合のエラー。"""


@dataclass(frozen=True)
class BackupRecord:
    created_at: datetime
    path: Path


def fail(reason: str) -> None:
    raise RetentionError(reason)


def log(event: str, **fields: object) -> None:
    suffix = " ".join(f"{name}={value}" for name, value in fields.items())
    print(f"acervo-offsite event={event}" + (f" {suffix}" if suffix else ""))


def positive_environment_integer(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise RetentionError("retention_configuration_invalid") from error
    if value < 1:
        fail("retention_configuration_invalid")
    return value


def retention_limits() -> tuple[int, int, int]:
    return (
        positive_environment_integer("ACERVO_BACKUP_RETENTION_DAILY", 14),
        positive_environment_integer("ACERVO_BACKUP_RETENTION_WEEKLY", 8),
        positive_environment_integer("ACERVO_BACKUP_RETENTION_MONTHLY", 12),
    )


def backup_records(root: Path) -> list[BackupRecord]:
    if not root.is_dir() or root.is_symlink():
        fail("backup_root_invalid")
    records: list[BackupRecord] = []
    for entry in root.iterdir():
        if not entry.is_dir() or entry.is_symlink():
            continue
        match = BACKUP_ID_PATTERN.fullmatch(entry.name)
        if match is None:
            continue
        try:
            created_at = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        except ValueError as error:
            raise RetentionError("backup_id_invalid") from error
        records.append(BackupRecord(created_at=created_at, path=entry))
    return sorted(records, key=lambda record: record.created_at, reverse=True)


def retention_candidates(records: list[BackupRecord]) -> list[BackupRecord]:
    daily_limit, weekly_limit, monthly_limit = retention_limits()
    keep: set[Path] = set()
    seen_days: set[object] = set()
    seen_weeks: set[object] = set()
    seen_months: set[object] = set()
    for record in records:
        day = record.created_at.date()
        week = record.created_at.isocalendar()[:2]
        month = (record.created_at.year, record.created_at.month)
        if day not in seen_days and len(seen_days) < daily_limit:
            seen_days.add(day)
            keep.add(record.path)
        if week not in seen_weeks and len(seen_weeks) < weekly_limit:
            seen_weeks.add(week)
            keep.add(record.path)
        if month not in seen_months and len(seen_months) < monthly_limit:
            seen_months.add(month)
            keep.add(record.path)
    return [record for record in records if record.path not in keep]


def remove_candidate(root: Path, record: BackupRecord) -> None:
    expected_parent = root.resolve()
    if record.path.parent.resolve() != expected_parent or record.path.is_symlink():
        fail("retention_target_invalid")
    try:
        shutil.rmtree(record.path)
    except OSError as error:
        raise RetentionError("retention_cleanup_failed") from error


def run(root: Path, *, apply: bool) -> None:
    candidates = retention_candidates(backup_records(root))
    for record in candidates:
        log("retention_candidate", backup_id=record.path.name)
    if not apply:
        log("retention_dry_run", candidates=len(candidates))
        return
    for record in candidates:
        remove_candidate(root, record)
    log("retention_completed", deleted=len(candidates))


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    try:
        run(arguments.root, apply=arguments.apply)
    except RetentionError as error:
        log("retention_failed", reason=error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
