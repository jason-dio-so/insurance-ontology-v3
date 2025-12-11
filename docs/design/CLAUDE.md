# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Insurance ontology + Hybrid-RAG system for Korean insurance documents. Parses insurance terms, business specifications, and proposal documents into structured ontology + relational DB (PostgreSQL) + graph DB (Neo4j) + vector index, enabling natural language queries, product comparison, and plan validation.

## Common Commands

```bash
# Start services (Postgres, Neo4j, Qdrant)
./scripts/start_hybrid_services.sh

# Initialize databases
docker run --rm --network insurance-ontology_default \
  -v $PWD:/app -w /app \
  -e POSTGRES_URL=postgresql://postgres:postgres@postgres:5432/insurance_ontology \
  python:3.12 bash -c "pip install -r requirements.txt && ./scripts/init_db.sh"

# Load sample documents
./scripts/load_sample.sh

# Phase 2: Entity Extraction
python -m ingestion.coverage_pipeline --carrier all    # Extract coverages
python -m ingestion.extract_benefits                   # Extract benefits
python -m ingestion.load_disease_codes                 # Load disease codes
python -m ingestion.link_clauses --method all          # Link clauses to coverages

# Phase 3: Graph Sync
python -m ingestion.graph_loader --all                 # Sync to Neo4j

# Phase 4: Build vector index (requires OPENAI_API_KEY)
python -m vector_index.build_index

# Run tests
pytest tests/                    # all tests
pytest tests/test_pipeline.py   # single file
pytest tests/test_pipeline.py::test_function_name  # single test

# CLI commands
python -m api.cli docs --limit 5
python -m api.cli search "암진단시 보장" --limit 3
python -m api.cli hybrid "마이헬스 1종 소액암 보장?"
python -m api.cli plan-report --company 삼성화재 --product "..." --format text
```

## Architecture

### Data Flow
```
PDF Documents → ingestion/pipeline.py (extract clauses)
             → db_loader.py (Postgres: document, document_clause)
             → graph_loader.py (Neo4j nodes/relationships)
             → vector_index/build_index.py (embeddings → pgvector/Qdrant)
```

### Core Modules

