Quickstart
==========

Once the server is configured in your MCP client you can start querying arXiv immediately.
Below are example prompts and the tool calls they map to.

Search by Topic
---------------

Ask your assistant:

  *"Find the most relevant papers on diffusion models for image generation."*

The assistant calls :ref:`arxiv_search` with:

.. code-block:: json

   {
     "query": "abs:diffusion model AND abs:image generation",
     "max_results": 10,
     "sort_by": "relevance"
   }

----

Search by Author
----------------

  *"What has Yann LeCun published about self-supervised learning?"*

.. code-block:: json

   {
     "query": "au:lecun AND ti:self-supervised",
     "sort_by": "submittedDate",
     "sort_order": "descending"
   }

----

Look Up a Specific Paper
------------------------

  *"Get the full details for the Attention Is All You Need paper."*

The assistant calls :ref:`arxiv_get_paper` with:

.. code-block:: json

   {
     "paper_id": "1706.03762"
   }

----

Browse a Category
-----------------

  *"Show me the latest preprints in machine learning from the past few days."*

The assistant calls :ref:`arxiv_list_by_category` with:

.. code-block:: json

   {
     "category": "cs.LG",
     "max_results": 20,
     "sort_by": "submittedDate"
   }

Common category codes:

.. list-table::
   :header-rows: 1
   :widths: 15 40 15 30

   * - Code
     - Subject
     - Code
     - Subject
   * - ``cs.LG``
     - Machine Learning
     - ``cs.AI``
     - Artificial Intelligence
   * - ``cs.CL``
     - Computation & Language (NLP)
     - ``cs.CV``
     - Computer Vision
   * - ``cs.CR``
     - Cryptography & Security
     - ``cs.RO``
     - Robotics
   * - ``stat.ML``
     - Statistics — Machine Learning
     - ``math.CO``
     - Combinatorics
   * - ``physics.quant-ph``
     - Quantum Physics
     - ``q-bio.NC``
     - Neurons & Cognition

----

Read a Paper's Text
-------------------

  *"Read the introduction of the GPT-4 technical report."*

.. code-block:: json

   {
     "paper_id": "2303.08774"
   }

The tool fetches the HTML-rendered version of the paper (when available) and
returns up to 10,000 characters of extracted text.

----

Query Syntax Reference
-----------------------

The arXiv query language supports **field prefixes** and **boolean operators**:

.. list-table::
   :header-rows: 1
   :widths: 15 35 50

   * - Prefix
     - Searches
     - Example
   * - ``ti:``
     - Title
     - ``ti:transformer``
   * - ``au:``
     - Author
     - ``au:vaswani``
   * - ``abs:``
     - Abstract
     - ``abs:contrastive learning``
   * - ``cat:``
     - Category
     - ``cat:cs.LG``
   * - ``all:``
     - All fields
     - ``all:attention mechanism``

Combine terms with ``AND``, ``OR``, and ``ANDNOT``:

.. code-block:: text

   ti:large language model AND cat:cs.LG
   au:lecun AND (cat:cs.CV OR cat:cs.LG)
   abs:diffusion ANDNOT abs:audio
