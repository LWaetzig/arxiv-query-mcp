from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, field_validator


# MARK: Enums

class SortBy(str, Enum):
    """Criterion used to order arXiv search results."""

    RELEVANCE = "relevance"
    LAST_UPDATED = "lastUpdatedDate"
    SUBMITTED = "submittedDate"


class SortOrder(str, Enum):
    """Direction of the sort applied to search results."""

    DESCENDING = "descending"
    ASCENDING = "ascending"


class ResponseFormat(str, Enum):
    """Output serialisation format returned by each tool."""

    MARKDOWN = "markdown"
    JSON = "json"


# MARK: Input Models

class SearchInput(BaseModel):
    """Input parameters for the arxiv_search tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra="forbid"
    )

    query: str = Field(
        ...,
        description=(
            "arXiv search query. Supports field prefixes: "
            "ti: (title), au: (author), abs: (abstract), cat: (category), all: (all fields). "
            "Combine with AND, OR, ANDNOT. "
            "Examples: 'ti:transformer AND cat:cs.LG', 'au:hinton', 'abs:diffusion model'"
        ),
        min_length=1,
        max_length=500,
    )
    max_results: int = Field(
        default=10, description="Results per page (1–50)", ge=1, le=50
    )
    start: int = Field(
        default=0, description="Pagination offset (0-based)", ge=0
    )
    sort_by: SortBy = Field(
        default=SortBy.RELEVANCE,
        description="Sort criterion: relevance | lastUpdatedDate | submittedDate",
    )
    sort_order: SortOrder = Field(
        default=SortOrder.DESCENDING,
        description="Sort direction: descending | ascending",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: markdown | json"
    )

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, v: str) -> str:
        """Reject queries that are blank after whitespace stripping."""
        if not v.strip():
            raise ValueError("query must not be blank")
        return v


class GetPaperInput(BaseModel):
    """Input parameters for the arxiv_get_paper tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra="forbid"
    )

    paper_id: str = Field(
        ...,
        description="arXiv paper ID, e.g. '2303.08774' or '2303.08774v2' or 'hep-th/9901001'",
        min_length=5,
        max_length=40,
    )
    response_format: ResponseFormat | None = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: markdown | json"
    )


class ListByCategoryInput(BaseModel):
    """Input parameters for the arxiv_list_by_category tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra="forbid"
    )

    category: str = Field(
        ...,
        description=(
            "arXiv category code, e.g. 'cs.LG' (ML), 'cs.AI', 'cs.CL' (NLP), "
            "'cs.CV' (vision), 'cs.CR' (security), 'math.CO', 'physics.quant-ph', 'stat.ML'"
        ),
        min_length=2,
        max_length=30,
    )
    max_results: int = Field(
        default=20, description="Results per page (1–50)", ge=1, le=50
    )
    start: int = Field(default=0, description="Pagination offset", ge=0)
    sort_by: SortBy = Field(
        default=SortBy.SUBMITTED,
        description="Sort criterion: relevance | lastUpdatedDate | submittedDate",
    )
    sort_order: SortOrder = Field(
        default=SortOrder.DESCENDING,
        description="Sort direction: descending | ascending",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: markdown | json"
    )


class FetchPaperTextInput(BaseModel):
    """Input parameters for the arxiv_fetch_paper_text tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra="forbid"
    )

    paper_id: str = Field(
        ...,
        description="arXiv paper ID, e.g. '2303.08774'. Use arxiv_get_paper first to confirm the ID.",
        min_length=5,
        max_length=40,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: markdown | json"
    )
