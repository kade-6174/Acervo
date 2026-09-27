#!/usr/bin/env python3
"""別ホストのAcervoバックアップ保存先の安全な状態を検査する。"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

DEFAULT_ROOT = Path("/srv/acervo-backup/sftp/incoming")
REQUIRED_UNITS = ("ssh.service", "acervo-finalize-incoming.path")


class HealthError(Exception):
    """運用上の注意が必要な状態を表す。"""


def log(event: str, **fields: object) -> None:
    suffix = " ".join(f"{name}={value}" for name, value in fields.items())
    print(f"acervo-offsite event={event}" + (f" {suffix}" if suffix else ""))


def environment_integer(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise HealthError("health_configuration_invalid") from error
    if not minimum <= value <= maximum:
        raise HealthError("health_configuration_invalid")
    return value


def ensure_required_units_active() -> None:
    for unit in REQUIRED_UNITS:
        result = subprocess.run(
            ["/usr/bin/systemctl", "is-active", "--quiet", unit], check=False
        )
        if result.returncode != 0:
            raise HealthError("required_unit_inactive")


def inspect_capacity(root: Path) -> tuple[int, int]:
    if not root.is_dir() or root.is_symlink():
        raise HealthError("backup_root_invalid")
    usage = shutil.disk_usage(root)
    used_percent = usage.used * 100 // usage.total
    free_gib = usage.free // 1024**3
    minimum_free_gib = environment_integer(
        "ACERVO_OFFSITE_MIN_FREE_GIB", 50, minimum=1, maximum=1_000_000
    )
    maximum_used_percent = environment_integer(
        "ACERVO_OFFSITE_MAX_USED_PERCENT", 85, minimum=1, maximum=99
    )
    if free_gib < minimum_free_gib or used_percent >= maximum_used_percent:
        raise HealthError("capacity_threshold_exceeded")
    return used_percent, free_gib


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--skip-unit-check", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    try:
        if not arguments.skip_unit_check:
            ensure_required_units_active()
        used_percent, free_gib = inspect_capacity(arguments.root)
    except HealthError as error:
        log("health_failed", reason=error)
        return 1
    log("health_ok", used_percent=used_percent, free_gib=free_gib)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
