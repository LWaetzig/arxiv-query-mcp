"""Tests for HTML-to-text extraction in :mod:`arxiv_query_mcp.utils`."""

from arxiv_query_mcp.config import Config
from arxiv_query_mcp.utils import (
    _clean_id,
    _parse_atom_response,
    _pdf_to_text,
    _strip_html,
    _versioned_id,
)


def test_strip_html_keeps_headings_and_paragraphs():
    html = (
        "<article><h1>Title</h1><section>"
        '<h2><span class="ltx_tag">1 </span>Introduction</h2>'
        "<p>First\n   paragraph.</p><p>Second paragraph.</p>"
        "</section></article>"
    )

    assert _strip_html(html) == (
        "# Title\n\n## 1 Introduction\n\nFirst paragraph.\n\nSecond paragraph."
    )


def test_strip_html_renders_list_items():
    html = "<article><ul><li><p>first</p></li><li>second</li></ul></article>"

    assert _strip_html(html) == "- first\n\n- second"


def test_strip_html_replaces_math_with_latex_source():
    html = (
        '<article><p>Energy is <math alttext="E=mc^{2}"><semantics>'
        "<mrow><mi>E</mi><mo>=</mo><mi>m</mi></mrow>"
        '<annotation encoding="application/x-tex">E=mc^{2}</annotation>'
        "</semantics></math> here.</p></article>"
    )

    assert _strip_html(html) == "Energy is $E=mc^{2}$ here."


def test_strip_html_skips_chrome_and_prefers_article():
    html = (
        "<html><body><nav>menu</nav><header>top</header><p>outside</p>"
        "<article><p>body</p><script>var x;</script></article>"
        "<footer>bottom</footer></body></html>"
    )

    assert _strip_html(html) == "body"


def test_strip_html_without_article_returns_page_text():
    html = "<html><body><nav>menu</nav><p>one</p><p>two</p></body></html>"

    assert _strip_html(html) == "one\n\ntwo"


def test_versioned_id_keeps_version_and_clean_id_drops_it():
    for raw in ("2303.08774v2", "https://arxiv.org/abs/2303.08774v2", " 2303.08774v2/ "):
        assert _versioned_id(raw) == "2303.08774v2"
        assert _clean_id(raw) == "2303.08774"
    assert _versioned_id("hep-th/9901001") == "hep-th/9901001"
    assert _clean_id("https://arxiv.org/pdf/hep-th/9901001v3") == "hep-th/9901001"


def test_parse_entry_reports_version():
    xml = """<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
      <opensearch:totalResults>1</opensearch:totalResults>
      <entry>
        <id>http://arxiv.org/abs/1706.03762v2</id>
        <title>Attention Is All You Need</title>
        <summary>Abstract.</summary>
        <published>2017-06-12T17:57:34Z</published>
        <updated>2017-06-19T16:49:45Z</updated>
        <author><name>A. Vaswani</name></author>
      </entry>
    </feed>"""

    total, papers = _parse_atom_response(xml, Config())

    assert total == 1
    assert papers[0]["id"] == "1706.03762"
    assert papers[0]["version"] == "v2"
    assert papers[0]["html_url"] == "https://arxiv.org/html/1706.03762v2"


def _make_pdf(lines: list[str]) -> bytes:
    """Build a minimal one-page PDF showing *lines* of text."""
    ops = " ".join(f"({line}) Tj 0 -14 Td" for line in lines)
    stream = f"BT /F1 12 Tf 72 720 Td {ops} ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


def test_pdf_to_text_extracts_lines():
    text = _pdf_to_text(_make_pdf(["1 Introduction", "We study   gradient descent."]))

    assert text == "1 Introduction\nWe study gradient descent."


def test_pdf_ligatures_are_expanded(monkeypatch):
    class _Page:
        def extract_text(self):
            return "e\ufb03cient \ufb01rst-order \ufb02ow"

    class _Reader:
        def __init__(self, stream):
            self.pages = [_Page()]

    monkeypatch.setattr("arxiv_query_mcp.utils.PdfReader", _Reader)

    assert _pdf_to_text(b"") == "efficient first-order flow"


def test_pdf_to_text_returns_empty_for_unreadable_data():
    assert _pdf_to_text(b"this is not a pdf") == ""
