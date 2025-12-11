"""
실제 데이터 검색 테스트 (LLM API 호출 없이)
"""
import os
os.environ['POSTGRES_URL'] = 'postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology'

from retrieval.hybrid_retriever import HybridRetriever
import json

def test_search(query: str, top_k: int = 5):
    """검색 테스트 실행"""
    print(f"\n{'='*80}")
    print(f"🔍 검색어: {query}")
    print(f"{'='*80}\n")

    with HybridRetriever() as retriever:
        # 1. 엔티티 추출
        print("📋 Step 1: 엔티티 추출")
        entities = retriever.nl_mapper.extract_entities(query)
        print(f"   - 회사: {entities.get('companies', [])}")
        print(f"   - 상품: {entities.get('products', [])}")
        print(f"   - 담보: {entities.get('coverages', [])}")
        print(f"   - 필터: {entities.get('filters', {})}")
        print()

        # 2. 검색 실행
        print("🔎 Step 2: 벡터 검색 실행")
        results = retriever.search(query, top_k=top_k)
        print(f"   ✅ 검색 결과: {len(results)}개\n")

        # 3. 결과 출력
        print("📄 검색 결과:")
        print("-" * 80)

        for i, result in enumerate(results, 1):
            print(f"\n[{i}] Clause ID: {result['clause_id']}")
            print(f"    유사도: {result['similarity']:.4f}")
            print(f"    문서 타입: {result['doc_type']}")
            print(f"    조항 타입: {result['clause_type']}")
            print(f"    상품 ID: {result['product_id']}")
            print(f"    내용: {result['clause_text'][:200]}...")

        print("\n" + "="*80 + "\n")

        return results

if __name__ == "__main__":
    # 테스트 쿼리들
    test_queries = [
        "암 진단금 3000만원",
        "삼성화재 뇌출혈 보장",
        "입원일당 얼마인가요?",
    ]

    for query in test_queries:
        test_search(query, top_k=3)
