#!/usr/bin/env python3
"""
문서 변환 스크립트

PDF 문서를 변환하고 documents_metadata.json을 자동 생성
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Optional

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.pdf_converter import convert_document


def parse_document_metadata_from_path(pdf_path: Path) -> Dict:
    """
    PDF 경로에서 메타데이터 추출

    경로 패턴: examples/{carrier}/{carrier}_{doc_type_kr}[({variant})][_YYMM].pdf
    예: examples/samsung/삼성_약관.pdf
        examples/lotte/롯데_약관(남).pdf
        examples/db/DB_가입설계서(40세이하)_2511.pdf
    """
    import unicodedata

    # ⚠️ CRITICAL: macOS 파일시스템은 NFD 형식으로 파일명 저장
    # 모든 한글 문자열을 NFC로 정규화하여 비교 가능하게 만듦
    filename = unicodedata.normalize('NFC', pdf_path.stem)
    parts = filename.split('_')

    # 기본값
    carrier_kr = parts[0]

    # Carrier code mapping (NFC 정규화된 문자열)
    carrier_map = {
        unicodedata.normalize('NFC', '삼성'): 'samsung',
        'DB': 'db',
        unicodedata.normalize('NFC', '롯데'): 'lotte',
        unicodedata.normalize('NFC', '한화'): 'hanwha',
        unicodedata.normalize('NFC', '현대'): 'hyundai',
        'KB': 'kb',
        unicodedata.normalize('NFC', '메리츠'): 'meritz',
        unicodedata.normalize('NFC', '흥국'): 'heungkuk'
    }

    # Doc type mapping (NFC 정규화된 문자열)
    doc_type_map = {
        unicodedata.normalize('NFC', '약관'): 'terms',
        unicodedata.normalize('NFC', '사업방법서'): 'business_spec',
        unicodedata.normalize('NFC', '사업설명서'): 'business_spec',
        unicodedata.normalize('NFC', '상품요약서'): 'product_summary',
        unicodedata.normalize('NFC', '쉬운요약서'): 'easy_summary',
        unicodedata.normalize('NFC', '가입설계서'): 'proposal'
    }

    carrier_code = carrier_map.get(carrier_kr, carrier_kr.lower())

    # Extract variant first (from parentheses)
    doc_subtype = None
    attributes = {}

    if '(남)' in filename or '(남자)' in filename:
        doc_subtype = 'male'
        attributes['target_gender'] = 'male'
    elif '(여)' in filename or '(여자)' in filename:
        doc_subtype = 'female'
        attributes['target_gender'] = 'female'
    elif '40세이하' in filename or '40세 이하' in filename:
        doc_subtype = 'age_40_under'
        attributes['target_age_range'] = '≤40'
    elif '41세이상' in filename or '41세 이상' in filename:
        doc_subtype = 'age_41_over'
        attributes['target_age_range'] = '≥41'

    # Remove parentheses content for doc_type extraction
    import re
    filename_clean = re.sub(r'\([^)]*\)', '', filename)

    # Extract doc_type from cleaned filename
    doc_type = "unknown"
    doc_type_kr_final = "unknown"

    for kr_name, en_code in doc_type_map.items():
        if kr_name in filename_clean:
            doc_type = en_code
            doc_type_kr_final = kr_name
            break

    # Special case: easy_summary
    if doc_type == 'easy_summary':
        doc_subtype = 'easy_summary'

    return {
        'carrier_code': carrier_code,
        'carrier_kr': carrier_kr,
        'doc_type': doc_type,
        'doc_type_kr': doc_type_kr_final,
        'doc_subtype': doc_subtype,
        'attributes': attributes if attributes else None
    }


def scan_pdf_documents(examples_dir: Path = Path("examples")) -> List[Dict]:
    """
    examples/ 디렉토리를 스캔하여 모든 PDF 문서 메타데이터 추출
    """
    documents = []

    for carrier_dir in examples_dir.iterdir():
        if not carrier_dir.is_dir():
            continue

        carrier_code = carrier_dir.name

        # Load product info from product_info.json
        product_info_path = carrier_dir / "product_info.json"
        if not product_info_path.exists():
            print(f"Warning: {product_info_path} not found, skipping {carrier_code}")
            continue

        with open(product_info_path, 'r', encoding='utf-8') as f:
            product_info = json.load(f)

        for pdf_file in carrier_dir.glob("*.pdf"):
            # Parse metadata from filename
            meta = parse_document_metadata_from_path(pdf_file)

            # Generate document_id
            variant_suffix = f"-{meta['doc_subtype']}" if meta['doc_subtype'] and meta['doc_subtype'] != 'easy_summary' else ""
            if meta['doc_subtype'] == 'easy_summary':
                variant_suffix = ""

            document_id = f"{carrier_code}-{meta['doc_type']}{variant_suffix}"

            doc_metadata = {
                'document_id': document_id,
                'company_code': carrier_code,
                'company_name': meta['carrier_kr'],
                'product_code': product_info['product_code'],
                'product_name': product_info['product_name'],
                'version': product_info['version'],
                'effective_date': product_info.get('effective_date', '2025-01-01'),
                'doc_type': meta['doc_type'],
                'doc_type_kr': meta['doc_type_kr'],
                'doc_subtype': meta['doc_subtype'],
                'file_path': str(pdf_file.absolute()),
                'attributes': meta['attributes']
            }

            documents.append(doc_metadata)

    return documents


def main():
    parser = argparse.ArgumentParser(description="PDF 문서를 표준 포맷으로 변환")
    parser.add_argument(
        "--examples-dir",
        default="examples",
        help="PDF 문서가 있는 examples 디렉토리"
    )
    parser.add_argument(
        "--output-dir",
        default="data/converted",
        help="변환 결과 출력 디렉토리"
    )
    parser.add_argument(
        "--metadata-output",
        default="data/documents_metadata.json",
        help="생성할 메타데이터 JSON 파일"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="최대 파싱 페이지 수 (테스트용, None이면 전체)"
    )
    parser.add_argument(
        "--company-code",
        help="특정 회사만 변환 (samsung, db, kb 등)"
    )

    args = parser.parse_args()

    # Scan PDF documents
    print(f"Scanning {args.examples_dir} for PDF documents...")
    documents = scan_pdf_documents(Path(args.examples_dir))

    print(f"Found {len(documents)} documents")
    print()

    # 필터링
    if args.company_code:
        documents = [doc for doc in documents if doc["company_code"] == args.company_code]
        print(f"Filtering by company_code: {args.company_code} -> {len(documents)} documents")

    if not documents:
        print("No documents to convert.")
        sys.exit(0)

    # 변환 실행
    results = []
    converted_documents = []

    for idx, doc in enumerate(documents, 1):
        print(f"\n[{idx}/{len(documents)}] Converting {doc['document_id']}")
        print(f"  File: {doc['file_path']}")
        print(f"  Type: {doc['doc_type_kr']} ({doc['doc_type']})")

        # PDF 파일 존재 확인
        pdf_path = Path(doc["file_path"])
        if not pdf_path.exists():
            print(f"  ✗ PDF file not found: {pdf_path}")
            results.append({
                "document_id": doc["document_id"],
                "status": "error",
                "error": "PDF file not found"
            })
            continue

        try:
            result = convert_document(
                pdf_path=str(pdf_path),
                document_id=doc["document_id"],
                company_name=doc.get("company_name", "Unknown"),
                product_name=doc.get("product_name", "Unknown"),
                doc_type=doc["doc_type"],
                version=doc.get("version", "v1"),
                effective_date=doc.get("effective_date", "2025-01-01"),
                output_base_dir=args.output_dir,
                max_pages=args.max_pages
            )

            # Add total_pages to document metadata
            doc['total_pages'] = result['total_pages']

            results.append({
                "document_id": doc["document_id"],
                "status": "success",
                **result
            })

            converted_documents.append(doc)

        except Exception as e:
            print(f"  ✗ Error: {e}")
            results.append({
                "document_id": doc["document_id"],
                "status": "error",
                "error": str(e)
            })

    # 결과 요약
    print("\n" + "=" * 60)
    print("Conversion Summary")
    print("=" * 60)

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")

    print(f"Total: {len(results)}")
    print(f"Success: {success_count}")
    print(f"Error: {error_count}")
    print()

    if error_count > 0:
        print("Errors:")
        for r in results:
            if r["status"] == "error":
                print(f"  - {r['document_id']}: {r.get('error', 'Unknown error')}")

    # 성공한 문서 목록
    if success_count > 0:
        print("\nSuccessfully converted:")
        for r in results:
            if r["status"] == "success":
                print(f"  ✓ {r['document_id']}")
                print(f"    Pages: {r['processed_pages']}/{r['total_pages']}")
                print(f"    Tables: {r['tables_extracted']}")
                print(f"    Sections: {r['sections_detected']}")
                print(f"    Output: {r['output_dir']}")

    # Save metadata JSON
    if converted_documents:
        metadata_path = Path(args.metadata_output)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(converted_documents, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Metadata saved to: {metadata_path}")
        print(f"   {len(converted_documents)} documents")


if __name__ == "__main__":
    main()
