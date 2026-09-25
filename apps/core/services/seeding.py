"""Create-only reference seed (SPEC §12): never overwrites rows that already exist (owner edits survive).

Reference rows the seed owns (roles/permissions, beat schedule) are synced idempotently by their own services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from xml.sax.saxutils import escape

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.content.models import Category, Tag
from apps.core.models import FAQ, Page, SiteSetting
from apps.core.seeds import institutions as inst_seed
from apps.core.seeds import pages as page_seed
from apps.core.seeds import professions as prof_seed
from apps.core.seeds import programs as prog_seed
from apps.core.seeds import taxonomy as tax_seed
from apps.institutions.models import (
    Institution,
    InstitutionContact,
    InstitutionMetric,
    Profession,
    ProfessionInstitution,
    Program,
)
from apps.telegram.models import SourceStatus, TelegramSource

TAGLINE = "Huquqni muhofaza qilish taʼlim muassasalarining yagona rasmiy axborot-tahliliy platformasi"
RANK_SYSTEM_NOTE = "Maxsus unvonlar amaldagi qonunchilik va idoraviy nizomlarga muvofiq beriladi."


@dataclass
class SeedReport:
    """Number of rows created per model (0 everywhere on a second run)."""

    created: dict[str, int] = field(default_factory=dict)

    def add(self, name: str, was_created: bool) -> None:
        self.created[name] = self.created.get(name, 0) + int(was_created)


def placeholder_logo_svg(abbreviation: str, color: str) -> str:
    """Square SVG badge with the abbreviation in white on the brand color (until real logos are uploaded)."""
    size = 34 if len(abbreviation) <= 3 else 26
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" role="img" '
        f'aria-label="{escape(abbreviation)}">'
        f'<rect width="120" height="120" rx="24" fill="{escape(color)}"/>'
        f'<text x="60" y="60" dy=".35em" text-anchor="middle" font-family="Manrope, Arial, sans-serif" '
        f'font-weight="700" font-size="{size}" fill="#FFFFFF">{escape(abbreviation)}</text></svg>'
    )


def seed_site_setting(report: SeedReport) -> None:
    _obj, created = SiteSetting.objects.get_or_create(
        pk=1,
        defaults={
            "site_name": "EDUCORE",
            "tagline": TAGLINE,
            "publish_mode": settings.PUBLISH_MODE,
            "publish_confidence_threshold": settings.PUBLISH_CONFIDENCE_THRESHOLD,
            "on_source_delete": settings.ON_SOURCE_DELETE,
            "ai_daily_usd_budget": Decimal(str(settings.AI_DAILY_USD_BUDGET)),
            "ai_translate_to": list(settings.AI_TRANSLATE_TO),
            "footer_text": "Manba: muassasalarning rasmiy Telegram kanallari.",
        },
    )
    report.add("SiteSetting", created)


def seed_institutions(report: SeedReport) -> dict[str, Institution]:
    by_abbr: dict[str, Institution] = {}
    year = timezone.localdate().year
    for data in inst_seed.INSTITUTIONS:
        values = dict(data)
        slug = values.pop("slug")
        inst, created = Institution.objects.get_or_create(
            slug=slug, defaults={**values, "needs_verification": True}
        )
        report.add("Institution", created)
        if created and not inst.logo:
            svg = placeholder_logo_svg(inst.abbreviation, inst.color)
            inst.logo.save(f"{slug}-logo.svg", ContentFile(svg.encode("utf-8")), save=True)
        by_abbr[inst.abbreviation] = inst

        for order, (kind, title, phone, email, hours) in enumerate(inst_seed.CONTACTS.get(slug, [])):
            _c, c_created = InstitutionContact.objects.get_or_create(
                institution=inst,
                kind=kind,
                title=title,
                defaults={"phone": phone, "email": email, "hours": hours, "order": order},
            )
            report.add("InstitutionContact", c_created)

        for key in inst_seed.METRIC_KEYS:
            _m, m_created = InstitutionMetric.objects.get_or_create(
                institution=inst, year=year, key=key, defaults={"needs_verification": True}
            )
            report.add("InstitutionMetric", m_created)

        username = data["telegram_username"].lower()
        _s, s_created = TelegramSource.objects.get_or_create(
            username=username,
            defaults={
                "institution": inst,
                "title": inst.short_name,
                "status": SourceStatus.OFFLINE,
                "signature_patterns": list(inst_seed.SIGNATURE_PATTERNS),
            },
        )
        report.add("TelegramSource", s_created)
    return by_abbr


def seed_taxonomy(report: SeedReport) -> None:
    for order, (slug, name, icon, in_nav, description) in enumerate(tax_seed.CATEGORIES):
        _c, created = Category.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "icon": icon,
                "show_in_nav": in_nav,
                "description": description,
                "order": order,
                "color": tax_seed.CATEGORY_COLOR,
            },
        )
        report.add("Category", created)
    for slug, name in tax_seed.TAGS:
        _t, created = Tag.objects.get_or_create(slug=slug, defaults={"name": name})
        report.add("Tag", created)


def seed_professions(report: SeedReport, by_abbr: dict[str, Institution]) -> dict[str, Profession]:
    professions: dict[str, Profession] = {}
    for order, data in enumerate(prof_seed.PROFESSIONS):
        names = [by_abbr[a].short_name for a in data["institutions"] if a in by_abbr]
        prof, created = Profession.objects.get_or_create(
            slug=data["slug"],
            defaults={
                "name": data["name"],
                "icon": data["icon"],
                "summary": data["summary"],
                "description": f"<p>{data['summary']}</p>",
                "responsibilities": data["responsibilities"],
                "requirements": data["requirements"],
                "work_places": data["work_places"],
                "education_path": "Kasbga tayyorlovchi muassasalar: " + ", ".join(names) + ".",
                "rank_system": RANK_SYSTEM_NOTE,
                "salary_note": "Ish haqi lavozim, unvon va xizmat stajiga qarab belgilanadi.",
                "order": order,
                "needs_verification": True,
            },
        )
        report.add("Profession", created)
        for abbr in data["institutions"]:
            if abbr in by_abbr:
                _l, l_created = ProfessionInstitution.objects.get_or_create(
                    profession=prof, institution=by_abbr[abbr]
                )
                report.add("ProfessionInstitution", l_created)
        professions[prof.slug] = prof
    return professions


def seed_programs(
    report: SeedReport, by_abbr: dict[str, Institution], professions: dict[str, Profession]
) -> None:
    for abbr, slug, name, level, form, years, language, prof_slugs in prog_seed.PROGRAMS:
        inst = by_abbr[abbr]
        program, created = Program.objects.get_or_create(
            institution=inst,
            slug=slug,
            defaults={
                "name": name,
                "level": level,
                "form": form,
                "duration_years": Decimal(str(years)) if years is not None else None,
                "language": language,
                "description": f"<p>{inst.short_name}da «{name}» yoʻnalishi boʻyicha taʼlim.</p>",
                "admission_requirements": prog_seed.LEVEL_REQUIREMENTS[level],
                "qualification": prog_seed.LEVEL_QUALIFICATION[level],
                "needs_verification": True,
            },
        )
        report.add("Program", created)
        if created:
            program.professions.set([professions[s] for s in prof_slugs if s in professions])


def seed_pages_and_faq(report: SeedReport) -> None:
    for slug, title, body, in_footer, order in page_seed.PAGES:
        _p, created = Page.objects.get_or_create(
            slug=slug, defaults={"title": title, "body": body, "show_in_footer": in_footer, "order": order}
        )
        report.add("Page", created)
    for order, (topic, question, answer) in enumerate(page_seed.FAQ):
        _f, created = FAQ.objects.get_or_create(
            question=question, defaults={"topic": topic, "answer": answer, "order": order}
        )
        report.add("FAQ", created)


@transaction.atomic
def seed_reference_data() -> SeedReport:
    """Create every missing reference row; existing rows are left untouched."""
    report = SeedReport()
    seed_site_setting(report)
    by_abbr = seed_institutions(report)
    seed_taxonomy(report)
    professions = seed_professions(report, by_abbr)
    seed_programs(report, by_abbr, professions)
    seed_pages_and_faq(report)
    return report