- **ingestion/**: PDF parsing and data extraction
  - `ingest_documents_v2.py`: Extract page-level clauses, infer document type/company/product
    - **Table Extraction**: Uses `tabula.read_pdf(pdf_path, pages='all')` for ALL carriers (동일)
    - **Table Parsing**: Uses carrier-specific parsers (보험사별)
  - `parsers/`: Table parsing modules
    - `parser_factory.py`: Routes to carrier-specific parser based on company_code
    - `carrier_parsers/`: 8 carrier-specific parsers (Samsung, DB, Lotte, Meritz, KB, Hanwha, Hyundai, Heungkuk)
  - `coverage_pipeline.py`: Parse coverage metadata from proposal documents (Phase 2.1)
  - `extract_benefits.py`: Extract benefit information from table_row clauses (Phase 2.4)
  - `load_disease_codes.py`: Load disease code sets and codes (Phase 2.2)
  - `link_clauses.py`: Map clauses to coverage IDs using 3-tier matching (Phase 2.3)
  - `graph_loader.py`: Sync PostgreSQL entities to Neo4j graph (Phase 3)

- **api/cli.py**: Main query interface with hybrid search (ontology mapping + vector retrieval + LLM)

- **ontology/nl_mapping.py**: Map natural language queries to ontology entities (Coverage, DiseaseCodeSet, Product)

### Database Schema (db/postgres/schema.sql)

Key tables: `company`, `product`, `product_variant`, `coverage`, `benefit`, `condition`, `exclusion`, `disease_code_set`, `disease_code`, `refund_policy`, `coverage_schedule`, `plan`, `plan_coverage`, `document`, `document_clause`, `clause_embedding`

### Hybrid Query Pipeline

1. NL mapper extracts entity mentions from query
2. Fetch matching coverage IDs from Postgres/Neo4j
3. Vector search clauses filtered by coverage_id
4. LLM generates answer with structured facts + clause references

### Full Ingestion Pipeline Order

**Current Implementation (Phases 0-3 Complete):**
```
Phase 0: Design & Analysis ✅
Phase 1: Document Ingestion ✅
  → ingest_documents_v2.py (38 docs → 80,521 clauses)

Phase 2: Entity Extraction ✅
  → coverage_pipeline.py (240 coverages)
  → extract_benefits.py (240 benefits)
  → load_disease_codes.py (9 sets, 131 codes)
  → link_clauses.py --method all (480 mappings: exact + fuzzy)

Phase 3: Graph Sync ✅
  → graph_loader.py --all (640 nodes, 623 relationships)

Phase 4: Vector Index (Next)
  → vector_index.build_index (embeddings for 80,521 clauses)
```

### Key Entity Relationships

```
Company → Product → ProductVariant → Coverage → Benefit
                                   ↓           ↓
                              Condition    RiskEvent
                              Exclusion    DiseaseCodeSet
                              RefundPolicy ProcedureCodeSet

Plan → PlanCoverage (with schedule/condition_facts/refund_facts JSON)
Document → DocumentClause → ClauseEmbedding (with coverage_id in metadata)
```

### Document Structure Variations by Carrier

**Standard 4-Document Set**:
- Terms (약관)
- Business Specification (사업방법서)
- Product Summary (상품요약서)
- Proposal (가입설계서)

**Carrier-Specific Variations**:

| Carrier | Document Structure | Total Docs | Notes |
|---------|-------------------|------------|-------|
| **Samsung Fire** | • Business Spec → "사업설명서"<br>• Product Summary + **Easy Summary** (쉬운요약서) | 5 | Extra consumer-friendly summary |
| **DB Insurance** | • Proposal split by age:<br>  - Age ≤40<br>  - Age ≥41 | 5 | Age-based proposal templates |
| **Lotte Insurance** | • **All documents split by gender**:<br>  - Terms: Male / Female<br>  - Business Spec: Male / Female<br>  - Product Summary: Male / Female<br>  - Proposal: Male / Female | **8** | Complete gender-based separation |

**Implementation Strategy**:
- Keep standard `doc_type`: `terms`, `business_spec`, `product_summary`, `proposal`
- Handle variations via metadata:
  - `doc_subtype`: `easy_summary`, `age_40_under`, `age_41_over`, `male`, `female`
  - `document.attributes` (JSONB): `{target_age_range: "≤40", target_gender: "male"}`

**When adding documents**:
```bash
# Example: Samsung Easy Summary
python -m scripts.convert_documents \
  --company-code samsung \
  --metadata-override '{"doc_subtype": "easy_summary"}'

# Example: DB Age-specific Proposal
python -m scripts.convert_documents \
  --document-id db-realsok-proposal-v1-20250901-age40under \
  --metadata-override '{"doc_subtype": "age_40_under", "attributes": {"target_age_range": "≤40"}}'
```

### Carrier Onboarding Checklist

To add a new insurance carrier (e.g., KB, 메리츠):
1. **Document Collection**:
   - Identify carrier's document structure (4-doc standard or variations)
   - Add PDFs + metadata JSON to `examples/<carrier>/`
   - Note any naming differences (e.g., "사업설명서" vs "사업방법서")
   - Document age/gender/variant splits in metadata
2. Run `load_sample.sh` with `INGESTION_DOC_FILTER=<carrier>`
3. Run `load_coverage.sh <carrier>` + prepare disease/benefit CSVs
4. Execute `refresh_section_types`, `link_clauses`, `condition_loader`, `refund_loader`
5. Run `plan_validator --persist` on sample proposals
6. Rebuild embeddings: `python -m vector_index.build_index`
7. Sync Neo4j: `python -m ingestion.graph_loader --sync-coverage --sync-benefits`
8. Run Hybrid smoke tests to verify

## Code Style

- snake_case for files, functions, variables, DB tables/columns, graph nodes/relationships
- PascalCase for class names
- Format with `black`
- All new features require tests in `tests/`

## Environment Variables

Key vars in `.env`:
- `POSTGRES_URL`: PostgreSQL connection string
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`: Neo4j connection
- `OPENAI_API_KEY`: For embeddings and LLM responses
- `VECTOR_BACKEND`: `pgvector` or `qdrant`
- `INGESTION_DOC_FILTER`, `INGESTION_MAX_DOCS`, `INGESTION_MAX_PAGES`: Control document ingestion scope

## Design Documentation

**IMPORTANT**: Always refer to `ONTOLOGY_DESIGN.md` for:
- Document roles and structure (약관, 사업방법서, 상품요약서, 가입설계서)
- Core ontology entities and relationships
- Design philosophy and extensibility principles
- Data integration strategy across Postgres/Neo4j/Vector
- **Phase 0-7 Roadmap**: Requirements, ingestion pipeline, IE implementation, hybrid retrieval, and business features
  - Phase 4: Information Extraction (IE) pipeline details
  - Phase 5: Hybrid Retrieval orchestrator design
  - Phase 6: Insurance agent/recruiter features (상품 비교, QA bot, 설계 검증, 민원 알림)

This design document is the single source of truth for ontology architecture and implementation roadmap.

## Important Notes

- Run DB operations via Docker containers on `insurance-ontology_default` network (host ports may be blocked)
- Schema changes require: migration + `scripts/init_db.sh` + data reload + index rebuild + test update
- `/examples/` contains only public/anonymized documents - never commit PII or customer data
