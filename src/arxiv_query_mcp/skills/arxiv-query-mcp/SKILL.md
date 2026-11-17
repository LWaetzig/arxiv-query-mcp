---
name: arxiv-query-mcp
description: Search arXiv, look up papers by ID, browse subject categories, read paper text, and find similar, cited and citing papers through the arxiv-query-mcp server. Use when the user asks to find, cite, summarise, compare, or monitor academic papers or preprints, asks what a paper builds on or who cites it, mentions an arXiv ID or URL, or needs recent research on a technical topic. Not for general web search, non-arXiv venues, or papers that are not on arXiv.
---

# arXiv research with arxiv-query-mcp

This skill covers five read-only tools from the `arxiv-query-mcp` server. They are
usually exposed by the client as `arxiv_search`, `arxiv_get_paper`,
`arxiv_list_by_category`, `arxiv_fetch_paper_text` and `arxiv_related_papers`
(some clients prefix them,
e.g. `mcp__arxiv__arxiv_search`).

If none of these tools are available, tell the user the arXiv MCP server is not
connected instead of guessing paper details from memory.

## When to use it

Use it when the answer should come from the actual literature:

- "Find papers on X", "what's new in Y", "who has worked on Z"
- The user gives an arXiv ID, an `arxiv.org/abs|pdf|html/...` URL, or a paper
  title that is probably on arXiv
- Summarising, comparing or critiquing specific papers
- Building a reading list or related-work section, or tracing what a paper
  builds on and who followed up on it
- Checking a claim, citation, author list or date

Do not use it for: general web questions, blog posts, documentation, papers
or searching for papers that are not on arXiv (`arxiv_related_papers` can
surface them, but only starting from an arXiv paper).

Never invent titles, authors, IDs or results. If a paper cannot be found, say so.

## Choosing a tool

| Goal | Tool |
|---|---|
| Discover papers by topic, title, author or keyword | `arxiv_search` |
| Get full metadata and the abstract of a known paper | `arxiv_get_paper` |
| See the newest preprints in a field | `arxiv_list_by_category` |
| Read the body of a paper (methods, results, details) | `arxiv_fetch_paper_text` |
| Similar papers, a paper's references, or papers citing it | `arxiv_related_papers` |

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
| `date_from` / `date_to` | none | `YYYY-MM-DD`, inclusive submission-date bounds; either can be used alone |
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
`2303.08774v2`, old-style `hep-th/9901001`, or a full arxiv.org URL. With a
version suffix it returns that version; without one, the latest. The result
reports which `version` it describes.

### `arxiv_list_by_category`

`category` (required, e.g. `cs.LG`, `cs.CL`, `cs.CV`, `cs.AI`, `cs.CR`, `stat.ML`,
`math.CO`, `physics.quant-ph`), plus `max_results` (default 20), `start`,
`sort_by` (default `submittedDate`), `sort_order`, `date_from`, `date_to`,
`response_format`. Use it to
monitor a field, not to answer a topical question; use `arxiv_search` for that.

### `arxiv_fetch_paper_text`

`paper_id` (required) plus optional `offset` and `response_format`. Returns one
page of the paper's text (about 10,000 characters) and states which character
range it covers. When more text remains, the response gives the next `offset`;
call again with that value to continue, and repeat until no further offset is
reported. Read only as far as the question requires.

The text comes from the HTML version when there is one (headings as `#`,
formulas as `$LaTeX$`). Otherwise it is extracted from the PDF, and the response
says so: treat formulas, tables and reading order in PDF text with caution. If
neither works, the tool returns the abstract and links and says so. A version
suffix on the ID (`2303.08774v1`) reads that version instead of the latest.

### `arxiv_related_papers`

`paper_id` (required), `relation` (`similar` default, `references`, `cited_by`),
`max_results` (default 10), `start` (references and cited_by only),
`response_format`. Data comes from Semantic Scholar, not arXiv: results include
citation counts and can include papers that are not on arXiv (no `arxiv_id`;
the other arXiv tools cannot open those). Use it to expand from a paper you
already trust instead of guessing new search terms: `references` for background,
`cited_by` for follow-up work, `similar` for neighbours. Very new preprints may
not be indexed yet; then fall back to `arxiv_search`.

## Search strategy

- Start specific, then broaden. A narrow query with `ti:` or `au:` plus `cat:`
  beats a long free-text query.
- Add `cat:` when a term is ambiguous (e.g. "transformer", "agent").
- For a time window ("this month", "since 2025", "before 2020"), set `date_from`
  and/or `date_to` instead of paging through sorted results.
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

Failures come back as tool errors (`isError`) with one of these messages. An
empty search is not an error: it returns `No papers found ...` as normal text.

| Message | What to do |
|---|---|
| `Invalid query syntax` | Fix the query: check prefixes, quotes, parentheses |
| `Rate limit exceeded` | The server already retries with back-off. Wait, then try once more; do not loop |
| `timed out` | Retry once; if it persists, tell the user arXiv is slow |
| `Paper '<id>' not found` | Re-check the ID with `arxiv_search`; do not guess |
| `HTTP 5xx` | arXiv is having problems; report it and stop |
| `Semantic Scholar has no record` | The paper is too new or not indexed; use `arxiv_search` instead |
| `Semantic Scholar rate limit` | Wait before retrying; suggest the user set `ARXIV_MCP_S2_API_KEY` |

The server caches results and spaces requests (about one every 3 seconds), so
repeating an identical call is cheap, but firing many different calls in
parallel is slow. Plan queries instead of scattering them, and avoid
re-fetching papers you have already read in this conversation.
