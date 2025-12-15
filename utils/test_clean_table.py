#!/usr/bin/env python3
"""
_clean_table() 개선 로직 테스트

기존 로직과 개선 로직을 비교하여 부작용 여부를 확인합니다.
"""

import json
from pathlib import Path
from typing import List


def clean_table_original(table: List[List]) -> List[List[str]]:
    """기존 _clean_table() 로직"""
    import re
    if not table:
        return []

    cleaned = []
    for row in table:
        if row is None:
            continue
        cleaned_row = []
        for cell in row:
            if cell is None:
                cleaned_row.append("")
            else:
                cell_str = str(cell).replace('\n', ' ').strip()
                cell_str = re.sub(r'\s+', ' ', cell_str)
                cleaned_row.append(cell_str)

        if any(cell for cell in cleaned_row):
            cleaned.append(cleaned_row)

    return cleaned


def clean_table_improved(table: List[List]) -> List[List[str]]:
    """개선된 _clean_table() 로직"""
    import re
    if not table:
        return []

    cleaned = []
    for row in table:
        if row is None:
            continue
        cleaned_row = []
        for cell in row:
            if cell is None:
                cleaned_row.append("")
            else:
                cell_str = str(cell).replace('\n', ' ').strip()
                cell_str = re.sub(r'\s+', ' ', cell_str)
                cleaned_row.append(cell_str)

        if any(cell for cell in cleaned_row):
            cleaned.append(cleaned_row)

    # 개선 1: 빈 열 제거
    cleaned = remove_empty_columns(cleaned)

    # 개선 2: 연속 빈 셀 병합 (선택적)
    # cleaned = merge_spanning_cells(cleaned)

    return cleaned


def remove_empty_columns(table: List[List[str]]) -> List[List[str]]:
    """완전히 비어있는 열 제거"""
    if not table:
        return table

    num_cols = len(table[0]) if table else 0

    # 각 열이 비어있는지 확인
    empty_cols = set()
    for col_idx in range(num_cols):
        is_empty = all(
            row[col_idx] == "" if col_idx < len(row) else True
            for row in table
        )
        if is_empty:
            empty_cols.add(col_idx)

    # 빈 열 제거
    if not empty_cols:
        return table

    result = []
    for row in table:
        new_row = [
            cell for idx, cell in enumerate(row)
            if idx not in empty_cols
        ]
        result.append(new_row)

    return result


def merge_spanning_cells(table: List[List[str]]) -> List[List[str]]:
    """연속된 빈 셀을 앞 셀과 병합 (행 단위)"""
    result = []
    for row in table:
        new_row = []
        for cell in row:
            if cell == "" and new_row:
                # 빈 셀은 스킵 (앞 셀에 이미 값이 있음)
                continue
            new_row.append(cell)
        result.append(new_row)
    return result


def compare_results(original: List[List[str]], improved: List[List[str]], table_id: str):
    """결과 비교"""
    print(f"\n{'='*60}")
    print(f"테이블: {table_id}")
    print(f"{'='*60}")

    print(f"\n[기존] 행: {len(original)}, 열: {len(original[0]) if original else 0}")
    print(f"[개선] 행: {len(improved)}, 열: {len(improved[0]) if improved else 0}")

    # 첫 3행 비교
    print("\n--- 첫 3행 비교 ---")
    for i in range(min(3, len(original))):
        print(f"\n행 {i+1} [기존]: {original[i][:6]}...")  # 처음 6열만
        if i < len(improved):
            print(f"행 {i+1} [개선]: {improved[i][:6] if len(improved[i]) >= 6 else improved[i]}...")

    # 변경 요약
    orig_empty = sum(1 for row in original for cell in row if cell == "")
    impr_empty = sum(1 for row in improved for cell in row if cell == "")

    print(f"\n--- 변경 요약 ---")
    print(f"빈 셀 수: {orig_empty} → {impr_empty} (감소: {orig_empty - impr_empty})")

    orig_cols = len(original[0]) if original else 0
    impr_cols = len(improved[0]) if improved else 0
    print(f"열 수: {orig_cols} → {impr_cols} (제거: {orig_cols - impr_cols})")


def main():
    tables_dir = Path("data/converted_v2/test/test-document/tables")

    if not tables_dir.exists():
        print(f"테이블 디렉토리가 없습니다: {tables_dir}")
        return

    # 테스트할 테이블 선택
    test_tables = [
        "table_004_01.json",  # 보장내용 (34x6)
        "table_005_01.json",  # 가입조건 (17x15) - 병합 셀 많음
        "table_002_02.json",  # 작은 테이블
    ]

    print("=" * 60)
    print("_clean_table() 개선 로직 테스트")
    print("=" * 60)

    for table_file in test_tables:
        table_path = tables_dir / table_file
        if not table_path.exists():
            print(f"\n⚠️ {table_file} 없음, 스킵")
            continue

        with open(table_path, 'r', encoding='utf-8') as f:
            table_data = json.load(f)

        # 이미 clean된 데이터이므로 그대로 사용
        original = table_data
        improved = remove_empty_columns(table_data)

        compare_results(original, improved, table_file)

    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()
