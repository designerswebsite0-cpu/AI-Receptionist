"""CLI entrypoint for importing the RKPR corpus into the knowledge base.

    python -m app.scripts.import_rkpr_knowledge --path ./RKPR_RAG_FINAL_DOCS --dry-run
    python -m app.scripts.import_rkpr_knowledge --path ./RKPR_RAG_FINAL_DOCS --execute

--dry-run builds the reconciliation report and prints it — no DB writes,
no embedding API calls, safe to run repeatedly. --execute performs the
real import: uploads files to Storage, extracts/chunks/embeds via the
real OpenAI API (this costs money and requires OPENAI_API_KEY), and
writes knowledge_sources/knowledge_media/knowledge_conflicts/
knowledge_benchmark_questions rows. --execute is idempotent — re-running
it against an unchanged corpus creates nothing new (each row is checked
against existing checksums/keys before any write); this script itself
does not thin-wrap that idempotency, app.knowledge.governance.importer
enforces it.

All the actual logic lives in app.knowledge.governance.importer — this
script is a thin CLI shell around it, per the module layout in
docs/phase-3/IMPLEMENTATION_PLAN.md.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Registers every table on Base.metadata (mirrors alembic/env.py's import
# list) — this script's own import chain doesn't otherwise touch
# app.users.models, so a bare create_source/get_source_by_checksum call
# fails to resolve knowledge_sources.created_by's FK target ("users") at
# query time even though the real table exists in the live database.
from app.audit.models import AuditLog  # noqa: F401
from app.config import get_settings
from app.conversations.models import Conversation, ConversationStateEvent  # noqa: F401
from app.customers.models import Customer, CustomerContact, CustomerNote, CustomerTag  # noqa: F401
from app.database import AsyncSessionLocal
from app.knowledge.embeddings import OpenAIEmbeddingProvider
from app.knowledge.governance.importer import (
    build_reconciliation_report,
    import_benchmark_questions,
    import_conflicts,
    import_sources_from_report,
    load_benchmark_question_rows,
    load_conflict_rows,
)
from app.messages.models import Message, MessageAttachment  # noqa: F401
from app.orchestration.models import OrchestrationTurn, ServiceRequest  # noqa: F401
from app.resort.models import ResortSettings  # noqa: F401
from app.users.models import User  # noqa: F401


def _print_report(report) -> None:
    print("=== Reconciliation report ===")
    for key, value in report.summary.items():
        print(f"  {key}: {value}")

    print("\n=== Unmatched register rows (need manual resolution) ===")
    if not report.unmatched_register_rows:
        print("  (none)")
    for row in report.unmatched_register_rows:
        print(f"  {row.source_id} | {row.title} | {row.file_path_or_url}")

    plans_with_warnings = [p for p in report.plans if p.warnings]
    print(f"\n=== Plans with warnings ({len(plans_with_warnings)}) ===")
    for plan in plans_with_warnings:
        print(f"  {plan.manifest_row.relative_path} | action={plan.action} | {plan.warnings}")


async def _run_dry_run(rkpr_root: Path) -> None:
    report = build_reconciliation_report(rkpr_root)
    _print_report(report)


async def _run_execute(rkpr_root: Path) -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        print("ERROR: OPENAI_API_KEY is not configured — --execute requires real embeddings.", file=sys.stderr)
        sys.exit(1)

    report = build_reconciliation_report(rkpr_root)
    _print_report(report)

    embedding_provider = OpenAIEmbeddingProvider()

    async with AsyncSessionLocal() as db:
        outcomes = await import_sources_from_report(
            db, report=report, rkpr_root=rkpr_root, actor_user_id=None, embedding_provider=embedding_provider
        )
        print(f"\n=== Source import outcomes ({len(outcomes)}) ===")
        for outcome in outcomes:
            print(f"  {outcome.relative_path} | {outcome.result} | {outcome.detail}")

        conflict_rows = load_conflict_rows(rkpr_root)
        conflict_outcomes = await import_conflicts(db, conflict_rows=conflict_rows, actor_user_id=None)
        print(f"\n=== Conflict import outcomes ({len(conflict_outcomes)}) ===")
        for outcome in conflict_outcomes:
            print(f"  {outcome.relative_path} | {outcome.result}")

        question_rows = load_benchmark_question_rows(rkpr_root)
        question_outcomes = await import_benchmark_questions(db, question_rows=question_rows, actor_user_id=None)
        print(f"\n=== Benchmark question import outcomes ({len(question_outcomes)}) ===")
        print(f"  created={sum(1 for o in question_outcomes if o.result == 'created')}")
        print(f"  skipped_unchanged={sum(1 for o in question_outcomes if o.result == 'skipped_unchanged')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the RKPR knowledge corpus")
    parser.add_argument("--path", required=True, help="Path to the RKPR corpus root (e.g. ./RKPR_RAG_FINAL_DOCS)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Build and print the reconciliation report only")
    mode.add_argument("--execute", action="store_true", help="Perform the real import (writes to DB + Storage)")
    args = parser.parse_args()

    rkpr_root = Path(args.path).resolve()
    if not rkpr_root.is_dir():
        print(f"ERROR: {rkpr_root} is not a directory", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        asyncio.run(_run_dry_run(rkpr_root))
    else:
        asyncio.run(_run_execute(rkpr_root))


if __name__ == "__main__":
    main()
