from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from handsfree_portfolio.adapters.public_source import (
    SourcePolicyError,
    authorize_source,
    exact_anchor_span,
    fetch_exact_public_source,
    load_source_policy,
)

ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = ROOT / "knowledge" / "portfolio-public" / "source-policy.json"
REVISION = "b5fd57725c910b149910371964adb35d9280016e"


def test_policy_allows_only_exact_pinned_fossil_source() -> None:
    policy = load_source_policy(POLICY_PATH)
    authorize_source(policy, repository="Pukujan/fossil-core", revision=REVISION, path="ARCHITECTURE.md")

    with pytest.raises(SourcePolicyError):
        authorize_source(policy, repository="Pukujan/fossil-core", revision="main", path="ARCHITECTURE.md")
    with pytest.raises(SourcePolicyError):
        authorize_source(policy, repository="Pukujan/private-study-log", revision=REVISION, path="README.md")
    with pytest.raises(SourcePolicyError):
        authorize_source(policy, repository="Pukujan/fossil-core", revision=REVISION, path="../secret")


def test_fetch_uses_exact_allowlisted_raw_url() -> None:
    policy = load_source_policy(POLICY_PATH)
    seen: list[str] = []

    def opener(url: str) -> bytes:
        seen.append(url)
        return b"FOSSIL exact fixture bytes"

    source = fetch_exact_public_source(
        policy,
        repository="Pukujan/fossil-core",
        revision=REVISION,
        path="ARCHITECTURE.md",
        opener=opener,
    )

    assert seen == [f"https://raw.githubusercontent.com/Pukujan/fossil-core/{REVISION}/ARCHITECTURE.md"]
    assert source.repository_ref == f"Pukujan/fossil-core@{REVISION}:ARCHITECTURE.md"


@given(prefix=st.binary(max_size=30), suffix=st.binary(max_size=30))
def test_exact_anchor_span_round_trips_bytes(prefix: bytes, suffix: bytes) -> None:
    anchor = "unique portfolio anchor"
    data = prefix + anchor.encode() + suffix
    start, end = exact_anchor_span(data, anchor)
    assert data[start:end] == anchor.encode()


def test_exact_anchor_span_rejects_missing_or_ambiguous_anchor() -> None:
    with pytest.raises(SourcePolicyError):
        exact_anchor_span(b"abc", "missing")
    with pytest.raises(SourcePolicyError):
        exact_anchor_span(b"same same", "same")
