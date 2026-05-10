arxiv-query-mcp
===============

An MCP (Model Context Protocol) server that gives AI assistants direct access to `arXiv <https://arxiv.org>`_.
Search papers, retrieve full metadata, browse subject categories, and read paper text — all from any MCP-compatible client.

.. code-block:: json

   {
     "mcpServers": {
       "arxiv": {
         "command": "python",
         "args": ["-m", "arxiv_query_mcp.server"]
       }
     }
   }

----

.. rubric:: Available Tools

+---------------------------------+-------------------------------------------------------------+
| Tool                            | What it does                                                |
+=================================+=============================================================+
| :ref:`arxiv_search`             | Full-text search with field prefixes and boolean operators  |
+---------------------------------+-------------------------------------------------------------+
| :ref:`arxiv_get_paper`          | Retrieve complete metadata for a paper by arXiv ID          |
+---------------------------------+-------------------------------------------------------------+
| :ref:`arxiv_list_by_category`   | Browse recent preprints in a subject category               |
+---------------------------------+-------------------------------------------------------------+
| :ref:`arxiv_fetch_paper_text`   | Extract readable text from a paper's HTML page              |
+---------------------------------+-------------------------------------------------------------+

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: Tool Reference

   tools/index

.. toctree::
   :maxdepth: 1
   :caption: Configuration

   configuration

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/index
