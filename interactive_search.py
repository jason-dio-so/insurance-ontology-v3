"""
대화형 검색 인터페이스 (LLM API 호출 없이)
"""
import os
os.environ['POSTGRES_URL'] = 'postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology'

from retrieval.hybrid_retriever import HybridRetriever
import psycopg2

def get_full_context(clause_id: int, conn):
    """조항의 전체 컨텍스트 가져오기"""
    with conn.cursor() as cur:
        # 조항 정보와 상품/회사 정보 가져오기
        cur.execute("""
            SELECT
                dc.clause_text,
                p.product_name,
                c.company_name,
                d.doc_type,
                ce.metadata as embedding_metadata
            FROM document_clause dc
            JOIN document d ON dc.document_id = d.id
            JOIN product p ON d.product_id = p.id
            JOIN company c ON p.company_id = c.id
            LEFT JOIN clause_embedding ce ON dc.id = ce.clause_id
            WHERE dc.id = %s
        """, (clause_id,))

        result = cur.fetchone()
        if result:
            return {
                'clause_text': result[0],
                'product_name': result[1],
                'company_name': result[2],
                'doc_type': result[3],
                'embedding_metadata': result[4]
            }
        return None

def interactive_search():
    """대화형 검색"""
    print("\n" + "="*80)
    print("🔍 보험 온톨로지 검색 시스템 (LLM 호출 없음)")
    print("="*80)
    print("\n명령어:")
    print("  - 검색어 입력: 자연어로 검색")
    print("  - 'q' 또는 'quit': 종료")
    print("  - 'help': 도움말")
    print("  - 'stats': 데이터베이스 통계")
    print()

    conn = psycopg2.connect('postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology')
    retriever = HybridRetriever()

    try:
        while True:
            query = input("검색어 > ").strip()

            if not query:
                continue

            if query.lower() in ['q', 'quit', 'exit']:
                print("👋 종료합니다.")
                break

            if query.lower() == 'help':
                print("\n검색 예시:")
                print("  - 암 진단금")
                print("  - 삼성화재 뇌출혈 보장")
                print("  - KB손보 입원일당")
                print("  - 수술비 1000만원")
                print()
                continue

            if query.lower() == 'stats':
                show_stats(conn)
                continue

            # 검색 실행
            print(f"\n{'─'*80}")
            print(f"🔍 검색: {query}")
            print(f"{'─'*80}\n")

            # 엔티티 추출
            entities = retriever.nl_mapper.extract_entities(query)

            if entities.get('companies') or entities.get('products') or entities.get('coverages'):
                print("📌 추출된 정보:")
                if entities.get('companies'):
                    print(f"   회사: {', '.join(entities['companies'])}")
                if entities.get('products'):
                    print(f"   상품: {', '.join(entities['products'])}")
                if entities.get('coverages'):
                    print(f"   담보: {', '.join(entities['coverages'])}")
                if entities.get('filters'):
                    filters = entities['filters']
                    if filters.get('amount'):
                        amt = filters['amount']
                        if amt.get('min') == amt.get('max'):
                            print(f"   금액: {amt['min']:,}원")
                        else:
                            print(f"   금액: {amt.get('min', 0):,}원 ~ {amt.get('max', float('inf')):,}원")
                print()

            # 벡터 검색
            results = retriever.search(query, top_k=5)

            if not results:
                print("❌ 검색 결과가 없습니다.\n")
                continue

            print(f"✅ {len(results)}개 결과 발견\n")

            # 결과 출력
            for i, result in enumerate(results, 1):
                # 전체 컨텍스트 가져오기
                context = get_full_context(result['clause_id'], conn)

                print(f"━━━ 결과 {i} ━━━")
                print(f"회사: {context['company_name']}")
                print(f"상품: {context['product_name']}")
                print(f"문서타입: {result['doc_type']}")
                print(f"유사도: {result['similarity']:.4f}")
                print(f"\n내용:")
                print(f"{result['clause_text']}")

                # structured_data가 있으면 출력
                emb_meta = context.get('embedding_metadata', {})
                structured = emb_meta.get('structured_data', {}) if emb_meta else {}
                if structured:
                    print(f"\n📊 구조화된 정보:")
                    if structured.get('coverage_name'):
                        print(f"   담보명: {structured['coverage_name']}")
                    if structured.get('coverage_amount'):
                        print(f"   보장금액: {structured['coverage_amount']}")
                    if structured.get('premium_amount'):
                        print(f"   보험료: {structured['premium_amount']}")

                print()

    finally:
        conn.close()
        retriever.close()

def show_stats(conn):
    """데이터베이스 통계 출력"""
    with conn.cursor() as cur:
        # 회사 수
        cur.execute("SELECT COUNT(*) FROM company")
        company_count = cur.fetchone()[0]

        # 상품 수
        cur.execute("SELECT COUNT(*) FROM product")
        product_count = cur.fetchone()[0]

        # 문서 수 (타입별)
        cur.execute("""
            SELECT doc_type, COUNT(*)
            FROM document
            GROUP BY doc_type
            ORDER BY COUNT(*) DESC
        """)
        doc_stats = cur.fetchall()

        # 조항 수
        cur.execute("SELECT COUNT(*) FROM document_clause")
        clause_count = cur.fetchone()[0]

        # 임베딩 수
        cur.execute("SELECT COUNT(*) FROM clause_embedding")
        embedding_count = cur.fetchone()[0]

        print("\n📊 데이터베이스 통계")
        print("─"*50)
        print(f"회사: {company_count}개")
        print(f"상품: {product_count}개")
        print(f"총 조항: {clause_count:,}개")
        print(f"임베딩: {embedding_count:,}개")
        print(f"\n문서 타입별:")
        for doc_type, count in doc_stats:
            print(f"  - {doc_type}: {count}개")
        print()

if __name__ == "__main__":
    interactive_search()
