#!/usr/bin/env python3
"""
Gold QA Set 평가 스크립트

Usage:
    python scripts/evaluate_qa.py \
        --qa-set data/gold_qa_set_50.json \
        --output results/phase5_evaluation.json
"""

import json
import time
import sys
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.cli import InsuranceCLI


class QAEvaluator:
    """Gold QA Set 평가기"""

    def __init__(self, qa_set_path: str):
        """
        Args:
            qa_set_path: Gold QA Set JSON 파일 경로
        """
        with open(qa_set_path, 'r', encoding='utf-8') as f:
            self.qa_data = json.load(f)

        # Use full Hybrid RAG pipeline instead of just retriever
        self.cli = InsuranceCLI()
        self.results = []

    def evaluate_query(self, query_obj: Dict[str, Any]) -> Dict[str, Any]:
        """
        단일 쿼리 평가

        Args:
            query_obj: Query object from Gold QA Set

        Returns:
            평가 결과 딕셔너리
        """
        query_id = query_obj['id']
        query_text = query_obj['query']
        category = query_obj['category']
        difficulty = query_obj['difficulty']

        print(f"\n[{query_id}] {query_text}")
        print(f"  Category: {category}, Difficulty: {difficulty}")

        # Run full Hybrid RAG pipeline
        start_time = time.time()
        try:
            # Suppress CLI output temporarily
            import io
            from contextlib import redirect_stdout

            f = io.StringIO()
            with redirect_stdout(f):
                result = self.cli.hybrid_query(query_text, limit=5, use_llm=True)

            latency_ms = (time.time() - start_time) * 1000
            answer = result.get('answer', '')
            num_results = len(result.get('context', {}).get('clauses', []))

        except Exception as e:
            print(f"  ❌ Error: {e}")

            # Transaction Isolation: Rollback failed transaction
            try:
                self.cli.pg_conn.rollback()
                self.cli.retriever.pg_conn.rollback()
                self.cli.assembler.pg_conn.rollback()
            except:
                pass  # Ignore rollback errors

            return {
                "query_id": query_id,
                "query": query_text,
                "category": category,
                "difficulty": difficulty,
                "status": "error",
                "error": str(e),
                "latency_ms": 0,
                "num_results": 0
            }

        # Check if LLM answer contains expected keywords
        expected_contains = query_obj.get('expected_answer_contains', [])
        matched_keywords = []

        for keyword in expected_contains:
            if keyword in answer:
                matched_keywords.append(keyword)

        keyword_match_rate = len(matched_keywords) / len(expected_contains) if expected_contains else 1.0

        # Success criteria: Check if LLM answer contains expected keywords
        # Edge case queries may expect no results or specific behavior
        if query_obj.get('expected_result') == 'no_results':
            # For edge cases expecting no answer, check if answer indicates no info found
            success = ('찾을 수 없' in answer or '정보가 없' in answer or '제공되지 않' in answer)
        else:
            # For normal queries, require at least 70% keyword match
            success = (keyword_match_rate >= 0.7)

        eval_result = {
            "query_id": query_id,
            "query": query_text,
            "category": category,
            "difficulty": difficulty,
            "status": "success" if success else "fail",
            "latency_ms": round(latency_ms, 2),
            "num_results": num_results,
            "keyword_match_rate": round(keyword_match_rate, 2),
            "matched_keywords": matched_keywords,
            "expected_keywords": expected_contains,
            "answer": answer
        }

        status_icon = "✅" if success else "❌"
        print(f"  {status_icon} Keywords: {len(matched_keywords)}/{len(expected_contains)} ({keyword_match_rate:.1%}), " +
              f"Latency: {latency_ms:.2f}ms")

        return eval_result

    def evaluate_all(self) -> Dict[str, Any]:
        """전체 QA Set 평가"""
        queries = self.qa_data['queries']
        total = len(queries)

        print(f"\n{'='*80}")
        print(f"Starting evaluation: {total} queries")
        print(f"{'='*80}")

        for query_obj in queries:
            result = self.evaluate_query(query_obj)
            self.results.append(result)

        # 통계 계산
        success_count = sum(1 for r in self.results if r['status'] == 'success')
        error_count = sum(1 for r in self.results if r['status'] == 'error')
        overall_accuracy = success_count / total * 100

        # 카테고리별 통계
        category_stats = {}
        for category in set(r['category'] for r in self.results):
            category_results = [r for r in self.results if r['category'] == category]
            category_success = sum(1 for r in category_results if r['status'] == 'success')
            category_stats[category] = {
                "total": len(category_results),
                "success": category_success,
                "accuracy": round(category_success / len(category_results) * 100, 2)
            }

        # 난이도별 통계
        difficulty_stats = {}
        for difficulty in set(r['difficulty'] for r in self.results):
            difficulty_results = [r for r in self.results if r['difficulty'] == difficulty]
            difficulty_success = sum(1 for r in difficulty_results if r['status'] == 'success')
            difficulty_stats[difficulty] = {
                "total": len(difficulty_results),
                "success": difficulty_success,
                "accuracy": round(difficulty_success / len(difficulty_results) * 100, 2)
            }

        # 지연시간 통계
        latencies = [r['latency_ms'] for r in self.results if r['status'] != 'error']
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0

        evaluation_summary = {
            "metadata": {
                "evaluation_date": datetime.now().isoformat(),
                "total_queries": total,
                "qa_set_version": self.qa_data['metadata']['version']
            },
            "overall": {
                "total": total,
                "success": success_count,
                "error": error_count,
                "accuracy": round(overall_accuracy, 2)
            },
            "by_category": category_stats,
            "by_difficulty": difficulty_stats,
            "latency": {
                "avg_ms": round(avg_latency, 2),
                "p95_ms": round(p95_latency, 2)
            },
            "detailed_results": self.results
        }

        return evaluation_summary

    def print_summary(self, summary: Dict[str, Any]):
        """평가 결과 요약 출력"""
        print(f"\n{'='*80}")
        print(f"EVALUATION SUMMARY")
        print(f"{'='*80}")

        overall = summary['overall']
        print(f"\n📊 Overall Performance:")
        print(f"   Total: {overall['total']}")
        print(f"   Success: {overall['success']}")
        print(f"   Error: {overall['error']}")
        print(f"   Accuracy: {overall['accuracy']}%")

        # 목표 달성 여부
        target_accuracy = self.qa_data['metadata']['success_criteria']['overall_accuracy']
        target_value = 90.0  # ≥90%
        if overall['accuracy'] >= target_value:
            print(f"   Status: ✅ PASS (Target: {target_accuracy})")
        else:
            print(f"   Status: ❌ FAIL (Target: {target_accuracy}, Got: {overall['accuracy']}%)")

        # 카테고리별
        print(f"\n📈 By Category:")
        for category, stats in summary['by_category'].items():
            print(f"   {category:15s}: {stats['success']:2d}/{stats['total']:2d} ({stats['accuracy']:5.1f}%)")

        # 난이도별
        print(f"\n🎯 By Difficulty:")
        for difficulty, stats in summary['by_difficulty'].items():
            print(f"   {difficulty:7s}: {stats['success']:2d}/{stats['total']:2d} ({stats['accuracy']:5.1f}%)")

        # 지연시간
        latency = summary['latency']
        print(f"\n⏱️  Latency:")
        print(f"   Average: {latency['avg_ms']:.2f}ms")
        print(f"   P95: {latency['p95_ms']:.2f}ms")
        target_latency = 5000  # 5초
        if latency['p95_ms'] < target_latency:
            print(f"   Status: ✅ PASS (Target: <{target_latency}ms)")
        else:
            print(f"   Status: ❌ FAIL (Target: <{target_latency}ms)")

    def save_results(self, output_path: str):
        """결과 저장"""
        summary = self.evaluate_all()
        self.print_summary(summary)

        # JSON 저장
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Results saved to: {output_path}")

        return summary


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate Gold QA Set")
    parser.add_argument("--qa-set", default="data/gold_qa_set_50.json",
                        help="Path to Gold QA Set JSON")
    parser.add_argument("--output", default="results/phase5_evaluation.json",
                        help="Output path for evaluation results")

    args = parser.parse_args()

    evaluator = QAEvaluator(args.qa_set)
    evaluator.save_results(args.output)


if __name__ == "__main__":
    main()
