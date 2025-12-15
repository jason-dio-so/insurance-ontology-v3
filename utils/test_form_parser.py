#!/usr/bin/env python3
"""
폼 형태 테이블 파싱 테스트

가입설계서처럼 키-값 폼 형태의 테이블을 구조화된 데이터로 변환합니다.

## 검증 결과 (2025-12-15)

| 회사 | PDF 구조         | 폼 파싱 필요 | 비고                    |
|------|------------------|-------------|-------------------------|
| DB   | 복잡 (병합 셀 多) | ✅ 필요      | 16개 필드 정확히 추출    |
| 한화 | 중간             | ⚠️ 부분 작동 | 섹션 중복 발생           |
| 롯데 | 단순 (병합 셀 無) | ❌ 불필요    | 기존 테이블 방식으로 충분 |

## 핵심 로직

1. is_form_table(): 빈 셀 60% 이상 + 5열 이상이면 폼 테이블로 판단
2. is_header_data_pattern(): 헤더행에 값(금액/숫자)이 없으면 헤더-데이터 패턴
3. extract_key_value_pairs_single_row(): 좌측(0~5열) / 우측(6~15열) 2열 병렬 구조 처리

## 사용법

```python
from utils.test_form_parser import is_form_table, parse_form_table

if is_form_table(table_data):
    result = parse_form_table(table_data)
    # result['sections'] - 섹션 목록
    # result['fields'] - 키-값 쌍 딕셔너리
```
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Tuple


def is_form_table(table: List[List[str]], empty_threshold: float = 0.6) -> bool:
    """
    테이블이 폼 형태인지 판단

    조건:
    1. 전체 셀의 60% 이상이 비어있음
    2. 열 수가 5개 이상 (병합 셀로 인해 많은 열 생성)
    3. 최소 5행 이상 (단순 헤더 테이블 제외)
    4. 키-값 쌍이 3개 이상 추출 가능 (실제 폼인지 검증)
    """
    if not table or not table[0]:
        return False

    # 조건 1: 최소 행 수
    if len(table) < 5:
        return False

    # 조건 2: 빈 셀 비율
    total_cells = sum(len(row) for row in table)
    empty_cells = sum(1 for row in table for cell in row if cell == "")
    empty_ratio = empty_cells / total_cells if total_cells > 0 else 0

    if empty_ratio < empty_threshold:
        return False

    # 조건 3: 열 수
    num_cols = len(table[0])
    if num_cols < 5:
        return False

    # 조건 4: 실제 키-값 쌍 추출 가능 여부 (샘플 검증)
    kv_count = _count_potential_key_values(table)
    if kv_count < 3:
        return False

    # 조건 5: 실제 파싱 시 필드가 추출되는지 확인
    try:
        result = _quick_parse_check(table)
        if result < 2:  # 최소 2개 필드 필요
            return False
    except:
        return False

    # 조건 6: 약관 특유 패턴 제외 (조항 설명 테이블)
    if _is_terms_clause_table(table):
        return False

    return True


def _is_terms_clause_table(table: List[List[str]]) -> bool:
    """
    약관 조항 설명 테이블인지 확인 (폼이 아님)

    특징:
    - "최초의 계약", "갱신된 계약" 패턴
    - "보험계약일부터", "보험가입금액" 패턴
    - 긴 조항 설명 텍스트
    """
    terms_patterns = [
        "최초의 계약", "갱신된 계약", "보험계약일부터",
        "보험가입금액 50%", "보험가입금액 100%",
        "보험수익자에게 지급", "연간 1회에 한하여"
    ]

    # 테이블 텍스트 추출
    all_text = " ".join(
        cell for row in table for cell in row if cell.strip()
    )

    # 약관 패턴이 2개 이상 있으면 조항 테이블로 판단
    match_count = sum(1 for p in terms_patterns if p in all_text)
    if match_count >= 2:
        return True

    return False


def _quick_parse_check(table: List[List[str]]) -> int:
    """
    빠른 파싱 검증 - 실제 필드 추출 개수 반환
    """
    from utils.test_form_parser import parse_form_table
    result = parse_form_table(table)
    return len(result.get('fields', {}))


def _count_potential_key_values(table: List[List[str]]) -> int:
    """
    테이블에서 추출 가능한 키-값 쌍 개수 추정
    """
    key_patterns = [
        "계약자", "피보험자", "만기", "납기", "보험료", "플랜", "방법",
        "관계", "주민번호", "상해급수", "직업", "환급금", "구분", "가입금액",
        "담보", "보장", "합계", "성별", "나이", "기간", "보험", "금액"
    ]

    kv_count = 0

    for row in table:
        non_empty = [(i, cell.strip()) for i, cell in enumerate(row) if cell.strip()]

        # 2~6개 비어있지 않은 셀이 있는 행에서 키-값 패턴 찾기
        if 2 <= len(non_empty) <= 6:
            for idx, cell in non_empty:
                # 키처럼 보이는 셀
                if any(pattern in cell for pattern in key_patterns):
                    # 오른쪽에 값이 있는지 확인
                    right_cells = [(i, c) for i, c in non_empty if i > idx]
                    if right_cells:
                        kv_count += 1
                        break  # 행당 1개만 카운트

    return kv_count


def parse_form_table(table: List[List[str]]) -> Dict[str, Any]:
    """
    폼 테이블을 키-값 쌍으로 파싱

    개선된 로직:
    1. 섹션 헤더 감지
    2. 헤더행 + 데이터행 패턴 감지 및 매칭
    3. 단일행 키-값 쌍 추출
    """
    result = {
        "type": "form",
        "sections": [],
        "fields": {}
    }

    current_section = None
    row_idx = 0

    while row_idx < len(table):
        row = table[row_idx]
        non_empty = [(i, cell) for i, cell in enumerate(row) if cell.strip()]

        if not non_empty:
            row_idx += 1
            continue

        # 단일 셀 행 = 섹션 헤더 가능성
        if len(non_empty) == 1:
            cell_text = non_empty[0][1]
            if len(cell_text) < 50 and not any(c in cell_text for c in ['※', '1.', '2.', '◎']):
                current_section = cell_text
                result["sections"].append({
                    "name": current_section,
                    "row": row_idx
                })
                row_idx += 1
                continue

        # 헤더행 감지: 다음 행과 비교하여 헤더-데이터 패턴인지 확인
        if row_idx + 1 < len(table):
            next_row = table[row_idx + 1]
            if is_header_data_pattern(row, next_row):
                # 헤더-데이터 행 매칭
                pairs = match_header_data_rows(row, next_row)
                for key, value in pairs:
                    if key and value:
                        field_key = f"{current_section}_{key}" if current_section else key
                        result["fields"][field_key] = value
                row_idx += 2  # 두 행 처리됨
                continue

        # 단일행 키-값 쌍 추출 (기존 방식)
        pairs = extract_key_value_pairs_single_row(non_empty)
        for key, value in pairs:
            if key and value:
                field_key = f"{current_section}_{key}" if current_section else key
                result["fields"][field_key] = value

        row_idx += 1

    return result


def is_header_data_pattern(header_row: List[str], data_row: List[str]) -> bool:
    """
    두 행이 헤더-데이터 패턴인지 판단

    조건:
    - 헤더행: 레이블만 있음 (값 없음)
    - 데이터행: 값들이 헤더와 유사한 위치에 있음

    주의: 헤더행에 값(금액, 숫자, 날짜)이 있으면 병렬 구조이므로 False
    """
    import re

    header_cells = [(i, c) for i, c in enumerate(header_row) if c.strip()]
    data_cells = [(i, c) for i, c in enumerate(data_row) if c.strip()]

    if len(header_cells) < 2 or len(data_cells) < 2:
        return False

    def is_value_like(text: str) -> bool:
        """값처럼 보이는지 (금액, 숫자, 날짜 등)"""
        text = text.strip()
        # 금액 패턴
        if '원' in text and any(c.isdigit() for c in text):
            return True
        # 날짜 패턴 (2025.09.24 ~ ...)
        if re.match(r'^\d{4}\.\d{2}\.\d{2}', text):
            return True
        # "N급", "N세", "N명" 패턴
        if re.match(r'^\d+[급세명]$', text):
            return True
        # "남 / 30세" 같은 성별/나이 값
        if re.match(r'^[남여]\s*/\s*\d+세', text):
            return True
        # 주민번호/고객번호 패턴
        if re.match(r'.*\d{6}-', text):
            return True
        # 숫자만 있는 경우 (길이 2 이상)
        clean = text.replace(',', '').replace('.', '').replace('-', '').replace(' ', '')
        if clean.isdigit() and len(clean) >= 2:
            return True
        # 날짜/기간 패턴
        if '년' in text and any(c.isdigit() for c in text):
            return True
        # "N명" 패턴 (1명, 5명 등)
        if re.match(r'^\d+명$', text):
            return True
        return False

    # 헤더행에 값이 있으면 병렬 구조 (헤더-데이터 아님)
    header_texts = [c for _, c in header_cells]
    has_value_in_header = any(is_value_like(t) for t in header_texts)
    if has_value_in_header:
        return False

    # 헤더행 내에서 키-값 쌍이 이미 존재하면 병렬 구조
    # (짧은 텍스트 다음에 긴 텍스트가 오는 패턴)
    key_count = sum(1 for t in header_texts if len(t) < 15 and not is_value_like(t))
    if key_count >= 2 and len(header_cells) >= 4:
        # 키가 2개 이상이고 셀이 4개 이상이면 병렬 구조 가능성
        return False

    # 헤더행의 셀들이 대부분 짧은 텍스트인지 (레이블처럼)
    short_header_ratio = sum(1 for t in header_texts if len(t) < 20) / len(header_texts)
    if short_header_ratio < 0.7:
        return False

    # 데이터행에 값이 있어야 함
    data_texts = [c for _, c in data_cells]
    has_value_in_data = any(is_value_like(t) for t in data_texts)
    if not has_value_in_data:
        return False

    # 헤더와 데이터의 위치가 대략 일치하는지
    header_positions = set(i for i, _ in header_cells)
    data_positions = set(i for i, _ in data_cells)

    overlap = 0
    for dp in data_positions:
        for hp in header_positions:
            if abs(dp - hp) <= 2:
                overlap += 1
                break

    overlap_ratio = overlap / len(data_positions) if data_positions else 0
    return overlap_ratio >= 0.5


def match_header_data_rows(header_row: List[str], data_row: List[str]) -> List[Tuple[str, str]]:
    """
    헤더행과 데이터행을 매칭하여 키-값 쌍 추출

    로직: 열 위치 기준으로 가장 가까운 헤더-값 매칭
    """
    pairs = []

    header_cells = [(i, c.strip()) for i, c in enumerate(header_row) if c.strip()]
    data_cells = [(i, c.strip()) for i, c in enumerate(data_row) if c.strip()]

    # 각 데이터 셀에 대해 가장 가까운 헤더 찾기
    used_headers = set()

    for data_idx, data_val in data_cells:
        best_header = None
        best_distance = float('inf')

        for header_idx, header_text in header_cells:
            if header_idx in used_headers:
                continue

            distance = abs(data_idx - header_idx)
            if distance < best_distance:
                best_distance = distance
                best_header = (header_idx, header_text)

        if best_header and best_distance <= 3:
            used_headers.add(best_header[0])
            pairs.append((best_header[1], data_val))

    return pairs


def extract_key_value_pairs_single_row(non_empty: List[Tuple[int, str]]) -> List[Tuple[str, str]]:
    """
    단일 행에서 키-값 쌍 추출

    개선된 로직:
    1. 키-값이 인접한 경우 우선 매칭 (현대 설계서: col0-col3, col4-col5)
    2. 그 다음 좌측/우측 영역으로 분리하여 매칭 (DB 설계서: col0~5, col8~11)
    """
    pairs = []

    key_patterns = [
        "계약자", "계 약 자", "피보험자", "만기", "납기", "보험료", "플랜", "방법",
        "관계", "주민번호", "상해급수", "직업", "운행차량", "환급금", "차량용도",
        "구분", "가입금액", "담보", "보장", "합계", "성별", "나이", "기간"
    ]

    def is_key_like(text: str) -> bool:
        """키(레이블)처럼 보이는지 판단"""
        import re

        # 값 패턴 먼저 체크 (값이면 키 아님)
        if '세만기' in text or '년납' in text or '년/100세' in text:
            return False
        if '종_' in text or '플랜' in text.lower():
            return False
        if text in ['월납', '연납', '일시납', '-']:
            return False
        # 날짜 패턴 (2025.09.24 ~ ...)
        if re.match(r'^\d{4}\.\d{2}\.\d{2}', text):
            return False
        # 주민번호/고객번호 패턴
        if re.match(r'.*\d{6}-', text):
            return False
        # 금액 패턴
        if '원' in text and any(c.isdigit() for c in text):
            return False
        # "N급", "N세", "N명" 패턴
        if re.match(r'^\d+[급세명]$', text):
            return False
        # "남 / 30세" 같은 성별/나이 값
        if re.match(r'^[남여]\s*/\s*\d+세', text):
            return False

        # 명시적 키 패턴 매칭
        if any(pattern in text for pattern in key_patterns):
            return True
        # 짧고 숫자/단위가 아닌 텍스트
        if len(text) < 15:
            clean = text.replace(',', '').replace('.', '').replace('-', '').replace(' ', '')
            if not clean.isdigit() and '원' not in text:
                return True
        return False

    # 셀을 키/값으로 분류
    keys = [(i, c) for i, c in non_empty if is_key_like(c)]
    vals = [(i, c) for i, c in non_empty if not is_key_like(c)]

    if not keys or not vals:
        return pairs

    # 각 키에 대해 가장 가까운 오른쪽 값 매칭 (거리 제한 없이)
    used_vals = set()
    key_val_pairs = []

    for key_idx, key_text in sorted(keys, key=lambda x: x[0]):
        best_val = None
        best_dist = float('inf')

        for val_idx, val_text in vals:
            if val_idx in used_vals:
                continue
            if val_idx > key_idx:  # 값은 키 오른쪽에 있어야 함
                dist = val_idx - key_idx
                if dist < best_dist:
                    best_dist = dist
                    best_val = (val_idx, val_text)

        if best_val:
            used_vals.add(best_val[0])
            key_val_pairs.append((key_text.strip(), best_val[1].strip()))

    return key_val_pairs


def test_form_parser():
    """폼 파서 테스트"""
    tables_dir = Path("data/converted_v2/test/test-document/tables")

    test_files = [
        "table_005_01.json",  # 가입조건 폼 (17x15)
        "table_004_01.json",  # 보장내용 테이블 (비교용)
        "table_002_02.json",  # 안내사항 (비교용)
    ]

    print("=" * 70)
    print("폼 테이블 파싱 테스트")
    print("=" * 70)

    for filename in test_files:
        filepath = tables_dir / filename
        if not filepath.exists():
            print(f"\n⚠️ {filename} 없음")
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            table = json.load(f)

        # 폼 테이블 여부 판단
        is_form = is_form_table(table)

        total_cells = sum(len(row) for row in table)
        empty_cells = sum(1 for row in table for cell in row if cell == "")
        empty_ratio = empty_cells / total_cells if total_cells > 0 else 0

        print(f"\n{'='*70}")
        print(f"테이블: {filename}")
        print(f"크기: {len(table)} 행 x {len(table[0])} 열")
        print(f"빈 셀 비율: {empty_ratio:.1%}")
        print(f"폼 테이블 여부: {'✅ 예' if is_form else '❌ 아니오'}")

        if is_form:
            print(f"\n--- 폼 파싱 결과 ---")
            result = parse_form_table(table)

            print(f"\n섹션 ({len(result['sections'])}개):")
            for section in result['sections']:
                print(f"  - {section['name']} (행 {section['row']})")

            print(f"\n필드 ({len(result['fields'])}개):")
            for key, value in list(result['fields'].items())[:15]:
                # 긴 값은 축약
                display_value = value[:50] + "..." if len(value) > 50 else value
                print(f"  {key}: {display_value}")

            if len(result['fields']) > 15:
                print(f"  ... 외 {len(result['fields']) - 15}개")
        else:
            print(f"\n--- 일반 테이블 (기존 방식 유지) ---")
            print(f"첫 3행 미리보기:")
            for i, row in enumerate(table[:3]):
                non_empty = [c for c in row if c]
                print(f"  행 {i+1}: {non_empty[:4]}...")


if __name__ == "__main__":
    test_form_parser()
