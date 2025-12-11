"""
Graph Loader - PostgreSQL to Neo4j Synchronization

Purpose: Sync entities from PostgreSQL to Neo4j graph database
Strategy:
  1. Sync Company, Product, ProductVariant nodes
  2. Sync Coverage, Benefit nodes
  3. Sync DiseaseCodeSet, DiseaseCode nodes
  4. Create relationships between nodes

Design: Phase 3 of TODO.md
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from neo4j import GraphDatabase
from typing import List, Dict
import logging
import argparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GraphLoader:
    """Load entities from PostgreSQL into Neo4j"""

    def __init__(self, postgres_url: str, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.postgres_url = postgres_url
        self.neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    def close(self):
        """Close Neo4j connection"""
        self.neo4j_driver.close()

    def clear_graph(self):
        """Clear all nodes and relationships in Neo4j"""
        with self.neo4j_driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("Cleared all Neo4j nodes and relationships")

    def sync_products(self) -> Dict:
        """
        Sync Company, Product, ProductVariant from PostgreSQL to Neo4j

        Returns:
            Summary dictionary
        """
        conn = psycopg2.connect(self.postgres_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get companies
        cur.execute("""
            SELECT id, company_name, company_code, business_type
            FROM company
        """)
        companies = cur.fetchall()

        # Get products
        cur.execute("""
            SELECT p.id, p.company_id, p.product_name, p.product_code, p.business_type,
                   c.company_name, c.company_code
            FROM product p
            JOIN company c ON p.company_id = c.id
        """)
        products = cur.fetchall()

        # Get product variants
        cur.execute("""
            SELECT pv.id, pv.product_id, pv.variant_name, pv.variant_code,
                   pv.target_gender, pv.target_age_range,
                   p.product_name, p.product_code
            FROM product_variant pv
            JOIN product p ON pv.product_id = p.id
        """)
        variants = cur.fetchall()

        cur.close()
        conn.close()

        # Load into Neo4j
        with self.neo4j_driver.session() as session:
            # Create Company nodes
            company_count = 0
            for company in companies:
                session.run("""
                    MERGE (c:Company {id: $id})
                    SET c.name = $name,
                        c.code = $code,
                        c.business_type = $business_type
                """, {
                    'id': company['id'],
                    'name': company['company_name'],
                    'code': company['company_code'],
                    'business_type': company['business_type']
                })
                company_count += 1

            # Create Product nodes and relationships
            product_count = 0
            for product in products:
                session.run("""
                    MERGE (p:Product {id: $id})
                    SET p.name = $name,
                        p.code = $code,
                        p.business_type = $business_type
                    WITH p
                    MATCH (c:Company {id: $company_id})
                    MERGE (c)-[:HAS_PRODUCT]->(p)
                """, {
                    'id': product['id'],
                    'name': product['product_name'],
                    'code': product['product_code'],
                    'business_type': product['business_type'],
                    'company_id': product['company_id']
                })
                product_count += 1

            # Create ProductVariant nodes and relationships
            variant_count = 0
            for variant in variants:
                session.run("""
                    MERGE (pv:ProductVariant {id: $id})
                    SET pv.name = $name,
                        pv.code = $code,
                        pv.target_gender = $gender,
                        pv.target_age_range = $age_range
                    WITH pv
                    MATCH (p:Product {id: $product_id})
                    MERGE (p)-[:HAS_VARIANT]->(pv)
                """, {
                    'id': variant['id'],
                    'name': variant['variant_name'],
                    'code': variant['variant_code'],
                    'gender': variant['target_gender'],
                    'age_range': variant['target_age_range'],
                    'product_id': variant['product_id']
                })
                variant_count += 1

        summary = {
            'companies': company_count,
            'products': product_count,
            'variants': variant_count
        }

        logger.info(f"Synced {company_count} companies, {product_count} products, {variant_count} variants to Neo4j")
        return summary

    def sync_coverage(self) -> Dict:
        """
        Sync Coverage nodes from PostgreSQL to Neo4j

        Returns:
            Summary dictionary
        """
        conn = psycopg2.connect(self.postgres_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get coverages
        cur.execute("""
            SELECT c.id, c.product_id, c.coverage_name, c.coverage_code,
                   c.coverage_category, c.renewal_type, c.is_basic,
                   p.product_name, p.product_code
            FROM coverage c
            JOIN product p ON c.product_id = p.id
        """)
        coverages = cur.fetchall()

        cur.close()
        conn.close()

        # Load into Neo4j
        with self.neo4j_driver.session() as session:
            coverage_count = 0
            for coverage in coverages:
                session.run("""
                    MERGE (cov:Coverage {id: $id})
                    SET cov.name = $name,
                        cov.code = $code,
                        cov.category = $category,
                        cov.renewal_type = $renewal_type,
                        cov.is_basic = $is_basic
                    WITH cov
                    MATCH (p:Product {id: $product_id})
                    MERGE (p)-[:OFFERS]->(cov)
                """, {
                    'id': coverage['id'],
                    'name': coverage['coverage_name'],
                    'code': coverage['coverage_code'],
                    'category': coverage['coverage_category'],
                    'renewal_type': coverage['renewal_type'],
                    'is_basic': coverage['is_basic'],
                    'product_id': coverage['product_id']
                })
                coverage_count += 1

        logger.info(f"Synced {coverage_count} coverages to Neo4j")
        return {'coverages': coverage_count}

    def sync_benefits(self) -> Dict:
        """
        Sync Benefit nodes from PostgreSQL to Neo4j

        Returns:
            Summary dictionary
        """
        conn = psycopg2.connect(self.postgres_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get benefits
        cur.execute("""
            SELECT b.id, b.coverage_id, b.benefit_name, b.benefit_amount,
                   b.benefit_type, b.benefit_amount_text,
                   c.coverage_name
            FROM benefit b
            JOIN coverage c ON b.coverage_id = c.id
        """)
        benefits = cur.fetchall()

        cur.close()
        conn.close()

        # Load into Neo4j
        with self.neo4j_driver.session() as session:
            benefit_count = 0
            for benefit in benefits:
                # Convert Decimal to int
                amount = int(benefit['benefit_amount']) if benefit['benefit_amount'] else None

                session.run("""
                    MERGE (b:Benefit {id: $id})
                    SET b.name = $name,
                        b.amount = $amount,
                        b.amount_text = $amount_text,
                        b.type = $type
                    WITH b
                    MATCH (cov:Coverage {id: $coverage_id})
                    MERGE (cov)-[:HAS_BENEFIT]->(b)
                """, {
                    'id': benefit['id'],
                    'name': benefit['benefit_name'],
                    'amount': amount,
                    'amount_text': benefit['benefit_amount_text'],
                    'type': benefit['benefit_type'],
                    'coverage_id': benefit['coverage_id']
                })
                benefit_count += 1

        logger.info(f"Synced {benefit_count} benefits to Neo4j")
        return {'benefits': benefit_count}

    def sync_documents(self) -> Dict:
        """
        Sync Document nodes from PostgreSQL to Neo4j

        Returns:
            Summary dictionary
        """
        conn = psycopg2.connect(self.postgres_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get documents with company, product, variant info
        cur.execute("""
            SELECT d.id, d.document_id, d.doc_type, d.doc_subtype, d.version,
                   d.total_pages, d.company_id, d.product_id, d.variant_id,
                   c.company_name, c.company_code,
                   p.product_name, p.product_code,
                   pv.variant_name, pv.variant_code
            FROM document d
            JOIN company c ON d.company_id = c.id
            LEFT JOIN product p ON d.product_id = p.id
            LEFT JOIN product_variant pv ON d.variant_id = pv.id
        """)
        documents = cur.fetchall()

        cur.close()
        conn.close()

        # Load into Neo4j
        with self.neo4j_driver.session() as session:
            document_count = 0
            for doc in documents:
                # Create Document node and link to Company (always exists)
                session.run("""
                    MERGE (d:Document {id: $id})
                    SET d.document_id = $document_id,
                        d.doc_type = $doc_type,
                        d.doc_subtype = $doc_subtype,
                        d.version = $version,
                        d.total_pages = $total_pages
                    WITH d
                    MATCH (c:Company {id: $company_id})
                    MERGE (c)-[:HAS_DOCUMENT]->(d)
                """, {
                    'id': doc['id'],
                    'document_id': doc['document_id'],
                    'doc_type': doc['doc_type'],
                    'doc_subtype': doc['doc_subtype'],
                    'version': doc['version'],
                    'total_pages': doc['total_pages'],
                    'company_id': doc['company_id']
                })

                # Link to Product if exists
                if doc['product_id']:
                    session.run("""
                        MATCH (d:Document {id: $doc_id})
                        MATCH (p:Product {id: $product_id})
                        MERGE (p)-[:HAS_DOCUMENT]->(d)
                    """, {
                        'doc_id': doc['id'],
                        'product_id': doc['product_id']
                    })

                # Link to ProductVariant if exists
                if doc['variant_id']:
                    session.run("""
                        MATCH (d:Document {id: $doc_id})
                        MATCH (pv:ProductVariant {id: $variant_id})
                        MERGE (pv)-[:HAS_DOCUMENT]->(d)
                    """, {
                        'doc_id': doc['id'],
                        'variant_id': doc['variant_id']
                    })

                document_count += 1

        logger.info(f"Synced {document_count} documents to Neo4j")
        return {'documents': document_count}

    def sync_disease_codes(self) -> Dict:
        """
        Sync DiseaseCodeSet and DiseaseCode nodes from PostgreSQL to Neo4j

        Returns:
            Summary dictionary
        """
        conn = psycopg2.connect(self.postgres_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get disease code sets
        cur.execute("""
            SELECT id, set_name, description, version
            FROM disease_code_set
        """)
        code_sets = cur.fetchall()

        # Get disease codes
        cur.execute("""
            SELECT dc.id, dc.code_set_id, dc.code, dc.code_type, dc.description_kr,
                   dcs.set_name
            FROM disease_code dc
            JOIN disease_code_set dcs ON dc.code_set_id = dcs.id
        """)
        codes = cur.fetchall()

        cur.close()
        conn.close()

        # Load into Neo4j
        with self.neo4j_driver.session() as session:
            # Create DiseaseCodeSet nodes
            code_set_count = 0
            for code_set in code_sets:
                session.run("""
                    MERGE (dcs:DiseaseCodeSet {id: $id})
                    SET dcs.name = $name,
                        dcs.description = $description,
                        dcs.version = $version
                """, {
                    'id': code_set['id'],
                    'name': code_set['set_name'],
                    'description': code_set['description'],
                    'version': code_set['version']
                })
                code_set_count += 1

            # Create DiseaseCode nodes and relationships
            code_count = 0
            for code in codes:
                session.run("""
                    MERGE (dc:DiseaseCode {id: $id})
                    SET dc.code = $code,
                        dc.type = $type,
                        dc.description = $description
                    WITH dc
                    MATCH (dcs:DiseaseCodeSet {id: $code_set_id})
                    MERGE (dcs)-[:CONTAINS]->(dc)
                """, {
                    'id': code['id'],
                    'code': code['code'],
                    'type': code['code_type'],
                    'description': code['description_kr'],
                    'code_set_id': code['code_set_id']
                })
                code_count += 1

        logger.info(f"Synced {code_set_count} code sets, {code_count} codes to Neo4j")
        return {'code_sets': code_set_count, 'codes': code_count}

    def get_graph_stats(self) -> Dict:
        """Get Neo4j graph statistics"""
        with self.neo4j_driver.session() as session:
            # Manual count (APOC not available)
            labels = {}
            for label in ['Company', 'Product', 'ProductVariant', 'Coverage', 'Benefit', 'Document', 'DiseaseCodeSet', 'DiseaseCode']:
                count_result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                labels[label] = count_result.single()['count']

            rel_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            total_rels = rel_result.single()['count']

            return {
                'labels': labels,
                'total_relationships': total_rels
            }


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Sync PostgreSQL data to Neo4j')
    parser.add_argument('--clear', action='store_true', help='Clear all Neo4j data first')
    parser.add_argument('--sync-products', action='store_true', help='Sync products and companies')
    parser.add_argument('--sync-coverage', action='store_true', help='Sync coverages')
    parser.add_argument('--sync-benefits', action='store_true', help='Sync benefits')
    parser.add_argument('--sync-documents', action='store_true', help='Sync documents')
    parser.add_argument('--sync-disease-codes', action='store_true', help='Sync disease codes')
    parser.add_argument('--all', action='store_true', help='Sync all entities')

    args = parser.parse_args()

    postgres_url = os.getenv('POSTGRES_URL', 'postgresql://postgres:postgres@localhost:5432/insurance_ontology')
    neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
    neo4j_password = os.getenv('NEO4J_PASSWORD', 'password')

    loader = GraphLoader(postgres_url, neo4j_uri, neo4j_user, neo4j_password)

    try:
        if args.clear:
            logger.info("Clearing Neo4j database...")
            loader.clear_graph()

        if args.sync_products or args.all:
            logger.info("Syncing products...")
            summary = loader.sync_products()
            print(f"\n✅ Products Sync Complete:")
            print(f"   Companies: {summary['companies']}")
            print(f"   Products: {summary['products']}")
            print(f"   Variants: {summary['variants']}")

        if args.sync_coverage or args.all:
            logger.info("Syncing coverages...")
            summary = loader.sync_coverage()
            print(f"\n✅ Coverage Sync Complete:")
            print(f"   Coverages: {summary['coverages']}")

        if args.sync_benefits or args.all:
            logger.info("Syncing benefits...")
            summary = loader.sync_benefits()
            print(f"\n✅ Benefits Sync Complete:")
            print(f"   Benefits: {summary['benefits']}")

        if args.sync_documents or args.all:
            logger.info("Syncing documents...")
            summary = loader.sync_documents()
            print(f"\n✅ Documents Sync Complete:")
            print(f"   Documents: {summary['documents']}")

        if args.sync_disease_codes or args.all:
            logger.info("Syncing disease codes...")
            summary = loader.sync_disease_codes()
            print(f"\n✅ Disease Codes Sync Complete:")
            print(f"   Code Sets: {summary['code_sets']}")
            print(f"   Codes: {summary['codes']}")

        # Show final stats
        stats = loader.get_graph_stats()
        print(f"\n📊 Neo4j Graph Statistics:")
        if 'labels' in stats and isinstance(stats['labels'], dict):
            print(f"   Nodes:")
            for label, count in stats['labels'].items():
                print(f"     - {label}: {count}")
            if 'total_relationships' in stats:
                print(f"   Total Relationships: {stats['total_relationships']}")

    finally:
        loader.close()


if __name__ == '__main__':
    main()
