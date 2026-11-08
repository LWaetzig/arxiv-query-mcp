Caching and Rate Limiting
=========================

Every call to arXiv goes through a resilience layer that avoids repeated
requests and keeps the server within arXiv's usage guidelines. The behaviour is
tuned through the environment variables listed in :doc:`configuration`.

Two-tier cache
--------------

Results of the API tools and the extracted text of :ref:`arxiv_fetch_paper_text`
are stored in :class:`~arxiv_query_mcp.cache.TwoTierCache`:

1. **L1, in memory.** A size-limited least-recently-used cache with a short TTL
   (5 minutes by default). Private to the running process.
2. **L2, on disk.** A `diskcache <https://grantjenks.com/docs/diskcache/>`_
   (SQLite) store with a longer TTL (4 hours by default). It survives restarts
   and is shared by every server process that uses the same cache directory.

A lookup checks L1, then L2 (promoting hits to L1), and only then calls arXiv.

Concurrent requests for the same key are coalesced ("single flight"): one
request fetches, the others wait for its result. If the fetching request is
cancelled, a waiting request takes over instead of hanging. Failed requests
are never cached.

Empty results (no papers found, or no HTML version of a paper) use the shorter
negative TTL, 60 seconds by default, so a temporary miss does not stick.

Rate limiting
-------------

:class:`~arxiv_query_mcp.ratelimit.RateLimiter` spaces requests at least
``ARXIV_MCP_RATE_LIMIT_PERIOD`` seconds apart. The timestamp of the last request
lives in the shared disk cache behind a lock, so several server processes
(for example one per MCP client) coordinate instead of each sending requests at
full speed. At most ``ARXIV_MCP_MAX_CONCURRENCY`` requests are in flight per
process.

Retries
-------

:func:`~arxiv_query_mcp.ratelimit.resilient_get` retries a request when it:

- times out or fails at the transport level, or
- returns ``429``, ``500``, ``502``, ``503`` or ``504``.

Waits grow exponentially from ``ARXIV_MCP_BACKOFF_BASE`` with random jitter, up
to ``ARXIV_MCP_BACKOFF_MAX``. If the response carries a numeric ``Retry-After``
header, the wait is the larger of that value and the back-off interval, again
capped at ``ARXIV_MCP_BACKOFF_MAX``. Every attempt, including retries, passes
through the rate limiter. Other errors, such as ``404``, are returned
immediately. After ``ARXIV_MCP_MAX_RETRIES`` attempts the final error is
reported to the caller.

Turning it off
--------------

Set ``ARXIV_MCP_CACHE_ENABLED=false`` to bypass the cache and
``ARXIV_MCP_RATE_LIMIT_ENABLED=false`` to disable request spacing. Retries stay
active in both cases.
