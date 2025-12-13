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

    def sync_coverage_hierarchy(self) -> Dict:
        """
        Sync PARENT_OF relationships for Coverage nodes from PostgreSQL to Neo4j

        Creates PARENT_OF relationships between Coverage nodes based on
        parent_coverage_id in PostgreSQL.

        Returns:
            Summary dictionary with relationship count
        """
        conn = psycopg2.connect(self.postgres_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get coverages with parent relationships
        cur.execute("""
            SELECT c.id as child_id, c.coverage_name as child_name,
                   p.id as parent_id, p.coverage_name as parent_name
            FROM coverage c
            JOIN coverage p ON c.parent_coverage_id = p.id
            WHERE c.parent_coverage_id IS NOT NULL
        """)
        relationships = cur.fetchall()

        cur.close()
        conn.close()

        # Load into Neo4j
        with self.neo4j_driver.session() as session:
            rel_count = 0
            for rel in relationships:
                session.run("""
                    MATCH (child:Coverage {id: $child_id})
                    MATCH (parent:Coverage {id: $parent_id})
                    MERGE (parent)-[:PARENT_OF]->(child)
                """, {
                    'child_id': rel['child_id'],
                    'parent_id': rel['parent_id']
                })
                rel_count += 1

        logger.info(f"Synced {rel_count} PARENT_OF relationships to Neo4j")
        return {'parent_of_relationships': rel_count}

    def sync_risk_events(self) -> Dict:
        """
        Sync RiskEvent nodes and TRIGGERS relationships from PostgreSQL to Neo4j

        Returns:
            Summary dictionary with node and relationship counts
        """
        conn = psycopg2.connect(self.postgres_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get risk events
        cur.execute("""
            SELECT id, event_type, event_name, severity_level, icd_code_pattern, description
            FROM risk_event
        """)
        risk_events = cur.fetchall()

        # Get benefit-risk_event relationships
        cur.execute("""
            SELECT bre.benefit_id, bre.risk_event_id
            FROM benefit_risk_event bre
        """)
        relationships = cur.fetchall()

        cur.close()
        conn.close()

        # Load into Neo4j
        with self.neo4j_driver.session() as session:
            # Create RiskEvent nodes
            event_count = 0
            for event in risk_events:
                session.run("""
                    MERGE (re:RiskEvent {id: $id})
                    SET re.event_type = $event_type,
                        re.event_name = $event_name,
                        re.severity_level = $severity_level,
                        re.icd_code_pattern = $icd_code_pattern,
                        re.description = $description
                """, {
                    'id': event['id'],
                    'event_type': event['event_type'],
                    'event_name': event['event_name'],
                    'severity_level': event['severity_level'],
                    'icd_code_pattern': event['icd_code_pattern'],
                    'description': event['description']
                })
                event_count += 1

            # Create TRIGGERS relationships
            rel_count = 0
            for rel in relationships:
                session.run("""
                    MATCH (b:Benefit {id: $benefit_id})
                    MATCH (re:RiskEvent {id: $risk_event_id})
                    MERGE (b)-[:TRIGGERS]->(re)
                """, {
                    'benefit_id': rel['benefit_id'],
                    'risk_event_id': rel['risk_event_id']
                })
                rel_count += 1

        logger.info(f"Synced {event_count} risk events, {rel_count} TRIGGERS relationships to Neo4j")
        return {'risk_events': event_count, 'triggers_relationships': rel_count}

    def sync_conditions(self) -> Dict:
        """
        Sync Condition nodes and HAS_CONDITION relationships from PostgreSQL to Neo4j

        Returns:
            Summary dictionary with node and relationship counts
        """
        conn = psycopg2.connect(self.postgres_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get conditions (from existing condition table)
        cur.execute("""
            SELECT id, coverage_id, condition_type, condition_text,
                   min_age, max_age, waiting_period_days
            FROM condition
        """)
        conditions = cur.fetchall()

        cur.close()
        conn.close()

        # Load into Neo4j
        with self.neo4j_driver.session() as session:
            cond_count = 0
            for cond in conditions:
                session.run("""
                    MERGE (c:Condition {id: $id})
                    SET c.condition_type = $condition_type,
                        c.condition_text = $condition_text,
                        c.min_age = $min_age,
                        c.max_age = $max_age,
                        c.waiting_period_days = $waiting_period_days
                    WITH c
                    MATCH (cov:Coverage {id: $coverage_id})
                    MERGE (cov)-[:HAS_CONDITION]->(c)
                """, {
                    'id': cond['id'],
                    'coverage_id': cond['coverage_id'],
                    'condition_type': cond['condition_type'],
                    'condition_text': cond['condition_text'],
                    'min_age': cond['min_age'],
                    'max_age': cond['max_age'],
                    'waiting_period_days': cond['waiting_period_days']
                })
                cond_count += 1

        logger.info(f"Synced {cond_count} conditions to Neo4j")
        return {'conditions': cond_count}

    def sync_exclusions(self) -> Dict:
        """
        Sync Exclusion nodes and HAS_EXCLUSION relationships from PostgreSQL to Neo4j

        Returns:
            Summary dictionary with node and relationship counts
        """
        conn = psycopg2.connect(self.postgres_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get exclusions (from existing exclusion table)
        cur.execute("""
            SELECT id, coverage_id, exclusion_type, exclusion_text, is_absolute
            FROM exclusion
        """)
        exclusions = cur.fetchall()

        cur.close()
        conn.close()

        # Load into Neo4j
        with self.neo4j_driver.session() as session:
            excl_count = 0
            for excl in exclusions:
                session.run("""
                    MERGE (e:Exclusion {id: $id})
                    SET e.exclusion_type = $exclusion_type,
                        e.exclusion_text = $exclusion_text,
                        e.is_absolute = $is_absolute
                    WITH e
                    MATCH (cov:Coverage {id: $coverage_id})
                    MERGE (cov)-[:HAS_EXCLUSION]->(e)
                """, {
                    'id': excl['id'],
                    'coverage_id': excl['coverage_id'],
                    'exclusion_type': excl['exclusion_type'],
                    'exclusion_text': excl['exclusion_text'],
                    'is_absolute': excl['is_absolute']
                })
                excl_count += 1

        logger.info(f"Synced {excl_count} exclusions to Neo4j")
        return {'exclusions': excl_count}

    def sync_plans(self) -> Dict:
        """
        Sync Plan nodes and relationships from PostgreSQL to Neo4j

        Creates:
        - Plan nodes
        - FOR_PRODUCT: Plan -> Product
        - HAS_VARIANT: Plan -> ProductVariant (if variant_id exists)
        - INCLUDES: Plan -> Coverage (with sum_insured, premium properties)
        - FROM_DOCUMENT: Plan -> Document (if document_id exists)

        Returns:
            Summary dictionary with node and relationship counts
        """
        conn = psycopg2.connect(self.postgres_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get plans
        cur.execute("""
            SELECT id, document_id, product_id, variant_id, plan_name,
                   target_gender, target_age, insurance_period, payment_period,
                   payment_cycle, total_premium, attributes
            FROM plan
        """)
        plans = cur.fetchall()

        # Get plan_coverage relationships
        cur.execute("""
            SELECT plan_id, coverage_id, sum_insured, sum_insured_text, premium, is_basic
            FROM plan_coverage
        """)
        plan_coverages = cur.fetchall()

        cur.close()
        conn.close()

        # Load into Neo4j
        with self.neo4j_driver.session() as session:
            # Create Plan nodes
            plan_count = 0
            for plan in plans:
                # Convert Decimal to float
                total_premium = float(plan['total_premium']) if plan['total_premium'] else None

                session.run("""
                    MERGE (pl:Plan {id: $id})
                    SET pl.plan_name = $plan_name,
                        pl.target_gender = $target_gender,
                        pl.target_age = $target_age,
                        pl.insurance_period = $insurance_period,
                        pl.payment_period = $payment_period,
                        pl.payment_cycle = $payment_cycle,
                        pl.total_premium = $total_premium,
                        pl.product_id = $product_id
                    WITH pl
                    MATCH (p:Product {id: $product_id})
                    MERGE (pl)-[:FOR_PRODUCT]->(p)
                """, {
                    'id': plan['id'],
                    'plan_name': plan['plan_name'],
                    'target_gender': plan['target_gender'],
                    'target_age': plan['target_age'],
                    'insurance_period': plan['insurance_period'],
                    'payment_period': plan['payment_period'],
                    'payment_cycle': plan['payment_cycle'],
                    'total_premium': total_premium,
                    'product_id': plan['product_id']
                })

                # Link to ProductVariant if exists
                if plan['variant_id']:
                    session.run("""
                        MATCH (pl:Plan {id: $plan_id})
                        MATCH (pv:ProductVariant {id: $variant_id})
                        MERGE (pl)-[:HAS_VARIANT]->(pv)
                    """, {
                        'plan_id': plan['id'],
                        'variant_id': plan['variant_id']
                    })

                # Link to Document if exists
                if plan['document_id']:
                    session.run("""
                        MATCH (pl:Plan {id: $plan_id})
                        MATCH (d:Document {id: $document_id})
                        MERGE (pl)-[:FROM_DOCUMENT]->(d)
                    """, {
                        'plan_id': plan['id'],
                        'document_id': plan['document_id']
                    })

                plan_count += 1

            # Create INCLUDES relationships with properties
            includes_count = 0
            for pc in plan_coverages:
                # Convert Decimal to float
                sum_insured = float(pc['sum_insured']) if pc['sum_insured'] else None
                premium = float(pc['premium']) if pc['premium'] else None

                session.run("""
                    MATCH (pl:Plan {id: $plan_id})
                    MATCH (cov:Coverage {id: $coverage_id})
                    MERGE (pl)-[r:INCLUDES]->(cov)
                    SET r.sum_insured = $sum_insured,
                        r.sum_insured_text = $sum_insured_text,
                        r.premium = $premium,
                        r.is_basic = $is_basic
                """, {
                    'plan_id': pc['plan_id'],
                    'coverage_id': pc['coverage_id'],
                    'sum_insured': sum_insured,
                    'sum_insured_text': pc['sum_insured_text'],
                    'premium': premium,
                    'is_basic': pc['is_basic']
                })
                includes_count += 1

        logger.info(f"Synced {plan_count} plans, {includes_count} INCLUDES relationships to Neo4j")
        return {'plans': plan_count, 'includes_relationships': includes_count}

    def get_graph_stats(self) -> Dict:
        """Get Neo4j graph statistics"""
        with self.neo4j_driver.session() as session:
            # Manual count (APOC not available)
            labels = {}
            for label in ['Company', 'Product', 'ProductVariant', 'Coverage', 'Benefit',
                          'Document', 'DiseaseCodeSet', 'DiseaseCode',
                          'RiskEvent', 'Condition', 'Exclusion', 'Plan']:
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
    parser.add_argument('--sync-coverage-hierarchy', action='store_true', help='Sync PARENT_OF relationships')
    parser.add_argument('--sync-risk-events', action='store_true', help='Sync risk events (ontology extension)')
    parser.add_argument('--sync-conditions', action='store_true', help='Sync conditions (ontology extension)')
    parser.add_argument('--sync-exclusions', action='store_true', help='Sync exclusions (ontology extension)')
    parser.add_argument('--sync-plans', action='store_true', help='Sync plans (가입설계)')
    parser.add_argument('--all', action='store_true', help='Sync all entities')

    args = parser.parse_args()

    postgres_url = os.getenv('POSTGRES_URL')
    neo4j_uri = os.getenv('NEO4J_URI')
    neo4j_user = os.getenv('NEO4J_USER')
    neo4j_password = os.getenv('NEO4J_PASSWORD')

    if not postgres_url:
        raise ValueError("POSTGRES_URL environment variable is required. Check .env file.")
    if not neo4j_uri or not neo4j_user or not neo4j_password:
        raise ValueError("NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD environment variables are required. Check .env file.")

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

        if args.sync_coverage_hierarchy or args.all:
            logger.info("Syncing coverage hierarchy (PARENT_OF)...")
            summary = loader.sync_coverage_hierarchy()
            print(f"\n✅ Coverage Hierarchy Sync Complete:")
            print(f"   PARENT_OF relationships: {summary['parent_of_relationships']}")

        if args.sync_risk_events or args.all:
            logger.info("Syncing risk events...")
            summary = loader.sync_risk_events()
            print(f"\n✅ Risk Events Sync Complete:")
            print(f"   Risk Events: {summary['risk_events']}")
            print(f"   TRIGGERS relationships: {summary['triggers_relationships']}")

        if args.sync_conditions or args.all:
            logger.info("Syncing conditions...")
            summary = loader.sync_conditions()
            print(f"\n✅ Conditions Sync Complete:")
            print(f"   Conditions: {summary['conditions']}")

        if args.sync_exclusions or args.all:
            logger.info("Syncing exclusions...")
            summary = loader.sync_exclusions()
            print(f"\n✅ Exclusions Sync Complete:")
            print(f"   Exclusions: {summary['exclusions']}")

        if args.sync_plans or args.all:
            logger.info("Syncing plans...")
            summary = loader.sync_plans()
            print(f"\n✅ Plans Sync Complete:")
            print(f"   Plans: {summary['plans']}")
            print(f"   INCLUDES relationships: {summary['includes_relationships']}")

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
