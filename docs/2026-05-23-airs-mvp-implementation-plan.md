# AIRS MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working MVP of the AIRS overseas strategic intelligence platform with MCP tools, shared SQL/vector memory, lightweight collector mini-agent logic, analysis, prediction, briefing, and Feishu distribution.

**Architecture:** Implement a Python backend with focused modules for domain models, repository access, collection, retrieval, agents, MCP tools, API routes, and Feishu delivery. Use Supabase PostgreSQL with pgvector as the shared intelligence memory, while keeping tests fast through in-memory fakes.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, Supabase PostgreSQL, pgvector, OpenAI-compatible embeddings, MCP Python SDK, httpx, pytest, ruff, Streamlit, Feishu webhook.

---

## File Structure

Create this structure:

```text
pyproject.toml
.env.example
README.md
docs/2026-05-23-airs-strategic-intelligence-design.md
docs/superpowers/plans/2026-05-23-airs-mvp-implementation-plan.md
src/airs/__init__.py
src/airs/config.py
src/airs/domain.py
src/airs/db/schema.sql
src/airs/db/__init__.py
src/airs/db/repository.py
src/airs/embeddings.py
src/airs/retrieval.py
src/airs/collectors/__init__.py
src/airs/collectors/query_planner.py
src/airs/collectors/dedup.py
src/airs/collectors/web_search.py
src/airs/collectors/pipeline.py
src/airs/agents/__init__.py
src/airs/agents/analysis.py
src/airs/agents/prediction.py
src/airs/agents/briefing.py
src/airs/feishu.py
src/airs/mcp_server.py
src/airs/api.py
app/console.py
tests/conftest.py
tests/test_domain.py
tests/test_dedup.py
tests/test_query_planner.py
tests/test_repository_fake.py
tests/test_retrieval.py
tests/test_collector_pipeline.py
tests/test_analysis_agent.py
tests/test_prediction_agent.py
tests/test_briefing_agent.py
tests/test_feishu.py
tests/test_api.py
```

Responsibility boundaries:

- `domain.py`: Pydantic models and enums shared by all modules.
- `repository.py`: storage interface, Supabase implementation, and test fake.
- `embeddings.py`: embedding provider interface and deterministic test embedding.
- `retrieval.py`: metadata filtering, semantic search orchestration, context pack assembly, trend snapshots.
- `collectors/*`: lightweight collection pipeline only; no final strategic analysis.
- `agents/*`: deterministic MVP analysis, prediction, and briefing composition using stored evidence.
- `mcp_server.py`: MCP tool surface used by agents and external clients.
- `api.py`: FastAPI routes for local testing and internal console.
- `feishu.py`: Feishu webhook delivery and delivery metadata.
- `app/console.py`: simple Streamlit console for briefing review and source traceability.

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `README.md`
- Create: `src/airs/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the initial project files**

Create `pyproject.toml`:

```toml
[project]
name = "airs"
version = "0.1.0"
description = "AIRS overseas strategic intelligence platform MVP"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "pydantic>=2.8.0",
  "pydantic-settings>=2.4.0",
  "httpx>=0.27.0",
  "supabase>=2.6.0",
  "numpy>=1.26.0",
  "mcp>=1.2.0",
  "streamlit>=1.37.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.0",
  "pytest-asyncio>=0.23.0",
  "ruff>=0.5.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

Create `.env.example`:

```text
SUPABASE_URL=https://example.supabase.co
SUPABASE_SERVICE_ROLE_KEY=replace-with-service-role-key
OPENAI_API_KEY=replace-with-openai-compatible-key
OPENAI_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-3-small
WEB_SEARCH_PROVIDER=mock
WEB_SEARCH_API_KEY=replace-with-search-key
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/replace
```

Create `README.md`:

````markdown
# AIRS

AIRS is an MVP overseas strategic intelligence platform for Chow Tai Fook Jewellery Group.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
```

## Main services

- FastAPI app: `uvicorn airs.api:app --reload`
- MCP server: `python -m airs.mcp_server`
- Streamlit console: `streamlit run app/console.py`
````

Create `src/airs/__init__.py`:

```python
"""AIRS overseas strategic intelligence platform MVP."""
```

Create `tests/conftest.py`:

```python
import pytest

from airs.db.repository import InMemoryRepository
from airs.embeddings import DeterministicEmbeddingProvider


@pytest.fixture
def repository() -> InMemoryRepository:
    return InMemoryRepository()


@pytest.fixture
def embedder() -> DeterministicEmbeddingProvider:
    return DeterministicEmbeddingProvider(dimensions=8)
```

- [ ] **Step 2: Install dependencies**

Run:

```powershell
python -m pip install -e ".[dev]"
```

Expected: dependencies install without resolver errors.

- [ ] **Step 3: Run the empty test suite**

Run:

```powershell
pytest
```

Expected: pytest exits successfully with no collected tests or only import-free setup.

- [ ] **Step 4: Commit**

```powershell
git add pyproject.toml .env.example README.md src/airs/__init__.py tests/conftest.py
git commit -m "chore: scaffold AIRS project"
```

---

### Task 2: Domain Models

**Files:**
- Create: `src/airs/domain.py`
- Create: `tests/test_domain.py`

- [ ] **Step 1: Write failing tests for the shared domain schema**

Create `tests/test_domain.py`:

```python
from airs.domain import (
    AnalysisPayload,
    DocumentCreate,
    DocumentType,
    IntelFilters,
    Region,
    StrategicVertical,
    Topic,
)


def test_document_create_accepts_intel_card_metadata() -> None:
    document = DocumentCreate(
        doc_type=DocumentType.INTEL_CARD,
        title="Dubai gold jewellery demand rises",
        content="Retailers report stronger gold jewellery demand before Ramadan.",
        metadata={
            "region": Region.MIDDLE_EAST.value,
            "topic": Topic.PRODUCT.value,
            "strategic_vertical": StrategicVertical.GOLD_JEWELLERY.value,
            "importance_score": 0.82,
            "confidence_score": 0.76,
        },
        source_url="https://example.com/dubai-gold",
        created_by_agent="middle_east_collector",
    )

    assert document.doc_type == DocumentType.INTEL_CARD
    assert document.metadata["region"] == "middle_east"


def test_filters_serialize_to_metadata_filters() -> None:
    filters = IntelFilters(
        region=Region.MIDDLE_EAST,
        topic=Topic.SOCIAL,
        strategic_vertical=StrategicVertical.GOLD_JEWELLERY,
        min_importance_score=0.7,
    )

    assert filters.to_metadata_filter() == {
        "region": "middle_east",
        "topic": "social",
        "strategic_vertical": "gold_jewellery",
    }


