# arxiv-query-mcp

An MCP (Model Context Protocol) server that gives AI assistants direct access to arXiv. Search papers, retrieve full metadata, browse categories, and read paper text.

## Table of Contents
1. [Features](#features)
2. [Installation](#installation)
3. [Usage](#usage)
4. [Configuration](#configuration)
5. [Contributing](#contributing)

## Features

- **Search arXiv** — Full query syntax support with title, author, abstract, and category filters
- **Get paper metadata** — Retrieve complete details for any paper by ID (abstract, authors, categories, DOI, links)
- **Browse by category** — List recent papers in specific subject areas (ML, AI, NLP, Computer Vision, etc.)
- **Read paper text** — Fetch HTML-rendered paper content or fallback to abstracts with links
- **Flexible formatting** — Response support for both markdown (human-readable) and JSON (programmatic)
- **Pagination** — Handle large result sets with configurable limits and offsets
- **Caching** — Two-tier cache (in-memory plus on-disk) so repeated queries and paper texts are served without hitting arXiv
- **Polite to arXiv** — Cross-process request spacing, a concurrency cap, and automatic retries with back-off on `429`/`5xx` responses

## Installation

### Prerequisites

- `Python 3.12` or later
- Dependencies `mcp[cli]>=2.3.0`, `httpx>=0.27.0`, `pydantic>=2.0.0`, `tenacity>=9.0`, `diskcache>=5.6`, `platformdirs>=4.0` (see [pyproject.toml](pyproject.toml)) (project uses `poetry` for dependency management)

> **Upgrading from 1.x:** the server now requires the MCP Python SDK 2.x (`FastMCP` was renamed to `MCPServer`). The tool names and parameters are unchanged; only environments that pin `mcp<2` need to upgrade.

### Install from PyPI

```bash
pip install arxiv-query-mcp
```

### Build from Source

```bash
git clone https://github.com/LWaetzig/arxiv-mcp.git
cd arxiv-mcp
pip install -e .
```

---

## Usage

- Detailed documentation about single tools can be found [here](https://personal-public-packages.gitlab.io/arxiv-query-mcp)

### Integration with Claude Desktop

Add the server to your Claude Desktop configuration:

| Platform | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

Add the `arxiv` entry under `mcpServers`, replacing the path with the absolute path to your clone:

```json
{
  "mcpServers": {
    "arxiv": {
      "command": "arxiv-query-mcp"
    }
  }
}
```

Restart Claude Desktop. You should see the arxiv tools available in the tool picker.

### Integration with Other MCP Clients

Any MCP client (e.g., Cline, Continue, or custom tools) can use this server. Configure the connection to:

```
Command: arxiv-query-mcp
Transport: stdio
```

## Configuration

The server works out of the box. Every setting can be overridden with an environment variable, which you can set in the `env` block of your MCP client configuration:

```json
{
  "mcpServers": {
    "arxiv": {
      "command": "arxiv-query-mcp",
      "env": { "ARXIV_MCP_L2_TTL": "86400" }
    }
  }
}
```

| Variable | Default | Description |
|---|---|---|
| `ARXIV_API_URL` | `https://export.arxiv.org/api/query` | arXiv Atom API endpoint |
| `ARXIV_MCP_REQUEST_TIMEOUT` | `30` | Seconds before an HTTP request times out |
| `ARXIV_MCP_MAX_FETCH_CHARS` | `10000` | Maximum characters returned by `arxiv_fetch_paper_text` |
| `ARXIV_MCP_USER_AGENT` | `arxiv-query-mcp/<version> (…)` | `User-Agent` header sent to arXiv |
| `ARXIV_MCP_CACHE_ENABLED` | `true` | Set to `false`, `0`, `no` or `off` to disable caching |
| `ARXIV_MCP_CACHE_DIR` | platform cache dir | Directory of the on-disk cache (shared between server processes) |
| `ARXIV_MCP_L1_TTL` | `300` | Seconds an entry stays in the in-memory cache |
| `ARXIV_MCP_L2_TTL` | `14400` | Seconds an entry stays in the on-disk cache |
| `ARXIV_MCP_NEGATIVE_TTL` | `60` | Seconds empty / not-found results are cached |
| `ARXIV_MCP_L1_MAXSIZE` | `256` | Maximum entries in the in-memory cache (LRU) |
| `ARXIV_MCP_RATE_LIMIT_ENABLED` | `true` | Set to `false` to disable request spacing |
| `ARXIV_MCP_RATE_LIMIT_PERIOD` | `3` | Minimum seconds between arXiv requests, across all server processes |
| `ARXIV_MCP_MAX_CONCURRENCY` | `2` | Maximum simultaneous in-flight requests per process |
| `ARXIV_MCP_MAX_RETRIES` | `4` | Attempts per request before giving up |
| `ARXIV_MCP_BACKOFF_BASE` | `1` | Initial retry back-off in seconds (doubles per attempt) |
| `ARXIV_MCP_BACKOFF_MAX` | `30` | Upper bound for a single retry wait, including `Retry-After` |

Invalid numeric values stop the server at startup with an error naming the variable.

### Agent skill

The repository ships an agent skill, [`skills/arxiv-query-mcp/SKILL.md`](skills/arxiv-query-mcp/SKILL.md), that explains when and how to use the tools (query syntax, search strategy, pagination, error handling). The server advertises its URL in the MCP server instructions, which clients show to the agent when it connects, so agents that support skills or can fetch URLs can pick it up automatically. Copy the file into your client's skills directory (e.g. `~/.claude/skills/arxiv-query-mcp/`) to install it permanently.

### How caching and rate limiting work

- Lookups check memory first, then disk, and only then call arXiv. Concurrent identical requests share a single fetch.
- Empty results use the shorter `ARXIV_MCP_NEGATIVE_TTL` so a transient miss doesn't stick around.
- Failed requests are never cached.
- Retries happen on timeouts, transport errors and `429`/`500`/`502`/`503`/`504`. A numeric `Retry-After` header is honoured (up to `ARXIV_MCP_BACKOFF_MAX`). Every attempt, including retries, respects the request spacing.
- arXiv asks clients to make at most one request every 3 seconds; lowering `ARXIV_MCP_RATE_LIMIT_PERIOD` below that is not recommended.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes with clear messages
4. Push to your fork
5. Open a pull request

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

## License

[See LICENSE file](LICENSE)