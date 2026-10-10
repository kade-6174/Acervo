"""本番用設定。秘密値が不足している場合は起動させない。"""

import os

from django.core.exceptions import ImproperlyConfigured

from accounts.security import (
    validate_enrollment_settings,
    validate_mfa_fernet_keys,
    validate_production_public_origin,
)

from .base import *  # noqa: F403

# 内容が変わった資産はURLも変え、以前の長期キャッシュを参照しない。
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
}

if not SECRET_KEY:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEYの設定が必要です。")
if not ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTSの設定が必要です。")
if not DATABASES["default"]["PASSWORD"]:  # noqa: F405
    raise ImproperlyConfigured("POSTGRES_PASSWORDの設定が必要です。")

validate_mfa_fernet_keys(ACERVO_MFA_FERNET_KEYS)  # noqa: F405
if not os.environ.get("ACERVO_ENROLLMENT_POLICY"):
    raise ImproperlyConfigured("ACERVO_ENROLLMENT_POLICYの設定が必要です。")
if not isinstance(ACERVO_SITE_NAME, str) or not ACERVO_SITE_NAME.strip():  # noqa: F405
    raise ImproperlyConfigured("ACERVO_SITE_NAMEの設定が必要です。")
if not os.environ.get("ACERVO_SPECIMEN_CODE_PREFIX"):
    raise ImproperlyConfigured("ACERVO_SPECIMEN_CODE_PREFIXの設定が必要です。")
if "ACERVO_BASE_THIRD_YEAR_COHORT" in os.environ:
    raise ImproperlyConfigured(
        "ACERVO_BASE_THIRD_YEAR_COHORTは廃止されました。"
        "ACERVO_BASE_FIRST_YEAR_COHORTへ設定を移行してください。"
    )
if ACERVO_ENROLLMENT_POLICY == "school_cohort":  # noqa: F405
    for variable_name in (
        "ACERVO_SCHOOL_YEAR_START_MONTH",
        "ACERVO_SCHOOL_YEAR_START_DAY",
        "ACERVO_BASE_SCHOOL_YEAR",
        "ACERVO_BASE_FIRST_YEAR_COHORT",
    ):
        value = env(variable_name, default=None)  # noqa: F405
        if not isinstance(value, str) or not value.strip():
            raise ImproperlyConfigured(f"{variable_name}の設定が必要です。")
validate_enrollment_settings(  # noqa: F405
    ACERVO_ENROLLMENT_POLICY,
    ACERVO_SCHOOL_YEAR_START_MONTH,
    ACERVO_SCHOOL_YEAR_START_DAY,
    ACERVO_BASE_SCHOOL_YEAR,
    ACERVO_BASE_FIRST_YEAR_COHORT,
)

if MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN:  # noqa: F405
    raise ImproperlyConfigured("本番環境ではMFA_WEBAUTHN_ALLOW_INSECURE_ORIGINを有効にできません。")

CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])  # noqa: F405
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured("DJANGO_CSRF_TRUSTED_ORIGINSの設定が必要です。")

validate_production_public_origin(  # noqa: F405
    ACERVO_PUBLIC_BASE_URL,
    ALLOWED_HOSTS,
    CSRF_TRUSTED_ORIGINS,
)

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "acervo_rate_limit_cache",
    }
}

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
}

if os.environ.get("ACERVO_CI_CSRF_DIAGNOSTICS") == "1":
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "csrf_diagnostics": {
                "class": "logging.StreamHandler",
                "formatter": "csrf_diagnostics",
            },
        },
        "formatters": {
            "csrf_diagnostics": {"format": "%(levelname)s %(message)s"},
        },
        "loggers": {
            "django.security.csrf": {
                "handlers": ["csrf_diagnostics"],
                "level": "WARNING",
                "propagate": False,
            },
            "accounts.ci_csrf_diagnostics": {
                "handlers": ["csrf_diagnostics"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }
