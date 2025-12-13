#!/usr/bin/env python3
"""
PDF Parsing Quality Audit Script

전체 보험사의 파싱 품질을 측정하고 문제를 진단합니다.

Usage:
    python scripts/audit_parsing_quality.py --output data/parsing_audit.json
    python scripts/audit_parsing_quality.py --format markdown
"""

import os
import json
import psycopg2
from typing import Dict, List, Any
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ParsingQualityAuditor:
    """파싱 품질 감사기"""

    def __init__(self, postgres_url: str = None):
        self.postgres_url = postgres_url or os.getenv("POSTGRES_URL")
        if not self.postgres_url:
            raise ValueError("POSTGRES_URL environment variable is required. Check .env file.")
        self.conn = psycopg2.connect(self.postgres_url)

    def audit_all_companies(self) -> Dict[str, Any]:
        """모든 보험사의 파싱 품질 감사"""
        companies = self._get_companies()
        results = {}

        for company in companies:
            company_name = company['name']
            company_code = company['code']

            print(f"\n📊 Auditing {company_name} ({company_code})...")

            results[company_code] = self.audit_company(company['id'], company_name)

        return results

    def audit_company(self, company_id: int, company_name: str) -> Dict[str, Any]:
        """특정 보험사의 파싱 품질 감사"""
        metrics = {
            "company_name": company_name,
            "total_clauses": 0,
            "by_doc_type": {},
            "issues": []
        }

        # 문서 타입별로 분석
        doc_types = ['proposal', 'business_spec', 'terms', 'product_summary']

        for doc_type in doc_types:
            doc_metrics = self._audit_doc_type(company_id, doc_type)
            if doc_metrics['total_clauses'] > 0:
                metrics['by_doc_type'][doc_type] = doc_metrics
                metrics['total_clauses'] += doc_metrics['total_clauses']

                # 이슈 수집
                if doc_metrics['issues']:
                    metrics['issues'].extend(doc_metrics['issues'])

        return metrics

    def _audit_doc_type(self, company_id: int, doc_type: str) -> Dict[str, Any]:
        """특정 문서 타입의 파싱 품질 감사"""
        with self.conn.cursor() as cur:
            # Table rows 조회
            cur.execute("""
                SELECT
                    dc.id,
                    dc.clause_text,
                    ce.metadata->>'clause_type' as clause_type,
                    ce.metadata->>'doc_type' as doc_type
                FROM document_clause dc
                JOIN clause_embedding ce ON dc.id = ce.clause_id
                JOIN document d ON dc.document_id = d.id
                WHERE d.company_id = %s
                  AND ce.metadata->>'doc_type' = %s
                  AND ce.metadata->>'clause_type' = 'table_row'
            """, (company_id, doc_type))

            rows = cur.fetchall()

            if not rows:
                return {
                    'total_clauses': 0,
                    'table_rows': 0,
                    'issues': []
                }

            # 분석
            total = len(rows)
            issues = []

            # Coverage name 품질 체크
            short_names = 0  # < 3자
            numeric_only = 0  # 숫자만
            missing_amount = 0  # 금액 정보 없음

            for row_id, clause_text, clause_type, doc_type_val in rows:
                # Issue 1: 담보명이 너무 짧음 (< 3자)
                if len(clause_text) < 3:
                    short_names += 1
                    issues.append({
                        "type": "short_coverage_name",
                        "clause_id": row_id,
                        "text": clause_text,
                        "severity": "critical"
                    })

                # Issue 2: 숫자로만 구성됨 ("16.", "21.")
                if clause_text.strip().rstrip('.').isdigit():
                    numeric_only += 1
                    issues.append({
                        "type": "numeric_only_coverage_name",
                        "clause_id": row_id,
                        "text": clause_text,
                        "severity": "critical"
                    })

                # Issue 3: 금액 정보 누락
                if not self._has_amount(clause_text):
                    missing_amount += 1
                    # 너무 많으면 critical
                    if missing_amount <= 5:  # 처음 5개만 기록
                        issues.append({
                            "type": "missing_amount",
                            "clause_id": row_id,
                            "text": clause_text[:100],
                            "severity": "medium"
                        })

            metrics = {
                'total_clauses': total,
                'table_rows': total,
                'short_coverage_name_count': short_names,
                'short_coverage_name_rate': short_names / total if total > 0 else 0,
                'numeric_only_count': numeric_only,
                'numeric_only_rate': numeric_only / total if total > 0 else 0,
                'missing_amount_count': missing_amount,
                'missing_amount_rate': missing_amount / total if total > 0 else 0,
                'issues': issues
            }

            return metrics

    def _has_amount(self, clause_text: str) -> bool:
        """금액 정보 포함 여부 확인"""
        import re
        patterns = [
            r'\d+천만원',
            r'\d{1,3}(?:,\d{3})+만원',
            r'\d+만원',
            r'\d{1,3}(?:,\d{3})+원',
        ]

        for pattern in patterns:
            if re.search(pattern, clause_text):
                return True

        return False

    def _get_companies(self) -> List[Dict[str, Any]]:
        """모든 보험사 조회"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, company_name, company_code
                FROM company
                ORDER BY company_name
            """)

            companies = []
            for row in cur.fetchall():
                companies.append({
                    'id': row[0],
                    'name': row[1],
                    'code': row[2]
                })

            return companies

    def generate_report_markdown(self, audit_results: Dict[str, Any]) -> str:
        """Markdown 형식 리포트 생성"""
        lines = [
            "# PDF Parsing Quality Audit Report",
            "",
            f"**Generated**: {self._now()}",
            "",
            "## Summary",
            "",
            "| Company | Total Clauses | Critical Issues | Medium Issues |",
            "|---------|---------------|-----------------|---------------|"
        ]

        for company_code, metrics in audit_results.items():
            critical_count = sum(
                1 for issue in metrics['issues']
                if issue.get('severity') == 'critical'
            )
            medium_count = sum(
                1 for issue in metrics['issues']
                if issue.get('severity') == 'medium'
            )

            status = "🔴" if critical_count > 0 else "🟢"

            lines.append(
                f"| {status} {metrics['company_name']} | "
                f"{metrics['total_clauses']} | "
                f"{critical_count} | "
                f"{medium_count} |"
            )

        lines.append("")
        lines.append("## Detailed Issues")
        lines.append("")

        for company_code, metrics in audit_results.items():
            if not metrics['issues']:
                continue

            lines.append(f"### {metrics['company_name']} ({company_code})")
            lines.append("")

            # Issue 유형별로 그룹화
            issues_by_type = defaultdict(list)
            for issue in metrics['issues']:
                issues_by_type[issue['type']].append(issue)

            for issue_type, issues in issues_by_type.items():
                severity = issues[0]['severity']
                icon = "🔴" if severity == "critical" else "🟡"

                lines.append(f"#### {icon} {issue_type.replace('_', ' ').title()}")
                lines.append(f"**Count**: {len(issues)}")
                lines.append("")

                # 처음 3개 예시만
                for issue in issues[:3]:
                    lines.append(f"- clause_id: {issue['clause_id']}")
                    lines.append(f"  ```")
                    lines.append(f"  {issue['text'][:100]}")
                    lines.append(f"  ```")
                    lines.append("")

                if len(issues) > 3:
                    lines.append(f"  ... and {len(issues) - 3} more")
                    lines.append("")

        return "\n".join(lines)

    def _now(self) -> str:
        """현재 시각"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def close(self):
        """리소스 정리"""
        if self.conn:
            self.conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Audit PDF parsing quality")
    parser.add_argument(
        '--output',
        type=str,
        help='Output JSON file path'
    )
    parser.add_argument(
        '--format',
        choices=['json', 'markdown'],
        default='json',
        help='Output format'
    )

    args = parser.parse_args()

    auditor = ParsingQualityAuditor()

    try:
        print("🔍 Starting parsing quality audit...")
        results = auditor.audit_all_companies()

        if args.format == 'markdown':
            report = auditor.generate_report_markdown(results)
            print("\n" + report)

            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(report)
                print(f"\n✅ Report saved to {args.output}")

        else:  # JSON
            print(json.dumps(results, indent=2, ensure_ascii=False))

            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                print(f"\n✅ Results saved to {args.output}")

    finally:
        auditor.close()


if __name__ == '__main__':
    main()
