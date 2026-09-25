"""Custom user model: e-mail is the login identifier."""

from __future__ import annotations

from typing import Any, ClassVar

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(DjangoUserManager["User"]):
    """Manager creating users keyed by e-mail instead of username."""

    use_in_migrations = True

    def _create_user_by_email(self, email: str, password: str | None, **extra: Any) -> User:
        if not email:
            raise ValueError("An e-mail address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(  # type: ignore[override]
        self, email: str, password: str | None = None, **extra: Any
    ) -> User:
        """Create a regular (non-staff) user."""
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user_by_email(email, password, **extra)

    def create_superuser(  # type: ignore[override]
        self, email: str, password: str | None = None, **extra: Any
    ) -> User:
        """Create a superuser; both staff and superuser flags are forced on."""
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if extra["is_staff"] is not True or extra["is_superuser"] is not True:
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")
        return self._create_user_by_email(email, password, **extra)


class User(AbstractUser):
    """Staff account. Public visitors never log in."""

    username = None  # type: ignore[assignment]
    email = models.EmailField(_("e-mail"), unique=True)
    full_name = models.CharField(_("full name"), max_length=150, blank=True)
    phone = models.CharField(_("phone"), max_length=32, blank=True)
    locale = models.CharField(_("interface language"), max_length=10, default="uz")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects: ClassVar[UserManager] = UserManager()  # type: ignore[assignment]

    class Meta:
        ordering = ("email",)
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def __str__(self) -> str:
        return self.full_name or self.email

    def get_full_name(self) -> str:
        return self.full_name or self.email

    def get_short_name(self) -> str:
        return self.full_name.split(" ")[0] if self.full_name else self.email
