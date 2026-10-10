"""CIのCaddy経路で、画面・PWAが参照する内容別URLの静的資産を確認する。"""

import http.client
import json
import os
import re
import socket
import ssl
from urllib.parse import urlsplit

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

import django

django.setup()

from django.templatetags.static import static  # noqa: E402


class DirectConnection(http.client.HTTPSConnection):
    def __init__(self):
        # CIで生成したlocalhost用証明書だけを検証対象にする。
        super().__init__("acervo.localhost", timeout=10, context=ssl._create_unverified_context())

    def connect(self):
        connection = socket.create_connection(("proxy", 443), self.timeout)
        self.sock = self._context.wrap_socket(connection, server_hostname="acervo.localhost")


def request(path):
    connection = (
        DirectConnection()
        if os.environ["ACERVO_CI_MODE"] == "direct"
        else http.client.HTTPConnection("proxy", 8080, timeout=10)
    )
    try:
        connection.request("GET", path, headers={"Host": "acervo.localhost"})
        response = connection.getresponse()
        content = response.read()
        assert response.status == 200, f"static_check status={response.status}"
        return content, response.getheader("Cache-Control", "")
    finally:
        connection.close()


login, _ = request("/accounts/login/")
worker, worker_cache = request("/service-worker.js")
manifest, manifest_cache = request("/manifest.webmanifest")
assert "no-store" in worker_cache and "no-store" in manifest_cache
assert b"acervo-static-v5-" in worker
paths = set(re.findall(r'(?:src|href)="(/static/[^"<>]+)"', login.decode()))
paths.update(re.findall(r'"(/static/[^"\n]+)"', worker.decode()))
paths.update(icon["src"] for icon in json.loads(manifest)["icons"])
paths.add(static("js/taxon-hierarchy.js"))
assert paths
for path in paths:
    assert re.search(r"\.[0-9a-f]{12}\.[^/]+$", urlsplit(path).path), "unversioned_static_asset"
    content, cache = request(path)
    assert content and "immutable" in cache
print(f"versioned_static_assets=verified count={len(paths)} worker_cache=updated")
