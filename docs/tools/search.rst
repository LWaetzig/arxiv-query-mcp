.. _arxiv_search:

arxiv_search
============

Search arXiv for academic papers using the full arXiv query syntax.

Returns a paginated list of matching papers with title, authors, abstract
snippet, primary category, and direct links to the abstract, PDF, and
HTML-rendered page.

Parameters
----------

.. list-table::
   :header-rows: 1
   :widths: 20 12 12 56

   * - Parameter
     - Type
     - Default
     - Description
   * - ``query``
     - ``str``
     - *(required)*
     - arXiv query string. Supports field prefixes (``ti:``, ``au:``, ``abs:``,
       ``cat:``, ``all:``) and boolean operators (``AND``, ``OR``, ``ANDNOT``).
       Max 500 characters.
   * - ``max_results``
     - ``int``
     - ``10``
     - Number of results to return. Range: 1 – 50.
   * - ``start``
     - ``int``
     - ``0``
     - Zero-based pagination offset.
   * - ``sort_by``
     - ``str``
     - ``relevance``
     - Sort criterion: ``relevance`` · ``lastUpdatedDate`` · ``submittedDate``
   * - ``sort_order``
     - ``str``
     - ``descending``
     - Sort direction: ``descending`` · ``ascending``
   * - ``response_format``
     - ``str``
     - ``markdown``
     - Output format: ``markdown`` · ``json``

Query Syntax
------------

Field prefixes narrow the search to a specific metadata field:

.. code-block:: text

   ti:attention            ← title contains "attention"
   au:vaswani              ← author surname "vaswani"
   abs:contrastive         ← abstract contains "contrastive"
   cat:cs.LG               ← papers in the cs.LG category
   all:vision transformer  ← any field

Combine with boolean operators:

.. code-block:: text

   ti:transformer AND cat:cs.LG
   au:lecun AND (cat:cs.CV OR cat:cs.LG)
   abs:diffusion ANDNOT abs:audio

Examples
--------

**Keyword search:**

.. code-block:: json

   {
     "query": "ti:large language model AND cat:cs.LG",
     "max_results": 10,
     "sort_by": "submittedDate"
   }

**Author search:**

.. code-block:: json

   {
     "query": "au:lecun AND cat:cs.CV",
     "sort_by": "submittedDate",
     "sort_order": "descending"
   }

**Paginating results:**

.. code-block:: json

   { "query": "abs:diffusion model", "max_results": 10, "start": 10 }

JSON Response Schema
--------------------

When ``response_format`` is ``"json"``:

.. code-block:: json

   {
     "total": 1234,
     "count": 10,
     "start": 0,
     "has_more": true,
     "next_start": 10,
     "papers": [
       {
         "id": "2303.08774",
         "title": "GPT-4 Technical Report",
         "authors": ["OpenAI"],
         "abstract": "...",
         "published": "2023-03-15T00:00:00Z",
         "updated": "2024-03-04T00:00:00Z",
         "primary_category": "cs.CL",
         "categories": ["cs.CL", "cs.AI"],
         "abstract_url": "https://arxiv.org/abs/2303.08774",
         "pdf_url": "https://arxiv.org/pdf/2303.08774",
         "html_url": "https://arxiv.org/html/2303.08774",
         "comment": "",
         "journal_ref": "",
         "doi": ""
       }
     ]
   }
