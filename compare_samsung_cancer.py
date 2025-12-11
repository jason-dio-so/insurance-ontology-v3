"""
삼성화재 암진단비 상세 비교
"""
import os
os.environ['POSTGRES_URL'] = 'postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology'

from retrieval.hybrid_retriever import HybridRetriever
import psycopg2

def compare_samsung_cancer():
    """삼성화재의 암 관련 담보 비교"""

    conn = psycopg2.connect('postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology')
    retriever = HybridRetriever()

    print("\n" + "="*100)
    print("🏥 삼성화재 암진단비 상세 비교")
    print("="*100 + "\n")

    # 삼성화재 ID 가져오기
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM company WHERE company_name LIKE '%삼성%'")
        samsung_id = cur.fetchone()
        if not samsung_id:
            print("❌ 삼성화재를 찾을 수 없습니다.")
            return
        samsung_id = samsung_id[0]

    # 암 관련 담보 검색
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT
                ce.clause_id,
                dc.clause_text,
                p.product_name,
                ce.metadata->'structured_data'->>'coverage_name' as coverage_name,
                ce.metadata->'structured_data'->>'coverage_amount' as coverage_amount,
                ce.metadata->'structured_data'->>'premium_amount' as premium_amount,
                ce.metadata->>'doc_type' as doc_type
            FROM clause_embedding ce
            JOIN document_clause dc ON ce.clause_id = dc.id
            JOIN document d ON dc.document_id = d.id
            JOIN product p ON d.product_id = p.id
            WHERE p.company_id = %s
              AND (
                  ce.metadata->'structured_data'->>'coverage_name' LIKE '%암%'
                  OR dc.clause_text LIKE '%암%'
              )
              AND ce.metadata->>'doc_type' = 'proposal'
            ORDER BY
                CASE
                    WHEN ce.metadata->'structured_data'->>'coverage_name' LIKE '%암 진단%' THEN 1
                    WHEN ce.metadata->'structured_data'->>'coverage_name' LIKE '%암진단%' THEN 2
                    WHEN ce.metadata->'structured_data'->>'coverage_name' LIKE '%암%' THEN 3
                    ELSE 4
                END,
                coverage_name
            LIMIT 30
        """, (samsung_id,))

        results = cur.fetchall()

    if not results:
        print("❌ 암 관련 담보를 찾을 수 없습니다.\n")
        return

    print(f"✅ {len(results)}개 암 관련 담보 발견\n")

    # 담보별로 그룹화
    coverage_groups = {}
    for row in results:
        clause_id, clause_text, product_name, coverage_name, coverage_amount, premium_amount, doc_type = row

        if coverage_name not in coverage_groups:
            coverage_groups[coverage_name] = []

        coverage_groups[coverage_name].append({
            'clause_id': clause_id,
            'clause_text': clause_text,
            'product_name': product_name,
            'coverage_amount': coverage_amount,
            'premium_amount': premium_amount,
            'doc_type': doc_type
        })

    # 결과 출력
    print("┌" + "─"*98 + "┐")
    print(f"│ {'담보명':<40} │ {'보장금액':>15} │ {'월보험료':>15} │ {'상품':^20} │")
    print("├" + "─"*98 + "┤")

    total_coverage = 0
    total_premium = 0

    for coverage_name in sorted(coverage_groups.keys()):
        items = coverage_groups[coverage_name]

        for i, item in enumerate(items):
            display_name = coverage_name if i == 0 else ""

            # 보장금액 파싱
            amount_str = item['coverage_amount'] or "N/A"
            amount_display = amount_str

            try:
                # "3,000만원" -> 30000000
                if '만원' in amount_str:
                    num = int(amount_str.replace('만원', '').replace(',', '').replace(' ', ''))
                    amount_val = num * 10000
                    amount_display = f"{amount_val:,}원"
                    total_coverage += amount_val
                elif '천만원' in amount_str:
                    num = int(amount_str.replace('천만원', '').replace(',', '').replace(' ', ''))
                    amount_val = num * 10000000
                    amount_display = f"{amount_val:,}원"
                    total_coverage += amount_val
                elif '억' in amount_str:
                    num = int(amount_str.split('억')[0].replace(',', '').replace(' ', ''))
                    amount_val = num * 100000000
                    amount_display = f"{amount_val:,}원"
                    total_coverage += amount_val
            except:
                pass

            # 보험료 파싱
            premium_str = item['premium_amount'] or "N/A"
            premium_display = premium_str

            try:
                if '원' in premium_str:
                    num = int(premium_str.replace('원', '').replace(',', '').replace(' ', ''))
                    premium_display = f"{num:,}원"
                    total_premium += num
            except:
                pass

            product_short = item['product_name'][:18] if item['product_name'] else "N/A"

            print(f"│ {display_name:<40} │ {amount_display:>15} │ {premium_display:>15} │ {product_short:^20} │")

    print("├" + "─"*98 + "┤")
    print(f"│ {'합계':<40} │ {total_coverage:>14,}원 │ {total_premium:>14,}원 │ {'':^20} │")
    print("└" + "─"*98 + "┘")

    print("\n📊 요약:")
    print(f"   • 총 담보 수: {len(coverage_groups)}개")
    print(f"   • 총 보장금액: {total_coverage:,}원")
    print(f"   • 총 월보험료: {total_premium:,}원")

    # 주요 담보 하이라이트
    print("\n💡 주요 담보:")
    highlight_keywords = ['암 진단비', '암진단비', '일반암', '고액']
    for keyword in highlight_keywords:
        for coverage_name, items in coverage_groups.items():
            if coverage_name and keyword in coverage_name:
                amount = items[0]['coverage_amount']
                print(f"   • {coverage_name}: {amount}")

    print("\n" + "="*100 + "\n")

    conn.close()
    retriever.close()

if __name__ == "__main__":
    compare_samsung_cancer()
