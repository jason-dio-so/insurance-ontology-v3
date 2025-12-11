#!/usr/bin/env python3
"""
Batch Ingestion Script with Checkpoint Support

Features:
- Process documents in batches (default: 5)
- Save progress to checkpoint file
- Resume from last successful batch
- Timeout-resistant (each batch < 2 min)

Usage:
    # Ingest all documents in batches
    python scripts/batch_ingest.py --all

    # Ingest specific carrier
    python scripts/batch_ingest.py --carrier lotte

    # Custom batch size
    python scripts/batch_ingest.py --all --batch-size 3

    # Resume from checkpoint
    python scripts/batch_ingest.py --resume
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.ingest_v3 import DocumentIngestionPipeline

# Checkpoint file
CHECKPOINT_FILE = 'data/checkpoints/phase1_progress.json'


def load_checkpoint():
    """Load checkpoint from JSON file"""
    if not os.path.exists(CHECKPOINT_FILE):
        return {'completed': [], 'failed': [], 'last_updated': None}

    with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_checkpoint(completed, failed):
    """Save checkpoint to JSON file"""
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)

    checkpoint = {
        'completed': completed,
        'failed': failed,
        'last_updated': datetime.now().isoformat(),
    }

    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(checkpoint, f, indent=2, ensure_ascii=False)

    print(f"💾 Checkpoint saved: {len(completed)} completed, {len(failed)} failed")


def load_metadata(metadata_json='data/documents_metadata.json'):
    """Load documents metadata"""
    with open(metadata_json, 'r', encoding='utf-8') as f:
        return json.load(f)


def filter_documents(documents, carrier=None, completed_ids=None):
    """
    Filter documents by carrier and remove completed ones

    Args:
        documents: List of document metadata dicts
        carrier: Carrier code filter (optional)
        completed_ids: List of already completed document IDs

    Returns:
        Filtered list of documents
    """
    filtered = documents

    # Filter by carrier
    if carrier:
        filtered = [d for d in filtered if d.get('company_code') == carrier]

    # Remove completed
    if completed_ids:
        filtered = [d for d in filtered if d['document_id'] not in completed_ids]

    return filtered


def chunks(lst, n):
    """Yield successive n-sized chunks from lst"""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def ingest_batch(pipeline, batch, batch_num, total_batches):
    """
    Ingest a batch of documents

    Args:
        pipeline: DocumentIngestionPipeline instance
        batch: List of document metadata dicts
        batch_num: Current batch number (1-indexed)
        total_batches: Total number of batches

    Returns:
        Tuple of (completed_ids, failed_ids)
    """
    print(f"\n{'='*60}")
    print(f"📦 Batch {batch_num}/{total_batches} ({len(batch)} documents)")
    print(f"{'='*60}")

    completed = []
    failed = []

    for doc_meta in batch:
        doc_id = doc_meta['document_id']

        try:
            result = pipeline.ingest_document(doc_meta)

            if result['status'] == 'success':
                completed.append(doc_id)
                print(f"  ✅ {doc_id}: {result['clause_count']} clauses")
            else:
                failed.append(doc_id)
                print(f"  ❌ {doc_id}: {result.get('message')}")

        except Exception as e:
            failed.append(doc_id)
            print(f"  ❌ {doc_id}: {str(e)}")

    return completed, failed


def main():
    parser = argparse.ArgumentParser(description='Batch document ingestion')
    parser.add_argument('--all', action='store_true', help='Process all documents')
    parser.add_argument('--carrier', type=str, help='Process specific carrier (e.g., lotte, samsung)')
    parser.add_argument('--batch-size', type=int, default=5, help='Batch size (default: 5)')
    parser.add_argument('--resume', action='store_true', help='Resume from checkpoint')
    parser.add_argument('--metadata', type=str, default='data/documents_metadata.json', help='Metadata JSON path')

    args = parser.parse_args()

    # Get DB URL from environment
    db_url = os.getenv('POSTGRES_URL')
    if not db_url:
        print("❌ Error: POSTGRES_URL environment variable not set")
        sys.exit(1)

    # Load checkpoint
    checkpoint = load_checkpoint()
    completed_ids = checkpoint['completed']
    failed_ids = checkpoint['failed']

    if args.resume:
        print(f"📂 Resuming from checkpoint:")
        print(f"  Completed: {len(completed_ids)} documents")
        print(f"  Failed: {len(failed_ids)} documents")

    # Load documents
    documents = load_metadata(args.metadata)

    # Filter documents
    documents_to_process = filter_documents(
        documents,
        carrier=args.carrier,
        completed_ids=completed_ids if args.resume else None
    )

    if not documents_to_process:
        print("✅ No documents to process (all done or none matched filters)")
        return

    print(f"\n📋 Documents to process: {len(documents_to_process)}")
    print(f"⚙️  Batch size: {args.batch_size}")

    # Initialize pipeline
    pipeline = DocumentIngestionPipeline(db_url)

    # Process in batches
    batches = list(chunks(documents_to_process, args.batch_size))
    total_batches = len(batches)

    for i, batch in enumerate(batches, 1):
        batch_completed, batch_failed = ingest_batch(pipeline, batch, i, total_batches)

        # Update checkpoint
        completed_ids.extend(batch_completed)
        failed_ids.extend(batch_failed)
        save_checkpoint(completed_ids, failed_ids)

    # Final summary
    print(f"\n{'='*60}")
    print(f"🎉 Ingestion Complete")
    print(f"{'='*60}")
    print(f"  Total documents: {len(documents)}")
    print(f"  Completed: {len(completed_ids)}")
    print(f"  Failed: {len(failed_ids)}")

    if failed_ids:
        print(f"\n⚠️  Failed documents:")
        for doc_id in failed_ids:
            print(f"    - {doc_id}")


if __name__ == '__main__':
    main()
