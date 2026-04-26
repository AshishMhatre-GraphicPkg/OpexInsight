"""Render Jinja2 email templates."""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .grouper import ManagerDigest

log = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def _make_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


_env = _make_env()


def render_html(digest: ManagerDigest, subject: str) -> str:
    tmpl = _env.get_template("email.html.j2")
    return tmpl.render(digest=digest, subject=subject)


def render_text(digest: ManagerDigest, subject: str) -> str:
    tmpl = _env.get_template("email.txt.j2")
    return tmpl.render(digest=digest, subject=subject)


def render_admin_alert(reason: str, details: str) -> str:
    tmpl = _env.get_template("admin_alert.html.j2")
    return tmpl.render(reason=reason, details=details)
