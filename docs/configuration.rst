Configuration
=============

The server is configured through the :class:`~arxiv_query_mcp.config.Config`
dataclass. At startup it is built with :meth:`~arxiv_query_mcp.config.Config.from_env`,
so every setting has a sensible default and can be overridden with an
environment variable. No configuration files are required.

See the full class reference at :class:`arxiv_query_mcp.config.Config`.

----

Setting environment variables
-----------------------------

Set variables in the ``env`` block of your MCP client configuration:

.. code-block:: json

   {
     "mcpServers": {
       "arxiv": {
         "command": "arxiv-query-mcp",
         "env": {
           "ARXIV_MCP_CACHE_DIR": "/data/arxiv-cache",
           "ARXIV_MCP_L2_TTL": "86400"
         }
       }
     }
   }

Numeric values that cannot be parsed stop the server at startup with an error
that names the offending variable. Boolean switches are false for ``0``,
``false``, ``no`` and ``off`` (case-insensitive) and true for anything else.

----

Connection and output
---------------------

.. list-table::
   :header-rows: 1
   :widths: 28 22 50

   * - Environment variable
     - Default
     - Description
   * - ``ARXIV_API_URL``
     - ``https://export.arxiv.org/api/query``
     - Official arXiv Atom API endpoint
   * - ``ARXIV_MCP_REQUEST_TIMEOUT``
     - ``30``
     - Seconds before an HTTP request times out
   * - ``ARXIV_MCP_MAX_FETCH_CHARS``
     - ``10000``
     - Character limit for :ref:`arxiv_fetch_paper_text`
   * - ``ARXIV_MCP_USER_AGENT``
     - ``arxiv-query-mcp/<version> (…)``
     - ``User-Agent`` header sent with every request

.. list-table::
   :header-rows: 1
   :widths: 28 22 50

   * - Environment variable
     - Default
     - Description
   * - ``ARXIV_MCP_SKILL_URL``
     - GitHub raw URL of ``skills/arxiv-query-mcp/SKILL.md``
     - URL of the agent skill, advertised to clients in the server instructions
       (see :ref:`agent-skill`). Set to an empty string to disable the notice.

The URL prefixes ``arxiv_abs_base``, ``arxiv_html_base`` and ``arxiv_pdf_base``
(``https://arxiv.org/abs``, ``/html`` and ``/pdf``) are fixed defaults and have
no environment variable.

Caching
-------

.. list-table::
   :header-rows: 1
   :widths: 28 22 50

   * - Environment variable
     - Default
     - Description
   * - ``ARXIV_MCP_CACHE_ENABLED``
     - ``true``
     - Set to ``false`` to bypass the cache completely
   * - ``ARXIV_MCP_CACHE_DIR``
     - platform cache dir
     - Directory of the on-disk cache; empty means the user cache directory
       from ``platformdirs`` (falling back to the system temp directory)
   * - ``ARXIV_MCP_L1_TTL``
     - ``300``
     - Seconds an entry stays in the in-memory cache
   * - ``ARXIV_MCP_L2_TTL``
     - ``14400``
     - Seconds an entry stays in the on-disk cache (4 hours)
   * - ``ARXIV_MCP_NEGATIVE_TTL``
     - ``60``
     - Seconds empty or not-found results are cached
   * - ``ARXIV_MCP_L1_MAXSIZE``
     - ``256``
     - Maximum entries in the in-memory cache (least recently used evicted)

Rate limiting and retries
-------------------------

.. list-table::
   :header-rows: 1
   :widths: 28 22 50

   * - Environment variable
     - Default
     - Description
   * - ``ARXIV_MCP_RATE_LIMIT_ENABLED``
     - ``true``
     - Set to ``false`` to disable request spacing
   * - ``ARXIV_MCP_RATE_LIMIT_PERIOD``
     - ``3``
     - Minimum seconds between arXiv requests, shared by all server processes
       using the same cache directory
   * - ``ARXIV_MCP_MAX_CONCURRENCY``
     - ``2``
     - Maximum simultaneous requests per process
   * - ``ARXIV_MCP_MAX_RETRIES``
     - ``4``
     - Attempts per request before the error is returned
   * - ``ARXIV_MCP_BACKOFF_BASE``
     - ``1``
     - Initial retry back-off in seconds (doubles with each attempt)
   * - ``ARXIV_MCP_BACKOFF_MAX``
     - ``30``
     - Upper bound for a single retry wait, including ``Retry-After``

.. warning::

   arXiv asks API clients to make no more than one request every three
   seconds. Lowering ``ARXIV_MCP_RATE_LIMIT_PERIOD`` below the default risks
   being blocked.

----

.. _agent-skill:

Agent skill
-----------

The repository ships an agent skill, ``skills/arxiv-query-mcp/SKILL.md``, that
explains when and how to use the tools: query syntax, search strategy,
pagination, and error handling. The server advertises its URL in the MCP server
*instructions*, which clients show to the agent when it connects, for example:

.. code-block:: text

   Agent skill: a SKILL.md with guidance on when and how to use these tools is
   available at https://raw.githubusercontent.com/.../SKILL.md. If your client
   supports skills or can fetch URLs, read it before your first call.

Point ``ARXIV_MCP_SKILL_URL`` at your own copy to customise the guidance, or set
it to an empty string to remove the notice. To install the skill permanently,
copy the file into your client's skills directory.

Programmatic configuration
--------------------------

``Config`` is a frozen dataclass. To override defaults in code, instantiate it
with explicit values in a custom server entry point:

.. code-block:: python

   from arxiv_query_mcp.config import Config
   from arxiv_query_mcp import server

   # Increase timeout and fetch limit, keep everything else at the defaults
   server.config = Config(request_timeout=60.0, max_fetch_chars=20_000)

Assign ``server.config`` before the server starts, because the cache and rate
limiter are created from it in the server lifespan.
