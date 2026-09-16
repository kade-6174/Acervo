"""導入先表示名をテンプレートへ渡す。"""

from django.conf import settings


def site_identity(_request):
    return {
        "acervo_site_name": settings.ACERVO_SITE_NAME,
        "acervo_organization_name": settings.ACERVO_ORGANIZATION_NAME,
    }
