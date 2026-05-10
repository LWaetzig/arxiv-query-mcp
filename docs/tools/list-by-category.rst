.. _arxiv_list_by_category:

arxiv_list_by_category
======================

List recent papers in a specific arXiv subject category.

Retrieves papers filtered to one category, sorted by submission date by default.
Useful for monitoring a research area's latest preprints or surveying the current
state of a field.

Parameters
----------

.. list-table::
   :header-rows: 1
   :widths: 20 12 15 53

   * - Parameter
     - Type
     - Default
     - Description
   * - ``category``
     - ``str``
     - *(required)*
     - arXiv category code, e.g. ``cs.LG``, ``math.CO``, ``physics.quant-ph``.
       Min 2, max 30 characters.
   * - ``max_results``
     - ``int``
     - ``20``
     - Number of papers to return. Range: 1 – 50.
   * - ``start``
     - ``int``
     - ``0``
     - Zero-based pagination offset.
   * - ``sort_by``
     - ``str``
     - ``submittedDate``
     - Sort criterion: ``relevance`` · ``lastUpdatedDate`` · ``submittedDate``
   * - ``sort_order``
     - ``str``
     - ``descending``
     - Sort direction: ``descending`` · ``ascending``
   * - ``response_format``
     - ``str``
     - ``markdown``
     - Output format: ``markdown`` · ``json``

Category Codes
--------------

Computer Science
~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Code
     - Subject area
   * - ``cs.LG``
     - Machine Learning
   * - ``cs.AI``
     - Artificial Intelligence
   * - ``cs.CL``
     - Computation and Language (NLP)
   * - ``cs.CV``
     - Computer Vision and Pattern Recognition
   * - ``cs.CR``
     - Cryptography and Security
   * - ``cs.RO``
     - Robotics
   * - ``cs.NE``
     - Neural and Evolutionary Computing

Mathematics & Statistics
~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Code
     - Subject area
   * - ``math.CO``
     - Combinatorics
   * - ``math.ST``
     - Statistics Theory
   * - ``stat.ML``
     - Machine Learning (Statistics)

Other Disciplines
~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Code
     - Subject area
   * - ``physics.quant-ph``
     - Quantum Physics
   * - ``q-bio.NC``
     - Neurons and Cognition
   * - ``econ.GN``
     - General Economics

A full list of arXiv subject categories is available at
`arxiv.org/category_taxonomy <https://arxiv.org/category_taxonomy>`_.

Examples
--------

**Latest ML preprints:**

.. code-block:: json

   {
     "category": "cs.LG",
     "max_results": 20,
     "sort_by": "submittedDate"
   }

**Oldest NLP papers first:**

.. code-block:: json

   {
     "category": "cs.CL",
     "sort_by": "submittedDate",
     "sort_order": "ascending"
   }

**Paginating through Computer Vision results:**

.. code-block:: json

   { "category": "cs.CV", "max_results": 20, "start": 20 }
