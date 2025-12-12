# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Insurance ontology + Hybrid-RAG system for Korean insurance documents. Parses insurance terms, business specifications, and proposal documents into structured ontology + relational DB (PostgreSQL) + graph DB (Neo4j) + vector index (pgvector), enabling natural language queries, product comparison, and plan validation.

**Status**: Phase 0-5 완료 ✅ (86% QA accuracy)

## Common Commands

```bash
# Start services (PostgreSQL, Neo4j)
./scripts/start_hybrid_services.sh

# Initialize databases
./scripts/init_db.sh
./scripts/init_neo4j.sh

# Phase 1: Document Ingestion (완료 ✅)
python -m ingestion.ingest_v3

# Phase 2: Entity Extraction (완료 ✅)
python -m ingestion.coverage_pipeline --carrier all    # Extract coverages
python -m ingestion.extract_benefits                   # Extract benefits
python -m ingestion.load_disease_codes                 # Load disease codes
python -m ingestion.link_clauses --method all          # Link clauses to coverages

# Phase 3: Graph Sync (완료 ✅)
python -m ingestion.graph_loader --all                 # Sync to Neo4j

# Phase 4: Build vector index (완료 ✅, requires OPENAI_API_KEY)
python -m vector_index.build_index

# Phase 5: Test Hybrid RAG (완료 ✅)
python scripts/evaluate_qa.py --qa-set data/gold_qa_set_50.json

# Run tests
pytest tests/                    # all tests
pytest tests/test_pipeline.py   # single file

# CLI commands
python -m api.cli search "암진단시 보장" --limit 5
python -m api.cli hybrid "삼성화재 암 진단금 3000만원"
```

## Architecture

### Data Flow
```
38 PDF Documents (8 carriers)
      ↓
Phase 1: ingestion/ingest_v3.py
  → Parser routing (Text/Table/Hybrid V2)
  → PostgreSQL: document (38), document_clause (134,844)
      ↓
Phase 2: Entity Extraction
  → coverage_pipeline.py: coverage (363)
  → extract_benefits.py: benefit (357)
  → load_disease_codes.py: disease_code_set (9), disease_code (131)
  → link_clauses.py: clause_coverage (4,903)
      ↓
Phase 3: ingestion/graph_loader.py
  → Neo4j: 640 nodes, 623 relationships
      ↓
Phase 4: vector_index/build_index.py
  → PostgreSQL pgvector: clause_embedding (134,644, 1.8GB)
  → Model: OpenAI text-embedding-3-small (1536d)
      ↓
Phase 5: retrieval/hybrid_retriever.py
  → 5-tier fallback search + LLM (GPT-4o-mini)
```

### Core Modules

