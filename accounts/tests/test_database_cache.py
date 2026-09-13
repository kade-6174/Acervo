from unittest.mock import patch

from allauth.core.internal import ratelimit
from django.contrib.auth.models import AnonymousUser
from django.core.cache.backends.db import DatabaseCache
from django.core.management import call_command
from django.test import RequestFactory, TransactionTestCase, override_settings

DATABASE_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "acervo_rate_limit_cache",
    }
}


@override_settings(CACHES=DATABASE_CACHE)
class DatabaseCacheIntegrationTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("createcachetable", verbosity=0)

    def setUp(self):
        self.cache_one = DatabaseCache("acervo_rate_limit_cache", {})
        self.cache_two = DatabaseCache("acervo_rate_limit_cache", {})
        self.cache_one.clear()

    def test_cache_table_creation_is_repeatable_and_preserves_data(self):
        self.cache_one.set("sentinel", "retained", timeout=60)

        call_command("createcachetable", verbosity=0)

        self.assertEqual(self.cache_two.get("sentinel"), "retained")

    def test_rate_limit_state_is_shared_between_independent_cache_instances(self):
        request = RequestFactory().post(
            "/accounts/login/",
            HTTP_X_ACERVO_CLIENT_IP="198.51.100.30",
        )
        request.user = AnonymousUser()
        config = {"login": "1/m/ip"}

        with patch("allauth.core.internal.ratelimit.cache", self.cache_one):
            first = ratelimit.consume(request, action="login", config=config)
        with patch("allauth.core.internal.ratelimit.cache", self.cache_two):
            second = ratelimit.consume(request, action="login", config=config)

        self.assertTrue(first)
        self.assertFalse(second)
