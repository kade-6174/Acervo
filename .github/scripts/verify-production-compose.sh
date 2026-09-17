#!/usr/bin/env bash
set -euo pipefail

mode="${1:?公開方式（direct または cloudflare）を指定してください。}"
case "$mode" in
  direct)
    compose=(docker compose -f compose.production.yaml -f compose.direct.yaml)
    caddy_base_url="https://proxy:443"
    ;;
  cloudflare)
    compose=(docker compose -f compose.production.yaml -f compose.cloudflare.yaml)
    caddy_base_url="http://proxy:8080"
    ;;
  *)
    echo "未対応の公開方式です。" >&2
    exit 2
    ;;
esac

export COMPOSE_PROJECT_NAME="acervo-ci-${mode}"

cleanup() {
  local status=$?
  if [[ "$status" -ne 0 ]]; then
    "${compose[@]}" logs --no-color --tail=100 web proxy || true
  fi
  "${compose[@]}" down --volumes --remove-orphans
  return "$status"
}
trap cleanup EXIT

"${compose[@]}" config --quiet
"${compose[@]}" run --rm --no-deps --entrypoint caddy proxy adapt --config /etc/caddy/Caddyfile --validate
"${compose[@]}" run --rm --no-deps --entrypoint caddy proxy validate --config /etc/caddy/Caddyfile

if [[ "$mode" == "direct" ]]; then
  "${compose[@]}" build web
  "${compose[@]}" config --format json | python3 -c '
import json, sys
services = json.load(sys.stdin)["services"]
ports = services["proxy"].get("ports", [])
assert {(str(port["published"]), str(port["target"]), port.get("protocol", "tcp")) for port in ports} == {
    ("80", "80", "tcp"),
    ("443", "443", "tcp"),
    ("443", "443", "udp"),
}
assert not services["web"].get("ports")
assert not services["db"].get("ports")
'
else
  "${compose[@]}" config --format json | python3 -c '
import json, sys
services = json.load(sys.stdin)["services"]
for name in ("proxy", "web", "db", "tunnel"):
    assert not services[name].get("ports"), name
tunnel = services["tunnel"]
assert tunnel["image"] == "cloudflare/cloudflared:2026.9.0"
assert tunnel["command"] == ["tunnel", "--no-autoupdate", "run"]
assert tunnel["read_only"] is True
assert "no-new-privileges:true" in tunnel["security_opt"]
assert set(tunnel["networks"]) == {"frontend"}
assert not tunnel.get("privileged", False)
assert not tunnel.get("network_mode")
'
fi

"${compose[@]}" up --detach --wait db web proxy

test "$("${compose[@]}" exec -T web id -u)" = "10001"
"${compose[@]}" exec -T web python manage.py check --deploy
"${compose[@]}" exec -T web python manage.py help reset_admin_mfa | grep -q "最後の有効な管理者"
"${compose[@]}" exec -T web python manage.py shell -c "from django.conf import settings; cache = settings.CACHES['default']; assert cache['BACKEND'] == 'django.core.cache.backends.db.DatabaseCache'; assert cache['LOCATION'] == 'acervo_rate_limit_cache'"

if [[ "$mode" == "direct" ]]; then
  "${compose[@]}" exec -T web python - <<'PY'
import http.client
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request


class DirectHttpsConnection(http.client.HTTPSConnection):
    def __init__(self):
        super().__init__("acervo.localhost", timeout=10, context=ssl._create_unverified_context())

    def connect(self):
        connection = socket.create_connection(("proxy", 443), self.timeout)
        self.sock = self._context.wrap_socket(connection, server_hostname="acervo.localhost")


def request(path, headers=None):
    connection = DirectHttpsConnection()
    connection.request("GET", path, headers={"Host": "acervo.localhost", **(headers or {})})
    response = connection.getresponse()
    body = response.read()
    connection.close()
    return response, body


for path in ("/health/", "/static/css/acervo.css", "/accounts/login/"):
    response, _ = request(path)
    assert response.status == 200, (path, response.status)

response, _ = request("/admin/")
assert response.status == 404, response.status

response, _ = request("/management/")
assert response.status == 302, response.status
location = urllib.parse.urlsplit(response.getheader("Location"))
assert not location.scheme and not location.netloc, location
assert location.path == "/accounts/login/", location
assert urllib.parse.parse_qs(location.query) == {"next": ["/management/"]}, location
PY
else
  "${compose[@]}" exec -T web python - <<'PY'
import urllib.error
import urllib.parse
import urllib.request

