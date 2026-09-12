#!/usr/bin/env python
"""Django管理コマンドのエントリーポイント。"""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Djangoを読み込めません。依存関係をインストールしてください。") from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
