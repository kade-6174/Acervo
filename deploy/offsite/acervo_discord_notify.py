#!/usr/bin/env python3
"""root専用のDiscord Webhook設定を使い、失敗したunit名だけを通知する。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_CONFIG = Path("/etc/acervo/discord-webhook.url")


def webhook_url(config: Path) -> str:
    try:
        url = config.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise ValueError("webhook_configuration_unavailable") from error
    if not url.startswith("https://discord.com/api/webhooks/") or any(
        character.isspace() for character in url
    ):
        raise ValueError("webhook_configuration_invalid")
    return url


def notify(config: Path, failed_unit: str) -> None:
    url = webhook_url(config)
    message = f"Acervo バックアップ運用の確認が必要です: {failed_unit}"
    request = Request(
        url,
        data=json.dumps({"content": message}, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Acervo-Backup/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 -- URL is locally managed.
            if not 200 <= response.status < 300:
                raise ValueError("webhook_delivery_failed")
    except HTTPError as error:
        raise ValueError(f"webhook_http_{error.code}") from error
    except TimeoutError as error:
        raise ValueError("webhook_timeout") from error
    except URLError as error:
        raise ValueError("webhook_connection_failed") from error


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("failed_unit")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    try:
        notify(arguments.config, arguments.failed_unit)
    except ValueError as error:
        print(f"acervo-offsite event=discord_notification_failed reason={error}")
        return 1
    print(f"acervo-offsite event=discord_notification_sent unit={arguments.failed_unit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
