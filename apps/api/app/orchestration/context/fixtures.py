"""Deterministic context-assembly fixtures for tests — shaped exactly
like real app.knowledge.retrieval.service.search output (RetrievedCitation
mirrors CitationOut's fields), so context-assembler tests exercise the
real trimming/truncation logic without needing a live embedded corpus.
Covers the boundary cases the Phase 4 brief calls out explicitly: empty
retrieval, low-confidence retrieval, excessive retrieval, conflicting
sources, safety-critical retrieval.
"""

import uuid

from app.orchestration.domain import RetrievedCitation


def empty_retrieval() -> list[RetrievedCitation]:
    return []


def low_confidence_retrieval() -> list[RetrievedCitation]:
    return [
        RetrievedCitation(
            chunk_id=uuid.uuid4(),
            content="This might be loosely related to the question but isn't a strong match.",
            source_title="General FAQ",
            source_priority="low",
            authoritative=False,
            score=0.12,
        )
    ]


def excessive_retrieval(count: int = 50) -> list[RetrievedCitation]:
    return [
        RetrievedCitation(
            chunk_id=uuid.uuid4(),
            content=f"Filler resort content chunk number {i}, repeated padding text to consume token budget. " * 20,
            source_title=f"Source {i}",
            source_priority="normal",
            authoritative=False,
            score=0.5 - (i * 0.001),
        )
        for i in range(count)
    ]


def conflicting_sources() -> list[RetrievedCitation]:
    """Same topic (pool closing time), two different answers — the
    higher-priority/authoritative one must be preserved and should sort
    first; conflict RESOLUTION (which one wins) is a governance decision
    already baked into retrieval scoring, not something the context
    assembler re-litigates."""
    return [
        RetrievedCitation(
            chunk_id=uuid.uuid4(),
            content="The pool closes at 9:00 PM daily, per the official Resort Directory and Timings.",
            source_title="Resort Directory and Timings",
            source_priority="critical",
            authoritative=True,
            score=0.9,
        ),
        RetrievedCitation(
            chunk_id=uuid.uuid4(),
            content="The pool closes at 8:00 PM according to the website.",
            source_title="RKPR Resort Official Website",
            source_priority="normal",
            authoritative=False,
            score=0.6,
        ),
    ]


def safety_critical_retrieval() -> list[RetrievedCitation]:
    return [
        RetrievedCitation(
            chunk_id=uuid.uuid4(),
            content="In case of fire, use the nearest emergency exit and proceed to the assembly point.",
            source_title="Emergency and Safety Info",
            source_priority="critical",
            authoritative=True,
            score=0.95,
        )
    ]