- **ingestion/**: PDF parsing and data extraction
  - `ingest_v3.py`: Main ingestion pipeline
    - Parser routing: Text (약관) / Table (가입설계서) / Hybrid V2 (사업방법서, 상품요약서)
    - Output: document_clause (134,844 clauses)
  - `parsers/`: Parsing modules
    - `text_parser.py`: Article-based parsing for terms
    - `table_parser.py`: Carrier-specific table parsing for proposals
    - `hybrid_parser_v2.py`: Mixed text+table parsing
    - `parser_factory.py`: Routes to carrier-specific parser
  - `coverage_pipeline.py`: Extract coverage metadata (Phase 2.1)
  - `extract_benefits.py`: Extract benefits from table_row clauses (Phase 2.4)
  - `load_disease_codes.py`: Load disease code sets (Phase 2.2)
  - `link_clauses.py`: Multi-tier clause→coverage mapping (Phase 2.3)
  - `graph_loader.py`: PostgreSQL → Neo4j sync (Phase 3)

- **vector_index/**: Embedding generation
  - `build_index.py`: Generate embeddings using OpenAI API
  - `openai_embedder.py`: OpenAI text-embedding-3-small wrapper
  - `retriever.py`: Vector search utilities

- **retrieval/**: Hybrid RAG system (Phase 5)
  - `hybrid_retriever.py`: 5-tier fallback vector search
  - `context_assembly.py`: Coverage/benefit enrichment
  - `prompts.py`: System prompt v5
  - `llm_client.py`: GPT-4o-mini wrapper

- **ontology/nl_mapping.py**: Natural language → entity mapping

- **api/cli.py**: Command-line interface

### Database Schema

**PostgreSQL** (primary storage):
- **Insurance Domain**: `company`, `product`, `product_variant`, `coverage`, `benefit`, `condition`, `exclusion`
- **Document Domain**: `document`, `document_clause`, `clause_embedding`
- **Mapping**: `clause_coverage`, `coverage_group`, `coverage_category`
- **Disease Codes**: `disease_code_set`, `disease_code`

**Neo4j** (graph queries):
- Nodes: Company, Product, Coverage, Benefit, DiseaseCodeSet, DiseaseCode
- Relationships: COVERS, OFFERS, HAS_COVERAGE, CONTAINS, APPLIES_TO

### Current Data Scale (as of Phase 5)

| Entity | Count | Notes |
|--------|-------|-------|
| Documents | 38 | 8 carriers |
| Document Clauses | 134,844 | article: 129,667, text_block: 4,286, table_row: 891 |
| Coverages | 363 | 6 parent coverages, 52 child coverages |
| Benefits | 357 | diagnosis, surgery, treatment, death, other |
| Clause-Coverage Mappings | 4,903 | exact: 829, fuzzy: 185, parent_linking: 3,889 |
| Embeddings | 134,644 | 1.8GB, 1536d |
| Neo4j Nodes | 640 | Synced from PostgreSQL |
| Neo4j Relationships | 623 | Synced from PostgreSQL |

### Hybrid Query Pipeline (Phase 5)

**Example**: "삼성화재 암 진단금 3,000만원"

1. **NL Mapper** (`ontology/nl_mapping.py`)
   - Extract entities: company, coverage, amount

2. **Coverage Query Detection**
   - Detect coverage keywords → Prioritize proposal + table_row

3. **5-Tier Fallback Vector Search** (`retrieval/hybrid_retriever.py`)
   - Tier 0: proposal + table_row (기본)
   - Tier 1: proposal only
   - Tier 2: business_spec + table_row
   - Tier 3: business_spec only
   - Tier 4: terms
   - Tier 5: all doc_types

4. **SQL Vector Search**
   - Korean amount parsing: "3,000만원" → 30000000
   - Metadata filtering: company_id, doc_type, clause_type, amount

5. **Context Assembly** (`retrieval/context_assembly.py`)
   - Enrich with coverage/benefit metadata
   - Format citations: [1], [2], ...

6. **LLM Answer** (`retrieval/llm_client.py`)
   - Model: GPT-4o-mini (temp=0.1)
   - Returns structured answer with citations

### Key Entity Relationships

```
Company → Product → ProductVariant → Coverage → Benefit
                                   ↓           ↓
                              Condition    DiseaseCodeSet
                              Exclusion

Document → DocumentClause → ClauseEmbedding
         ↓                ↓
    ProductVariant   ClauseCoverage → Coverage
```

### Document Structure Variations by Carrier

**Standard 4-Document Set**:
- Terms (약관)
- Business Specification (사업방법서)
- Product Summary (상품요약서)
- Proposal (가입설계서)

**Carrier-Specific Variations**:

| Carrier | Variation | Total Docs |
|---------|-----------|------------|
| **Samsung Fire** | + Easy Summary (쉬운요약서) | 5 |
| **DB Insurance** | Proposal split by age (≤40 / ≥41) | 5 |
| **Lotte Insurance** | All documents split by gender (Male / Female) | 8 |
| **Meritz** | Business Spec → "사업설명서" | 4 |
| **Others** | Standard 4-doc set | 4 each |

**Metadata Handling**:
- `doc_type`: `terms`, `business_spec`, `product_summary`, `proposal`
- `doc_subtype`: `easy_summary`, `age_40_under`, `age_41_over`, `male`, `female`
- `document.attributes` (JSONB): `{target_age_range: "≤40", target_gender: "male"}`

## Code Style

- snake_case for files, functions, variables, DB tables/columns, graph nodes/relationships
- PascalCase for class names
- Format with `black`
- All new features require tests in `tests/`

## Environment Variables

Key vars in `.env`:
- `POSTGRES_URL`: PostgreSQL connection string
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`: Neo4j connection
- `OPENAI_API_KEY`: For embeddings (text-embedding-3-small) and LLM (GPT-4o-mini)
- `EMBEDDING_BACKEND`: `openai` (default, recommended)
- `INGESTION_DOC_FILTER`, `INGESTION_MAX_DOCS`, `INGESTION_MAX_PAGES`: Control document ingestion scope (optional)

## Design Documentation

**Primary Reference**: `docs/design/DESIGN.md`

Key sections:
- **Section 3**: Data Model v2 (E-R diagram, schema)
- **Section 4**: Pipeline Architecture (6-phase implementation)
- **Section 10**: Phase 3-5 implementation details
- **Section 11**: System summary (data scale, performance)

This design document is the single source of truth for ontology architecture and implementation roadmap.

## Important Notes

- **Production Ready**: Phase 0-5 완료, 86% QA accuracy (43/50 queries)
- **Vector Backend**: OpenAI text-embedding-3-small (1536d) via pgvector
- **LLM**: GPT-4o-mini (temperature=0.1)
- **Zero-Result Prevention**: 5-tier fallback search ensures 0% zero-result rate
- **Coverage Hierarchy**: Parent-child coverage linking for better clause retrieval
- **Korean Amount Parsing**: SQL-based parsing for "3,000만원" → 30000000

## Next Steps (Phase 6)

- [ ] Production API deployment
- [ ] Frontend integration (React InfoQueryBuilder)
- [ ] Performance optimization (90%+ accuracy target)
- [ ] Business features: 상품 비교, 설계서 검증, QA Bot
