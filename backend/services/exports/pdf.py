"""F8: renders the same print-styled HTML (services/exports/html.py) to a
PDF via headless Chromium, so what a reviewer sees on screen and what
lands in the exported file are byte-for-byte the same document.

Chromium isn't bundled with the `playwright` pip package — it has to be
fetched separately (`playwright install --with-deps chromium`, which
render.yaml's backend buildCommand runs, matching what
.github/workflows/ci.yml already does for this repo's own tests). If
that step is ever missing from wherever this runs, launch() fails fast
with PdfRenderingError instead of an opaque 500 or a hang.
"""
from __future__ import annotations

import os

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

_SANDBOX_CHROMIUM = "/opt/pw-browsers/chromium"


class PdfRenderingError(Exception):
    """Raised when headless Chromium can't be launched — most likely
    because `playwright install chromium` was never run in this
    environment. See render.yaml's backend buildCommand."""


def _executable_path() -> str | None:
    return _SANDBOX_CHROMIUM if os.path.exists(_SANDBOX_CHROMIUM) else None


def render_html_to_pdf(html: str) -> bytes:
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=_executable_path())
            try:
                page = browser.new_page()
                page.set_content(html, wait_until="load")
                return page.pdf(format="A4", print_background=True)
            finally:
                browser.close()
    except PlaywrightError as exc:
        raise PdfRenderingError(
            "PDF export is unavailable: headless Chromium could not be launched "
            "on this server. This usually means `playwright install chromium` "
            "hasn't been run in the deploy environment — see render.yaml's "
            f"backend buildCommand. Underlying error: {exc}"
        ) from exc
