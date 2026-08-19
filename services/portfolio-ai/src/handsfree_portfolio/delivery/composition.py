from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from handsfree_portfolio.adapters.clock import SystemClock
from handsfree_portfolio.adapters.fossil_claim_catalog import FossilClaimCatalog
from handsfree_portfolio.adapters.fossil_pack import FossilPackWorkspace, FossilSchemaRoot, public_runtime_access
from handsfree_portfolio.adapters.retrieval_policy import load_retrieval_policy
from handsfree_portfolio.adapters.session_memory import InMemoryConversationSessions
from handsfree_portfolio.application.conversation_kernel import ConversationKernel
from handsfree_portfolio.application.grounded_rendering import ClaimBoundTemplateRenderer, DeterministicGroundingVerifier
from handsfree_portfolio.application.retrieval import PublicClaimRetriever


class RuntimeConfigurationError(RuntimeError):
    pass


def _required_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        raise RuntimeConfigurationError(f"{name} is required for the grounded conversation runtime")
    path = Path(value)
    if not path.exists():
        raise RuntimeConfigurationError(f"{name} does not exist: {path}")
    return path


@lru_cache(maxsize=1)
def runtime_kernel() -> ConversationKernel:
    pack_root = _required_path("PORTFOLIO_PACK_ROOT")
    schema_root = _required_path("FOSSIL_SCHEMA_ROOT")
    policy_path = Path(os.environ.get("PORTFOLIO_RETRIEVAL_POLICY", str(pack_root / "retrieval-v1.json")))
    if not policy_path.exists():
        raise RuntimeConfigurationError(f"retrieval policy does not exist: {policy_path}")

    workspace = FossilPackWorkspace(pack_root, FossilSchemaRoot(schema_root))
    workspace.load_manifest()
    catalog = FossilClaimCatalog(
        event_store=workspace.event_store,
        source_store=workspace.source_store,
        access=public_runtime_access(),
    )
    retriever = PublicClaimRetriever(catalog, load_retrieval_policy(policy_path))
    return ConversationKernel(
        catalog=catalog,
        retriever=retriever,
        sessions=InMemoryConversationSessions(),
        renderer=ClaimBoundTemplateRenderer(),
        verifier=DeterministicGroundingVerifier(),
        clock=SystemClock(),
    )
