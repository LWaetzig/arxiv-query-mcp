.. _arxiv_related_papers:

arxiv_related_papers
====================

Find papers related to a known arXiv paper: papers on the same topic, the
papers it cites, or the papers that cite it.

arXiv has no citation or similarity data, so this tool queries the
`Semantic Scholar API <https://www.semanticscholar.org/product/api>`_, which
indexes arXiv papers by their arXiv ID.

.. note::

   Results can include papers that are not on arXiv. They have no ``arxiv_id``
   and link to Semantic Scholar instead. Very new preprints can take a few days
   to appear in Semantic Scholar.

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
     - arXiv paper ID or URL, e.g. ``1706.03762``. A version suffix is ignored,
       since relations are tracked per paper.
   * - ``relation``
     - ``str``
     - ``similar``
     - ``similar`` (recommendations on the same topic) · ``references``
       (papers this one cites) · ``cited_by`` (papers citing this one)
   * - ``max_results``
     - ``int``
     - ``10``
     - Number of results to return. Range: 1 – 50.
   * - ``start``
     - ``int``
     - ``0``
     - Pagination offset for ``references`` and ``cited_by``. Recommendations
       are a single list, so ``similar`` only accepts ``0``.
   * - ``response_format``
     - ``str``
     - ``markdown``
     - Output format: ``markdown`` · ``json``

Return Values
-------------

Each paper carries its title, authors, year, citation count, venue, a link (the
arXiv abstract page when the paper is on arXiv) and an abstract snippet. With
``response_format`` set to ``json``:

.. code-block:: json

   {
     "paper_id": "1706.03762",
     "relation": "similar",
     "source": "semantic_scholar",
     "start": 0,
     "count": 10,
     "has_more": false,
     "next_start": null,
     "papers": [
       {
         "title": "Transformer++",
         "authors": ["Prakhar Thapak", "Prodip Hore"],
         "year": 2020,
         "published": "2020-03-11",
         "arxiv_id": "2003.04974",
         "doi": "",
         "venue": "arXiv.org",
         "citation_count": 0,
         "url": "https://arxiv.org/abs/2003.04974",
         "abstract": "..."
       }
     ]
   }

Examples
--------

**Papers similar to Attention Is All You Need:**

.. code-block:: json

   { "paper_id": "1706.03762" }

**What the Adam paper builds on:**

.. code-block:: json

   { "paper_id": "1412.6980", "relation": "references" }

**The second page of papers citing DeepSeekMath:**

.. code-block:: json

   { "paper_id": "2402.03300", "relation": "cited_by", "max_results": 20, "start": 20 }

Rate Limits
-----------

Without an API key, requests share Semantic Scholar's public quota and are
throttled more often. Request a free key from Semantic Scholar and set
``ARXIV_MCP_S2_API_KEY`` to give the server its own quota. Requests are spaced
by ``ARXIV_MCP_S2_RATE_LIMIT_PERIOD`` (default one second), independently of the
arXiv spacing, and results are cached like arXiv results (see
:doc:`../caching`).
