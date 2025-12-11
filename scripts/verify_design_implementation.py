"""
Design Philosophy Verification Script

DESIGN.md에 정의된 핵심 설계 원칙들이 실제로 구현되었는지 검증합니다.

Usage:
    python scripts/verify_design_implementation.py
"""

import psycopg2
import os
from pathlib import Path
from typing import Dict, List, Any
import json

class DesignVerifier:
    def __init__(self):
        self.postgres_url = 'postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology'
        self.results = {
            "passed": [],
            "failed": [],
            "warnings": []
        }

    def connect_db(self):
        return psycopg2.connect(self.postgres_url)

    def verify_all(self):
        """모든 설계 원칙 검증"""
        print("="*80)
        print("DESIGN PHILOSOPHY VERIFICATION")
        print("="*80)
        print()

        # 1. Database Schema
        print("📊 [1/6] Verifying Database Schema...")
        self.verify_schema()
        print()

        # 2. Parser Implementation
        print("📄 [2/6] Verifying Parser Implementation...")
        self.verify_parsers()
        print()

        # 3. Coverage Mapping
        print("🔗 [3/6] Verifying Coverage Mapping...")
        self.verify_coverage_mapping()
        print()

        # 4. structured_data Usage
        print("💾 [4/6] Verifying structured_data Usage...")
        self.verify_structured_data()
        print()

        # 5. Hybrid Search Components
        print("🔍 [5/6] Verifying Hybrid Search Components...")
        self.verify_hybrid_search()
        print()

        # 6. Actual Data Validation
        print("✅ [6/6] Verifying Actual Data...")
        self.verify_actual_data()
        print()

        # Summary
        self.print_summary()

    def verify_schema(self):
        """DB 스키마 검증"""
        conn = self.connect_db()
        cur = conn.cursor()

        # 원칙 1: ProductVariant Hierarchy (DESIGN.md 섹션 3.1 #2)
        print("  Principle 1: ProductVariant Hierarchy")
        try:
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'product_variant'
                ORDER BY ordinal_position
            """)
            columns = cur.fetchall()

            if not columns:
                self.results["failed"].append({
                    "principle": "ProductVariant Hierarchy",
                    "reason": "product_variant table does not exist"
                })
                print("    ❌ FAILED: product_variant table not found")
            else:
                required_cols = ['target_gender', 'target_age_range']
                col_names = [c[0] for c in columns]
                missing = [c for c in required_cols if c not in col_names]

                if missing:
                    self.results["failed"].append({
                        "principle": "ProductVariant Hierarchy",
                        "reason": f"Missing columns: {missing}"
                    })
                    print(f"    ❌ FAILED: Missing columns {missing}")
                else:
                    self.results["passed"].append("ProductVariant Hierarchy")
                    print(f"    ✅ PASSED: product_variant table with {len(columns)} columns")
        except Exception as e:
            self.results["failed"].append({
                "principle": "ProductVariant Hierarchy",
                "reason": str(e)
            })
            print(f"    ❌ ERROR: {e}")

        # 원칙 2: DocumentClause.structured_data (DESIGN.md 섹션 3.3)
        print("  Principle 2: DocumentClause.structured_data (JSONB)")
        try:
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'document_clause'
                  AND column_name IN ('clause_type', 'structured_data')
            """)
            columns = dict(cur.fetchall())

            if 'structured_data' not in columns:
                self.results["failed"].append({
                    "principle": "structured_data JSONB",
                    "reason": "structured_data column not found"
                })
                print("    ❌ FAILED: structured_data column not found")
            elif columns['structured_data'] != 'jsonb':
                self.results["failed"].append({
                    "principle": "structured_data JSONB",
                    "reason": f"Wrong type: {columns['structured_data']}, expected jsonb"
                })
                print(f"    ❌ FAILED: Wrong type {columns['structured_data']}")
            else:
                self.results["passed"].append("structured_data JSONB")
                print("    ✅ PASSED: structured_data column (jsonb)")

            if 'clause_type' not in columns:
                self.results["failed"].append({
                    "principle": "clause_type field",
                    "reason": "clause_type column not found"
                })
                print("    ❌ FAILED: clause_type column not found")
            else:
                self.results["passed"].append("clause_type field")
                print("    ✅ PASSED: clause_type column")
        except Exception as e:
            self.results["failed"].append({
                "principle": "structured_data JSONB",
                "reason": str(e)
            })
            print(f"    ❌ ERROR: {e}")

        # 원칙 3: ClauseCoverage Mapping Table (DESIGN.md 섹션 3.3)
        print("  Principle 3: ClauseCoverage M:N Mapping")
        try:
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'clause_coverage'
                ORDER BY ordinal_position
            """)
            columns = cur.fetchall()

            if not columns:
                self.results["failed"].append({
                    "principle": "ClauseCoverage Mapping",
                    "reason": "clause_coverage table does not exist"
                })
                print("    ❌ FAILED: clause_coverage table not found")
            else:
                col_names = [c[0] for c in columns]
                # Note: DESIGN.md says 'confidence' but actual implementation uses 'relevance_score'
                required_cols = ['clause_id', 'coverage_id', 'extraction_method']
                missing = [c for c in required_cols if c not in col_names]

                if missing:
                    self.results["failed"].append({
                        "principle": "ClauseCoverage Mapping",
                        "reason": f"Missing columns: {missing}"
                    })
                    print(f"    ❌ FAILED: Missing columns {missing}")
                else:
                    # Check if either 'confidence' or 'relevance_score' exists
                    if 'confidence' not in col_names and 'relevance_score' not in col_names:
                        self.results["warnings"].append({
                            "principle": "ClauseCoverage Mapping",
                            "warning": "Neither 'confidence' nor 'relevance_score' found (DESIGN.md specifies 'confidence')"
                        })
                        print("    ⚠️  WARNING: No confidence/relevance_score column")
                    else:
                        self.results["passed"].append("ClauseCoverage Mapping")
                        print(f"    ✅ PASSED: clause_coverage table with {len(columns)} columns")
        except Exception as e:
            self.results["failed"].append({
                "principle": "ClauseCoverage Mapping",
                "reason": str(e)
            })
            print(f"    ❌ ERROR: {e}")

        # 원칙 4: parent_coverage_id (최근 추가된 기능)
        print("  Principle 4: Coverage Hierarchy (parent_coverage_id)")
        try:
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'coverage'
                  AND column_name = 'parent_coverage_id'
            """)
            result = cur.fetchone()

            if result:
                self.results["passed"].append("Coverage Hierarchy")
                print("    ✅ PASSED: parent_coverage_id column exists")
            else:
                self.results["warnings"].append({
                    "principle": "Coverage Hierarchy",
                    "warning": "parent_coverage_id not found (may not be in original DESIGN.md)"
                })
                print("    ⚠️  WARNING: parent_coverage_id not found")
        except Exception as e:
            print(f"    ❌ ERROR: {e}")

        cur.close()
        conn.close()

    def verify_parsers(self):
        """파서 구현 검증 (DESIGN.md 섹션 3.1 #1: Hybrid Document Model)"""
        base_path = Path('/Users/cheollee/insurance-ontology-v2/ingestion/parsers')

        print("  Principle: Hybrid Document Model (3 parser types)")

        required_parsers = {
            'text_parser.py': 'TextParser (약관)',
            'table_parser.py': 'TableParser (가입설계서)',
            'hybrid_parser.py': 'HybridParser (사업방법서, 상품요약서)'
        }

        for parser_file, description in required_parsers.items():
            parser_path = base_path / parser_file
            if parser_path.exists():
                self.results["passed"].append(f"Parser: {parser_file}")
                print(f"    ✅ FOUND: {description}")
            else:
                self.results["failed"].append({
                    "principle": "Hybrid Document Model",
                    "reason": f"Missing {parser_file}"
                })
                print(f"    ❌ MISSING: {description}")

    def verify_coverage_mapping(self):
        """Coverage Mapping 3-tier 검증 (DESIGN.md 섹션 4.3)"""
        link_clauses_path = Path('/Users/cheollee/insurance-ontology-v2/ingestion/link_clauses.py')

        print("  Principle: 3-Tier Coverage Mapping (exact/fuzzy/llm)")

        if not link_clauses_path.exists():
            self.results["failed"].append({
                "principle": "3-Tier Coverage Mapping",
                "reason": "link_clauses.py not found"
            })
            print("    ❌ FAILED: link_clauses.py not found")
            return

        content = link_clauses_path.read_text()

        # Check for 3 tiers
        tiers = {
            'exact_match': 'Tier 1: Exact Match',
            'fuzzy_match': 'Tier 2: Fuzzy Match',
            'llm': 'Tier 3: LLM Fallback'
        }

        found_tiers = []
        for tier_key, tier_name in tiers.items():
            if tier_key in content.lower() or tier_key.replace('_', '') in content.lower():
                found_tiers.append(tier_name)
                print(f"    ✅ FOUND: {tier_name}")

        if len(found_tiers) >= 2:  # At least 2 tiers
            self.results["passed"].append("3-Tier Coverage Mapping")
        else:
            self.results["warnings"].append({
                "principle": "3-Tier Coverage Mapping",
                "warning": f"Only {len(found_tiers)}/3 tiers found"
            })
            print(f"    ⚠️  WARNING: Only {len(found_tiers)}/3 tiers found")

    def verify_structured_data(self):
        """structured_data 실제 사용 검증"""
        conn = self.connect_db()
        cur = conn.cursor()

        print("  Checking structured_data usage in document_clause")

        try:
            # Count clauses with structured_data
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(structured_data) as with_data,
                    COUNT(CASE WHEN structured_data->>'coverage_amount' IS NOT NULL THEN 1 END) as with_amount,
                    COUNT(CASE WHEN structured_data->>'coverage_name' IS NOT NULL THEN 1 END) as with_name
                FROM document_clause
            """)

            result = cur.fetchone()
            total, with_data, with_amount, with_name = result

            print(f"    Total clauses: {total:,}")
            print(f"    With structured_data: {with_data:,} ({with_data/total*100:.1f}%)")
            print(f"    With coverage_amount: {with_amount:,}")
            print(f"    With coverage_name: {with_name:,}")

            if with_data == 0:
                self.results["failed"].append({
                    "principle": "structured_data Usage",
                    "reason": "No clauses have structured_data populated"
                })
                print("    ❌ FAILED: No structured_data found")
            elif with_data < total * 0.01:  # Less than 1%
                self.results["warnings"].append({
                    "principle": "structured_data Usage",
                    "warning": f"Very low usage: {with_data}/{total} ({with_data/total*100:.1f}%)"
                })
                print(f"    ⚠️  WARNING: Low usage ({with_data/total*100:.1f}%)")
            else:
                self.results["passed"].append("structured_data Usage")
                print(f"    ✅ PASSED: {with_data:,} clauses with structured_data")

            # Sample structured_data
            cur.execute("""
                SELECT structured_data
                FROM document_clause
                WHERE structured_data IS NOT NULL
                LIMIT 3
            """)
            samples = cur.fetchall()

            if samples:
                print("    Sample structured_data:")
                for i, (data,) in enumerate(samples, 1):
                    print(f"      [{i}] Keys: {list(data.keys())}")

        except Exception as e:
            self.results["failed"].append({
                "principle": "structured_data Usage",
                "reason": str(e)
            })
            print(f"    ❌ ERROR: {e}")

        cur.close()
        conn.close()

    def verify_hybrid_search(self):
        """Hybrid Search 구성 요소 검증 (DESIGN.md 섹션 3.1 #3, 4.2)"""
        base_path = Path('/Users/cheollee/insurance-ontology-v2')

        components = {
            'ontology/nl_mapping.py': 'NL Mapper (query → entities)',
            'retrieval/hybrid_retriever.py': 'Hybrid Retriever (filtered vector search)',
            'retrieval/context_assembly.py': 'Context Assembly',
            'retrieval/prompts.py': 'LLM Prompts'
        }

        print("  Principle: Coverage-Centric Search Components")

        for component_path, description in components.items():
            full_path = base_path / component_path
            if full_path.exists():
                self.results["passed"].append(f"Component: {component_path}")
                print(f"    ✅ FOUND: {description}")
            else:
                self.results["warnings"].append({
                    "principle": "Coverage-Centric Search",
                    "warning": f"Missing {component_path}"
                })
                print(f"    ⚠️  MISSING: {description}")

    def verify_actual_data(self):
        """실제 데이터 검증"""
        conn = self.connect_db()
        cur = conn.cursor()

        print("  Validating actual data in database")

        # 1. Documents
        cur.execute("SELECT COUNT(*) FROM document")
        doc_count = cur.fetchone()[0]
        print(f"    Documents: {doc_count} (target: 38)")

        # 2. Clauses
        cur.execute("SELECT COUNT(*) FROM document_clause")
        clause_count = cur.fetchone()[0]
        print(f"    Clauses: {clause_count:,} (target: ~80,000)")

        # 3. Coverages
        cur.execute("SELECT COUNT(*) FROM coverage")
        coverage_count = cur.fetchone()[0]
        print(f"    Coverages: {coverage_count} (target: ~240-400)")

        # 4. ClauseCoverage mappings
        cur.execute("SELECT COUNT(*) FROM clause_coverage")
        mapping_count = cur.fetchone()[0]
        print(f"    Clause→Coverage mappings: {mapping_count:,}")

        # 5. clause_type distribution
        cur.execute("""
            SELECT clause_type, COUNT(*)
            FROM document_clause
            WHERE clause_type IS NOT NULL
            GROUP BY clause_type
            ORDER BY COUNT(*) DESC
        """)
        clause_types = cur.fetchall()

        if clause_types:
            print("    Clause types:")
            for ctype, count in clause_types:
                print(f"      - {ctype}: {count:,}")

        # 6. Parent-child coverage relationships
        cur.execute("""
            SELECT COUNT(*)
            FROM coverage
            WHERE parent_coverage_id IS NOT NULL
        """)
        child_coverage_count = cur.fetchone()[0]
        print(f"    Child coverages (with parent): {child_coverage_count}")

        # Validation
        if doc_count < 30:
            self.results["warnings"].append({
                "data": "Documents",
                "warning": f"Only {doc_count} documents (target: 38)"
            })
        else:
            self.results["passed"].append(f"Documents: {doc_count}")

        if clause_count < 50000:
            self.results["warnings"].append({
                "data": "Clauses",
                "warning": f"Only {clause_count:,} clauses (target: ~80,000)"
            })
        else:
            self.results["passed"].append(f"Clauses: {clause_count:,}")

        if coverage_count < 200:
            self.results["warnings"].append({
                "data": "Coverages",
                "warning": f"Only {coverage_count} coverages (target: 240-400)"
            })
        else:
            self.results["passed"].append(f"Coverages: {coverage_count}")

        cur.close()
        conn.close()

    def print_summary(self):
        """검증 결과 요약"""
        print("="*80)
        print("VERIFICATION SUMMARY")
        print("="*80)
        print()

        passed = len(self.results["passed"])
        failed = len(self.results["failed"])
        warnings = len(self.results["warnings"])
        total = passed + failed + warnings

        print(f"✅ PASSED:   {passed}/{total}")
        print(f"❌ FAILED:   {failed}/{total}")
        print(f"⚠️  WARNINGS: {warnings}/{total}")
        print()

        if self.results["failed"]:
            print("FAILED CHECKS:")
            for fail in self.results["failed"]:
                print(f"  ❌ {fail.get('principle', 'Unknown')}: {fail['reason']}")
            print()

        if self.results["warnings"]:
            print("WARNINGS:")
            for warn in self.results["warnings"]:
                principle = warn.get('principle') or warn.get('data', 'Unknown')
                warning = warn.get('warning', 'No detail')
                print(f"  ⚠️  {principle}: {warning}")
            print()

        # Overall verdict
        if failed == 0 and warnings == 0:
            print("🎉 ALL CHECKS PASSED! Design principles fully implemented.")
        elif failed == 0:
            print("✅ MOSTLY COMPLIANT: All critical checks passed, minor warnings only.")
        else:
            print("⚠️  IMPLEMENTATION GAPS: Some design principles not fully implemented.")

        print("="*80)


if __name__ == '__main__':
    verifier = DesignVerifier()
    verifier.verify_all()
