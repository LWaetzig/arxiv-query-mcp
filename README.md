# arxiv-query-mcp

An MCP (Model Context Protocol) server that gives AI assistants direct access to arXiv. Search papers, retrieve full metadata, browse categories, and read paper text.

## Table of Contents
1. [Features](#features)
2. [Installation](#installation)
3. [Usage](#usage)
4. [Contributing](#contributing)

## Features

- **Search arXiv** — Full query syntax support with title, author, abstract, and category filters
- **Get paper metadata** — Retrieve complete details for any paper by ID (abstract, authors, categories, DOI, links)
- **Browse by category** — List recent papers in specific subject areas (ML, AI, NLP, Computer Vision, etc.)
- **Read paper text** — Fetch HTML-rendered paper content or fallback to abstracts with links
- **Flexible formatting** — Response support for both markdown (human-readable) and JSON (programmatic)
- **Pagination** — Handle large result sets with configurable limits and offsets

## Installation

### Prerequisites

- `Python 3.11` or later
- Dependencies `mcp[cli]>=1.0.0`, `httpx>=0.27.0`, `pydantic>=2.0.0` (see [pyproject.toml](pyproject.toml)) (project uses `poetry` for dependency management)

### Install from PyPI

```bash
pip install arxiv-query-mcp
```

### Build from Source

```bash
git clone https://github.com/LWaetzig/google-scholar-mcp.git
cd google-scholar-mcp
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
      "command": "python",
      "args": ["-m", "arxiv-query-mcp"]
    }
  }
}
```

Restart Claude Desktop. You should see the arxiv tools available in the tool picker.

### Integration with Other MCP Clients

Any MCP client (e.g., Cline, Continue, or custom tools) can use this server. Configure the connection to:

```
Command: python -m arxiv-query-mcp.server
Transport: stdio
```

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