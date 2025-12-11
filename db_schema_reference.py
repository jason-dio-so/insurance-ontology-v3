"""
데이터베이스 스키마 레퍼런스
항상 이 파일을 먼저 확인하고 쿼리 작성
"""
import psycopg2

def show_all_schemas():
    """모든 테이블의 스키마 출력"""
    conn = psycopg2.connect('postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology')

    tables = [
        'company',
        'product',
        'document',
        'document_clause',
        'clause_embedding',
        'product_variant',
        'coverage'
    ]

    print("\n" + "="*100)
    print("📚 데이터베이스 스키마 레퍼런스")
    print("="*100 + "\n")

    with conn.cursor() as cur:
        for table in tables:
            # 테이블 스키마
            cur.execute("""
                SELECT column_name, data_type, character_maximum_length
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table,))

            columns = cur.fetchall()

            if not columns:
                print(f"⚠️  테이블 '{table}'을 찾을 수 없습니다.\n")
                continue

            print(f"┌─ 📋 {table.upper()} " + "─"*(95-len(table)))
            print("│")

            for col_name, data_type, max_len in columns:
                type_str = f"{data_type}" + (f"({max_len})" if max_len else "")
                print(f"│  • {col_name:<30} {type_str:<30}")

            # 샘플 데이터 개수
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"│")
            print(f"│  총 {count:,}개 레코드")
            print("└" + "─"*98 + "\n")

    conn.close()

def show_metadata_structure():
    """clause_embedding의 metadata JSONB 구조 확인"""
    conn = psycopg2.connect('postgresql://postgres:postgres@127.0.0.1:5432/insurance_ontology')

    print("="*100)
    print("🔍 CLAUSE_EMBEDDING.METADATA 구조")
    print("="*100 + "\n")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT metadata
            FROM clause_embedding
            WHERE metadata->'structured_data' IS NOT NULL
            LIMIT 1
        """)

        result = cur.fetchone()
        if result:
            import json
            metadata = result[0]
            print("샘플 metadata:")
            print(json.dumps(metadata, indent=2, ensure_ascii=False))
            print()

            # structured_data 키들
            cur.execute("""
                SELECT DISTINCT jsonb_object_keys(metadata->'structured_data')
                FROM clause_embedding
                WHERE metadata->'structured_data' IS NOT NULL
                LIMIT 20
            """)

            keys = [row[0] for row in cur.fetchall()]
            print("structured_data의 주요 키:")
            for key in sorted(set(keys)):
                print(f"  • {key}")

    conn.close()

if __name__ == "__main__":
    show_all_schemas()
    print()
    show_metadata_structure()
