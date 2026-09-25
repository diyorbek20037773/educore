"""Staff roles (Django groups) and their permissions (SPEC §2.2, §8). Applied idempotently by `sync_roles`."""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import Group, Permission
from django.db import transaction

ALL = ("add", "change", "delete", "view")
VIEW = ("view",)
EDIT = ("add", "change", "view")


@dataclass(frozen=True)
class RoleSpec:
    """Permissions as {app_label: {model_name: actions}}; `"*"` as model name means every model of the app."""

    name: str
    grants: dict[str, dict[str, tuple[str, ...]]]


ROLES: tuple[RoleSpec, ...] = (
    RoleSpec(
        "admin",
        {
            app: {"*": ALL}
            for app in (
                "core",
                "accounts",
                "institutions",
                "telegram",
                "ai",
                "content",
                "appeals",
                "analytics",
                "ops",
                "auth",
                "django_celery_beat",
                "otp_totp",
                "otp_static",
            )
        },
    ),
    RoleSpec(
        "editor",
        {
            "content": {"*": ALL},
            "institutions": {"*": EDIT},
            "core": {"page": EDIT, "faq": ALL},
            "telegram": {
                "telegrampost": ("change", "view"),
                "telegrammedia": ("change", "view"),
                "telegramsource": VIEW,
                "ingestionoutbox": VIEW,
                "ingestionrequest": EDIT,
            },
            "ai": {"*": VIEW},
            "analytics": {"*": VIEW},
        },
    ),
    RoleSpec(
        "moderator",
        {
            "appeals": {"*": ALL},
            "institutions": {"institution": VIEW, "institutioncontact": VIEW},
        },
    ),
    RoleSpec(
        "analyst",
        {
            "analytics": {"*": VIEW},
            "content": {"*": VIEW},
            "institutions": {"*": VIEW},
            "telegram": {"telegramsource": VIEW, "telegrampost": VIEW},
            "ai": {"airun": VIEW, "aibudgetday": VIEW},
        },
    ),
)


def _permissions_for(grants: dict[str, dict[str, tuple[str, ...]]]) -> list[Permission]:
    wanted: list[Permission] = []
    for app_label, models in grants.items():
        app_perms = Permission.objects.filter(content_type__app_label=app_label).select_related(
            "content_type"
        )
        for perm in app_perms:
            action, _, model = perm.codename.partition("_")
            actions = models.get(perm.content_type.model) or models.get("*")
            if actions and action in actions and model == perm.content_type.model:
                wanted.append(perm)
    return wanted


@transaction.atomic
def sync_roles() -> dict[str, int]:
    """Create the four groups with exactly the permissions above; returns {group: permission count}."""
    result: dict[str, int] = {}
    for spec in ROLES:
        group, _ = Group.objects.get_or_create(name=spec.name)
        perms = _permissions_for(spec.grants)
        group.permissions.set(perms)
        result[spec.name] = len(perms)
    return result
