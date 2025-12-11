"""
삼성 vs 현대 암진단비 비교 (깔끔한 버전)
"""
import os
os.environ['POSTGRES_URL'] = 'postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology'

import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology')

print("\n" + "="*120)
print("🏥 삼성화재 vs 현대해상 암 관련 담보 비교")
print("="*120 + "\n")

def get_cancer_data(company_pattern):
    """회사의 암 관련 담보 조회"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, company_name
            FROM company
            WHERE company_name LIKE %s
        """, (f'%{company_pattern}%',))

        result = cur.fetchone()
        if not result:
            return None, None, []

        company_id, company_name = result

        cur.execute("""
            SELECT
                p.product_name,
                ce.metadata->'structured_data'->>'coverage_name' as coverage_name,
                ce.metadata->'structured_data'->>'coverage_amount' as coverage_amount
            FROM clause_embedding ce
            JOIN document_clause dc ON ce.clause_id = dc.id
            JOIN document d ON dc.document_id = d.id
            JOIN product p ON d.product_id = p.id
            WHERE p.company_id = %s
              AND ce.metadata->'structured_data'->>'coverage_name' LIKE '%%암%%'
              AND ce.metadata->>'doc_type' = 'proposal'
              AND ce.metadata->'structured_data'->>'coverage_name' IS NOT NULL
            GROUP BY
                p.product_name,
                ce.metadata->'structured_data'->>'coverage_name',
                ce.metadata->'structured_data'->>'coverage_amount'
            ORDER BY
                ce.metadata->'structured_data'->>'coverage_name'
        """, (company_id,))

        rows = cur.fetchall()
        product_name = rows[0][0] if rows else "N/A"

        coverages = {}
        for _, name, amount in rows:
            if name and name not in coverages:
                coverages[name] = amount

        return company_name, product_name, coverages

def parse_amount(amt_str):
    """한글 금액을 숫자로 변환"""
    if not amt_str:
        return 0

    try:
        amt_str = amt_str.strip()
        if '만원' in amt_str:
            num = int(amt_str.replace('만원', '').replace(',', '').replace(' ', ''))
            return num * 10000
        elif '천만원' in amt_str:
            num = int(amt_str.replace('천만원', '').replace(',', '').replace(' ', ''))
            return num * 10000000
        elif '억' in amt_str:
            num = int(amt_str.split('억')[0].replace(',', '').replace(' ', ''))
            return num * 100000000
        elif '원' in amt_str:
            return int(amt_str.replace('원', '').replace(',', '').replace(' ', ''))
    except:
        pass
    return 0

# 데이터 수집
samsung_name, samsung_product, samsung_cov = get_cancer_data('삼성')
hyundai_name, hyundai_product, hyundai_cov = get_cancer_data('현대')

print(f"🔵 {samsung_name}")
print(f"   상품: {samsung_product}")
print(f"   담보: {len(samsung_cov)}개\n")

print(f"🔴 {hyundai_name}")
print(f"   상품: {hyundai_product}")
print(f"   담보: {len(hyundai_cov)}개\n")

# 주요 담보 비교
print("┌" + "─"*118 + "┐")
print(f"│ {'담보 분류':<35} │ {samsung_name:^38} │ {hyundai_name:^38} │")
print("├" + "─"*118 + "┤")

# 1. 일반암 진단비
print(f"│ {'💊 일반암 진단비 (유사암 제외)':<35} │" + " "*39 + "│" + " "*39 + "│")

samsung_main = [k for k in samsung_cov.keys() if '암 진단비' in k or '암진단' in k]
samsung_main = [k for k in samsung_main if '유사' not in k and '갑상선' not in k and '피부' not in k and '제자리' not in k and '경계성' not in k and '대장' not in k and '신재진단' not in k]

hyundai_main = [k for k in hyundai_cov.keys() if '암 진단' in k or '암진단' in k]
hyundai_main = [k for k in hyundai_main if '유사' not in k and '갑상선' not in k and '피부' not in k and '제자리' not in k and '경계성' not in k and '대장' not in k and '신재진단' not in k]

max_main = max(len(samsung_main), len(hyundai_main), 1)
samsung_total_main = 0
hyundai_total_main = 0

