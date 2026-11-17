Tool Reference
==============

The server exposes five read-only MCP tools. All tools are idempotent and safe
— they only issue ``GET`` requests to the arXiv API (and, for
:ref:`arxiv_related_papers`, to Semantic Scholar).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tool
     - Purpose
   * - :ref:`arxiv_search`
     - Full-text search with field prefixes, booleans, sorting, and pagination
   * - :ref:`arxiv_get_paper`
     - Retrieve all metadata for a single paper by arXiv ID
   * - :ref:`arxiv_list_by_category`
     - Browse the most recent papers in a given subject category
   * - :ref:`arxiv_fetch_paper_text`
     - Read a paper's full text page by page, from its HTML version or PDF
   * - :ref:`arxiv_related_papers`
     - Find similar papers, a paper's references, or the papers citing it

.. toctree::
   :hidden:

   search
   get-paper
   list-by-category
   fetch-text
   related-papers

----

Common Parameters
-----------------

``response_format``
~~~~~~~~~~~~~~~~~~~

All search and retrieval tools support ``response_format``:

.. list-table::
   :header-rows: 1

   * - Value
     - Description
   * - ``markdown`` *(default)*
     - Human-readable Markdown — suited for direct display in a chat interface
   * - ``json``
     - Structured JSON — suited for programmatic processing

``sort_by`` / ``sort_order``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Parameter
     - Options
   * - ``sort_by``
     - ``relevance`` · ``lastUpdatedDate`` · ``submittedDate``
   * - ``sort_order``
     - ``descending`` *(default)* · ``ascending``
