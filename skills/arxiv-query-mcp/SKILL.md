---
name: arxiv-query-mcp
description: Search arXiv, look up papers by ID, browse subject categories, and read paper text through the arxiv-query-mcp server. Use when the user asks to find, cite, summarise, compare, or monitor academic papers or preprints, mentions an arXiv ID or URL, or needs recent research on a technical topic. Not for general web search, non-arXiv venues, or papers that are not on arXiv.
---

# arXiv research with arxiv-query-mcp

This skill covers four read-only tools from the `arxiv-query-mcp` server. They are
usually exposed by the client as `arxiv_search`, `arxiv_get_paper`,
`arxiv_list_by_category` and `arxiv_fetch_paper_text` (some clients prefix them,
e.g. `mcp__arxiv__arxiv_search`).

If none of these tools are available, tell the user the arXiv MCP server is not
connected instead of guessing paper details from memory.

## When to use it

Use it when the answer should come from the actual literature:

- "Find papers on X", "what's new in Y", "who has worked on Z"
- The user gives an arXiv ID, an `arxiv.org/abs|pdf|html/...` URL, or a paper
  title that is probably on arXiv
- Summarising, comparing or critiquing specific papers
- Building a reading list or related-work section
- Checking a claim, citation, author list or date

Do not use it for: general web questions, blog posts, documentation, papers
behind publishers that are not on arXiv, or citation counts and impact metrics
(arXiv does not provide them).

Never invent titles, authors, IDs or results. If a paper cannot be found, say so.

## Choosing a tool

| Goal | Tool |
|---|---|
| Discover papers by topic, title, author or keyword | `arxiv_search` |
| Get full metadata and the abstract of a known paper | `arxiv_get_paper` |
| See the newest preprints in a field | `arxiv_list_by_category` |
| Read the body of a paper (methods, results, details) | `arxiv_fetch_paper_text` |

Typical flow: **search → pick candidates → get_paper to confirm → fetch_paper_text
only for the papers you need to read in depth.** Abstracts are enough for most
screening; full text is long, so fetch it selectively.

## Calling the tools

Every tool takes a single object argument named `params`. Put all fields inside it:

```json
{ "params": { "query": "ti:attention AND cat:cs.LG", "max_results": 10 } }
```

### `arxiv_search`

| Field | Default | Notes |
|---|---|---|
| `query` | required | 1-500 chars, arXiv query syntax (below) |
| `max_results` | 10 | 1-50 |
| `start` | 0 | pagination offset |
| `sort_by` | `relevance` | `relevance`, `lastUpdatedDate`, `submittedDate` |
| `sort_order` | `descending` | or `ascending` |
| `response_format` | `markdown` | or `json` |

Query syntax: field prefixes `ti:` (title), `au:` (author), `abs:` (abstract),
`cat:` (category), `all:` (everything); combine with `AND`, `OR`, `ANDNOT` and
parentheses; quote exact phrases.

```
ti:"attention is all you need"
au:lecun AND (cat:cs.CV OR cat:cs.LG)
abs:diffusion ANDNOT abs:audio
```

### `arxiv_get_paper`

`paper_id` (required) plus optional `response_format`. Accepts `2303.08774`,
`2303.08774v2`, old-style `hep-th/9901001`, or a full arxiv.org URL.

### `arxiv_list_by_category`

`category` (required, e.g. `cs.LG`, `cs.CL`, `cs.CV`, `cs.AI`, `cs.CR`, `stat.ML`,
`math.CO`, `physics.quant-ph`), plus `max_results` (default 20), `start`,
`sort_by` (default `submittedDate`), `sort_order`, `response_format`. Use it to
monitor a field, not to answer a topical question; use `arxiv_search` for that.

### `arxiv_fetch_paper_text`

`paper_id` (required) plus optional `response_format`. Returns up to about 10,000
characters of the HTML version of the paper. When HTML is unavailable it falls
back to the abstract and links, and the response says so. A truncation notice
includes the full HTML URL; point the user there rather than retrying.

## Search strategy

- Start specific, then broaden. A narrow query with `ti:` or `au:` plus `cat:`
  beats a long free-text query.
- Add `cat:` when a term is ambiguous (e.g. "transformer", "agent").
- For "latest" or "recent", sort by `submittedDate` descending. For "best
  match", keep `relevance`.
- For a known paper, search the title as a quoted phrase, then confirm with
  `arxiv_get_paper`.
- Run a few differently worded queries (synonyms, acronyms) before concluding
  that nothing exists.
- Use `response_format: "json"` when you need to process results (dedupe,
  filter by date, extract IDs). Use `markdown` when showing results to the user.

## Pagination

Results are paged. With `json`, the response contains `total`, `count`, `start`,
`has_more` and `next_start`; call again with `start = next_start` for the next
page. Stop when you have enough: do not page through hundreds of results unless
the user asked for an exhaustive survey. Keep `max_results` modest (10-20) to
save context.

## Presenting results

- Cite as **title, authors, arXiv ID, and date**, and link the abstract page
  (`https://arxiv.org/abs/<id>`).
- State which version you read if it matters (`v1` vs `v2`), since content can
  change between versions.
- Distinguish what the abstract says from what you read in the full text.
- Mention that arXiv papers are preprints and may not be peer reviewed when the
  distinction matters to the user's decision.
- When summarising several papers, give each one line of substance (problem,
  method, key result) rather than repeating the abstract.

## Errors and limits

Tools return text starting with `Error:` instead of raising.

| Message | What to do |
|---|---|
| `Invalid query syntax` | Fix the query: check prefixes, quotes, parentheses |
| `Rate limit exceeded` | The server already retries with back-off. Wait, then try once more; do not loop |
| `timed out` | Retry once; if it persists, tell the user arXiv is slow |
| `Paper '<id>' not found` | Re-check the ID with `arxiv_search`; do not guess |
| `HTTP 5xx` | arXiv is having problems; report it and stop |

The server caches results and spaces requests (about one every 3 seconds), so
repeating an identical call is cheap, but firing many different calls in
parallel is slow. Plan queries instead of scattering them, and avoid
re-fetching papers you have already read in this conversation.
