"""
삼성 vs 현대 암진단비 비교
"""
import os
os.environ['POSTGRES_URL'] = 'postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology'

import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology')

print("\n" + "="*120)
print("🏥 삼성화재 vs 현대해상 암진단비 비교")
print("="*120 + "\n")

# 회사별 데이터 수집 함수
def get_cancer_coverage(company_name_pattern):
    """특정 회사의 암 관련 담보 조회"""
    with conn.cursor() as cur:
        # 회사 ID 찾기
        cur.execute("""
            SELECT id, company_name
            FROM company
            WHERE company_name LIKE %s
        """, (f'%{company_name_pattern}%',))

        result = cur.fetchone()
        if not result:
            return None, []

        company_id, company_name = result

        # 암 관련 담보 검색
        cur.execute("""
            SELECT
                ce.metadata->'structured_data'->>'coverage_name' as coverage_name,
                ce.metadata->'structured_data'->>'coverage_amount' as coverage_amount,
                ce.metadata->'structured_data'->>'premium_amount' as premium_amount,
                p.product_name,
                dc.clause_text
            FROM clause_embedding ce
            JOIN document_clause dc ON ce.clause_id = dc.id
            JOIN document d ON dc.document_id = d.id
            JOIN product p ON d.product_id = p.id
            WHERE p.company_id = %s
              AND ce.metadata->'structured_data'->>'coverage_name' LIKE '%%암%%'
              AND ce.metadata->>'doc_type' = 'proposal'
            GROUP BY
                ce.metadata->'structured_data'->>'coverage_name',
                ce.metadata->'structured_data'->>'coverage_amount',
                ce.metadata->'structured_data'->>'premium_amount',
                p.product_name,
                dc.clause_text
            ORDER BY
                CASE
                    WHEN ce.metadata->'structured_data'->>'coverage_name' LIKE '%%암 진단%%' THEN 1
                    WHEN ce.metadata->'structured_data'->>'coverage_name' LIKE '%%암진단%%' THEN 2
                    ELSE 3
                END,
                ce.metadata->'structured_data'->>'coverage_name'
        """, (company_id,))

        coverages = []
        for row in cur.fetchall():
            coverage_name, coverage_amount, premium_amount, product_name, clause_text = row

            if not coverage_name:
                continue

            # 중복 제거
            if not any(c['name'] == coverage_name for c in coverages):
                coverages.append({
                    'name': coverage_name,
                    'amount': coverage_amount,
                    'premium': premium_amount,
                    'product': product_name
                })

        return company_name, coverages

# 삼성화재 데이터
samsung_name, samsung_coverages = get_cancer_coverage('삼성')
print(f"✓ {samsung_name}: {len(samsung_coverages)}개 담보")

# 현대해상 데이터
hyundai_name, hyundai_coverages = get_cancer_coverage('현대')
print(f"✓ {hyundai_name}: {len(hyundai_coverages)}개 담보")
print()

if not samsung_coverages and not hyundai_coverages:
    print("❌ 비교할 데이터가 없습니다.\n")
    exit(0)

# 금액 파싱 함수
def parse_amount(amount_str):
    """한글 금액을 숫자로 변환"""
    if not amount_str or amount_str == '-':
        return 0, amount_str or '-'

    try:
        if '만원' in amount_str:
            num = int(amount_str.replace('만원', '').replace(',', '').replace(' ', ''))
            val = num * 10000
            return val, f"{val:,}원"
        elif '천만원' in amount_str:
            num = int(amount_str.replace('천만원', '').replace(',', '').replace(' ', ''))
            val = num * 10000000
            return val, f"{val:,}원"
        elif '억' in amount_str:
            num = int(amount_str.split('억')[0].replace(',', '').replace(' ', ''))
            val = num * 100000000
            return val, f"{val:,}원"
        elif '원' in amount_str:
            num = int(amount_str.replace('원', '').replace(',', '').replace(' ', ''))
            return num, f"{num:,}원"
    except:
        pass

    return 0, amount_str

