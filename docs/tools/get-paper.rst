.. _arxiv_get_paper:

arxiv_get_paper
===============

Retrieve complete metadata for a specific arXiv paper by its ID.

Returns all available information: title, full author list, abstract, all
categories, publication and update dates, journal reference, DOI, and direct
links to the abstract page, PDF, and HTML-rendered version.

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
     - arXiv paper ID. Accepts bare IDs (``2303.08774``), versioned IDs
       (``2303.08774v2``), old-style IDs (``hep-th/9901001``), and full
       arXiv URLs. Version suffixes are stripped automatically.
   * - ``response_format``
     - ``str``
     - ``markdown``
     - Output format: ``markdown`` · ``json``

Paper ID Formats
----------------

The tool accepts all common arXiv ID variants:

.. list-table::
   :header-rows: 1

   * - Format
     - Example
   * - Bare numeric ID
     - ``2303.08774``
   * - Versioned ID
     - ``2303.08774v2``
   * - Old-style category/ID
     - ``hep-th/9901001``
   * - Full abstract URL
     - ``https://arxiv.org/abs/2303.08774``

Examples
--------

.. code-block:: json

   { "paper_id": "1706.03762" }

.. code-block:: json

   { "paper_id": "2303.08774", "response_format": "json" }

.. code-block:: json

   { "paper_id": "2108.10991" }

Well-Known Papers
-----------------

.. list-table::
   :header-rows: 1

   * - Paper
     - ID
   * - Attention Is All You Need
     - ``1706.03762``
   * - GPT-4 Technical Report
     - ``2303.08774``
   * - AlphaFold 2
     - ``2108.10991``
   * - BERT
     - ``1810.04805``
   * - Stable Diffusion
     - ``2112.10752``

JSON Response Schema
--------------------

When ``response_format`` is ``"json"``:

.. code-block:: json

   {
     "id": "1706.03762",
     "title": "Attention Is All You Need",
     "authors": ["Ashish Vaswani", "Noam Shazeer", "..."],
     "abstract": "The dominant sequence transduction models ...",
     "published": "2017-06-12T00:00:00Z",
     "updated": "2023-08-02T00:00:00Z",
     "primary_category": "cs.CL",
     "categories": ["cs.CL", "cs.LG"],
     "abstract_url": "https://arxiv.org/abs/1706.03762",
     "pdf_url": "https://arxiv.org/pdf/1706.03762",
     "html_url": "https://arxiv.org/html/1706.03762",
     "comment": "15 pages, 5 figures",
     "journal_ref": "Advances in Neural Information Processing Systems 30",
     "doi": ""
   }