def test_analysis_payload_requires_evidence() -> None:
    payload = AnalysisPayload(
        conclusion="Gold jewellery attention is rising in the Middle East.",
        impact_assessment="Likely positive for campaign timing and inventory planning.",
        risk_or_opportunity="opportunity",
        affected_region=Region.MIDDLE_EAST,
        affected_strategic_vertical=StrategicVertical.GOLD_JEWELLERY,
        recommended_actions=["Review Ramadan campaign timing."],
        confidence_score=0.72,
        evidence_sufficiency="partial",
        evidence_doc_ids=["doc_1", "doc_2"],
    )

    assert payload.evidence_doc_ids == ["doc_1", "doc_2"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_domain.py -v
```

Expected: FAIL because `airs.domain` does not exist.

- [ ] **Step 3: Implement domain models**

Create `src/airs/domain.py`:

```python
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class DocumentType(StrEnum):
    RAW_SOURCE = "raw_source"
    INTEL_CARD = "intel_card"
    ANALYSIS = "analysis"
    PREDICTION = "prediction"
    BRIEFING = "briefing"


class Region(StrEnum):
    ASIA_PACIFIC = "asia_pacific"
    MIDDLE_EAST = "middle_east"
    EUROPE = "europe"
    AMERICAS = "americas"
    EMERGING_MARKETS = "emerging_markets"


class StrategicVertical(StrEnum):
    GOLD_JEWELLERY = "gold_jewellery"
    JADE_COLORED_GEMS_CULTURAL = "jade_colored_gems_cultural_jewellery"
    OVERSEAS_RETAIL_CHANNELS = "overseas_retail_channels"


class Topic(StrEnum):
    COMPETITION = "competition"
    PRODUCT = "product"
    PLATFORM = "platform"
    SOCIAL = "social"
    REGULATION = "regulation"
    MACRO_GOLD = "macro_gold"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvidenceSufficiency(StrEnum):
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    INSUFFICIENT_NEEDS_RETRIEVAL = "insufficient_needs_retrieval"


class DocumentCreate(BaseModel):
    doc_type: DocumentType
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_url: HttpUrl | str | None = None
    created_by_agent: str
    embedding: list[float] | None = None


class Document(DocumentCreate):
    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class IntelFilters(BaseModel):
    region: Region | None = None
    topic: Topic | None = None
    strategic_vertical: StrategicVertical | None = None
    doc_type: DocumentType | None = None
    min_importance_score: float | None = None
    min_confidence_score: float | None = None
    since: datetime | None = None

    def to_metadata_filter(self) -> dict[str, str]:
        filters: dict[str, str] = {}
        if self.region:
            filters["region"] = self.region.value
        if self.topic:
            filters["topic"] = self.topic.value
        if self.strategic_vertical:
            filters["strategic_vertical"] = self.strategic_vertical.value
        return filters


class SearchResult(BaseModel):
    document: Document
    score: float


class CollectionRequest(BaseModel):
    region: Region
    topic: Topic
    strategic_vertical: StrategicVertical
    time_window: str = "7d"
    query_focus: str
    source_types: list[str] = Field(default_factory=lambda: ["news", "industry"])


class CollectionResult(BaseModel):
    request_id: str
    created_source_ids: list[str]
    created_card_ids: list[str]
    coverage: dict[str, Any]


class AnalysisPayload(BaseModel):
    conclusion: str
    impact_assessment: str
    risk_or_opportunity: Literal["risk", "opportunity", "watch"]
    affected_region: Region
    affected_strategic_vertical: StrategicVertical
    recommended_actions: list[str]
    confidence_score: float = Field(ge=0, le=1)
    evidence_sufficiency: EvidenceSufficiency | str
    evidence_doc_ids: list[str] = Field(min_length=1)


class PredictionPayload(BaseModel):
    prediction_type: str
    forecast_horizon: str
    prediction: str
    confidence_score: float = Field(ge=0, le=1)
    evidence_doc_ids: list[str] = Field(min_length=1)
    risk_factors: list[str]
    suggested_actions: list[str]


class BriefingPayload(BaseModel):
    audience_type: Literal["regional_leader", "strategic_vertical_leader", "hq_strategy"]
    audience_key: str
    title: str
    executive_summary: str
    sections: list[dict[str, Any]]
    evidence_doc_ids: list[str]
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
pytest tests/test_domain.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/airs/domain.py tests/test_domain.py
git commit -m "feat: add AIRS domain models"
```

---

### Task 3: Database Schema and Repository

**Files:**
- Create: `src/airs/db/__init__.py`
- Create: `src/airs/db/schema.sql`
- Create: `src/airs/db/repository.py`
- Create: `tests/test_repository_fake.py`

- [ ] **Step 1: Write failing repository tests**

Create `tests/test_repository_fake.py`:

```python
from airs.db.repository import InMemoryRepository
from airs.domain import DocumentCreate, DocumentType, IntelFilters, Region, Topic


def test_repository_creates_and_gets_document() -> None:
    repo = InMemoryRepository()
    created = repo.create_document(
        DocumentCreate(
            doc_type=DocumentType.RAW_SOURCE,
            title="Source",
            content="Source content",
            metadata={"region": "middle_east", "topic": "product"},
            source_url="https://example.com/source",
            created_by_agent="test",
        )
    )

    loaded = repo.get_document(created.id)

    assert loaded.id == created.id
    assert loaded.title == "Source"


def test_repository_search_filters_metadata() -> None:
    repo = InMemoryRepository()
    repo.create_document(
        DocumentCreate(
            doc_type=DocumentType.INTEL_CARD,
            title="Middle East social signal",
            content="Gold jewellery is trending in short videos.",
            metadata={"region": "middle_east", "topic": "social", "importance_score": 0.8},
            created_by_agent="test",
        )
    )
    repo.create_document(
        DocumentCreate(
            doc_type=DocumentType.INTEL_CARD,
            title="Europe product signal",
            content="Colored gems appear in new collections.",
            metadata={"region": "europe", "topic": "product", "importance_score": 0.9},
            created_by_agent="test",
        )
    )

    results = repo.search_documents(
        query="gold jewellery",
        filters=IntelFilters(region=Region.MIDDLE_EAST, topic=Topic.SOCIAL),
        top_k=10,
    )

    assert len(results) == 1
    assert results[0].document.title == "Middle East social signal"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_repository_fake.py -v
```

Expected: FAIL because repository module does not exist.

- [ ] **Step 3: Add SQL schema**

Create `src/airs/db/schema.sql`:

```sql
create extension if not exists vector;

create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  doc_type text not null,
  title text not null,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  embedding vector(1536),
  source_url text,
  created_by_agent text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists documents_doc_type_idx on documents (doc_type);
create index if not exists documents_metadata_gin_idx on documents using gin (metadata);
create index if not exists documents_embedding_idx on documents using ivfflat (embedding vector_cosine_ops);

create table if not exists tasks (
  id uuid primary key default gen_random_uuid(),
  task_type text not null,
  status text not null default 'pending',
  requested_by_agent text,
  assigned_agent text,
  input_payload jsonb not null default '{}'::jsonb,
  result_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists agent_runs (
  id uuid primary key default gen_random_uuid(),
  agent_name text not null,
  tool_name text not null,
  input_payload jsonb not null default '{}'::jsonb,
  output_payload jsonb not null default '{}'::jsonb,
  status text not null,
  error_message text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists briefing_references (
  id uuid primary key default gen_random_uuid(),
  briefing_doc_id uuid not null references documents(id),
  briefing_item_id text not null,
  referenced_doc_id uuid not null references documents(id),
  reference_type text not null,
  created_at timestamptz not null default now()
);
```

- [ ] **Step 4: Implement repository**

Create `src/airs/db/__init__.py`:

```python
"""Database access for AIRS."""
```

Create `src/airs/db/repository.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import uuid4

from airs.domain import Document, DocumentCreate, IntelFilters, SearchResult


class IntelligenceRepository(Protocol):
    def create_document(self, document: DocumentCreate) -> Document: ...
    def get_document(self, document_id: str) -> Document: ...
    def search_documents(
        self, query: str, filters: IntelFilters | None = None, top_k: int = 10
    ) -> list[SearchResult]: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}

    def create_document(self, document: DocumentCreate) -> Document:
        now = datetime.utcnow()
        created = Document(
            id=f"doc_{uuid4().hex}",
            doc_type=document.doc_type,
            title=document.title,
            content=document.content,
            metadata=document.metadata,
            embedding=document.embedding,
            source_url=document.source_url,
            created_by_agent=document.created_by_agent,
            created_at=now,
            updated_at=now,
        )
        self._documents[created.id] = created
        return created

    def get_document(self, document_id: str) -> Document:
        return self._documents[document_id]

    def search_documents(
        self, query: str, filters: IntelFilters | None = None, top_k: int = 10
    ) -> list[SearchResult]:
        query_terms = {term.lower() for term in query.split() if term.strip()}
        matches: list[SearchResult] = []
        for document in self._documents.values():
            if filters and not self._matches_filters(document, filters):
                continue
            haystack = f"{document.title} {document.content}".lower()
            score = sum(1 for term in query_terms if term in haystack)
            matches.append(SearchResult(document=document, score=float(score)))
        matches.sort(
            key=lambda result: (
                result.score,
                result.document.metadata.get("importance_score", 0),
                result.document.created_at,
            ),
            reverse=True,
        )
        return matches[:top_k]

    def _matches_filters(self, document: Document, filters: IntelFilters) -> bool:
        if filters.doc_type and document.doc_type != filters.doc_type:
            return False
        for key, value in filters.to_metadata_filter().items():
            if document.metadata.get(key) != value:
                return False
        if filters.min_importance_score is not None:
            if float(document.metadata.get("importance_score", 0)) < filters.min_importance_score:
                return False
        if filters.min_confidence_score is not None:
            if float(document.metadata.get("confidence_score", 0)) < filters.min_confidence_score:
                return False
        if filters.since and document.created_at < filters.since:
            return False
        return True
```

- [ ] **Step 5: Run tests**

Run:

```powershell
pytest tests/test_repository_fake.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/airs/db tests/test_repository_fake.py
git commit -m "feat: add shared intelligence repository"
```

---

### Task 4: Embeddings, Retrieval, and Context Packs

**Files:**
- Create: `src/airs/embeddings.py`
- Create: `src/airs/retrieval.py`
- Create: `tests/test_retrieval.py`

- [ ] **Step 1: Write failing retrieval tests**

Create `tests/test_retrieval.py`:

```python
from airs.domain import DocumentCreate, DocumentType, IntelFilters, Region, StrategicVertical, Topic
from airs.retrieval import RetrievalService


def test_context_pack_returns_ranked_documents(repository, embedder) -> None:
    source = repository.create_document(
        DocumentCreate(
            doc_type=DocumentType.RAW_SOURCE,
            title="Dubai gold demand",
            content="Gold jewellery demand increased before Ramadan.",
            metadata={"region": "middle_east", "topic": "product", "importance_score": 0.8},
            source_url="https://example.com/gold",
            created_by_agent="collector",
        )
    )
    repository.create_document(
        DocumentCreate(
            doc_type=DocumentType.RAW_SOURCE,
            title="European watches",
            content="Luxury watches are promoted in Paris.",
            metadata={"region": "europe", "topic": "product", "importance_score": 0.6},
            created_by_agent="collector",
        )
    )
    service = RetrievalService(repository=repository, embedder=embedder)

    pack = service.build_context_pack(
        task_type="analysis",
        query="gold jewellery demand",
        filters=IntelFilters(
            region=Region.MIDDLE_EAST,
            topic=Topic.PRODUCT,
            strategic_vertical=None,
        ),
        doc_ids=[source.id],
        top_k=5,
    )

    assert pack["task_type"] == "analysis"
    assert pack["seed_documents"][0]["id"] == source.id
    assert pack["retrieved_documents"][0]["title"] == "Dubai gold demand"


def test_trend_snapshot_counts_by_topic(repository, embedder) -> None:
    repository.create_document(
        DocumentCreate(
            doc_type=DocumentType.INTEL_CARD,
            title="Signal 1",
            content="Gold product signal.",
            metadata={
                "region": "middle_east",
                "topic": "product",
                "strategic_vertical": "gold_jewellery",
                "importance_score": 0.8,
            },
            created_by_agent="collector",
        )
    )
    service = RetrievalService(repository=repository, embedder=embedder)

    snapshot = service.get_trend_snapshot(
        filters=IntelFilters(
            region=Region.MIDDLE_EAST,
            strategic_vertical=StrategicVertical.GOLD_JEWELLERY,
        ),
        time_window="30d",
    )

    assert snapshot["total_documents"] == 1
    assert snapshot["topic_counts"] == {"product": 1}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_retrieval.py -v
```

Expected: FAIL because retrieval modules do not exist.

- [ ] **Step 3: Implement embeddings and retrieval**

Create `src/airs/embeddings.py`:

```python
from __future__ import annotations

import hashlib
from typing import Protocol


class EmbeddingProvider(Protocol):
    def embed_text(self, text: str) -> list[float]: ...


class DeterministicEmbeddingProvider:
    def __init__(self, dimensions: int = 8) -> None:
        self.dimensions = dimensions

    def embed_text(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = []
        for index in range(self.dimensions):
            values.append(digest[index] / 255.0)
        return values
```

Create `src/airs/retrieval.py`:

```python
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from airs.db.repository import IntelligenceRepository
from airs.domain import Document, IntelFilters
from airs.embeddings import EmbeddingProvider


def serialize_document(document: Document) -> dict[str, Any]:
    return {
        "id": document.id,
        "doc_type": document.doc_type.value,
        "title": document.title,
        "content": document.content,
        "metadata": document.metadata,
        "source_url": str(document.source_url) if document.source_url else None,
        "created_by_agent": document.created_by_agent,
        "created_at": document.created_at.isoformat(),
    }


@dataclass
class RetrievalService:
    repository: IntelligenceRepository
    embedder: EmbeddingProvider

    def search_intel_documents(
        self, query: str, filters: IntelFilters | None = None, top_k: int = 10
    ) -> list[dict[str, Any]]:
        self.embedder.embed_text(query)
        results = self.repository.search_documents(query=query, filters=filters, top_k=top_k)
        return [
            {"document": serialize_document(result.document), "score": result.score}
            for result in results
        ]

    def build_context_pack(
        self,
        task_type: str,
        query: str,
        filters: IntelFilters | None = None,
        doc_ids: list[str] | None = None,
        top_k: int = 8,
    ) -> dict[str, Any]:
        seed_documents = [self.repository.get_document(doc_id) for doc_id in doc_ids or []]
        retrieved = self.repository.search_documents(query=query, filters=filters, top_k=top_k)
        return {
            "task_type": task_type,
            "query": query,
            "filters": filters.model_dump(mode="json") if filters else {},
            "seed_documents": [serialize_document(document) for document in seed_documents],
            "retrieved_documents": [
                serialize_document(result.document) for result in retrieved
            ],
        }

    def get_trend_snapshot(self, filters: IntelFilters | None, time_window: str) -> dict[str, Any]:
        results = self.repository.search_documents(query="", filters=filters, top_k=100)
        documents = [result.document for result in results]
        topic_counts = Counter(
            document.metadata.get("topic", "unknown") for document in documents
        )
        region_counts = Counter(
            document.metadata.get("region", "unknown") for document in documents
        )
        return {
            "time_window": time_window,
            "total_documents": len(documents),
            "topic_counts": dict(topic_counts),
            "region_counts": dict(region_counts),
            "average_importance_score": self._average_metadata(documents, "importance_score"),
            "average_confidence_score": self._average_metadata(documents, "confidence_score"),
        }

    def _average_metadata(self, documents: list[Document], key: str) -> float:
        values = [float(document.metadata.get(key, 0)) for document in documents]
        if not values:
            return 0.0
        return round(sum(values) / len(values), 3)
```

- [ ] **Step 4: Run retrieval tests**

Run:

```powershell
pytest tests/test_retrieval.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/airs/embeddings.py src/airs/retrieval.py tests/test_retrieval.py
git commit -m "feat: add retrieval and context packs"
```

---

### Task 5: Collector Query Planning and Deduplication

**Files:**
- Create: `src/airs/collectors/__init__.py`
- Create: `src/airs/collectors/query_planner.py`
- Create: `src/airs/collectors/dedup.py`
- Create: `tests/test_query_planner.py`
- Create: `tests/test_dedup.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_query_planner.py`:

```python
from airs.collectors.query_planner import plan_queries
from airs.domain import CollectionRequest, Region, StrategicVertical, Topic


def test_query_planner_creates_region_and_vertical_queries() -> None:
    request = CollectionRequest(
        region=Region.MIDDLE_EAST,
        topic=Topic.SOCIAL,
        strategic_vertical=StrategicVertical.GOLD_JEWELLERY,
        time_window="14d",
        query_focus="Ramadan wedding demand",
        source_types=["news", "social_trend"],
    )

    items = plan_queries(request)

    assert len(items) >= 3
    assert any("Middle East" in item.query for item in items)
    assert any("gold jewellery" in item.query for item in items)
```

Create `tests/test_dedup.py`:

```python
from airs.collectors.dedup import SearchCandidate, cluster_candidates, normalize_url


def test_normalize_url_removes_tracking_params() -> None:
    url = "https://example.com/story/?utm_source=x&id=1#section"
    assert normalize_url(url) == "https://example.com/story?id=1"


def test_cluster_candidates_groups_similar_event_titles() -> None:
    candidates = [
        SearchCandidate(
            title="Pandora opens new flagship store in Dubai",
            url="https://a.example/story",
            snippet="Pandora launched a new Dubai flagship jewellery store.",
            source_name="A",
            published_at="2026-05-20",
        ),
        SearchCandidate(
            title="Pandora launches Dubai flagship jewellery store",
            url="https://b.example/story",
            snippet="The brand opened a flagship store in Dubai.",
            source_name="B",
            published_at="2026-05-21",
        ),
    ]

    clusters = cluster_candidates(candidates)

    assert len(clusters) == 1
    assert len(clusters[0].candidates) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_query_planner.py tests/test_dedup.py -v
```

Expected: FAIL because collector modules do not exist.

- [ ] **Step 3: Implement query planner and dedup**

Create `src/airs/collectors/__init__.py`:

```python
"""Collector mini-agent components."""
```

Create `src/airs/collectors/query_planner.py`:

```python
from __future__ import annotations

from pydantic import BaseModel

from airs.domain import CollectionRequest, Region, StrategicVertical, Topic


REGION_LABELS = {
    Region.ASIA_PACIFIC: "Asia Pacific",
    Region.MIDDLE_EAST: "Middle East",
    Region.EUROPE: "Europe",
    Region.AMERICAS: "Americas",
    Region.EMERGING_MARKETS: "emerging markets",
}

VERTICAL_LABELS = {
    StrategicVertical.GOLD_JEWELLERY: "gold jewellery",
    StrategicVertical.JADE_COLORED_GEMS_CULTURAL: "jade colored gems cultural jewellery",
    StrategicVertical.OVERSEAS_RETAIL_CHANNELS: "overseas retail jewellery channels",
}

TOPIC_LABELS = {
    Topic.COMPETITION: "competitor moves",
    Topic.PRODUCT: "product trends",
    Topic.PLATFORM: "platform channels",
    Topic.SOCIAL: "social media trends",
    Topic.REGULATION: "regulation",
    Topic.MACRO_GOLD: "gold price macro dynamics",
}


class QueryWorkItem(BaseModel):
    query: str
    source_type: str
    depends_on: list[int] = []


def plan_queries(request: CollectionRequest) -> list[QueryWorkItem]:
    region = REGION_LABELS[request.region]
    vertical = VERTICAL_LABELS[request.strategic_vertical]
    topic = TOPIC_LABELS[request.topic]
    focus = request.query_focus
    source_types = request.source_types or ["news"]

    work_items = [
        QueryWorkItem(
            query=f"{region} {vertical} {topic} {focus}",
            source_type=source_types[0],
        ),
        QueryWorkItem(
            query=f"{region} jewellery market {focus} {request.time_window}",
            source_type=source_types[0],
        ),
        QueryWorkItem(
            query=f"{vertical} {topic} overseas jewellery {focus}",
            source_type=source_types[-1],
            depends_on=[0],
        ),
    ]
    if request.topic == Topic.MACRO_GOLD:
        work_items.append(
            QueryWorkItem(
                query=f"gold price {region} jewellery demand {focus}",
                source_type="macro",
                depends_on=[0],
            )
        )
    return work_items
```

Create `src/airs/collectors/dedup.py`:

```python
from __future__ import annotations

import re
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel


TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


class SearchCandidate(BaseModel):
    title: str
    url: str
    snippet: str = ""
    source_name: str = "unknown"
    published_at: str | None = None


class CandidateCluster(BaseModel):
    canonical_event_key: str
    candidates: list[SearchCandidate]


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query_pairs = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key in TRACKING_KEYS or any(key.startswith(prefix) for prefix in TRACKING_PREFIXES):
            continue
        query_pairs.append((key, value))
    query = urlencode(query_pairs)
    path = parts.path.rstrip("/") or parts.path
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def cluster_candidates(candidates: list[SearchCandidate]) -> list[CandidateCluster]:
    clusters: list[CandidateCluster] = []
    seen_urls: set[str] = set()
    for candidate in candidates:
        normalized = normalize_url(candidate.url)
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        placed = False
        for cluster in clusters:
            if _is_same_event(candidate, cluster.candidates[0]):
                cluster.candidates.append(candidate)
                placed = True
                break
        if not placed:
            clusters.append(
                CandidateCluster(
                    canonical_event_key=canonical_event_key(candidate),
                    candidates=[candidate],
                )
            )
    return clusters


def canonical_event_key(candidate: SearchCandidate) -> str:
    text = f"{candidate.title} {candidate.snippet}".lower()
    words = re.findall(r"[a-z0-9]+", text)
    important_words = [word for word in words if len(word) > 3][:8]
    return "|".join(important_words)


def _is_same_event(left: SearchCandidate, right: SearchCandidate) -> bool:
    left_text = f"{left.title} {left.snippet}".lower()
    right_text = f"{right.title} {right.snippet}".lower()
    similarity = SequenceMatcher(None, left_text, right_text).ratio()
    shared_words = set(re.findall(r"[a-z0-9]+", left_text)) & set(
        re.findall(r"[a-z0-9]+", right_text)
    )
    return similarity >= 0.58 or len([word for word in shared_words if len(word) > 4]) >= 4
```

- [ ] **Step 4: Run collector unit tests**

Run:

```powershell
pytest tests/test_query_planner.py tests/test_dedup.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/airs/collectors tests/test_query_planner.py tests/test_dedup.py
git commit -m "feat: add collector planning and deduplication"
```

---

### Task 6: Collector Pipeline

**Files:**
- Create: `src/airs/collectors/web_search.py`
- Create: `src/airs/collectors/pipeline.py`
- Create: `tests/test_collector_pipeline.py`

- [ ] **Step 1: Write failing collector pipeline test**

Create `tests/test_collector_pipeline.py`:

```python
from airs.collectors.dedup import SearchCandidate
from airs.collectors.pipeline import CollectorPipeline
from airs.collectors.web_search import StaticSearchProvider
from airs.domain import CollectionRequest, DocumentType, Region, StrategicVertical, Topic


def test_collector_creates_sources_and_cards(repository) -> None:
    provider = StaticSearchProvider(
        candidates=[
            SearchCandidate(
                title="Pandora opens new flagship store in Dubai",
                url="https://example.com/pandora-dubai",
                snippet="Pandora opened a flagship jewellery store in Dubai.",
                source_name="Example News",
                published_at="2026-05-20",
            ),
            SearchCandidate(
                title="Pandora launches Dubai flagship jewellery store",
                url="https://example.org/pandora-dubai",
                snippet="The jewellery brand opened a Dubai flagship store.",
                source_name="Example Trade",
                published_at="2026-05-21",
            ),
        ]
    )
    pipeline = CollectorPipeline(repository=repository, search_provider=provider)
    result = pipeline.collect(
        CollectionRequest(
            region=Region.MIDDLE_EAST,
            topic=Topic.COMPETITION,
            strategic_vertical=StrategicVertical.OVERSEAS_RETAIL_CHANNELS,
            time_window="14d",
            query_focus="flagship store expansion",
            source_types=["news"],
        )
    )

    assert len(result.created_source_ids) == 2
    assert len(result.created_card_ids) == 1
    card = repository.get_document(result.created_card_ids[0])
    assert card.doc_type == DocumentType.INTEL_CARD
    assert card.metadata["source_count"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_collector_pipeline.py -v
```

Expected: FAIL because pipeline modules do not exist.

- [ ] **Step 3: Implement web search abstraction and collector pipeline**

Create `src/airs/collectors/web_search.py`:

```python
from __future__ import annotations

from typing import Protocol

from airs.collectors.dedup import SearchCandidate


class SearchProvider(Protocol):
    def search(self, query: str, source_type: str, time_window: str) -> list[SearchCandidate]: ...


class StaticSearchProvider:
    def __init__(self, candidates: list[SearchCandidate]) -> None:
        self.candidates = candidates

    def search(self, query: str, source_type: str, time_window: str) -> list[SearchCandidate]:
        return self.candidates
```

Create `src/airs/collectors/pipeline.py`:

```python
from __future__ import annotations

from uuid import uuid4

from airs.collectors.dedup import cluster_candidates
from airs.collectors.query_planner import plan_queries
from airs.collectors.web_search import SearchProvider
from airs.db.repository import IntelligenceRepository
from airs.domain import CollectionRequest, CollectionResult, DocumentCreate, DocumentType


class CollectorPipeline:
    def __init__(self, repository: IntelligenceRepository, search_provider: SearchProvider) -> None:
        self.repository = repository
        self.search_provider = search_provider

    def collect(self, request: CollectionRequest) -> CollectionResult:
        candidates = []
        for item in plan_queries(request):
            candidates.extend(
                self.search_provider.search(
                    query=item.query,
                    source_type=item.source_type,
                    time_window=request.time_window,
                )
            )

        clusters = cluster_candidates(candidates)
        created_source_ids: list[str] = []
        created_card_ids: list[str] = []

        for cluster in clusters:
            source_ids = []
            for candidate in cluster.candidates:
                source = self.repository.create_document(
                    DocumentCreate(
                        doc_type=DocumentType.RAW_SOURCE,
                        title=candidate.title,
                        content=candidate.snippet or candidate.title,
                        metadata={
                            "region": request.region.value,
                            "topic": request.topic.value,
                            "strategic_vertical": request.strategic_vertical.value,
                            "source_type": "web",
                            "published_at": candidate.published_at,
                            "source_name": candidate.source_name,
                            "evidence_quality": "snippet_only",
                        },
                        source_url=candidate.url,
                        created_by_agent="collector_mini_agent",
                    )
                )
                source_ids.append(source.id)
                created_source_ids.append(source.id)

            primary = cluster.candidates[0]
            card = self.repository.create_document(
                DocumentCreate(
                    doc_type=DocumentType.INTEL_CARD,
                    title=primary.title,
                    content=primary.snippet or primary.title,
                    metadata={
                        "region": request.region.value,
                        "topic": request.topic.value,
                        "strategic_vertical": request.strategic_vertical.value,
                        "importance_score": 0.6,
                        "confidence_score": min(0.95, 0.45 + 0.15 * len(source_ids)),
                        "canonical_event_key": cluster.canonical_event_key,
                        "primary_source_id": source_ids[0],
                        "supporting_source_ids": source_ids[1:],
                        "source_count": len(source_ids),
                        "evidence_quality": "snippet_only",
                    },
                    source_url=primary.url,
                    created_by_agent="collector_mini_agent",
                )
            )
            created_card_ids.append(card.id)

        return CollectionResult(
            request_id=f"retrieval_{uuid4().hex}",
            created_source_ids=created_source_ids,
            created_card_ids=created_card_ids,
            coverage={
                "regions": [request.region.value],
                "source_types": request.source_types,
                "time_window": request.time_window,
            },
        )
```

- [ ] **Step 4: Run pipeline test**

Run:

```powershell
pytest tests/test_collector_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/airs/collectors/web_search.py src/airs/collectors/pipeline.py tests/test_collector_pipeline.py
git commit -m "feat: add collector pipeline"
```

---

### Task 7: Analysis Agent

**Files:**
- Create: `src/airs/agents/__init__.py`
- Create: `src/airs/agents/analysis.py`
- Create: `tests/test_analysis_agent.py`

- [ ] **Step 1: Write failing analysis agent test**

Create `tests/test_analysis_agent.py`:

```python
from airs.agents.analysis import AnalysisAgent
from airs.domain import DocumentCreate, DocumentType, IntelFilters, Region, StrategicVertical, Topic
from airs.retrieval import RetrievalService


def test_analysis_agent_saves_analysis_with_evidence(repository, embedder) -> None:
    card = repository.create_document(
        DocumentCreate(
            doc_type=DocumentType.INTEL_CARD,
            title="Dubai gold demand rises",
            content="Gold jewellery demand is rising before Ramadan.",
            metadata={
                "region": "middle_east",
                "topic": "product",
                "strategic_vertical": "gold_jewellery",
                "importance_score": 0.8,
                "confidence_score": 0.7,
            },
            created_by_agent="collector",
        )
    )
    service = RetrievalService(repository=repository, embedder=embedder)
    agent = AnalysisAgent(repository=repository, retrieval=service)

    analysis = agent.analyze(
        query="gold jewellery demand",
        filters=IntelFilters(
            region=Region.MIDDLE_EAST,
            topic=Topic.PRODUCT,
            strategic_vertical=StrategicVertical.GOLD_JEWELLERY,
        ),
        seed_doc_ids=[card.id],
    )

    assert analysis.doc_type == DocumentType.ANALYSIS
    assert analysis.metadata["evidence_doc_ids"] == [card.id]
    assert analysis.metadata["evidence_sufficiency"] == "partial"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_analysis_agent.py -v
```

Expected: FAIL because analysis agent does not exist.

- [ ] **Step 3: Implement analysis agent**

Create `src/airs/agents/__init__.py`:

```python
"""AIRS analysis, prediction, and briefing agents."""
```

Create `src/airs/agents/analysis.py`:

```python
from __future__ import annotations

from airs.db.repository import IntelligenceRepository
from airs.domain import Document, DocumentCreate, DocumentType, IntelFilters
from airs.retrieval import RetrievalService


class AnalysisAgent:
    def __init__(self, repository: IntelligenceRepository, retrieval: RetrievalService) -> None:
        self.repository = repository
        self.retrieval = retrieval

    def analyze(
        self,
        query: str,
        filters: IntelFilters,
        seed_doc_ids: list[str],
    ) -> Document:
        context = self.retrieval.build_context_pack(
            task_type="analysis",
            query=query,
            filters=filters,
            doc_ids=seed_doc_ids,
            top_k=8,
        )
        evidence_ids = seed_doc_ids or [
            document["id"] for document in context["retrieved_documents"][:3]
        ]
        sufficiency = "sufficient" if len(evidence_ids) >= 3 else "partial"
        region = filters.region.value if filters.region else "global"
        vertical = filters.strategic_vertical.value if filters.strategic_vertical else "all"
        topic = filters.topic.value if filters.topic else "general"
        conclusion = f"{region} {vertical} shows a {topic} signal related to: {query}."
        impact = "Review the signal for timing, inventory, campaign, or channel implications."

        return self.repository.create_document(
            DocumentCreate(
                doc_type=DocumentType.ANALYSIS,
                title=f"Analysis: {query}",
                content=f"{conclusion}\n\nImpact: {impact}",
                metadata={
                    "region": region,
                    "topic": topic,
                    "strategic_vertical": vertical,
                    "conclusion": conclusion,
                    "impact_assessment": impact,
                    "risk_or_opportunity": "watch",
                    "recommended_actions": [
                        "Review supporting sources.",
                        "Escalate high-confidence signals in the next briefing.",
                    ],
                    "confidence_score": 0.68 if sufficiency == "partial" else 0.78,
                    "evidence_sufficiency": sufficiency,
                    "evidence_doc_ids": evidence_ids,
                },
                created_by_agent="analysis_agent",
            )
        )
```

- [ ] **Step 4: Run analysis test**

Run:

```powershell
pytest tests/test_analysis_agent.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/airs/agents tests/test_analysis_agent.py
git commit -m "feat: add analysis agent"
```

---

### Task 8: Prediction Agent

**Files:**
- Create: `src/airs/agents/prediction.py`
- Create: `tests/test_prediction_agent.py`

- [ ] **Step 1: Write failing prediction test**

Create `tests/test_prediction_agent.py`:

```python
from airs.agents.prediction import PredictionAgent
from airs.domain import DocumentCreate, DocumentType, IntelFilters, Region, StrategicVertical
from airs.retrieval import RetrievalService


def test_prediction_agent_saves_forecast(repository, embedder) -> None:
    card = repository.create_document(
        DocumentCreate(
            doc_type=DocumentType.INTEL_CARD,
            title="Middle East gold signal",
            content="Gold jewellery attention increased.",
            metadata={
                "region": "middle_east",
                "topic": "social",
                "strategic_vertical": "gold_jewellery",
                "importance_score": 0.8,
                "confidence_score": 0.75,
            },
            created_by_agent="collector",
        )
    )
    retrieval = RetrievalService(repository=repository, embedder=embedder)
    agent = PredictionAgent(repository=repository, retrieval=retrieval)

    prediction = agent.predict(
        query="gold jewellery demand",
        filters=IntelFilters(
            region=Region.MIDDLE_EAST,
            strategic_vertical=StrategicVertical.GOLD_JEWELLERY,
        ),
        forecast_horizon="30d",
        seed_doc_ids=[card.id],
    )

    assert prediction.doc_type == DocumentType.PREDICTION
    assert prediction.metadata["forecast_horizon"] == "30d"
    assert prediction.metadata["evidence_doc_ids"] == [card.id]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_prediction_agent.py -v
```

Expected: FAIL because prediction agent does not exist.

- [ ] **Step 3: Implement prediction agent**

Create `src/airs/agents/prediction.py`:

```python
from __future__ import annotations

from airs.db.repository import IntelligenceRepository
from airs.domain import Document, DocumentCreate, DocumentType, IntelFilters
from airs.retrieval import RetrievalService


class PredictionAgent:
    def __init__(self, repository: IntelligenceRepository, retrieval: RetrievalService) -> None:
        self.repository = repository
        self.retrieval = retrieval

    def predict(
        self,
        query: str,
        filters: IntelFilters,
        forecast_horizon: str,
        seed_doc_ids: list[str],
    ) -> Document:
        snapshot = self.retrieval.get_trend_snapshot(filters=filters, time_window=forecast_horizon)
        evidence_ids = seed_doc_ids
        region = filters.region.value if filters.region else "global"
        vertical = filters.strategic_vertical.value if filters.strategic_vertical else "all"
        direction = "upward watch" if snapshot["total_documents"] >= 1 else "insufficient signal"
        prediction = (
            f"{region} {vertical} has a {direction} over the next {forecast_horizon} "
            f"based on {snapshot['total_documents']} retrieved signals."
        )

        return self.repository.create_document(
            DocumentCreate(
                doc_type=DocumentType.PREDICTION,
                title=f"Prediction: {query}",
                content=prediction,
                metadata={
                    "region": region,
                    "strategic_vertical": vertical,
                    "prediction_type": "market_signal_trend",
                    "forecast_horizon": forecast_horizon,
                    "prediction": prediction,
                    "confidence_score": 0.62 if evidence_ids else 0.35,
                    "evidence_doc_ids": evidence_ids,
                    "risk_factors": ["source coverage may be incomplete"],
                    "suggested_actions": ["Use as a watch signal until more evidence is collected."],
                },
                created_by_agent="prediction_agent",
            )
        )
```

- [ ] **Step 4: Run prediction test**

Run:

```powershell
pytest tests/test_prediction_agent.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/airs/agents/prediction.py tests/test_prediction_agent.py
git commit -m "feat: add prediction agent"
```

---

### Task 9: Briefing Agent

**Files:**
- Create: `src/airs/agents/briefing.py`
- Create: `tests/test_briefing_agent.py`

- [ ] **Step 1: Write failing briefing test**

Create `tests/test_briefing_agent.py`:

```python
from airs.agents.briefing import BriefingAgent
from airs.domain import DocumentCreate, DocumentType, IntelFilters, Region
from airs.retrieval import RetrievalService


def test_briefing_agent_creates_regional_briefing(repository, embedder) -> None:
    card = repository.create_document(
        DocumentCreate(
            doc_type=DocumentType.INTEL_CARD,
            title="Dubai retail expansion",
            content="A competitor opened a Dubai flagship store.",
            metadata={"region": "middle_east", "topic": "competition", "importance_score": 0.8},
            created_by_agent="collector",
        )
    )
    retrieval = RetrievalService(repository=repository, embedder=embedder)
    agent = BriefingAgent(repository=repository, retrieval=retrieval)

    briefing = agent.create_briefing(
        audience_type="regional_leader",
        audience_key="middle_east",
        query="middle east jewellery signals",
        filters=IntelFilters(region=Region.MIDDLE_EAST),
    )

    assert briefing.doc_type == DocumentType.BRIEFING
    assert briefing.metadata["audience_type"] == "regional_leader"
    assert card.id in briefing.metadata["evidence_doc_ids"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_briefing_agent.py -v
```

Expected: FAIL because briefing agent does not exist.

- [ ] **Step 3: Implement briefing agent**

Create `src/airs/agents/briefing.py`:

```python
from __future__ import annotations

from typing import Literal

from airs.db.repository import IntelligenceRepository
from airs.domain import Document, DocumentCreate, DocumentType, IntelFilters
from airs.retrieval import RetrievalService


class BriefingAgent:
    def __init__(self, repository: IntelligenceRepository, retrieval: RetrievalService) -> None:
        self.repository = repository
        self.retrieval = retrieval

    def create_briefing(
        self,
        audience_type: Literal["regional_leader", "strategic_vertical_leader", "hq_strategy"],
        audience_key: str,
        query: str,
        filters: IntelFilters,
    ) -> Document:
        context = self.retrieval.build_context_pack(
            task_type="briefing",
            query=query,
            filters=filters,
            doc_ids=[],
            top_k=10,
        )
        evidence_ids = [document["id"] for document in context["retrieved_documents"][:5]]
        sections = [
            {
                "heading": "Key Signals",
                "items": [
                    {
                        "title": document["title"],
                        "summary": document["content"],
                        "source_url": document["source_url"],
                        "doc_id": document["id"],
                    }
                    for document in context["retrieved_documents"][:5]
                ],
            }
        ]
        executive_summary = (
            f"{audience_key} briefing contains {len(evidence_ids)} traceable signals."
        )

        return self.repository.create_document(
            DocumentCreate(
                doc_type=DocumentType.BRIEFING,
                title=f"AIRS Daily Briefing: {audience_key}",
                content=executive_summary,
                metadata={
                    "audience_type": audience_type,
                    "audience_key": audience_key,
                    "executive_summary": executive_summary,
                    "sections": sections,
                    "evidence_doc_ids": evidence_ids,
                },
                created_by_agent="briefing_agent",
            )
        )
```

- [ ] **Step 4: Run briefing test**

Run:

```powershell
pytest tests/test_briefing_agent.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/airs/agents/briefing.py tests/test_briefing_agent.py
git commit -m "feat: add briefing agent"
```

---

### Task 10: MCP Tool Server

**Files:**
- Create: `src/airs/mcp_server.py`

- [ ] **Step 1: Add MCP server with reusable tool functions**

Create `src/airs/mcp_server.py`:

```python
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from airs.agents.analysis import AnalysisAgent
from airs.agents.briefing import BriefingAgent
from airs.agents.prediction import PredictionAgent
from airs.collectors.pipeline import CollectorPipeline
from airs.collectors.web_search import StaticSearchProvider
from airs.db.repository import InMemoryRepository
from airs.domain import CollectionRequest, IntelFilters, Region, StrategicVertical, Topic
from airs.embeddings import DeterministicEmbeddingProvider
from airs.retrieval import RetrievalService


mcp = FastMCP("airs")
repository = InMemoryRepository()
embedder = DeterministicEmbeddingProvider()
retrieval = RetrievalService(repository=repository, embedder=embedder)
collector = CollectorPipeline(repository=repository, search_provider=StaticSearchProvider([]))


@mcp.tool()
def collect_market_intel(
    region: str,
    topic: str,
    strategic_vertical: str,
    time_window: str,
    query_focus: str,
    source_types: list[str],
) -> dict:
    result = collector.collect(
        CollectionRequest(
            region=Region(region),
            topic=Topic(topic),
            strategic_vertical=StrategicVertical(strategic_vertical),
            time_window=time_window,
            query_focus=query_focus,
            source_types=source_types,
        )
    )
    return result.model_dump()


@mcp.tool()
def search_intel_documents(query: str, filters: dict, top_k: int = 10) -> list[dict]:
    parsed_filters = IntelFilters(**filters)
    return retrieval.search_intel_documents(query=query, filters=parsed_filters, top_k=top_k)


@mcp.tool()
def build_context_pack(task_type: str, query: str, filters: dict, doc_ids: list[str]) -> dict:
    parsed_filters = IntelFilters(**filters)
    return retrieval.build_context_pack(
        task_type=task_type,
        query=query,
        filters=parsed_filters,
        doc_ids=doc_ids,
    )


@mcp.tool()
def save_analysis(query: str, filters: dict, seed_doc_ids: list[str]) -> dict:
    agent = AnalysisAgent(repository=repository, retrieval=retrieval)
    document = agent.analyze(query=query, filters=IntelFilters(**filters), seed_doc_ids=seed_doc_ids)
    return document.model_dump(mode="json")


@mcp.tool()
def save_prediction(
    query: str,
    filters: dict,
    forecast_horizon: str,
    seed_doc_ids: list[str],
) -> dict:
    agent = PredictionAgent(repository=repository, retrieval=retrieval)
    document = agent.predict(
        query=query,
        filters=IntelFilters(**filters),
        forecast_horizon=forecast_horizon,
        seed_doc_ids=seed_doc_ids,
    )
    return document.model_dump(mode="json")


@mcp.tool()
def save_briefing(audience_type: str, audience_key: str, query: str, filters: dict) -> dict:
    agent = BriefingAgent(repository=repository, retrieval=retrieval)
    document = agent.create_briefing(
        audience_type=audience_type,
        audience_key=audience_key,
        query=query,
        filters=IntelFilters(**filters),
    )
    return document.model_dump(mode="json")


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 2: Run import check**

Run:

```powershell
python -c "import airs.mcp_server; print('mcp ok')"
```

Expected: output contains `mcp ok`.

- [ ] **Step 3: Commit**

```powershell
git add src/airs/mcp_server.py
git commit -m "feat: expose AIRS MCP tools"
```

---

### Task 11: Feishu Distribution

**Files:**
- Create: `src/airs/feishu.py`
- Create: `tests/test_feishu.py`

- [ ] **Step 1: Write failing Feishu tests**

Create `tests/test_feishu.py`:

```python
from airs.feishu import build_feishu_message


def test_build_feishu_message_includes_sections_and_sources() -> None:
    payload = build_feishu_message(
        title="AIRS Daily Briefing: middle_east",
        executive_summary="Three traceable signals.",
        sections=[
            {
                "heading": "Key Signals",
                "items": [
                    {
                        "title": "Dubai retail expansion",
                        "summary": "A competitor opened a flagship store.",
                        "source_url": "https://example.com/source",
                        "doc_id": "doc_1",
                    }
                ],
            }
        ],
    )

    assert payload["msg_type"] == "post"
    assert "Dubai retail expansion" in str(payload)
    assert "https://example.com/source" in str(payload)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_feishu.py -v
```

Expected: FAIL because `airs.feishu` does not exist.

- [ ] **Step 3: Implement Feishu payload builder**

Create `src/airs/feishu.py`:

```python
from __future__ import annotations

from typing import Any

import httpx


def build_feishu_message(
    title: str,
    executive_summary: str,
    sections: list[dict[str, Any]],
) -> dict[str, Any]:
    content: list[list[dict[str, Any]]] = [
        [{"tag": "text", "text": f"{executive_summary}\n"}]
    ]
    for section in sections:
        content.append([{"tag": "text", "text": f"\n{section['heading']}\n"}])
        for item in section.get("items", []):
            text = f"- {item['title']}: {item['summary']} ({item.get('source_url')})\n"
            content.append([{"tag": "text", "text": text}])
    return {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": content,
                }
            }
        },
    }


def send_feishu_message(webhook_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = httpx.post(webhook_url, json=payload, timeout=20)
    response.raise_for_status()
    return response.json()
```

- [ ] **Step 4: Run Feishu test**

Run:

```powershell
pytest tests/test_feishu.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/airs/feishu.py tests/test_feishu.py
git commit -m "feat: add Feishu briefing payloads"
```

---

### Task 12: FastAPI Backend

**Files:**
- Create: `src/airs/api.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_api.py`:

```python
from fastapi.testclient import TestClient

from airs.api import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_collect_endpoint_returns_ids() -> None:
    client = TestClient(app)
    response = client.post(
        "/collect",
        json={
            "region": "middle_east",
            "topic": "competition",
            "strategic_vertical": "overseas_retail_channels",
            "time_window": "14d",
            "query_focus": "flagship store expansion",
            "source_types": ["news"],
        },
    )

    assert response.status_code == 200
    assert "created_card_ids" in response.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_api.py -v
```

Expected: FAIL because API module does not exist.

- [ ] **Step 3: Implement FastAPI app**

Create `src/airs/api.py`:

```python
from __future__ import annotations

from fastapi import FastAPI

from airs.agents.briefing import BriefingAgent
from airs.collectors.dedup import SearchCandidate
from airs.collectors.pipeline import CollectorPipeline
from airs.collectors.web_search import StaticSearchProvider
from airs.db.repository import InMemoryRepository
from airs.domain import CollectionRequest, IntelFilters
from airs.embeddings import DeterministicEmbeddingProvider
from airs.retrieval import RetrievalService


app = FastAPI(title="AIRS MVP")
repository = InMemoryRepository()
embedder = DeterministicEmbeddingProvider()
retrieval = RetrievalService(repository=repository, embedder=embedder)
collector = CollectorPipeline(
    repository=repository,
    search_provider=StaticSearchProvider(
        [
            SearchCandidate(
                title="Pandora opens new flagship store in Dubai",
                url="https://example.com/pandora-dubai",
                snippet="Pandora opened a flagship jewellery store in Dubai.",
                source_name="Example News",
                published_at="2026-05-20",
            )
        ]
    ),
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/collect")
def collect(request: CollectionRequest) -> dict:
    return collector.collect(request).model_dump()


@app.post("/search")
def search(payload: dict) -> list[dict]:
    filters = IntelFilters(**payload.get("filters", {}))
    return retrieval.search_intel_documents(
        query=payload.get("query", ""),
        filters=filters,
        top_k=payload.get("top_k", 10),
    )


@app.post("/briefings")
def create_briefing(payload: dict) -> dict:
    agent = BriefingAgent(repository=repository, retrieval=retrieval)
    document = agent.create_briefing(
        audience_type=payload["audience_type"],
        audience_key=payload["audience_key"],
        query=payload["query"],
        filters=IntelFilters(**payload.get("filters", {})),
    )
    return document.model_dump(mode="json")
```

- [ ] **Step 4: Run API tests**

Run:

```powershell
pytest tests/test_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Run local API smoke test**

Run:

```powershell
python -c "from airs.api import app; print(app.title)"
```

Expected: output is `AIRS MVP`.

- [ ] **Step 6: Commit**

```powershell
git add src/airs/api.py tests/test_api.py
git commit -m "feat: add AIRS FastAPI backend"
```

---

### Task 13: Internal Console

**Files:**
- Create: `app/console.py`

- [ ] **Step 1: Add Streamlit console**

Create `app/console.py`:

```python
from __future__ import annotations

import httpx
import streamlit as st


API_BASE = st.sidebar.text_input("API Base", value="http://localhost:8000")

st.title("AIRS Strategic Intelligence Console")

tab_collect, tab_briefing = st.tabs(["Collect", "Briefing"])

with tab_collect:
    region = st.selectbox(
        "Region",
        ["asia_pacific", "middle_east", "europe", "americas", "emerging_markets"],
    )
    topic = st.selectbox(
        "Topic",
        ["competition", "product", "platform", "social", "regulation", "macro_gold"],
    )
    vertical = st.selectbox(
        "Strategic Vertical",
        [
            "gold_jewellery",
            "jade_colored_gems_cultural_jewellery",
            "overseas_retail_channels",
        ],
    )
    focus = st.text_input("Query Focus", value="flagship store expansion")
    if st.button("Run Collection"):
        response = httpx.post(
            f"{API_BASE}/collect",
            json={
                "region": region,
                "topic": topic,
                "strategic_vertical": vertical,
                "time_window": "14d",
                "query_focus": focus,
                "source_types": ["news"],
            },
            timeout=30,
        )
        st.json(response.json())

with tab_briefing:
    audience_type = st.selectbox(
        "Audience Type",
        ["regional_leader", "strategic_vertical_leader", "hq_strategy"],
    )
    audience_key = st.text_input("Audience Key", value="middle_east")
    query = st.text_input("Briefing Query", value="middle east jewellery signals")
    if st.button("Create Briefing"):
        response = httpx.post(
            f"{API_BASE}/briefings",
            json={
                "audience_type": audience_type,
                "audience_key": audience_key,
                "query": query,
                "filters": {"region": "middle_east"},
            },
            timeout=30,
        )
        st.json(response.json())
```

- [ ] **Step 2: Run import check**

Run:

```powershell
python -m py_compile app/console.py
```

Expected: command exits successfully.

- [ ] **Step 3: Commit**

```powershell
git add app/console.py
git commit -m "feat: add internal console"
```

---

### Task 14: Configuration and Supabase Implementation

**Files:**
- Create: `src/airs/config.py`
- Modify: `src/airs/db/repository.py`

- [ ] **Step 1: Add configuration**

Create `src/airs/config.py`:

```python
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    web_search_provider: str = "mock"
    web_search_api_key: str = ""
    feishu_webhook_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 2: Add Supabase repository class**

Modify `src/airs/db/repository.py` by adding this class below `InMemoryRepository`:

```python
class SupabaseRepository:
    def __init__(self, url: str, service_role_key: str) -> None:
        from supabase import create_client

        self.client = create_client(url, service_role_key)

    def create_document(self, document: DocumentCreate) -> Document:
        payload = {
            "doc_type": document.doc_type.value,
            "title": document.title,
            "content": document.content,
            "metadata": document.metadata,
            "embedding": document.embedding,
            "source_url": str(document.source_url) if document.source_url else None,
            "created_by_agent": document.created_by_agent,
        }
        response = self.client.table("documents").insert(payload).execute()
        row = response.data[0]
        return Document(**row)

    def get_document(self, document_id: str) -> Document:
        response = (
            self.client.table("documents")
            .select("*")
            .eq("id", document_id)
            .single()
            .execute()
        )
        return Document(**response.data)

    def search_documents(
        self, query: str, filters: IntelFilters | None = None, top_k: int = 10
    ) -> list[SearchResult]:
        request = self.client.table("documents").select("*")
        if filters:
            if filters.doc_type:
                request = request.eq("doc_type", filters.doc_type.value)
            for key, value in filters.to_metadata_filter().items():
                request = request.contains("metadata", {key: value})
        response = request.limit(top_k).execute()
        return [SearchResult(document=Document(**row), score=0.0) for row in response.data]
```

- [ ] **Step 3: Run unit tests**

Run:

```powershell
pytest -v
```

Expected: PASS. The tests still use `InMemoryRepository`, so no Supabase credentials are required.

- [ ] **Step 4: Commit**

```powershell
git add src/airs/config.py src/airs/db/repository.py
git commit -m "feat: add configuration and Supabase repository"
```

---

### Task 15: End-to-End Smoke Script

**Files:**
- Create: `scripts/smoke_mvp.py`

- [ ] **Step 1: Add smoke script**

Create `scripts/smoke_mvp.py`:

```python
from airs.agents.analysis import AnalysisAgent
from airs.agents.briefing import BriefingAgent
from airs.agents.prediction import PredictionAgent
from airs.collectors.dedup import SearchCandidate
from airs.collectors.pipeline import CollectorPipeline
from airs.collectors.web_search import StaticSearchProvider
from airs.db.repository import InMemoryRepository
from airs.domain import CollectionRequest, IntelFilters, Region, StrategicVertical, Topic
from airs.embeddings import DeterministicEmbeddingProvider
from airs.retrieval import RetrievalService


def main() -> None:
    repository = InMemoryRepository()
    retrieval = RetrievalService(repository, DeterministicEmbeddingProvider())
    collector = CollectorPipeline(
        repository=repository,
        search_provider=StaticSearchProvider(
            [
                SearchCandidate(
                    title="Pandora opens new flagship store in Dubai",
                    url="https://example.com/pandora-dubai",
                    snippet="Pandora opened a flagship jewellery store in Dubai.",
                    source_name="Example News",
                    published_at="2026-05-20",
                )
            ]
        ),
    )
    collection = collector.collect(
        CollectionRequest(
            region=Region.MIDDLE_EAST,
            topic=Topic.COMPETITION,
            strategic_vertical=StrategicVertical.OVERSEAS_RETAIL_CHANNELS,
            time_window="14d",
            query_focus="flagship store expansion",
            source_types=["news"],
        )
    )
    filters = IntelFilters(
        region=Region.MIDDLE_EAST,
        strategic_vertical=StrategicVertical.OVERSEAS_RETAIL_CHANNELS,
    )
    analysis = AnalysisAgent(repository, retrieval).analyze(
        query="middle east retail expansion",
        filters=filters,
        seed_doc_ids=collection.created_card_ids,
    )
    prediction = PredictionAgent(repository, retrieval).predict(
        query="middle east retail expansion",
        filters=filters,
        forecast_horizon="30d",
        seed_doc_ids=collection.created_card_ids,
    )
    briefing = BriefingAgent(repository, retrieval).create_briefing(
        audience_type="regional_leader",
        audience_key="middle_east",
        query="middle east retail expansion",
        filters=filters,
    )
    print(
        {
            "collection": collection.model_dump(),
            "analysis_id": analysis.id,
            "prediction_id": prediction.id,
            "briefing_id": briefing.id,
        }
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run smoke script**

Run:

```powershell
python scripts/smoke_mvp.py
```

Expected: output contains `created_card_ids`, `analysis_id`, `prediction_id`, and `briefing_id`.

- [ ] **Step 3: Run full verification**

Run:

```powershell
ruff check .
pytest -v
```

Expected: both commands pass.

- [ ] **Step 4: Commit**

```powershell
git add scripts/smoke_mvp.py
git commit -m "test: add AIRS MVP smoke script"
```

---

## Execution Order

Use this order:

1. Task 1: Project Scaffolding
2. Task 2: Domain Models
3. Task 3: Database Schema and Repository
4. Task 4: Embeddings, Retrieval, and Context Packs
5. Task 5: Collector Query Planning and Deduplication
6. Task 6: Collector Pipeline
7. Task 7: Analysis Agent
8. Task 8: Prediction Agent
9. Task 9: Briefing Agent
10. Task 10: MCP Tool Server
11. Task 11: Feishu Distribution
12. Task 12: FastAPI Backend
13. Task 13: Internal Console
14. Task 14: Configuration and Supabase Implementation
15. Task 15: End-to-End Smoke Script

This order keeps the implementation testable at each layer and prevents the UI or Feishu integration from blocking the core intelligence pipeline.

## Coverage Check

This plan covers the design spec as follows:

- Shared SQL/vector memory: Tasks 3, 4, and 14.
- Collector mini-agent as lightweight retrieval executor: Tasks 5 and 6.
- URL, title/snippet, and event-level deduplication: Task 5.
- Analysis Agent and supplementary retrieval decision boundary: Task 7 provides the analysis layer and keeps retrieval as a callable service.
- Prediction Agent: Task 8.
- Briefing Agent: Task 9.
- MCP tool surface: Task 10.
- Feishu delivery: Task 11.
- Internal console: Task 13.
- MVP smoke path from collection to briefing: Task 15.

## Final Verification

Before claiming implementation complete, run:

```powershell
ruff check .
pytest -v
python scripts/smoke_mvp.py
```

Expected:

```text
ruff check . exits successfully
pytest reports all tests passed
smoke script prints collection, analysis_id, prediction_id, briefing_id
```
