"""Unfold admin configuration: branding and sidebar grouped like SPEC §8."""

from __future__ import annotations

from typing import Any

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _


def _item(title: Any, icon: str, url_name: str) -> dict[str, Any]:
    return {"title": title, "icon": icon, "link": reverse_lazy(url_name)}


def _cl(app_model: str) -> str:
    return f"admin:{app_model}_changelist"


SIDEBAR_NAVIGATION: list[dict[str, Any]] = [
    {
        "title": _("Boshqaruv"),
        "items": [_item(_("Dashboard"), "dashboard", "admin:index")],
    },
    {
        "title": _("Tahririyat"),
        "collapsible": True,
        "items": [
            _item(_("Koʻrik navbati"), "rate_review", _cl("content_reviewarticle")),
            _item(_("Maqolalar"), "article", _cl("content_article")),
            _item(_("Kategoriyalar"), "category", _cl("content_category")),
            _item(_("Teglar"), "sell", _cl("content_tag")),
            _item(_("Tadbirlar"), "event", _cl("content_event")),
            _item(_("Qabul"), "how_to_reg", _cl("content_admission")),
            _item(_("Hikoyalar"), "auto_stories", _cl("content_story")),
        ],
    },
    {
        "title": _("Telegram"),
        "collapsible": True,
        "items": [
            _item(_("Manbalar"), "podcasts", _cl("telegram_telegramsource")),
            _item(_("Postlar"), "forum", _cl("telegram_telegrampost")),
            _item(_("Media"), "perm_media", _cl("telegram_telegrammedia")),
            _item(_("Soʻrovlar"), "pending_actions", _cl("telegram_ingestionrequest")),
            _item(_("Outbox"), "outbox", _cl("telegram_ingestionoutbox")),
        ],
    },
    {
        "title": _("AI"),
        "collapsible": True,
        "items": [
            _item(_("AI ishga tushirishlar"), "smart_toy", _cl("ai_airun")),
            _item(_("Byudjet"), "payments", _cl("ai_aibudgetday")),
            _item(_("Klasterlar"), "hub", _cl("ai_eventcluster")),
        ],
    },
    {
        "title": _("Kontent"),
        "collapsible": True,
        "items": [
            _item(_("Muassasalar"), "account_balance", _cl("institutions_institution")),
            _item(_("Koʻrsatkichlar"), "monitoring", _cl("institutions_institutionmetric")),
            _item(_("Yoʻnalishlar"), "school", _cl("institutions_program")),
            _item(_("Kasblar"), "work", _cl("institutions_profession")),
            _item(_("Sahifalar"), "description", _cl("core_page")),
            _item(_("FAQ"), "help", _cl("core_faq")),
        ],
    },
    {
        "title": _("Murojaatlar"),
        "items": [_item(_("Murojaatlar"), "mail", _cl("appeals_appeal"))],
    },
    {
        "title": _("Analitika"),
        "collapsible": True,
        "items": [
            _item(_("Kunlik statistika"), "query_stats", _cl("analytics_dailystat")),
            _item(_("Muassasalar statistikasi"), "bar_chart", _cl("analytics_institutiondailystat")),
            _item(_("Qidiruvlar"), "search", _cl("analytics_searchlog")),
            _item(_("Ogohlantirishlar"), "notifications", _cl("ops_alertevent")),
        ],
    },
    {
        "title": _("Sozlamalar"),
        "collapsible": True,
        "items": [
            _item(_("Sayt sozlamalari"), "settings", _cl("core_sitesetting")),
            _item(_("Foydalanuvchilar"), "person", _cl("accounts_user")),
            _item(_("Rollar"), "group", _cl("auth_group")),
            _item(_("Davriy vazifalar"), "schedule", _cl("django_celery_beat_periodictask")),
        ],
    },
]
