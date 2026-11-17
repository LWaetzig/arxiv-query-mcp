from datetime import date
from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class Relation(str, Enum):
    """How the returned papers relate to the given paper."""

    SIMILAR = "similar"
    REFERENCES = "references"
    CITED_BY = "cited_by"


class ResponseFormat(str, Enum):
    """Output serialisation format returned by each tool."""

    MARKDOWN = "markdown"
    JSON = "json"


# MARK: Input Models

class _DateRangeMixin(BaseModel):
    """Optional submission-date range shared by the listing tools."""

    date_from: date | None = Field(
        default=None,
        description=(
            "Only papers submitted on or after this date (YYYY-MM-DD, UTC). "
            "Combine with date_to for a range."
        ),
    )
    date_to: date | None = Field(
        default=None,
        description="Only papers submitted on or before this date (YYYY-MM-DD, UTC).",
    )

    @model_validator(mode="after")
    def date_range_ordered(self) -> Self:
        """Reject ranges whose start lies after their end."""
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be later than date_to")
        return self


class SearchInput(_DateRangeMixin):
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
            "To restrict by submission date use date_from / date_to. "
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
        description=(
            "arXiv paper ID or URL, e.g. '2303.08774', 'hep-th/9901001' or "
            "'2303.08774v2'. A version suffix selects that version; without "
            "one the latest version is returned."
        ),
        min_length=5,
        max_length=40,
    )
    response_format: ResponseFormat | None = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: markdown | json"
    )


class ListByCategoryInput(_DateRangeMixin):
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
        description=(
            "arXiv paper ID, e.g. '2303.08774'. Add a version suffix "
            "('2303.08774v1') to read that version instead of the latest. "
            "Use arxiv_get_paper first to confirm the ID."
        ),
        min_length=5,
        max_length=40,
    )
    offset: int = Field(
        default=0,
        description=(
            "Character offset to start reading from (0-based). Pass the "
            "next_offset reported by the previous call to read the next part."
        ),
        ge=0,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: markdown | json"
    )


class RelatedPapersInput(BaseModel):
    """Input parameters for the arxiv_related_papers tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra="forbid"
    )

    paper_id: str = Field(
        ...,
        description=(
            "arXiv paper ID or URL, e.g. '1706.03762'. A version suffix is "
            "ignored: relations are tracked per paper, not per version."
        ),
        min_length=5,
        max_length=40,
    )
    relation: Relation = Field(
        default=Relation.SIMILAR,
        description=(
            "similar: papers on the same topic (recommendations); "
            "references: papers this one cites; "
            "cited_by: papers that cite this one."
        ),
    )
    max_results: int = Field(
        default=10, description="Results per page (1–50)", ge=1, le=50
    )
    start: int = Field(
        default=0,
        description=(
            "Pagination offset for references and cited_by. Recommendations "
            "are a single list, so 'similar' only supports start=0."
        ),
        ge=0,
        le=9_000,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: markdown | json"
    )

    @model_validator(mode="after")
    def similar_has_no_pages(self) -> Self:
        """Reject an offset for recommendations, which cannot be paged."""
        if self.relation == Relation.SIMILAR and self.start:
            raise ValueError(
                "relation 'similar' does not support start; raise max_results instead"
            )
        return self
