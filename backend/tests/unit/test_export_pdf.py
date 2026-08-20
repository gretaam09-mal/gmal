import pytest

from services.exports import pdf
from services.exports.pdf import PdfRenderingError, render_html_to_pdf


def test_render_html_to_pdf_raises_clean_error_when_chromium_is_missing(monkeypatch):
    """Simulates a deploy environment where `playwright install chromium`
    was never run (the Render bug this guards against) — Chromium's
    launch() fails, and that must surface as a clear PdfRenderingError,
    not a raw Playwright stack trace bubbling up as an opaque 500."""
    monkeypatch.setattr(pdf, "_executable_path", lambda: "/nonexistent/chromium-binary")

    with pytest.raises(PdfRenderingError, match="playwright install chromium"):
        render_html_to_pdf("<html><body>hi</body></html>")


def test_render_html_to_pdf_produces_valid_pdf_bytes():
    html = "<html><body><h1>Project Falcon</h1><p>Headline exposure.</p></body></html>"

    pdf_bytes = render_html_to_pdf(html)

    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 500


def test_render_html_to_pdf_is_deterministic_in_length_for_same_input():
    html = "<html><body><h1>Project Falcon</h1></body></html>"

    first = render_html_to_pdf(html)
    second = render_html_to_pdf(html)

    assert len(first) == len(second)
