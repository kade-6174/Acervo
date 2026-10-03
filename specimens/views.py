"""QR公開URLの安全な入口。"""

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from .access import can_use_qr
from .models import QRLabel


@never_cache
@login_required
def qr_resolve(request, token):
    """認可済み利用者だけに、QRの次の操作を案内する。

    標本の内容や標本番号はPhase 5までここから返さない。
    """

    if not can_use_qr(request.user):
        raise Http404
    label = QRLabel.objects.filter(token=token).only("status").first()
    if label is None:
        raise Http404
    if label.status == QRLabel.Status.RETIRED:
        return render(request, "specimens/qr_unavailable.html", status=410)
    if label.status == QRLabel.Status.UNUSED:
        return render(request, "specimens/qr_unused.html")
    return render(request, "specimens/qr_assigned.html")