for i in range(max_main):
    s_name = samsung_main[i] if i < len(samsung_main) else None
    h_name = hyundai_main[i] if i < len(hyundai_main) else None

    s_amt = ""
    h_amt = ""

    if s_name:
        s_val = parse_amount(samsung_cov[s_name])
        samsung_total_main += s_val
        s_amt = f"{s_val:,}원" if s_val > 0 else samsung_cov[s_name]

    if h_name:
        h_val = parse_amount(hyundai_cov[h_name])
        hyundai_total_main += h_val
        h_amt = f"{h_val:,}원" if h_val > 0 else hyundai_cov[h_name]

    print(f"│   {'':<33} │ {s_amt:>37} │ {h_amt:>37} │")

# 2. 유사암 진단비
print(f"│ {'💉 유사암 진단비':<35} │" + " "*39 + "│" + " "*39 + "│")

samsung_quasi = [k for k in samsung_cov.keys() if '유사암' in k or ('진단' in k and ('갑상선' in k or '피부' in k or '제자리' in k or '경계성' in k or '대장점막' in k))]
hyundai_quasi = [k for k in hyundai_cov.keys() if '유사암' in k or ('진단' in k and ('갑상선' in k or '피부' in k or '제자리' in k or '경계성' in k or '대장점막' in k))]

samsung_total_quasi = sum(parse_amount(samsung_cov[k]) for k in samsung_quasi)
hyundai_total_quasi = sum(parse_amount(hyundai_cov[k]) for k in hyundai_quasi)

s_quasi_display = f"{len(samsung_quasi)}종 / 합계 {samsung_total_quasi:,}원"
h_quasi_display = f"{len(hyundai_quasi)}종 / 합계 {hyundai_total_quasi:,}원"

print(f"│   {'':<33} │ {s_quasi_display:>37} │ {h_quasi_display:>37} │")

# 3. 수술비
print(f"│ {'🔪 수술비':<35} │" + " "*39 + "│" + " "*39 + "│")

samsung_surgery = [k for k in samsung_cov.keys() if '수술' in k]
hyundai_surgery = [k for k in hyundai_cov.keys() if '수술' in k]

samsung_total_surgery = sum(parse_amount(samsung_cov[k]) for k in samsung_surgery)
hyundai_total_surgery = sum(parse_amount(hyundai_cov[k]) for k in hyundai_surgery)

s_surgery_display = f"{len(samsung_surgery)}종 / 합계 {samsung_total_surgery:,}원"
h_surgery_display = f"{len(hyundai_surgery)}종 / 합계 {hyundai_total_surgery:,}원"

print(f"│   {'':<33} │ {s_surgery_display:>37} │ {h_surgery_display:>37} │")

# 4. 치료비
print(f"│ {'💉 치료비 (항암/약물 등)':<35} │" + " "*39 + "│" + " "*39 + "│")

samsung_treatment = [k for k in samsung_cov.keys() if '치료' in k]
hyundai_treatment = [k for k in hyundai_cov.keys() if '치료' in k]

samsung_total_treatment = sum(parse_amount(samsung_cov[k]) for k in samsung_treatment)
hyundai_total_treatment = sum(parse_amount(hyundai_cov[k]) for k in hyundai_treatment)

s_treatment_display = f"{len(samsung_treatment)}종 / 합계 {samsung_total_treatment:,}원"
h_treatment_display = f"{len(hyundai_treatment)}종 / 합계 {hyundai_total_treatment:,}원"

print(f"│   {'':<33} │ {s_treatment_display:>37} │ {h_treatment_display:>37} │")

print("├" + "─"*118 + "┤")

# 합계
samsung_grand_total = samsung_total_main + samsung_total_quasi + samsung_total_surgery + samsung_total_treatment
hyundai_grand_total = hyundai_total_main + hyundai_total_quasi + hyundai_total_surgery + hyundai_total_treatment

print(f"│ {'📊 총 보장금액 합계':<35} │ {samsung_grand_total:>36,}원 │ {hyundai_grand_total:>36,}원 │")
print("└" + "─"*118 + "┘")

# 상세 비교
print("\n📋 상세 담보 목록:\n")

print(f"🔵 {samsung_name} - 주요 일반암 진단비:")
for name in samsung_main:
    amt = samsung_cov[name]
    val = parse_amount(amt)
    print(f"   • {name}: {val:,}원")

print(f"\n🔴 {hyundai_name} - 주요 일반암 진단비:")
for name in hyundai_main:
    amt = hyundai_cov[name]
    val = parse_amount(amt)
    print(f"   • {name}: {val:,}원")

print("\n" + "="*120 + "\n")

conn.close()
