#!/usr/bin/env python3
"""
벡터 검색 모니터링 및 벤치마크 스크립트

용도: pgvector HNSW 인덱스 성능 모니터링 및 벤치마크
실행: python db_refactoring/scripts/monitor_vector_search.py [--benchmark] [--stats]
"""

import os
import sys
import time
import json
import argparse
import statistics
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import psycopg2
from psycopg2.extras import RealDictCursor


class VectorSearchMonitor:
    """벡터 검색 모니터링 및 벤치마크"""

    def __init__(self):
        self.postgres_url = os.getenv('POSTGRES_URL')
        if not self.postgres_url:
            raise ValueError("POSTGRES_URL 환경 변수가 필요합니다.")

    def get_connection(self):
        """DB 연결 생성"""
        return psycopg2.connect(self.postgres_url)

    def get_index_stats(self) -> dict:
        """인덱스 통계 조회"""
        conn = self.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        stats = {}

        # 테이블 통계
        cur.execute("""
            SELECT
                COUNT(*) as total_embeddings,
                COUNT(embedding) as with_embedding,
                COUNT(DISTINCT model_name) as model_count
            FROM clause_embedding
        """)
        stats['table'] = dict(cur.fetchone())

        # 모델별 통계
        cur.execute("""
            SELECT model_name, COUNT(*) as count
            FROM clause_embedding
            WHERE model_name IS NOT NULL
            GROUP BY model_name
            ORDER BY count DESC
        """)
        stats['models'] = [dict(row) for row in cur.fetchall()]

        # 인덱스 통계
        cur.execute("""
            SELECT
                i.indexname as name,
                pg_size_pretty(pg_relation_size(c.oid)) as size,
                pg_relation_size(c.oid) as size_bytes,
                am.amname as type
            FROM pg_indexes i
            JOIN pg_class c ON c.relname = i.indexname
            JOIN pg_am am ON am.oid = c.relam
            WHERE i.tablename = 'clause_embedding'
            ORDER BY pg_relation_size(c.oid) DESC
        """)
        stats['indexes'] = [dict(row) for row in cur.fetchall()]

        # 테이블 크기
        cur.execute("""
            SELECT
                pg_size_pretty(pg_total_relation_size('clause_embedding')) as total_size,
                pg_size_pretty(pg_table_size('clause_embedding')) as table_size,
                pg_size_pretty(pg_indexes_size('clause_embedding')) as index_size
        """)
        stats['sizes'] = dict(cur.fetchone())

        cur.close()
        conn.close()

        return stats

    def get_sample_embeddings(self, limit: int = 5) -> list:
        """샘플 임베딩 조회 (벤치마크용)"""
        conn = self.get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, embedding
            FROM clause_embedding
            WHERE embedding IS NOT NULL
            ORDER BY RANDOM()
            LIMIT %s
        """, (limit,))

        embeddings = cur.fetchall()
        cur.close()
        conn.close()

        return embeddings

    def benchmark_search(self, num_queries: int = 10, top_k: int = 10,
                         ef_search_values: list = None) -> dict:
        """벡터 검색 벤치마크 실행"""
        if ef_search_values is None:
            ef_search_values = [40, 100, 200]

        conn = self.get_connection()
        cur = conn.cursor()

        # 샘플 쿼리 벡터 가져오기
        sample_embeddings = self.get_sample_embeddings(num_queries)

        if not sample_embeddings:
            return {'error': '임베딩 데이터가 없습니다. build_index를 먼저 실행하세요.'}

        results = {}

        for ef_search in ef_search_values:
            cur.execute(f"SET hnsw.ef_search = {ef_search}")

            latencies = []

            for emb_id, embedding in sample_embeddings:
                # 벡터를 문자열로 변환
                embedding_str = str(list(embedding))

                start_time = time.perf_counter()

                cur.execute(f"""
                    SELECT id, embedding <=> %s::vector as distance
                    FROM clause_embedding
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """, (embedding_str, embedding_str, top_k))

                _ = cur.fetchall()
                end_time = time.perf_counter()

                latency_ms = (end_time - start_time) * 1000
                latencies.append(latency_ms)

            results[ef_search] = {
                'ef_search': ef_search,
                'num_queries': len(latencies),
                'top_k': top_k,
                'latency_ms': {
                    'min': round(min(latencies), 2),
                    'max': round(max(latencies), 2),
                    'mean': round(statistics.mean(latencies), 2),
                    'median': round(statistics.median(latencies), 2),
                    'p95': round(sorted(latencies)[int(len(latencies) * 0.95)], 2) if len(latencies) >= 20 else None,
                }
            }

        cur.close()
        conn.close()

        return results

    def check_index_usage(self) -> dict:
        """인덱스 사용 여부 확인"""
        conn = self.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 샘플 임베딩 가져오기
        sample = self.get_sample_embeddings(1)

        if not sample:
            return {'error': '임베딩 데이터가 없습니다.'}

        embedding_str = str(list(sample[0][1]))

        # EXPLAIN 실행
        cur.execute(f"""
            EXPLAIN (FORMAT JSON)
            SELECT id, embedding <=> %s::vector as distance
            FROM clause_embedding
            ORDER BY embedding <=> %s::vector
            LIMIT 10
        """, (embedding_str, embedding_str))

        plan = cur.fetchone()

        cur.close()
        conn.close()

        # Index Scan 확인
        plan_json = plan[0] if isinstance(plan, tuple) else plan
        plan_str = json.dumps(plan_json)

        return {
            'uses_hnsw_index': 'idx_clause_embedding_hnsw' in plan_str or 'Index Scan' in plan_str,
            'plan': plan_json
        }

    def print_stats(self):
        """통계 출력"""
        stats = self.get_index_stats()

        print("\n" + "=" * 60)
        print("벡터 검색 인덱스 통계")
        print("=" * 60)

        print("\n📊 테이블 통계:")
        print("-" * 40)
        print(f"  총 임베딩 수: {stats['table']['total_embeddings']:,}")
        print(f"  임베딩 있음: {stats['table']['with_embedding']:,}")
        print(f"  모델 수: {stats['table']['model_count']}")

        if stats['models']:
            print("\n📊 모델별 통계:")
            print("-" * 40)
            for model in stats['models']:
                print(f"  {model['model_name'] or 'NULL'}: {model['count']:,}")

        print("\n📊 인덱스 통계:")
        print("-" * 40)
        for idx in stats['indexes']:
            print(f"  {idx['name']}")
            print(f"    타입: {idx['type']}, 크기: {idx['size']}")

        print("\n📊 저장소 크기:")
        print("-" * 40)
        print(f"  테이블: {stats['sizes']['table_size']}")
        print(f"  인덱스: {stats['sizes']['index_size']}")
        print(f"  전체: {stats['sizes']['total_size']}")

        print("\n" + "=" * 60)

    def print_benchmark(self, num_queries: int = 10):
        """벤치마크 결과 출력"""
        print("\n" + "=" * 60)
        print("벡터 검색 벤치마크")
        print("=" * 60)

        # 인덱스 사용 확인
        index_check = self.check_index_usage()
        if 'error' in index_check:
            print(f"\n❌ {index_check['error']}")
            return

        print(f"\n🔍 HNSW 인덱스 사용: {'✅ 예' if index_check['uses_hnsw_index'] else '❌ 아니오'}")

        # 벤치마크 실행
        print(f"\n📊 벤치마크 실행 중 ({num_queries}개 쿼리)...")
        results = self.benchmark_search(num_queries=num_queries)

        if 'error' in results:
            print(f"\n❌ {results['error']}")
            return

        print("\n" + "-" * 60)
        print(f"{'ef_search':>10} {'min(ms)':>10} {'mean(ms)':>10} {'median(ms)':>12} {'max(ms)':>10}")
        print("-" * 60)

        for ef_search, data in sorted(results.items()):
            lat = data['latency_ms']
            print(f"{ef_search:>10} {lat['min']:>10.2f} {lat['mean']:>10.2f} {lat['median']:>12.2f} {lat['max']:>10.2f}")

        print("-" * 60)
        print("\n💡 권장사항:")
        print("  - ef_search=40: 기본값, 속도 우선")
        print("  - ef_search=100: 균형")
        print("  - ef_search=200: 정확도 우선")

        print("\n" + "=" * 60)

    def save_benchmark_result(self, num_queries: int = 20):
        """벤치마크 결과 저장"""
        stats = self.get_index_stats()
        benchmark = self.benchmark_search(num_queries=num_queries)

        result = {
            'timestamp': datetime.now().isoformat(),
            'stats': stats,
            'benchmark': benchmark,
            'config': {
                'num_queries': num_queries,
                'postgres_url': self.postgres_url.split('@')[1] if '@' in self.postgres_url else 'hidden'
            }
        }

        # 결과 저장
        output_dir = project_root / 'db_refactoring' / 'test_results'
        output_dir.mkdir(exist_ok=True)

        output_file = output_dir / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        print(f"\n✅ 결과 저장됨: {output_file}")

        return result


def main():
    parser = argparse.ArgumentParser(description='벡터 검색 모니터링 및 벤치마크')
    parser.add_argument('--stats', action='store_true', help='인덱스 통계 출력')
    parser.add_argument('--benchmark', action='store_true', help='벤치마크 실행')
    parser.add_argument('--save', action='store_true', help='벤치마크 결과 저장')
    parser.add_argument('--queries', type=int, default=10, help='벤치마크 쿼리 수 (기본: 10)')
    parser.add_argument('--json', action='store_true', help='JSON 형식으로 출력')

    args = parser.parse_args()

    monitor = VectorSearchMonitor()

    if args.json:
        result = {
            'stats': monitor.get_index_stats(),
        }
        if args.benchmark:
            result['benchmark'] = monitor.benchmark_search(num_queries=args.queries)
        print(json.dumps(result, indent=2, default=str))
    elif args.save:
        monitor.save_benchmark_result(num_queries=args.queries)
    elif args.benchmark:
        monitor.print_stats()
        monitor.print_benchmark(num_queries=args.queries)
    elif args.stats:
        monitor.print_stats()
    else:
        # 기본: 통계만 출력
        monitor.print_stats()


if __name__ == '__main__':
    main()
