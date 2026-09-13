"""ローカル開発用設定。PostgreSQLを使用する。"""

from .base import *  # noqa: F403

DEBUG = True
SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-development-key")  # noqa: F405
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

if not ACERVO_MFA_FERNET_KEYS:  # noqa: F405
    ACERVO_MFA_FERNET_KEYS = ["0YFsuKhANUHwqSsmdjDwiT5GUQXzE7d1c5bUpFPJgy4="]
