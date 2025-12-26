from __future__ import annotations

import argparse
from pathlib import Path

from utis.core.runtime import build_storage
from utis.core.events import EventProcessor
from utis.modules.email.analyzer import analyze_and_store, save_report
from utis.modules.whatsapp.analyzer import analyze_and_store as analyze_wa
from utis.modules.osint.providers import LocalFileProvider
from utis.modules.osint.service import CacheStore, OSINTService, RateLimiter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="utis")
    parser.add_argument("--storage", choices=["sqlite", "jsonl"], default="sqlite")
    parser.add_argument("--path", help="Path to storage file")

    subparsers = parser.add_subparsers(dest="command", required=True)

    email_parser = subparsers.add_parser("email", help="Email security analyzer")
    email_sub = email_parser.add_subparsers(dest="email_cmd", required=True)
    email_analyze = email_sub.add_parser("analyze")
    email_analyze.add_argument("input_path")
    email_analyze.add_argument("--entity", default="email_default")
    email_analyze.add_argument("--out", default="outputs/email_report.json")

    wa_parser = subparsers.add_parser("wa", help="WhatsApp analyzer")
    wa_sub = wa_parser.add_subparsers(dest="wa_cmd", required=True)
    wa_analyze = wa_sub.add_parser("analyze")
    wa_analyze.add_argument("input_path")
    wa_analyze.add_argument("--entity", default="wa_default")
    wa_analyze.add_argument("--export", default="outputs/wa")

    osint_parser = subparsers.add_parser("osint", help="OSINT footprint checker")
    osint_sub = osint_parser.add_subparsers(dest="osint_cmd", required=True)
    osint_search = osint_sub.add_parser("search")
    osint_search.add_argument("query")
    osint_search.add_argument("--entity", default="osint_default")
    osint_search.add_argument("--dataset", default="sample_data/osint_dataset.txt")
    osint_search.add_argument("--cache", default="data/osint_cache.db")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    storage = build_storage(args.storage, args.path)
    processor = EventProcessor(storage)

    if args.command == "email" and args.email_cmd == "analyze":
        report = analyze_and_store(Path(args.input_path), args.entity, processor)
        out_path = Path(args.out)
        save_report(report, out_path)
        print(f"Saved report to {out_path}")
        return

    if args.command == "wa" and args.wa_cmd == "analyze":
        stats = analyze_wa(Path(args.input_path), args.entity, processor, Path(args.export))
        print(f"WhatsApp analysis complete. Total messages: {stats['messages_total']}")
        return

    if args.command == "osint" and args.osint_cmd == "search":
        provider = LocalFileProvider(Path(args.dataset))
        cache = CacheStore(Path(args.cache))
        service = OSINTService([provider], cache, RateLimiter(), processor)
        report = service.search(args.query, args.entity)
        print(report)
        return


if __name__ == "__main__":
    main()
