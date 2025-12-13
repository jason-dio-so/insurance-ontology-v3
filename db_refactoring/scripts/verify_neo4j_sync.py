#!/usr/bin/env python3
"""
PostgreSQL ↔ Neo4j 동기화 검증 스크립트

용도: PostgreSQL과 Neo4j 간 엔티티 수 일치 여부 확인
실행: python db_refactoring/scripts/verify_neo4j_sync.py
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import psycopg2
from neo4j import GraphDatabase


class SyncVerifier:
    """PostgreSQL ↔ Neo4j 동기화 검증기"""

    def __init__(self):
        # PostgreSQL 연결
        self.postgres_url = os.getenv('POSTGRES_URL')
        if not self.postgres_url:
            raise ValueError("POSTGRES_URL 환경 변수가 필요합니다. .env 파일을 확인하세요.")

        # Neo4j 연결
        neo4j_uri = os.getenv('NEO4J_URI')
        neo4j_user = os.getenv('NEO4J_USER')
        neo4j_password = os.getenv('NEO4J_PASSWORD')

        if not all([neo4j_uri, neo4j_user, neo4j_password]):
            raise ValueError("NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD 환경 변수가 필요합니다.")

        self.neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    def close(self):
        """연결 종료"""
        self.neo4j_driver.close()

    def get_postgres_counts(self) -> dict:
        """PostgreSQL 엔티티 수 조회"""
        conn = psycopg2.connect(self.postgres_url)
        cur = conn.cursor()

        counts = {}

        # 엔티티별 카운트
        entities = [
            ('Company', 'company'),
            ('Product', 'product'),
            ('ProductVariant', 'product_variant'),
            ('Coverage', 'coverage'),
            ('Benefit', 'benefit'),
            ('Document', 'document'),
            ('DiseaseCodeSet', 'disease_code_set'),
            ('DiseaseCode', 'disease_code'),
        ]

        for label, table in entities:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            counts[label] = cur.fetchone()[0]

        cur.close()
        conn.close()

        return counts

    def get_neo4j_counts(self) -> dict:
        """Neo4j 노드 수 조회"""
        counts = {}

        with self.neo4j_driver.session() as session:
            labels = [
                'Company', 'Product', 'ProductVariant', 'Coverage',
                'Benefit', 'Document', 'DiseaseCodeSet', 'DiseaseCode'
            ]

            for label in labels:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                counts[label] = result.single()['count']

        return counts

    def get_neo4j_relationship_counts(self) -> dict:
        """Neo4j 관계 수 조회"""
        counts = {}

        with self.neo4j_driver.session() as session:
            rel_types = [
                'HAS_PRODUCT', 'HAS_VARIANT', 'OFFERS', 'HAS_BENEFIT',
                'HAS_DOCUMENT', 'CONTAINS', 'PARENT_OF'
            ]

            for rel_type in rel_types:
                result = session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count")
                counts[rel_type] = result.single()['count']

        return counts

    def verify(self) -> bool:
        """동기화 검증 실행"""
        print("\n" + "=" * 60)
        print("PostgreSQL ↔ Neo4j 동기화 검증")
        print("=" * 60)

        # 카운트 조회
        pg_counts = self.get_postgres_counts()
        neo4j_counts = self.get_neo4j_counts()
        rel_counts = self.get_neo4j_relationship_counts()

        # 노드 비교 테이블
        print("\n📊 노드 수 비교:")
        print("-" * 50)
        print(f"{'엔티티':<20} {'PostgreSQL':>10} {'Neo4j':>10} {'상태':>8}")
        print("-" * 50)

        all_match = True
        for label in pg_counts.keys():
            pg_count = pg_counts.get(label, 0)
            neo4j_count = neo4j_counts.get(label, 0)

            if pg_count == neo4j_count:
                status = "✓"
            else:
                status = "✗"
                all_match = False

            print(f"{label:<20} {pg_count:>10} {neo4j_count:>10} {status:>8}")

        print("-" * 50)

        # 관계 수
        print("\n📊 Neo4j 관계 수:")
        print("-" * 30)
        for rel_type, count in rel_counts.items():
            if count > 0:
                print(f"  {rel_type}: {count}")
        print("-" * 30)

        # 결과 요약
        print("\n" + "=" * 60)
        if all_match:
            print("✅ 동기화 검증 성공: 모든 엔티티 수 일치")
        else:
            print("❌ 동기화 검증 실패: 일부 엔티티 수 불일치")
            print("   → 'python -m ingestion.graph_loader --all' 실행 권장")
        print("=" * 60)

        return all_match


def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(description='PostgreSQL ↔ Neo4j 동기화 검증')
    parser.add_argument('--json', action='store_true', help='JSON 형식으로 출력')
    args = parser.parse_args()

    verifier = SyncVerifier()

    try:
        if args.json:
            import json
            pg_counts = verifier.get_postgres_counts()
            neo4j_counts = verifier.get_neo4j_counts()
            rel_counts = verifier.get_neo4j_relationship_counts()

            result = {
                'postgres': pg_counts,
                'neo4j': neo4j_counts,
                'relationships': rel_counts,
                'all_match': pg_counts == neo4j_counts
            }
            print(json.dumps(result, indent=2))
        else:
            success = verifier.verify()
            sys.exit(0 if success else 1)

    finally:
        verifier.close()


if __name__ == '__main__':
    main()
