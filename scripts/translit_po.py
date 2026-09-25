"""Generate `locale/uz_Cyrl/LC_MESSAGES/django.po` from the Uzbek Latin catalog (SPEC FR-I18N-2).

Every entry is transliterated from its Latin `msgstr` (or `msgid` when the source string is already Uzbek);
printf/format placeholders and HTML tags are preserved. Run via `make translit-po`, then
`make compilemessages`.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

import polib  # noqa: E402

from apps.core.translit import to_cyrillic  # noqa: E402

SOURCE = ROOT / "locale" / "uz" / "LC_MESSAGES" / "django.po"
TARGET = ROOT / "locale" / "uz_Cyrl" / "LC_MESSAGES" / "django.po"
_KEEP = re.compile(r"(%\(\w+\)[sdif]|%[sdif]|\{[^{}]*\}|<[^>]+>|&\w+;)")


def translit_keep_placeholders(text: str) -> str:
    """Transliterate everything except placeholders, HTML tags and entities."""
    parts = _KEEP.split(text)
    return "".join(part if i % 2 else to_cyrillic(part) for i, part in enumerate(parts))


def main() -> int:
    if not SOURCE.exists():
        print(f"missing {SOURCE.relative_to(ROOT)} — run `make messages` first", file=sys.stderr)
        return 1
    source = polib.pofile(str(SOURCE))
    target = polib.POFile()
    target.metadata = {**source.metadata, "Language": "uz_Cyrl"}
    for entry in source:
        if entry.obsolete:
            continue
        new = polib.POEntry(
            msgid=entry.msgid,
            msgid_plural=entry.msgid_plural,
            occurrences=entry.occurrences,
            msgctxt=entry.msgctxt,
            flags=[f for f in entry.flags if f != "fuzzy"],
        )
        if entry.msgid_plural:
            new.msgstr_plural = {
                k: translit_keep_placeholders(v or (entry.msgid if k == 0 else entry.msgid_plural))
                for k, v in (entry.msgstr_plural or {0: "", 1: ""}).items()
            }
        else:
            new.msgstr = translit_keep_placeholders(entry.msgstr or entry.msgid)
        target.append(new)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    target.save(str(TARGET))
    print(f"wrote {TARGET.relative_to(ROOT)} ({len(target)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