# 담보 카테고리 분류
def categorize_coverage(name):
    """담보를 카테고리로 분류"""
    if '암 진단비' in name or '암진단비' in name:
        if '유사암' in name or '갑상선' in name or '기타피부' in name or '제자리' in name or '경계성' in name or '대장점막' in name:
            return '유사암 진단비'
        else:
            return '일반암 진단비'
    elif '수술비' in name:
        return '수술비'
    elif '치료비' in name:
        return '치료비'
    else:
        return '기타'

# 카테고리별로 정리
samsung_by_category = {}
hyundai_by_category = {}

for cov in samsung_coverages:
    cat = categorize_coverage(cov['name'])
    if cat not in samsung_by_category:
        samsung_by_category[cat] = []
    samsung_by_category[cat].append(cov)

for cov in hyundai_coverages:
    cat = categorize_coverage(cov['name'])
    if cat not in hyundai_by_category:
        hyundai_by_category[cat] = []
    hyundai_by_category[cat].append(cov)

# 비교 테이블 출력
print("┌" + "─"*118 + "┐")
print(f"│ {'담보명':<50} │ {samsung_name:^30} │ {hyundai_name:^30} │")
print("├" + "─"*118 + "┤")

categories = ['일반암 진단비', '유사암 진단비', '수술비', '치료비', '기타']

samsung_total = 0
hyundai_total = 0

for category in categories:
    samsung_items = samsung_by_category.get(category, [])
    hyundai_items = hyundai_by_category.get(category, [])

    if not samsung_items and not hyundai_items:
        continue

    # 카테고리 헤더
    print(f"│ [{category}]" + " " * (50 - len(category) - 3) + "│" + " " * 31 + "│" + " " * 31 + "│")

    # 각 회사의 담보 출력
    max_items = max(len(samsung_items), len(hyundai_items))

    for i in range(max_items):
        samsung_item = samsung_items[i] if i < len(samsung_items) else None
        hyundai_item = hyundai_items[i] if i < len(hyundai_items) else None

        # 삼성 정보
        if samsung_item:
            s_name = samsung_item['name'][:25]
            s_amount_num, s_amount_display = parse_amount(samsung_item['amount'])
            samsung_total += s_amount_num
            samsung_info = f"{s_amount_display:>28}"
        else:
            s_name = ""
            samsung_info = " " * 30

        # 현대 정보
        if hyundai_item:
            h_name = hyundai_item['name'][:25]
            h_amount_num, h_amount_display = parse_amount(hyundai_item['amount'])
            hyundai_total += h_amount_num
            hyundai_info = f"{h_amount_display:>28}"
        else:
            h_name = ""
            hyundai_info = " " * 30

        # 담보명 (둘 중 하나만 표시)
        display_name = s_name if samsung_item else h_name

        print(f"│  {display_name:<48} │ {samsung_info} │ {hyundai_info} │")

print("├" + "─"*118 + "┤")
print(f"│ {'총 보장금액 합계':<50} │ {samsung_total:>28,}원 │ {hyundai_total:>28,}원 │")
print("└" + "─"*118 + "┘")

# 상세 비교
print("\n📊 상세 비교:\n")

print(f"🔵 {samsung_name}")
print(f"   • 상품: {samsung_coverages[0]['product'] if samsung_coverages else 'N/A'}")
print(f"   • 총 담보 수: {len(samsung_coverages)}개")
print(f"   • 주요 일반암 진단비: ", end="")
main_cancer = [c for c in samsung_coverages if '암 진단비' in c['name'] and '유사' not in c['name']]
if main_cancer:
    print(f"{main_cancer[0]['amount']}")
else:
    print("-")

print(f"\n🔴 {hyundai_name}")
print(f"   • 상품: {hyundai_coverages[0]['product'] if hyundai_coverages else 'N/A'}")
print(f"   • 총 담보 수: {len(hyundai_coverages)}개")
print(f"   • 주요 일반암 진단비: ", end="")
main_cancer = [c for c in hyundai_coverages if '암 진단비' in c['name'] and '유사' not in c['name']]
if main_cancer:
    print(f"{main_cancer[0]['amount']}")
else:
    print("-")

print("\n" + "="*120 + "\n")

conn.close()
