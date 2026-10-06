from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from specimens.access import can_use_qr


@login_required
def home(request):
    return render(request, "core/home.html", {"can_scan": can_use_qr(request.user)})


@never_cache
def manifest(request):
    return JsonResponse(
        {
            "id": "/",
            "name": settings.ACERVO_SITE_NAME,
            "short_name": settings.ACERVO_SITE_NAME,
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": "#ffffff",
            "theme_color": "#212529",
            "icons": [
                {"src": "/static/pwa/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/static/pwa/icon-512.png", "sizes": "512x512", "type": "image/png"},
            ],
        },
        content_type="application/manifest+json",
    )


@never_cache
def service_worker(request):
    source = settings.BASE_DIR / "static" / "js" / "service-worker.js"
    response = HttpResponse(source.read_bytes(), content_type="text/javascript; charset=utf-8")
    response["Service-Worker-Allowed"] = "/"
    return response


@never_cache
@login_required
def qr_scan(request):
    if not can_use_qr(request.user):
        raise Http404
    return render(request, "core/qr_scan.html")


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"status": "ok", "database": "ok"})
