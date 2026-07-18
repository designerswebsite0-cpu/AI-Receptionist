"""CLI entrypoint for the retrieval benchmark:

    python -m app.scripts.run_benchmark

Requires OPENAI_API_KEY (real embeddings) and a database already
populated by app.scripts.import_rkpr_knowledge --execute, since it scores
retrieval against knowledge_benchmark_questions imported from
Common_Guest_Questions_Dataset.xlsx.
"""

import asyncio
import sys

# Registers every table on Base.metadata (mirrors alembic/env.py's import
# list) — this script's own import chain doesn't otherwise touch models
# like app.users.models, which breaks FK resolution for queries that join
# through knowledge_sources.created_by/approved_by even though the real
# users table exists in the live database.
from app.audit.models import AuditLog  # noqa: F401
from app.config import get_settings
from app.conversations.models import Conversation, ConversationStateEvent  # noqa: F401
from app.customers.models import Customer, CustomerContact, CustomerNote, CustomerTag  # noqa: F401
from app.database import AsyncSessionLocal
from app.knowledge.benchmark import run_benchmark
from app.knowledge.embeddings import OpenAIEmbeddingProvider
from app.knowledge.retrieval.reranker import HeuristicReranker
from app.messages.models import Message, MessageAttachment  # noqa: F401
from app.orchestration.models import OrchestrationTurn, ServiceRequest  # noqa: F401
from app.resort.models import ResortSettings  # noqa: F401
from app.users.models import User  # noqa: F401


async def _main() -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        print("ERROR: OPENAI_API_KEY is not configured — the benchmark needs real embeddings.", file=sys.stderr)
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        summary = await run_benchmark(
            db, embedding_provider=OpenAIEmbeddingProvider(), reranker=HeuristicReranker()
        )

    print(f"Total: {summary.total}  Passed: {summary.passed}  Failed: {summary.failed}")
    print(f"Pass rate: {summary.pass_rate:.1%}")
    print(f"Average latency: {summary.average_latency_ms:.0f}ms")
    print("\nBy category:")
    for category, counts in summary.by_category.items():
        print(f"  {category}: {counts['passed']} passed / {counts['failed']} failed")

    failed = [r for r in summary.results if not r.passed]
    if failed:
        print(f"\nFailed questions ({len(failed)}):")
        for result in failed:
            print(f"  [{result.category}] {result.question}")


if __name__ == "__main__":
    asyncio.run(_main())
