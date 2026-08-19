from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_HEX40 = re.compile(r"^[0-9a-f]{40}$")


class SourcePolicyError(ValueError):
    pass


@dataclass(frozen=True)
class ExactPublicSource:
    repository: str
    revision: str
    path: str
    data: bytes

    @property
    def repository_ref(self) -> str:
        return f"{self.repository}@{self.revision}:{self.path}"


def load_source_policy(path: Path) -> dict:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("publicOnly") is not True or policy.get("allowUnpinnedRevision") is not False:
        raise SourcePolicyError("public source policy must require public, pinned revisions")
    return policy


def authorize_source(policy: dict, *, repository: str, revision: str, path: str) -> None:
    if not _HEX40.fullmatch(revision):
        raise SourcePolicyError("source revision must be an exact lowercase 40-character commit SHA")
    if path.startswith("/") or ".." in Path(path).parts:
        raise SourcePolicyError("source path must be a repository-relative safe path")
    for entry in policy.get("repositories", []):
        if entry.get("repository") != repository:
            continue
        if entry.get("revision") != revision:
            raise SourcePolicyError("source revision is not authorized by policy")
        if path not in entry.get("paths", []):
            raise SourcePolicyError("source path is not authorized by policy")
        return
    raise SourcePolicyError("source repository is not authorized by policy")


def fetch_exact_public_source(
    policy: dict,
    *,
    repository: str,
    revision: str,
    path: str,
    opener: Callable[[str], bytes] | None = None,
) -> ExactPublicSource:
    authorize_source(policy, repository=repository, revision=revision, path=path)
    url = f"https://raw.githubusercontent.com/{repository}/{revision}/{path}"
    if opener is None:
        with urllib.request.urlopen(url, timeout=20) as response:  # noqa: S310 - exact allowlisted GitHub URL
            data = response.read()
    else:
        data = opener(url)
    if not data:
        raise SourcePolicyError("authorized public source returned empty bytes")
    return ExactPublicSource(repository=repository, revision=revision, path=path, data=data)


def exact_anchor_span(data: bytes, anchor_text: str) -> tuple[int, int]:
    anchor = anchor_text.encode("utf-8")
    if not anchor:
        raise SourcePolicyError("citation anchor must not be empty")
    first = data.find(anchor)
    if first < 0:
        raise SourcePolicyError("citation anchor does not occur in exact source bytes")
    if data.find(anchor, first + 1) >= 0:
        raise SourcePolicyError("citation anchor is ambiguous in exact source bytes")
    return first, first + len(anchor)
