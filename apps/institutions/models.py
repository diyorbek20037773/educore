"""Institutions, their contacts and KPIs, programs (yoʻnalishlar) and professions (kasblar) — SPEC §2.3."""

from __future__ import annotations

from typing import ClassVar

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.core.colors import validate_hex_color, validate_text_color_on_white
from apps.core.models import TimeStampedModel


class InstitutionKind(models.TextChoices):
    ACADEMY = "academy", _("Akademiya")
    INSTITUTE = "institute", _("Institut")
    UNIVERSITY = "university", _("Universitet")


def institution_upload_to(instance: Institution, filename: str) -> str:
    return f"institutions/{instance.slug}/{filename}"


class Institution(TimeStampedModel):
    """One of the five education institutions. `order` is the fixed chart series order (ADR-007)."""

    slug = models.SlugField(_("slug"), max_length=80, unique=True)
    short_name = models.CharField(_("short name"), max_length=120)
    full_name = models.CharField(_("full name"), max_length=300)
    abbreviation = models.CharField(_("abbreviation"), max_length=10, unique=True)
    kind = models.CharField(_("kind"), max_length=12, choices=InstitutionKind.choices)
    parent_body = models.CharField(_("parent body"), max_length=300, blank=True)
    description = models.TextField(_("description"), blank=True)
    mission = models.TextField(_("mission"), blank=True)
    founded_year = models.PositiveSmallIntegerField(_("founded"), null=True, blank=True)
    website_url = models.URLField(_("website"), blank=True)
    telegram_username = models.CharField(_("Telegram username"), max_length=64, blank=True)
    email = models.EmailField(_("e-mail"), blank=True)
    phone = models.CharField(_("phone"), max_length=64, blank=True)
    address = models.CharField(_("address"), max_length=300, blank=True)
    city = models.CharField(_("city"), max_length=100, blank=True)
    latitude = models.DecimalField(_("latitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(_("longitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    logo = models.ImageField(_("logo"), upload_to=institution_upload_to, blank=True)
    hero_image = models.ImageField(_("hero image"), upload_to=institution_upload_to, blank=True)
    color = models.CharField(_("chart color"), max_length=7, validators=[validate_hex_color])
    color_text = models.CharField(_("text color"), max_length=7, validators=[validate_text_color_on_white])
    order = models.PositiveSmallIntegerField(_("order"), unique=True)
    is_active = models.BooleanField(_("active"), default=True, db_index=True)
    stats_cache = models.JSONField(_("stats cache"), default=dict, blank=True)
    needs_verification = models.BooleanField(_("needs verification"), default=True, db_index=True)

    class Meta:
        ordering = ("order",)
        verbose_name = _("institution")
        verbose_name_plural = _("institutions")

    def __str__(self) -> str:
        return self.short_name

    def get_absolute_url(self) -> str:
        return reverse("web:institution_detail", kwargs={"slug": self.slug})


class ContactKind(models.TextChoices):
    ADMISSIONS = "admissions", _("Qabul komissiyasi")
    PRESS = "press", _("Matbuot xizmati")
    APPEALS = "appeals", _("Murojaatlar")
    GENERAL = "general", _("Umumiy")
    DORMITORY = "dormitory", _("Yotoqxona")


class InstitutionContact(TimeStampedModel):
    institution = models.ForeignKey(
        Institution, verbose_name=_("institution"), on_delete=models.CASCADE, related_name="contacts"
    )
    kind = models.CharField(_("kind"), max_length=12, choices=ContactKind.choices)
    title = models.CharField(_("title"), max_length=200)
    phone = models.CharField(_("phone"), max_length=64, blank=True)
    email = models.EmailField(_("e-mail"), blank=True)
    hours = models.CharField(_("working hours"), max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(_("order"), default=0)

    class Meta:
        ordering = ("institution__order", "order", "pk")
        verbose_name = _("institution contact")
        verbose_name_plural = _("institution contacts")

    def __str__(self) -> str:
        return f"{self.institution.abbreviation}: {self.title}"


class MetricKey(models.TextChoices):
    STUDENTS = "students", _("Talabalar")
    CADETS = "cadets", _("Kursantlar")
    FACULTY = "faculty", _("Professor-oʻqituvchilar")
    PROGRAMS = "programs", _("Yoʻnalishlar")
    GRADUATES = "graduates", _("Bitiruvchilar")
    DORMITORY_PLACES = "dormitory_places", _("Yotoqxona oʻrinlari")
    LABS = "labs", _("Laboratoriyalar")
    PARTNERS = "partners", _("Xalqaro hamkorlar")


class InstitutionMetric(TimeStampedModel):
    """Editable KPI shown on profiles and comparison; empty value renders as "—"."""

    institution = models.ForeignKey(
        Institution, verbose_name=_("institution"), on_delete=models.CASCADE, related_name="metrics"
    )
    year = models.PositiveSmallIntegerField(_("year"))
    key = models.CharField(_("indicator"), max_length=20, choices=MetricKey.choices)
    value = models.PositiveIntegerField(_("value"), null=True, blank=True)
    unit = models.CharField(_("unit"), max_length=40, blank=True)
    note = models.CharField(_("note"), max_length=300, blank=True)
    source_url = models.URLField(_("source URL"), blank=True)
    needs_verification = models.BooleanField(_("needs verification"), default=True, db_index=True)

    class Meta:
        ordering = ("institution__order", "-year", "key")
        verbose_name = _("institution metric")
        verbose_name_plural = _("institution metrics")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["institution", "year", "key"], name="uniq_metric_inst_year_key"),
        ]

    def __str__(self) -> str:
        return f"{self.institution.abbreviation} {self.year} {self.key}"


class ProgramLevel(models.TextChoices):
    KURS = "kurs", _("Kurs")
    BAKALAVR = "bakalavr", _("Bakalavriat")
    MAGISTR = "magistr", _("Magistratura")
    QAYTA_TAYYORLASH = "qayta_tayyorlash", _("Qayta tayyorlash")
    MALAKA_OSHIRISH = "malaka_oshirish", _("Malaka oshirish")
    DOKTORANTURA = "doktorantura", _("Doktorantura")


class ProgramForm(models.TextChoices):
    KUNDUZGI = "kunduzgi", _("Kunduzgi")
    SIRTQI = "sirtqi", _("Sirtqi")
    MASOFAVIY = "masofaviy", _("Masofaviy")
    ARALASH = "aralash", _("Aralash")


def program_cover_upload_to(instance: Program, filename: str) -> str:
    return f"programs/{instance.institution_id}/{filename}"


class Program(TimeStampedModel):
    """Education program (yoʻnalish) of an institution."""

    institution = models.ForeignKey(
        Institution, verbose_name=_("institution"), on_delete=models.CASCADE, related_name="programs"
    )
    slug = models.SlugField(_("slug"), max_length=120)
    code = models.CharField(_("code"), max_length=32, blank=True)
    name = models.CharField(_("name"), max_length=300)
    level = models.CharField(_("level"), max_length=20, choices=ProgramLevel.choices, db_index=True)
    form = models.CharField(_("form"), max_length=12, choices=ProgramForm.choices, db_index=True)
    duration_years = models.DecimalField(
        _("duration (years)"), max_digits=3, decimal_places=1, null=True, blank=True
    )
    language = models.CharField(_("language of instruction"), max_length=100, blank=True)
    description = models.TextField(_("description"), blank=True)
    admission_requirements = models.TextField(_("admission requirements"), blank=True)
    qualification = models.CharField(_("qualification"), max_length=300, blank=True)
    quota = models.PositiveIntegerField(_("quota"), null=True, blank=True)
    tuition_note = models.CharField(_("tuition note"), max_length=300, blank=True)
    cover = models.ImageField(_("cover"), upload_to=program_cover_upload_to, null=True, blank=True)
    is_active = models.BooleanField(_("active"), default=True, db_index=True)
    source_url = models.URLField(_("source URL"), blank=True)
    needs_verification = models.BooleanField(_("needs verification"), default=True, db_index=True)
    professions = models.ManyToManyField(
        "Profession", verbose_name=_("professions"), related_name="programs", blank=True
    )

    class Meta:
        ordering = ("institution__order", "level", "name")
        verbose_name = _("program")
        verbose_name_plural = _("programs")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["institution", "slug"], name="uniq_program_inst_slug"),
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("web:program_detail", kwargs={"institution": self.institution.slug, "slug": self.slug})


