"""Render Jinja2 email templates."""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .grouper import ManagerDigest
from .regional import RegionalDigest

log = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def _make_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _comma_int(value) -> str:
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def _percent(value) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "—"


def _pluralize(count, singular: str, plural: str | None = None) -> str:
    """Return singular or plural word based on count."""
    if plural is None:
        plural = singular + "s"
    try:
        return singular if int(float(count)) == 1 else plural
    except (TypeError, ValueError):
        return plural


def _sheets_short(value) -> str:
    """Abbreviate large sheet counts for KPI tiles, e.g. 1234567 -> '1.2M', 84700 -> '84.7K'."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1_000_000:
        return f"{sign}{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{sign}{v / 1_000:.1f}K"
    return f"{sign}{v:,.0f}"


_env = _make_env()
_env.filters["comma_int"] = _comma_int
_env.filters["percent"] = _percent
_env.filters["pluralize"] = _pluralize
_env.filters["sheets_short"] = _sheets_short


def render_html(digest: ManagerDigest, subject: str) -> str:
    tmpl = _env.get_template("email.html.j2")
    return tmpl.render(digest=digest, subject=subject)


def render_text(digest: ManagerDigest, subject: str) -> str:
    tmpl = _env.get_template("email.txt.j2")
    return tmpl.render(digest=digest, subject=subject)


def render_admin_alert(reason: str, details: str) -> str:
    tmpl = _env.get_template("admin_alert.html.j2")
    return tmpl.render(reason=reason, details=details)


def render_regional_html(digest: RegionalDigest, subject: str) -> str:
    tmpl = _env.get_template("regional.html.j2")
    return tmpl.render(digest=digest, subject=subject)


def render_regional_text(digest: RegionalDigest, subject: str) -> str:
    tmpl = _env.get_template("regional.txt.j2")
    return tmpl.render(digest=digest, subject=subject)
