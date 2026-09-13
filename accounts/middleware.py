from django.shortcuts import redirect


class InitialPasswordChangeMiddleware:
    allowed_view_names = {
        "account_change_password",
        "account_logout",
        "core:health",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated or not request.user.must_change_password:
            return None
        if request.resolver_match.view_name in self.allowed_view_names:
            return None
        return redirect("account_change_password")
