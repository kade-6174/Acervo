from django.shortcuts import render
from django.views.decorators.cache import never_cache


@never_cache
def index(request):
    """Step 5Bの最小管理トップ。管理操作は後続Stepで追加する。"""

    return render(request, "management_portal/index.html")
