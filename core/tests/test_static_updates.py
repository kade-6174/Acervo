"""更新した画面資産とPWAキャッシュが同じ収集結果へ切り替わることを確認する。"""

import re
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.management import call_command
from django.template import Context, Template
from django.templatetags.static import static
from django.test import SimpleTestCase, override_settings
from django.urls import reverse


class StaticUpdateTests(SimpleTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="static-manifest-test-", dir=settings.BASE_DIR)
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.source = root / "source"
        worker = (settings.BASE_DIR / "static/js/service-worker.js").read_text(encoding="utf-8")
        paths = set(re.findall(r'"/static/([^"\n]+)"', worker))
        paths.add("js/taxon-hierarchy.js")
        for path in paths:
            file = self.source / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("/* first version */", encoding="utf-8")
        override = override_settings(
            DEBUG=False,
            STATIC_URL="/static/",
            STATIC_ROOT=root / "collected",
            STATICFILES_DIRS=[self.source],
            STATICFILES_FINDERS=["django.contrib.staticfiles.finders.FileSystemFinder"],
            STORAGES={
                "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                "staticfiles": {
                    "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
                },
            },
        )
        override.enable()
        self.addCleanup(override.disable)
        self.collect()

    def collect(self):
        call_command("collectstatic", interactive=False, verbosity=0)

    def test_changed_javascript_changes_template_url_and_worker_cache_version(self):
        template = Template("{% load static %}{% static 'js/taxon-hierarchy.js' %}")
        before = template.render(Context())
        first_worker = self.client.get(reverse("core:service_worker"))
        self.assertRegex(before, r"/static/js/taxon-hierarchy\.[0-9a-f]{12}\.js")

        (self.source / "js/taxon-hierarchy.js").write_text("/* second version */", encoding="utf-8")
        self.collect()
        after = template.render(Context())
        second_worker = self.client.get(reverse("core:service_worker"))
        self.assertNotEqual(before, after)
        self.assertNotEqual(first_worker.content, second_worker.content)
        self.assertIn(b"acervo-static-v5-", second_worker.content)
        self.assertIn("no-store", second_worker["Cache-Control"])

    def test_worker_and_manifest_reference_collected_icons_and_offline_page(self):
        worker = self.client.get(reverse("core:service_worker")).content.decode()
        self.assertIn(f'"{static("pwa/offline.html")}"', worker)
        self.assertNotIn('"/static/pwa/offline.html"', worker)
        self.assertIn(f'"{static("js/qr-scan.js")}"', worker)
        manifest = self.client.get(reverse("core:manifest")).json()
        self.assertEqual(manifest["icons"][0]["src"], static("pwa/icon-192.png"))
        self.assertEqual(manifest["icons"][1]["src"], static("pwa/icon-512.png"))

    def test_missing_asset_does_not_silently_fall_back_to_an_old_url(self):
        with self.assertRaisesMessage(ValueError, "Missing staticfiles manifest entry"):
            static("js/missing.js")
