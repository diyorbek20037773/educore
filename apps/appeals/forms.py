"""Public appeal form and tracking form (SPEC §6.10); submission logic lives in `services.submission`."""

from __future__ import annotations

import re
from typing import Any

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.appeals.models import AppealTopic
from apps.appeals.services.submission import validate_attachment
from apps.institutions.models import Institution

PHONE_RE = re.compile(r"^\+998\d{9}$")


def normalize_phone(value: str) -> str:
    digits = re.sub(r"[^\d+]", "", value or "")
    if digits.startswith("998"):
        digits = f"+{digits}"
    return digits


class AppealForm(forms.Form):
    institution = forms.ModelChoiceField(
        label=_("Muassasa"),
        queryset=Institution.objects.filter(is_active=True).order_by("order"),
        required=False,
        empty_label=_("Umumiy murojaat"),
    )
    topic = forms.ChoiceField(label=_("Mavzu"), choices=AppealTopic.choices)
    full_name = forms.CharField(label=_("F.I.Sh."), max_length=200, min_length=3)
    phone = forms.CharField(
        label=_("Telefon"),
        max_length=20,
        help_text=_("+998 XX XXX XX XX formatida"),
        widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel", "placeholder": "+998"}),
    )
    email = forms.EmailField(
        label=_("E-pochta"), required=False, widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    message = forms.CharField(
        label=_("Murojaat matni"), min_length=20, max_length=5000, widget=forms.Textarea(attrs={"rows": 6})
    )
    attachment = forms.FileField(
        label=_("Ilova (ixtiyoriy)"),
        required=False,
        help_text=_("PDF, JPG, PNG yoki DOCX, 5 MB gacha"),
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png,.docx"}),
    )
    consent = forms.BooleanField(label=_("Shaxsiy maʼlumotlarimni qayta ishlashga roziman"))
    # Honeypot: humans never see or fill it.
    website = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"})
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["full_name"].widget.attrs["autocomplete"] = "name"
        for name, field in self.fields.items():
            if name in ("consent", "website"):
                continue
            field.widget.attrs.setdefault("class", "form-input")
            if self.errors.get(name):
                field.widget.attrs["aria-invalid"] = "true"
                field.widget.attrs["aria-describedby"] = f"{name}-error"
            elif field.help_text:
                field.widget.attrs["aria-describedby"] = f"{name}-help"

    def clean_phone(self) -> str:
        phone = normalize_phone(self.cleaned_data["phone"])
        if not PHONE_RE.match(phone):
            raise ValidationError(
                _("Telefon raqami +998 bilan boshlanib, 12 ta raqamdan iborat boʻlishi kerak.")
            )
        return phone

    def clean_attachment(self) -> Any:
        upload = self.cleaned_data.get("attachment")
        if not upload:
            return None
        validate_attachment(upload)
        return upload

    def is_bot(self) -> bool:
        return bool(self.data.get("website"))


class TrackForm(forms.Form):
    code = forms.CharField(
        label=_("Kuzatish kodi"),
        max_length=20,
        widget=forms.TextInput(
            attrs={"class": "form-input", "autocomplete": "off", "placeholder": "EDC-2026-000000"}
        ),
    )

    def clean_code(self) -> str:
        return self.cleaned_data["code"].strip().upper()
