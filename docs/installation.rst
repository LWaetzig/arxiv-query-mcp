Installation
============

Prerequisites
-------------

- **Python 3.12** or later
- An MCP-compatible client (Claude Desktop, Cline, Continue, or any custom client)

Install from PyPI
-----------------

.. code-block:: bash

   pip install arxiv-query-mcp

Install with Poetry (recommended)
----------------------------------

.. code-block:: bash

   poetry add arxiv-query-mcp

Build from Source
-----------------

.. code-block:: bash

   git clone https://github.com/LWaetzig/arxiv-mcp.git
   cd arxiv-mcp
   pip install -e .

----

MCP Client Setup
----------------

Claude Desktop
~~~~~~~~~~~~~~

Add the server entry to your Claude Desktop configuration file:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Platform
     - Path
   * - macOS
     - ``~/Library/Application Support/Claude/claude_desktop_config.json``
   * - Windows
     - ``%APPDATA%\Claude\claude_desktop_config.json``

.. code-block:: json

   {
     "mcpServers": {
       "arxiv": {
         "command": "python",
         "args": ["-m", "arxiv_query_mcp.server"]
       }
     }
   }

Restart Claude Desktop. The arXiv tools appear in the tool picker automatically.

.. note::

   If you installed with Poetry, use ``"command": "poetry"`` and
   ``"args": ["run", "python", "-m", "arxiv_query_mcp.server"]`` instead.

Other MCP Clients
~~~~~~~~~~~~~~~~~

Any MCP client that supports stdio transport can connect to this server:

.. code-block:: text

   Command:   python -m arxiv_query_mcp.server
   Transport: stdio

----

Building the Docs
-----------------

.. code-block:: bash

   pip install "arxiv-query-mcp[docs]"
   # or: poetry install --with docs
   cd docs
   make html
   open _build/html/index.html
