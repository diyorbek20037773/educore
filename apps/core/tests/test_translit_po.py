"""`scripts/translit_po.py` keeps placeholders and tags intact."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load() -> object:
    path = Path(__file__).resolve().parents[3] / "scripts" / "translit_po.py"
    spec = importlib.util.spec_from_file_location("translit_po", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_placeholders_and_tags_preserved() -> None:
    module = _load()
    out = module.translit_keep_placeholders("%(n)d ta maqola <strong>eʼlon</strong> qilindi {name}")  # type: ignore[attr-defined]
    assert out == "%(n)d та мақола <strong>эълон</strong> қилинди {name}"


def test_precision_format_specs_preserved() -> None:
    module = _load()
    out = module.translit_keep_placeholders("kontrast %(ratio).2f:1, %5.1f%% va %s")  # type: ignore[attr-defined]
    assert out == "контраст %(ratio).2f:1, %5.1f%% ва %s"
