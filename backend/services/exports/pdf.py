"""F8: renders the same print-styled HTML (services/exports/html.py) to a
PDF via headless Chromium, so what a reviewer sees on screen and what
lands in the exported file are byte-for-byte the same document.
"""
from __future__ import annotations

import os

from playwright.sync_api import sync_playwright

_SANDBOX_CHROMIUM = "/opt/pw-browsers/chromium"


def _executable_path() -> str | None:
    return _SANDBOX_CHROMIUM if os.path.exists(_SANDBOX_CHROMIUM) else None


def render_html_to_pdf(html: str) -> bytes:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=_executable_path())
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            return page.pdf(format="A4", print_background=True)
        finally:
            browser.close()
