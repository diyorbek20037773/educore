"""Mandatory TOTP two-factor authentication for every staff user (SPEC §2.2, NFR-SEC-2)."""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django_otp import user_has_device


class RequireTwoFactorForStaff:
    """Redirect staff without a verified OTP session away from the admin.

    No confirmed device → the two-factor setup wizard; device present but session not verified → the
    two-factor login. The two-factor pages themselves, logout and non-admin URLs are never intercepted.
    Must run after `AuthenticationMiddleware` and `OTPMiddleware`.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.admin_prefix = f"/{settings.ADMIN_URL_PATH}/"
        self.exempt_prefixes = (f"{self.admin_prefix}account/", f"{self.admin_prefix}logout/")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        path = request.path_info
        if (
            user is not None
            and user.is_authenticated
            and user.is_staff
            and path.startswith(self.admin_prefix)
            and not path.startswith(self.exempt_prefixes)
            and not user.is_verified()  # type: ignore[union-attr]
        ):
            target = "two_factor:login" if user_has_device(user) else "two_factor:setup"
            return HttpResponseRedirect(f"{reverse(target)}?{urlencode({'next': request.get_full_path()})}")
        return self.get_response(request)
