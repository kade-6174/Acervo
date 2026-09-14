"""全環境で共有するDjango設定。"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env()
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="")
DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "accounts",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "accounts.middleware.InitialPasswordChangeMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "account_login"

ACCOUNT_ADAPTER = "accounts.adapters.AcervoAccountAdapter"
ACCOUNT_FORMS = {
    "change_password": "accounts.forms.AcervoChangePasswordForm",
    "login": "accounts.forms.AcervoLoginForm",
}
ACCOUNT_LOGIN_METHODS = {"username"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "password1*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGIN_BY_CODE_ENABLED = False
ACCOUNT_LOGOUT_ON_GET = False
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = False
ACCOUNT_SESSION_REMEMBER = False
ALLAUTH_TRUSTED_CLIENT_IP_HEADER = "X-Acervo-Client-IP"
ALLAUTH_TRUSTED_PROXY_COUNT = 0

MFA_ADAPTER = "accounts.adapters.AcervoMFAAdapter"
# Step 4B: 登録済みWebAuthn credentialをMFAとしてのみ公開する。
# passwordless 用 credential の登録選択肢にはこの設定が必要だが、対応URLは
# accounts.mfa_urls の allowlist に含めないため、Step 4Cまでpasswordlessログインは非公開。
MFA_SUPPORTED_TYPES = ["recovery_codes", "totp", "webauthn"]
MFA_PASSKEY_LOGIN_ENABLED = True
MFA_PASSKEY_SIGNUP_ENABLED = False
MFA_FORMS = {
    "authenticate": "accounts.forms.AcervoAuthenticateForm",
    "add_webauthn": "accounts.forms.AcervoAddWebAuthnForm",
    "edit_webauthn": "accounts.forms.AcervoEditWebAuthnForm",
    "authenticate_webauthn": "accounts.forms.AcervoAuthenticateWebAuthnForm",
    "reauthenticate_webauthn": "accounts.forms.AcervoReauthenticateWebAuthnForm",
    "login_webauthn": "accounts.forms.AcervoLoginWebAuthnForm",
}
MFA_RECOVERY_CODE_COUNT = 10
MFA_RECOVERY_CODES_SHOW_ONCE = True
MFA_TRUST_ENABLED = False
MFA_TOTP_ISSUER = "Acervo"
MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN = False

ACERVO_MFA_FERNET_KEYS = env.list("ACERVO_MFA_FERNET_KEYS", default=[])

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="acervo"),
        "USER": env("POSTGRES_USER", default="acervo"),
        "PASSWORD": env("POSTGRES_PASSWORD", default=""),
        "HOST": env("POSTGRES_HOST", default="localhost"),
        "PORT": env("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": 60,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ja"
TIME_ZONE = env("DJANGO_TIME_ZONE", default="Asia/Tokyo")
USE_I18N = True
USE_TZ = True

ACERVO_PUBLIC_BASE_URL = env("ACERVO_PUBLIC_BASE_URL", default="http://localhost:8000")

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
