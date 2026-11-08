Installation
============

Prerequisites
-------------

- **Python 3.12** or later
- The MCP Python SDK **2.3** or later (installed automatically as ``mcp[cli]>=2.3.0``)
- An MCP-compatible client (Claude Desktop, Cline, Continue, or any custom client)

Install from PyPI
-----------------

.. code-block:: bash

   pip install arxiv-query-mcp

.. note::

   Version 2.0 moved to the MCP Python SDK 2.x, where ``FastMCP`` became
   ``MCPServer``. The tool names and parameters are unchanged. Environments
   that pin ``mcp<2`` must be upgraded.

Install with Poetry (recommended)
----------------------------------

.. code-block:: bash

   poetry add arxiv-query-mcp

Build from Source
-----------------

.. code-block:: bash

   git clone https://github.com/LWaetzig/arxiv-query-mcp.git
   cd arxiv-query-mcp
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
         "command": "arxiv-query-mcp"
       }
     }
   }

Restart Claude Desktop. The arXiv tools appear in the tool picker automatically.

.. note::

   If you installed with Poetry, use ``"command": "poetry"`` and
   ``"args": ["run", "arxiv-query-mcp"]`` instead. Settings such as the cache
   directory can be passed through an ``"env"`` block; see :doc:`configuration`.

Other MCP Clients
~~~~~~~~~~~~~~~~~

Any MCP client that supports stdio transport can connect to this server:

.. code-block:: text

   Command:   arxiv-query-mcp
   Transport: stdio

----

Building the Docs
-----------------

.. code-block:: bash

   pip install "arxiv-query-mcp[docs]"
   # or: poetry install --with docs
   sphinx-build -W -b html docs docs/_build/html
   open docs/_build/html/index.html
