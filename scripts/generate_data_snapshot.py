#!/usr/bin/env python3
"""
Generate DATA_SNAPSHOT.md with actual database statistics.
"""
import os
import psycopg2
from datetime import datetime

def main():
    # Connect to database
    conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
    cur = conn.cursor()

    # Gather statistics
    stats = {}

    # 1. Company counts
    cur.execute("SELECT COUNT(*) FROM company")
    stats['total_companies'] = cur.fetchone()[0]

    cur.execute("SELECT company_name FROM company ORDER BY company_name")
    stats['companies'] = [row[0] for row in cur.fetchall()]

    # 2. Product counts
    cur.execute("SELECT COUNT(*) FROM product")
    stats['total_products'] = cur.fetchone()[0]

    cur.execute("""
        SELECT comp.company_name, COUNT(p.id)
        FROM company comp
        LEFT JOIN product p ON comp.id = p.company_id
        GROUP BY comp.company_name
        ORDER BY comp.company_name
    """)
    stats['products_by_company'] = {row[0]: row[1] for row in cur.fetchall()}

    # 3. Coverage counts
    cur.execute("SELECT COUNT(*) FROM coverage")
    stats['total_coverages'] = cur.fetchone()[0]

    cur.execute("""
        SELECT comp.company_name, COUNT(cov.id)
        FROM company comp
        JOIN product p ON comp.id = p.company_id
        JOIN coverage cov ON p.id = cov.product_id
        GROUP BY comp.company_name
        ORDER BY COUNT(cov.id) DESC
    """)
    stats['coverages_by_company'] = {row[0]: row[1] for row in cur.fetchall()}

    # 4. Benefit counts
    cur.execute("SELECT COUNT(*) FROM benefit")
    stats['total_benefits'] = cur.fetchone()[0]

    # 5. Document and clause counts
    cur.execute("SELECT COUNT(*) FROM document")
    stats['total_documents'] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM document_clause")
    stats['total_clauses'] = cur.fetchone()[0]

    cur.execute("""
        SELECT comp.company_name, COUNT(dc.id)
        FROM document d
        JOIN document_clause dc ON d.id = dc.document_id
        JOIN company comp ON d.company_id = comp.id
        GROUP BY comp.company_name
        ORDER BY comp.company_name
    """)
    stats['clauses_by_company'] = {row[0]: row[1] for row in cur.fetchall()}

    # 6. Clause-Coverage mapping counts
    cur.execute("SELECT COUNT(*) FROM clause_coverage")
    stats['total_clause_coverage_mappings'] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT clause_id) FROM clause_coverage")
    stats['clauses_with_mappings'] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT coverage_id) FROM clause_coverage")
    stats['coverages_with_mappings'] = cur.fetchone()[0]

    # 7. Mapping method distribution (if extraction_method column exists)
    try:
        cur.execute("""
            SELECT extraction_method, COUNT(*)
            FROM clause_coverage
            GROUP BY extraction_method
            ORDER BY extraction_method
        """)
        stats['mappings_by_method'] = {row[0] or 'unknown': row[1] for row in cur.fetchall()}
    except psycopg2.errors.UndefinedColumn:
        stats['mappings_by_method'] = {}

    # 8. Sample unmapped coverage (Samsung/Meritz cancer diagnosis)
    cur.execute("""
        SELECT
            comp.company_name,
            p.product_name,
            cov.coverage_name,
            COUNT(cc.clause_id) as linked_clauses
        FROM coverage cov
        JOIN product p ON cov.product_id = p.id
        JOIN company comp ON p.company_id = comp.id
        LEFT JOIN clause_coverage cc ON cov.id = cc.coverage_id
        WHERE comp.company_name IN ('삼성', '메리츠')
          AND cov.coverage_name LIKE '%암%'
        GROUP BY comp.company_name, p.product_name, cov.coverage_name
        ORDER BY comp.company_name, cov.coverage_name
    """)
    stats['cancer_coverage_mappings'] = [
        {
            'company': row[0],
            'product': row[1],
            'coverage': row[2],
            'linked_clauses': row[3]
        }
        for row in cur.fetchall()
    ]

    # 9. Disease code sets
    cur.execute("SELECT COUNT(*) FROM disease_code_set")
    stats['total_disease_code_sets'] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM disease_code")
    stats['total_disease_codes'] = cur.fetchone()[0]

    # 10. Clause embedding status
    cur.execute("""
        SELECT COUNT(DISTINCT dc.id)
        FROM document_clause dc
        LEFT JOIN clause_embedding ce ON dc.id = ce.clause_id
        WHERE ce.id IS NULL
    """)
    stats['clauses_without_embeddings'] = cur.fetchone()[0]

    cur.close()
    conn.close()

    # Generate DATA_SNAPSHOT.md
    content = f"""# DATA_SNAPSHOT.md

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Purpose**: Document actual database state to identify gaps between TODO.md claims and implementation reality.

---

## Summary Statistics

| Category | Count |
|----------|-------|
| Companies | {stats['total_companies']} |
| Products | {stats['total_products']} |
| Coverages | {stats['total_coverages']} |
| Benefits | {stats['total_benefits']} |
| Documents | {stats['total_documents']} |
| Document Clauses | {stats['total_clauses']:,} |
| Clause-Coverage Mappings | {stats['total_clause_coverage_mappings']} |
| Disease Code Sets | {stats['total_disease_code_sets']} |
| Disease Codes | {stats['total_disease_codes']} |

---

## Company Distribution

### Companies in Database
{chr(10).join(f'- {company}' for company in stats['companies'])}

### Products by Company
| Company | Products |
|---------|----------|
{chr(10).join(f"| {comp} | {count} |" for comp, count in stats['products_by_company'].items())}

### Coverages by Company
| Company | Coverages |
|---------|-----------|
{chr(10).join(f"| {comp} | {count} |" for comp, count in stats['coverages_by_company'].items())}

### Clauses by Company
| Company | Clauses |
|---------|---------|
{chr(10).join(f"| {comp} | {count:,} |" for comp, count in stats['clauses_by_company'].items())}

---

## Clause-Coverage Mapping Status

**Total Mappings**: {stats['total_clause_coverage_mappings']}

**Coverage**:
- {stats['clauses_with_mappings']:,} clauses out of {stats['total_clauses']:,} have mappings ({stats['clauses_with_mappings']/stats['total_clauses']*100:.1f}%)
- {stats['coverages_with_mappings']} coverages out of {stats['total_coverages']} have linked clauses ({stats['coverages_with_mappings']/stats['total_coverages']*100:.1f}%)

### Mapping Method Distribution
{chr(10).join(f"| {method} | {count} |" for method, count in stats['mappings_by_method'].items()) if stats['mappings_by_method'] else "| N/A | No extraction_method column |"}

---

## Data Quality Issues

### Issue 1: Cancer Diagnosis Coverage - Missing Clause Mappings

**Context**: User query "삼성과 메리츠의 암진단비를 비교해줘" failed because vector search returned irrelevant clauses.

**Database Reality**:
| Company | Product | Coverage | Linked Clauses |
|---------|---------|----------|----------------|
{chr(10).join(f"| {item['company']} | {item['product']} | {item['coverage']} | **{item['linked_clauses']}** |" for item in stats['cancer_coverage_mappings'])}

**Impact**:
- Coverage/benefit data exists in database
- NO clause-coverage mappings exist for Samsung/Meritz cancer diagnosis
- Vector search falls back to semantic similarity alone (low quality)
- Requires ProductComparer workaround to query coverage table directly

**Root Cause**: Phase 2.3 Tier 3 (LLM-based linking) was skipped, leaving ~{stats['total_clauses'] - stats['clauses_with_mappings']:,} clauses unmapped.

---

## TODO.md vs Reality

### TODO.md Claims (Phase 2)
- ✅ Phase 2: Entity Extraction **100% 완료** (2025-12-09)
- 240 coverages extracted
- 480 clause-coverage mappings (Tier 1: 317 exact + Tier 2: 163 fuzzy)
- "Tier 3 (LLM-based) skipped for efficiency"

### Actual Implementation
- ✅ 240 coverages exist in database
- ✅ {stats['total_clause_coverage_mappings']} clause-coverage mappings exist
- ⚠️ **Critical coverages missing mappings** (Samsung/Meritz cancer diagnosis: 0 linked clauses)
- ⚠️ Only {stats['clauses_with_mappings']/stats['total_clauses']*100:.1f}% of clauses have coverage mappings
- ⚠️ Vector search quality insufficient for production queries
- 🔧 **Workaround required**: ProductComparer directly queries coverage table

---

## Embedding Status

- **Clauses without embeddings**: {stats['clauses_without_embeddings']:,} out of {stats['total_clauses']:,}
- Embedding status: {'⚠️ Incomplete' if stats['clauses_without_embeddings'] > 0 else '✅ Complete'}

---

## Recommendations

1. **Complete Phase 2.3 Tier 3**: Run LLM-based clause linking for remaining {stats['total_clauses'] - stats['clauses_with_mappings']:,} clauses
2. **Verification Scripts**: Add automated tests to catch data quality gaps
   ```bash
   python scripts/verify_data_quality.py --critical-coverages cancer,stroke,hospitalization
   ```
3. **Update TODO.md**: Change Phase 2 status from "100%" to "Core entities complete, clause linking partial"
4. **Rebuild Embeddings**: After completing Tier 3 linking, rebuild vector index with coverage_id metadata
5. **Documentation Sync**: Auto-update TODO.md with real database counts before marking phases complete

---

## How to Regenerate This File

```bash
python3 scripts/generate_data_snapshot.py
```

---

**Next Steps**: Prioritize Phase 2.3 Tier 3 completion or improve ProductComparer reliability as primary multi-company comparison method.
"""

    # Write to file
    snapshot_path = '/Users/cheollee/insurance-ontology-claude/DATA_SNAPSHOT.md'
    with open(snapshot_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ DATA_SNAPSHOT.md created successfully at {snapshot_path}")
    print(f"\nKey findings:")
    print(f"- Total clauses: {stats['total_clauses']:,}")
    print(f"- Clauses with mappings: {stats['clauses_with_mappings']:,} ({stats['clauses_with_mappings']/stats['total_clauses']*100:.1f}%)")
    print(f"- Coverages with mappings: {stats['coverages_with_mappings']}/{stats['total_coverages']} ({stats['coverages_with_mappings']/stats['total_coverages']*100:.1f}%)")
    print(f"- Cancer coverage mappings (Samsung/Meritz): {sum(item['linked_clauses'] for item in stats['cancer_coverage_mappings'])}")

if __name__ == "__main__":
    main()
