"""自動テスト用設定。CIではPostgreSQL、ローカルではSQLiteを選択できる。"""

import os

from .base import *  # noqa: F403

SECRET_KEY = "test-only-secret-key"
ALLOWED_HOSTS = ["testserver"]

if os.environ.get("ACERVO_TEST_DATABASE") != "postgresql":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