def profession_cover_upload_to(instance: Profession, filename: str) -> str:
    return f"professions/{instance.slug}/{filename}"


class Profession(TimeStampedModel):
    """Profession (kasb) that graduates of the institutions go into."""

    slug = models.SlugField(_("slug"), max_length=120, unique=True)
    name = models.CharField(_("name"), max_length=200)
    summary = models.CharField(_("summary"), max_length=400, blank=True)
    description = models.TextField(_("description"), blank=True)
    responsibilities = models.TextField(_("responsibilities"), blank=True)
    requirements = models.TextField(_("requirements"), blank=True)
    education_path = models.TextField(_("education path"), blank=True)
    rank_system = models.TextField(_("rank system"), blank=True)
    work_places = models.TextField(_("work places"), blank=True)
    salary_note = models.CharField(_("salary note"), max_length=300, blank=True)
    icon = models.CharField(_("icon (lucide name)"), max_length=60, default="briefcase")
    cover = models.ImageField(_("cover"), upload_to=profession_cover_upload_to, null=True, blank=True)
    institutions = models.ManyToManyField(
        Institution,
        verbose_name=_("institutions"),
        through="ProfessionInstitution",
        related_name="professions",
        blank=True,
    )
    order = models.PositiveSmallIntegerField(_("order"), default=0)
    is_published = models.BooleanField(_("published"), default=True, db_index=True)
    needs_verification = models.BooleanField(_("needs verification"), default=True, db_index=True)

    class Meta:
        ordering = ("order", "name")
        verbose_name = _("profession")
        verbose_name_plural = _("professions")

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("web:profession_detail", kwargs={"slug": self.slug})


class ProfessionInstitution(TimeStampedModel):
    """Which institution (and optionally which program) prepares for a profession."""

    profession = models.ForeignKey(Profession, on_delete=models.CASCADE, related_name="institution_links")
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="profession_links")
    program = models.ForeignKey(
        Program, verbose_name=_("program"), on_delete=models.SET_NULL, null=True, blank=True
    )
    note = models.CharField(_("note"), max_length=300, blank=True)

    class Meta:
        ordering = ("institution__order", "pk")
        verbose_name = _("profession–institution link")
        verbose_name_plural = _("profession–institution links")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["profession", "institution"], name="uniq_profession_institution"),
        ]

    def __str__(self) -> str:
        return f"{self.profession} — {self.institution.abbreviation}"
