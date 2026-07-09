#!/usr/bin/env python3
"""CLI: run the evaluation suite.

    ANTHROPIC_API_KEY=sk-... python run_eval.py [--no-judge]
"""
import argparse
import os
import sys

from src.evaluation import run_eval, write_report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-judge", action="store_true",
                    help="skip LLM-as-judge (deterministic metrics only)")
    args = ap.parse_args()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Set ANTHROPIC_API_KEY first.")

    def progress(i, n, case_id):
        print(f"[{i + 1}/{n}] {case_id}", flush=True)

    report = run_eval(api_key, use_judge=not args.no_judge,
                      progress_cb=progress)
    path = write_report(report)
    print("\n=== Summary ===")
    for k, v in report["summary"].items():
        print(f"{k}: {v}")
    print(f"\nFull report: {path}")


if __name__ == "__main__":
    main()
