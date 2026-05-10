Configuration
=============

The server is configured via the :class:`~arxiv_query_mcp.config.Config` dataclass,
which is instantiated once at module level with sensible defaults.
No environment variables or configuration files are required.

See the full class reference at :class:`arxiv_query_mcp.config.Config`.

----

Defaults
--------

.. list-table::
   :header-rows: 1
   :widths: 30 45 25

   * - Field
     - Default value
     - Notes
   * - ``arxiv_api_url``
     - ``https://export.arxiv.org/api/query``
     - Official arXiv Atom API endpoint
   * - ``arxiv_abs_base``
     - ``https://arxiv.org/abs``
     - Abstract page URL prefix
   * - ``arxiv_html_base``
     - ``https://arxiv.org/html``
     - HTML rendering URL prefix
   * - ``arxiv_pdf_base``
     - ``https://arxiv.org/pdf``
     - PDF download URL prefix
   * - ``request_timeout``
     - ``30.0``
     - Seconds before an HTTP request times out
   * - ``max_fetch_chars``
     - ``10000``
     - Character limit for :ref:`arxiv_fetch_paper_text`

Extending Config
----------------

``Config`` is a frozen dataclass. To override defaults, instantiate it with
explicit values in a custom server entry point:

.. code-block:: python

   from arxiv_query_mcp.config import Config
   from arxiv_query_mcp import server

   # Increase timeout and fetch limit
   server.config = Config(request_timeout=60.0, max_fetch_chars=20_000)
