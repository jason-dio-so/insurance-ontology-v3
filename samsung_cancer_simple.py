"""
삼성화재 암진단비 비교 (간단 버전)
"""
import os
os.environ['POSTGRES_URL'] = 'postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology'

from retrieval.hybrid_retriever import HybridRetriever
import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology')

print("\n" + "="*100)
print("🏥 삼성화재 암진단비 상세 비교")
print("="*100 + "\n")

# Step 1: 삼성화재 찾기
with conn.cursor() as cur:
    cur.execute("SELECT id, company_name FROM company WHERE company_name LIKE '%삼성%'")
    result = cur.fetchone()
    if not result:
        print("❌ 삼성화재를 찾을 수 없습니다.")
        exit(1)

    samsung_id, company_name = result
    print(f"✓ 회사: {company_name} (ID: {samsung_id})\n")

# Step 2: 삼성화재 상품 찾기
with conn.cursor() as cur:
    cur.execute("""
        SELECT id, product_name
        FROM product
        WHERE company_id = %s
    """, (samsung_id,))
    products = cur.fetchall()
    print(f"✓ 상품: {len(products)}개")
    for prod_id, prod_name in products:
        print(f"  - {prod_name} (ID: {prod_id})")
    print()

# Step 3: 암 관련 담보 검색
with conn.cursor() as cur:
    cur.execute("""
        SELECT
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
          AND ce.metadata->'structured_data'->>'coverage_name' LIKE '%%암%%'
          AND ce.metadata->>'doc_type' = 'proposal'
        ORDER BY
            ce.metadata->'structured_data'->>'coverage_name'
        LIMIT 50
    """, (samsung_id,))

    results = cur.fetchall()

print(f"✓ 암 관련 담보: {len(results)}개 발견\n")

if not results:
    print("❌ 결과가 없습니다.\n")
    exit(0)

# 담보별로 그룹화
coverage_map = {}
for row in results:
    clause_id, clause_text, product_name, coverage_name, coverage_amount, premium_amount, doc_type = row

    if not coverage_name:
        continue

    if coverage_name not in coverage_map:
        coverage_map[coverage_name] = {
            'coverage_name': coverage_name,
            'coverage_amount': coverage_amount,
            'premium_amount': premium_amount,
            'product_name': product_name,
            'clause_text': clause_text[:100],
            'count': 0
        }

    coverage_map[coverage_name]['count'] += 1

# 결과 출력
print("┌" + "─"*98 + "┐")
print(f"│ {'담보명':<50} │ {'보장금액':>20} │ {'월보험료':>20} │")
print("├" + "─"*98 + "┤")

total_amount = 0
total_premium = 0

for coverage_name in sorted(coverage_map.keys()):
    item = coverage_map[coverage_name]

    # 금액 변환
    amount_str = item['coverage_amount'] or "-"
    premium_str = item['premium_amount'] or "-"

    # 보장금액 숫자로 변환 시도
    amount_num = 0
    try:
        if '만원' in amount_str:
            amount_num = int(amount_str.replace('만원', '').replace(',', '').strip()) * 10000
            amount_str = f"{amount_num:,}원"
        elif '천만원' in amount_str:
            amount_num = int(amount_str.replace('천만원', '').replace(',', '').strip()) * 10000000
            amount_str = f"{amount_num:,}원"
        elif '억' in amount_str:
            amount_num = int(amount_str.split('억')[0].replace(',', '').strip()) * 100000000
            amount_str = f"{amount_num:,}원"
    except:
        pass

    if amount_num > 0:
        total_amount += amount_num

    # 보험료 숫자로 변환 시도
    premium_num = 0
    try:
        if '원' in premium_str:
            premium_num = int(premium_str.replace('원', '').replace(',', '').strip())
            premium_str = f"{premium_num:,}원"
    except:
        pass

    if premium_num > 0:
        total_premium += premium_num

    print(f"│ {coverage_name:<50} │ {amount_str:>20} │ {premium_str:>20} │")

print("├" + "─"*98 + "┤")
print(f"│ {'합계':<50} │ {total_amount:>19,}원 │ {total_premium:>19,}원 │")
print("└" + "─"*98 + "┘")

print(f"\n📊 요약:")
print(f"   • 총 담보 종류: {len(coverage_map)}개")
print(f"   • 총 보장금액: {total_amount:,}원")
print(f"   • 총 월보험료: {total_premium:,}원")

# 주요 담보 하이라이트
print(f"\n💡 주요 암진단비:")
for name in sorted(coverage_map.keys()):
    if '진단비' in name and ('암 진단' in name or '암진단' in name):
        print(f"   • {name}: {coverage_map[name]['coverage_amount']}")

print("\n" + "="*100 + "\n")

conn.close()
