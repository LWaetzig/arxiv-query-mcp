.. _arxiv_fetch_paper_text:

arxiv_fetch_paper_text
======================

Fetch the readable text content of an arXiv paper.

This tool first attempts to retrieve the HTML-rendered version of the paper
(available for most papers submitted after ~2023 with LaTeX source). Headings,
paragraphs and list items are kept as lightweight Markdown and formulas are
given as LaTeX. If there is no HTML version, the text is extracted from the PDF
instead. Only when neither works does it return the full abstract and direct
links to the PDF.

.. note::

   Use :ref:`arxiv_search` or :ref:`arxiv_get_paper` first to identify the
   paper ID, then call this tool to read its content.

Parameters
----------

.. list-table::
   :header-rows: 1
   :widths: 20 12 12 56

   * - Parameter
     - Type
     - Default
     - Description
   * - ``paper_id``
     - ``str``
     - *(required)*
     - arXiv paper ID, e.g. ``2303.08774``. Accepts the same formats as
       :ref:`arxiv_get_paper` (bare, versioned, old-style, full URL).
   * - ``offset``
     - ``int``
     - ``0``
     - Character offset to start reading from. Pass the ``next_offset``
       reported by the previous call to read the next page.
   * - ``response_format``
     - ``str``
     - ``markdown``
     - ``markdown`` or ``json``.

Return Values
-------------

.. list-table::
   :header-rows: 1

   * - Scenario
     - Response
   * - HTML version available
     - One page of extracted article text (up to 10,000 characters) with the
       character range it covers. When more text remains, the response names
       the offset that continues the paper.
   * - No HTML version, PDF readable
     - One page of text extracted from the PDF, paginated the same way. The
       response says the text comes from the PDF; layout, tables and formulas
       may be imperfect.
   * - No text can be extracted
     - Full abstract, metadata fields, and links to the abstract page and PDF.

.. note::

   Extracted text is cached (see :doc:`../caching`), so reading the same paper
   again does not contact arXiv until the cache entry expires.

.. tip::

   The page size is set by :attr:`~arxiv_query_mcp.config.Config.max_fetch_chars`.
   To read a longer paper, call the tool again with the reported offset until
   no further offset is returned.

With ``response_format`` set to ``json`` a text page (``format`` is ``html``
or ``pdf``) looks like this:

.. code-block:: json

   {
     "id": "2303.08774",
     "source": "https://arxiv.org/html/2303.08774",
     "format": "html",
     "total_chars": 84210,
     "offset": 0,
     "count": 9996,
     "has_more": true,
     "next_offset": 9996,
     "text": "..."
   }

Examples
--------

**Read the GPT-4 technical report:**

.. code-block:: json

   { "paper_id": "2303.08774" }

**Read Attention Is All You Need:**

.. code-block:: json

   { "paper_id": "1706.03762" }

**Continue reading from where the previous page ended:**

.. code-block:: json

   { "paper_id": "2303.08774", "offset": 9996 }

**Using a versioned ID:**

.. code-block:: json

   { "paper_id": "2303.08774v2" }

HTML Availability
-----------------

arXiv provides HTML rendering for papers that:

- Were submitted **after approximately 2023**
- Include **LaTeX source** (not PDF-only submissions)

For older papers or PDF-only submissions the tool extracts the text from the
PDF. PDFs larger than ``ARXIV_MCP_MAX_PDF_BYTES`` and scanned PDFs without a
text layer are not parsed; for those the tool returns the abstract and links.
