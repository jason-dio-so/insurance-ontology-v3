"""
삼성 vs 현대 암진단비 최종 비교
"""
import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology')

print("\n" + "="*120)
print("🏥 삼성화재 vs 현대해상 암진단비 비교")
print("="*120 + "\n")

# 각 회사의 암 관련 담보 조회
def get_data(company):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                p.product_name,
                ce.metadata->'structured_data'->>'coverage_name' as name,
                ce.metadata->'structured_data'->>'coverage_amount' as amount
            FROM clause_embedding ce
            JOIN document_clause dc ON ce.clause_id = dc.id
            JOIN document d ON dc.document_id = d.id
            JOIN product p ON d.product_id = p.id
            JOIN company c ON p.company_id = c.id
            WHERE c.company_name = %s
              AND ce.metadata->'structured_data'->>'coverage_name' LIKE '%%암%%'
              AND ce.metadata->>'doc_type' = 'proposal'
            GROUP BY p.product_name, name, amount
            ORDER BY name
        """, (company,))
        return cur.fetchall()

samsung_data = get_data('삼성')
hyundai_data = get_data('현대')

# 상품명
s_product = samsung_data[0][0] if samsung_data else "N/A"
h_product = hyundai_data[0][0] if hyundai_data else "N/A"

print(f"🔵 삼성화재")
print(f"   상품: {s_product}")
print(f"   담보: {len(samsung_data)}개\n")

print(f"🔴 현대해상")
print(f"   상품: {h_product}")
print(f"   담보: {len(hyundai_data)}개\n")

# 데이터 정리
def organize_data(data):
    """담보를 카테고리별로 정리"""
    main_cancer = []
    quasi_cancer = []
    surgery = []
    treatment = []

    for _, name, amount in data:
        if not name:
            continue

        # 숫자로 변환
        try:
            amt_val = int(amount) if amount and amount.isdigit() else 0
        except:
            amt_val = 0

        item = (name, amt_val)

        # 카테고리 분류
        if '진단' in name:
            if any(x in name for x in ['유사', '갑상선', '피부', '제자리', '경계성', '대장점막']):
                quasi_cancer.append(item)
            else:
                main_cancer.append(item)
        elif '수술' in name:
            surgery.append(item)
        elif '치료' in name:
            treatment.append(item)

    return main_cancer, quasi_cancer, surgery, treatment

s_main, s_quasi, s_surgery, s_treatment = organize_data(samsung_data)
h_main, h_quasi, h_surgery, h_treatment = organize_data(hyundai_data)

# 비교 테이블
print("┌" + "─"*118 + "┐")
print(f"│ {'구분':<40} │ {'삼성화재':^35} │ {'현대해상':^35} │")
print("├" + "─"*118 + "┤")

# 일반암 진단비
print(f"│ {'💊 일반암 진단비 (유사암 제외)':<40} │" + " "*36 + "│" + " "*36 + "│")

max_main = max(len(s_main), len(h_main), 1)
for i in range(max_main):
    s_item = s_main[i] if i < len(s_main) else ('', 0)
    h_item = h_main[i] if i < len(h_main) else ('', 0)

    s_display = f"{s_item[1]:,}원" if s_item[1] > 0 else "-"
    h_display = f"{h_item[1]:,}원" if h_item[1] > 0 else "-"

    s_name = s_item[0][:20] if s_item[0] else ""
    h_name = h_item[0][:20] if h_item[0] else ""

    print(f"│   • {s_name:<37} │ {s_display:>34} │ {h_display:>34} │")

# 유사암 진단비
print(f"│ {'💉 유사암 진단비':<40} │" + " "*36 + "│" + " "*36 + "│")

s_quasi_total = sum(x[1] for x in s_quasi)
h_quasi_total = sum(x[1] for x in h_quasi)

print(f"│   • {len(s_quasi)}종류 담보" + " "*28 + f"│ {s_quasi_total:>33,}원 │ {h_quasi_total:>33,}원 │")

# 수술비
print(f"│ {'🔪 수술비':<40} │" + " "*36 + "│" + " "*36 + "│")

s_surgery_total = sum(x[1] for x in s_surgery)
h_surgery_total = sum(x[1] for x in h_surgery)

print(f"│   • {len(s_surgery)}종류 담보" + " "*28 + f"│ {s_surgery_total:>33,}원 │ {h_surgery_total:>33,}원 │")

# 치료비
print(f"│ {'💊 치료비 (항암/약물 등)':<40} │" + " "*36 + "│" + " "*36 + "│")

s_treatment_total = sum(x[1] for x in s_treatment)
h_treatment_total = sum(x[1] for x in h_treatment)

print(f"│   • {len(s_treatment)}종류 담보" + " "*28 + f"│ {s_treatment_total:>33,}원 │ {h_treatment_total:>33,}원 │")

print("├" + "─"*118 + "┤")

# 총합
s_total = sum(x[1] for x in s_main) + s_quasi_total + s_surgery_total + s_treatment_total
h_total = sum(x[1] for x in h_main) + h_quasi_total + h_surgery_total + h_treatment_total

print(f"│ {'📊 총 보장금액 합계':<40} │ {s_total:>34,}원 │ {h_total:>34,}원 │")
print("└" + "─"*118 + "┘")

# 상세 내역
print("\n📋 상세 담보 목록:\n")

print("🔵 삼성화재 - 일반암 진단비:")
for name, amt in s_main:
    print(f"   • {name}: {amt:,}원")

print(f"\n🔵 삼성화재 - 유사암 진단비 ({len(s_quasi)}종류):")
for name, amt in s_quasi:
    print(f"   • {name}: {amt:,}원")

print(f"\n🔴 현대해상 - 일반암 진단비:")
for name, amt in h_main:
    print(f"   • {name}: {amt:,}원")

print(f"\n🔴 현대해상 - 유사암 진단비 ({len(h_quasi)}종류):")
for name, amt in h_quasi:
    print(f"   • {name}: {amt:,}원")

print("\n" + "="*120 + "\n")

conn.close()
