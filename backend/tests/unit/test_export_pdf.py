from services.exports.pdf import render_html_to_pdf


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
