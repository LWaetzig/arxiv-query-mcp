.. _arxiv_fetch_paper_text:

arxiv_fetch_paper_text
======================

Fetch the readable text content of an arXiv paper.

This tool first attempts to retrieve the HTML-rendered version of the paper
(available for most papers submitted after ~2023 with LaTeX source). If the
HTML version is unavailable it falls back to returning the full abstract and
direct links to the PDF.

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

Return Values
-------------

.. list-table::
   :header-rows: 1

   * - Scenario
     - Response
   * - HTML version available
     - Extracted article text (up to 10,000 characters). A truncation notice
       with the full HTML URL is appended when the paper exceeds the limit.
   * - HTML version unavailable
     - Full abstract, metadata fields, and links to the abstract page and PDF.

.. tip::

   The 10,000-character limit is set by :attr:`~arxiv_query_mcp.config.Config.max_fetch_chars`.
   To read a longer paper, follow the ``html_url`` link returned in the
   truncation suffix.

Examples
--------

**Read the GPT-4 technical report:**

.. code-block:: json

   { "paper_id": "2303.08774" }

**Read Attention Is All You Need:**

.. code-block:: json

   { "paper_id": "1706.03762" }

**Using a versioned ID:**

.. code-block:: json

   { "paper_id": "2303.08774v2" }

HTML Availability
-----------------

arXiv provides HTML rendering for papers that:

- Were submitted **after approximately 2023**
- Include **LaTeX source** (not PDF-only submissions)

For older papers or PDF-only submissions the tool gracefully degrades to
returning the abstract and links, so callers never need to handle ``None``
or empty results.