base_url = "http://proxy:8080"
headers = {"Host": "acervo.localhost"}
for path in ("/health/", "/static/css/acervo.css", "/accounts/login/"):
    request = urllib.request.Request(f"{base_url}{path}", headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 200, (path, response.status)

try:
    urllib.request.urlopen(urllib.request.Request(f"{base_url}/admin/", headers=headers), timeout=10)
except urllib.error.HTTPError as error:
    assert error.code == 404, error.code
else:
    raise AssertionError("/admin/が404を返しませんでした。")

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None

opener = urllib.request.build_opener(NoRedirect)
try:
    opener.open(urllib.request.Request(f"{base_url}/management/", headers=headers), timeout=10)
except urllib.error.HTTPError as error:
    assert error.code == 302, error.code
    location = urllib.parse.urlsplit(error.headers["Location"])
    assert not location.scheme and not location.netloc, location
    assert location.path == "/accounts/login/", location
    assert urllib.parse.parse_qs(location.query) == {"next": ["/management/"]}, location
else:
    raise AssertionError("未認証の/management/がログインへ転送されませんでした。")
PY
fi

"${compose[@]}" exec -T -e ACERVO_CI_MODE="$mode" web python manage.py shell <<'PY'
import http.client
from http.cookies import SimpleCookie
import os
import re
import socket
import ssl
import urllib.parse

from django.db import connection


class DirectHttpsConnection(http.client.HTTPSConnection):
    def __init__(self):
        super().__init__("acervo.localhost", timeout=10, context=ssl._create_unverified_context())

    def connect(self):
        connection = socket.create_connection(("proxy", 443), self.timeout)
        self.sock = self._context.wrap_socket(connection, server_hostname="acervo.localhost")


def login_attempt(connection, headers, scheme):
    connection.request("GET", "/accounts/login/", headers=headers)
    response = connection.getresponse()
    assert response.status == 200, response.status
    body = response.read().decode()
    cookie_jar = SimpleCookie()
    for name, value in response.getheaders():
        if name.lower() == "set-cookie":
            cookie_jar.load(value)
    assert "csrftoken" in cookie_jar
    cookies = "; ".join(f"{name}={morsel.value}" for name, morsel in cookie_jar.items())
    csrf_token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', body).group(1)
    assert cookies and csrf_token and len(csrf_token) >= 32
    data = urllib.parse.urlencode({"csrfmiddlewaretoken": csrf_token, "login": "missing-user", "password": "wrong-password"}).encode()
    public_origin = f"{scheme}://acervo.localhost"
    connection.request("POST", "/accounts/login/", body=data, headers={**headers, "Cookie": cookies, "Content-Type": "application/x-www-form-urlencoded", "Origin": public_origin, "Referer": f"{public_origin}/accounts/login/"})
    response = connection.getresponse()
    if response.status != 200:
        raise AssertionError(
            f"login POST status={response.status} "
            f"location_present={bool(response.getheader('Location'))} "
            f"csrf_cookie_present=True csrf_token_length={len(csrf_token)} "
            "origin_matches=True"
        )
    response.read()
    connection.close()


def cache_keys():
    with connection.cursor() as cursor:
        cursor.execute("SELECT cache_key FROM acervo_rate_limit_cache WHERE cache_key LIKE %s", ["%:allauth:rl:login:ip:%"])
        return [row[0] for row in cursor.fetchall()]


with connection.cursor() as cursor:
    cursor.execute("DELETE FROM acervo_rate_limit_cache")

spoofed = {"Host": "acervo.localhost", "X-Acervo-Client-IP": "203.0.113.90", "X-Forwarded-For": "203.0.113.91", "CF-Connecting-IP": "203.0.113.92"}
if os.environ["ACERVO_CI_MODE"] == "direct":
    login_attempt(DirectHttpsConnection(), spoofed, "https")
    keys = cache_keys()
    assert len(keys) == 1, keys
    assert all("203.0.113." not in key for key in keys), keys
else:
    login_attempt(http.client.HTTPConnection("proxy", 8080, timeout=10), {**spoofed, "CF-Connecting-IP": "198.51.100.40"}, "https")
    keys = cache_keys()
    assert len(keys) == 1, keys
    assert keys[0].endswith(":198.51.100.40"), keys
    assert all("203.0.113." not in key for key in keys), keys
PY

"${compose[@]}" exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE TABLE ci_persistence_check (value text NOT NULL); INSERT INTO ci_persistence_check VALUES ('\''retained'\'');"'
"${compose[@]}" up --detach --force-recreate --wait db
test "$("${compose[@]}" exec -T db sh -c 'psql -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT value FROM ci_persistence_check;"')" = "retained"

"${compose[@]}" exec -T web sh -c 'printf %s retained > /app/media/ci-persistence-check.txt'
"${compose[@]}" up --detach --force-recreate --no-deps --wait web
test "$("${compose[@]}" exec -T web cat /app/media/ci-persistence-check.txt)" = "retained"

if [[ "$mode" == "direct" ]]; then
  proxy_id="$("${compose[@]}" ps -q proxy)"
  docker inspect --format '{{json .HostConfig.PortBindings}}' "$proxy_id" | python3 -c '
import json, sys
assert set(json.load(sys.stdin)) == {"80/tcp", "443/tcp", "443/udp"}
'
else
  for service in proxy web db tunnel; do
    container_id="$("${compose[@]}" ps -q "$service" || true)"
    if [[ -n "$container_id" ]]; then
      docker inspect --format '{{json .HostConfig.PortBindings}}' "$container_id" | python3 -c '
import json, sys
assert not json.load(sys.stdin)
'
    fi
  done
fi
