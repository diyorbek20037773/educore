"""Build `static/icons/sprite.svg` with only the Lucide symbols EDUCORE uses (the full sprite is ~500 KB).

Icon names are collected from templates (`{% icon "name" %}`), Python (`icon="name"` /
`"icon": "name"`) and the seed data (category and profession icons stored in the database).
Run via `make icons`; commit the result.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "static" / "vendor" / "lucide" / "sprite.svg"
TARGET = ROOT / "static" / "icons" / "sprite.svg"
EXTRA = {  # noqa: RUF012
    "menu",
    "x",
    "search",
    "sun",
    "moon",
    "globe",
    "chevron-down",
    "chevron-right",
    "chevron-left",
    "arrow-right",
    "arrow-left",
    "arrow-up-right",
    "external-link",
    "calendar",
    "calendar-days",
    "calendar-plus",
    "map-pin",
    "clock",
    "eye",
    "share-2",
    "send",
    "download",
    "table",
    "chart-column",
    "chart-line",
    "radio",
    "circle-alert",
    "circle-check",
    "circle-x",
    "info",
    "phone",
    "mail",
    "building",
    "graduation-cap",
    "users",
    "shield",
    "briefcase",
    "newspaper",
    "sparkles",
    "file-text",
    "message-square",
    "rss",
    "list",
    "layout-grid",
    "funnel",
    "copy",
    "printer",
    "image",
    "play",
    "file",
    "trophy",
    "quote",
    "landmark",
    "languages",
    "link",
    "check",
}
PATTERNS = [
    re.compile(r"""\{%\s*icon\s+["']([a-z0-9-]+)["']"""),
    re.compile(r"""icon\s*=\s*["']([a-z0-9-]+)["']"""),
    re.compile(r"""["']icon["']\s*:\s*["']([a-z0-9-]+)["']"""),
]
SEED_ICON = re.compile(r"""\(\s*"[a-z0-9-]+",\s*"[^"]+",\s*"([a-z0-9-]+)",\s*(?:True|False)""")


def used_icons() -> set[str]:
    names = set(EXTRA)
    for path in [*ROOT.glob("templates/**/*.html"), *ROOT.glob("apps/**/*.py")]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in PATTERNS:
            names.update(pattern.findall(text))
    names.update(SEED_ICON.findall((ROOT / "apps/core/seeds/taxonomy.py").read_text(encoding="utf-8")))
    return names


def main() -> int:
    sprite = SOURCE.read_text(encoding="utf-8")
    found = re.findall(r'(<symbol[^>]*id="([a-z0-9-]+)"[^>]*>.*?</symbol>)', sprite, re.S)
    symbols = {name: symbol for symbol, name in found}
    wanted = sorted(used_icons())
    missing = [n for n in wanted if n not in symbols]
    body = "\n".join(symbols[n] for n in wanted if n in symbols)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" style="display:none">\n' + body + "\n</svg>\n",
        encoding="utf-8",
    )
    size_kb = TARGET.stat().st_size // 1024
    print(f"wrote {TARGET.relative_to(ROOT)}: {len(wanted) - len(missing)} icons, {size_kb} KB")
    if missing:
        print("missing in Lucide:", ", ".join(missing), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
