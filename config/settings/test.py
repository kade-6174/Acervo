"""自動テスト用設定。CIではPostgreSQL、ローカルではSQLiteを選択できる。"""

import os

from .base import *  # noqa: F403

SECRET_KEY = "test-only-secret-key"
ALLOWED_HOSTS = ["testserver"]

if os.environ.get("ACERVO_TEST_DATABASE") != "postgresql":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

ACERVO_MFA_FERNET_KEYS = [
    "0YFsuKhANUHwqSsmdjDwiT5GUQXzE7d1c5bUpFPJgy4=",
    "68HlXiUn1Ncg15LUJ9KreAQl6YpPtCV42ivaTBprlGs=",
]
