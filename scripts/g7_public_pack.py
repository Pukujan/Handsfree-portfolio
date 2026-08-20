from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable

from fossil_core.adapters.s3 import S3ArtifactStore
from fossil_core.domain.lifecycle import KnowledgeState

from handsfree_portfolio.adapters.fossil_pack import (
    PUBLIC_PACK_ID,
    FossilPackWorkspace,
    FossilSchemaRoot,
    ingest_supported_claim,
)

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge" / "portfolio-public"
DEFAULT_OBSERVED_AT = "2026-08-19T20:10:00Z"
STATIC_PACK_FILES = ("manifest.json", "source-policy.json", "retrieval-v1.json")


def _require_empty_directory(path: Path) -> None:
    path = Path(path)
    if path.exists() and any(path.iterdir()):
        raise ValueError(f"destination must be empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def tree_sha256(root: Path) -> str:
    root = Path(root)
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def validate_materialized_pack(pack_root: Path, schema_root: Path) -> dict[str, Any]:
    workspace = FossilPackWorkspace(Path(pack_root), FossilSchemaRoot(Path(schema_root)))
    manifest = workspace.load_manifest()
    events = sorted(
        workspace.event_store.iter_events(),
        key=lambda event: (event["recorded_at"], event["event_id"]),
    )
    state = KnowledgeState.replay(events)
    claims_document = json.loads(
        (KNOWLEDGE / "slice1-reviewed-claims.json").read_text(encoding="utf-8")
    )
    expected_claim_ids = {str(item["claimId"]) for item in claims_document["claims"]}
    if set(state.claims) != expected_claim_ids:
        raise ValueError("materialized pack reconstructed an unexpected claim set")
    if any(state.claims[claim_id] != "supported" for claim_id in expected_claim_ids):
        raise ValueError("materialized pack contains a non-supported Slice-1 claim")
    if len(events) != len(expected_claim_ids) * 2:
        raise ValueError("materialized pack must contain proposal + support event per claim")
    if any(event["pack_id"] != PUBLIC_PACK_ID for event in events):
        raise ValueError("materialized pack contains an event outside the public pack")
    return {
        "packId": manifest["pack_id"],
        "claimCount": len(expected_claim_ids),
        "eventCount": len(events),
        "treeSha256": tree_sha256(pack_root),
    }


def materialize_public_pack(
    destination: Path,
    schema_root: Path,
    *,
    observed_at: str = DEFAULT_OBSERVED_AT,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    destination = Path(destination)
    _require_empty_directory(destination)
    for filename in STATIC_PACK_FILES:
        shutil.copyfile(KNOWLEDGE / filename, destination / filename)

    claims_document = json.loads(
        (KNOWLEDGE / "slice1-reviewed-claims.json").read_text(encoding="utf-8")
    )
    workspace = FossilPackWorkspace(destination, FossilSchemaRoot(Path(schema_root)))
    receipts = [
        ingest_supported_claim(
            workspace,
            policy_path=destination / "source-policy.json",
            claim=claim,
            observed_at=observed_at,
            opener=opener,
        )
        for claim in claims_document["claims"]
    ]
    if any(
        receipt["resolved_text"] != claim["source"]["anchorText"]
        for receipt, claim in zip(receipts, claims_document["claims"], strict=True)
    ):
        raise ValueError("materialization citation did not resolve to exact reviewed source bytes")

    result = validate_materialized_pack(destination, Path(schema_root))
    result.update(
        {
            "status": "PASS",
            "observedAt": observed_at,
            "snapshotCount": len({receipt["snapshot_id"] for receipt in receipts}),
            "allCitationsResolvedExactBytes": True,
        }
    )
    return result


def create_deterministic_bundle(pack_root: Path, bundle_path: Path) -> dict[str, Any]:
    pack_root = Path(pack_root)
    bundle_path = Path(bundle_path)
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    if bundle_path.exists():
        bundle_path.unlink()

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(item for item in pack_root.rglob("*") if item.is_file()):
            relative = path.relative_to(pack_root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes())

    data = bundle_path.read_bytes()
    return {
        "packId": PUBLIC_PACK_ID,
        "treeSha256": tree_sha256(pack_root),
        "bundleSha256": hashlib.sha256(data).hexdigest(),
        "bundleBytes": len(data),
    }


def restore_deterministic_bundle(bundle_path: Path, destination: Path) -> dict[str, Any]:
    destination = Path(destination)
    _require_empty_directory(destination)
    with zipfile.ZipFile(Path(bundle_path), "r") as archive:
        for info in archive.infolist():
            relative = Path(info.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"unsafe bundle member: {info.filename}")
            if info.is_dir():
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
    return {
        "packId": PUBLIC_PACK_ID,
        "treeSha256": tree_sha256(destination),
    }


def _s3_store(args: argparse.Namespace) -> S3ArtifactStore:
    return S3ArtifactStore(
        bucket=args.bucket,
        prefix=args.prefix,
        endpoint_url=args.endpoint_url,
        region_name=args.region,
    )


def _print(value: dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize, bundle and restore the public FOSSIL pack")
    subparsers = parser.add_subparsers(dest="command", required=True)

    materialize = subparsers.add_parser("materialize")
    materialize.add_argument("--output", type=Path, required=True)
    materialize.add_argument("--schema-root", type=Path, required=True)
    materialize.add_argument("--observed-at", default=DEFAULT_OBSERVED_AT)

    bundle = subparsers.add_parser("bundle")
    bundle.add_argument("--pack-root", type=Path, required=True)
    bundle.add_argument("--output", type=Path, required=True)

    restore = subparsers.add_parser("restore")
    restore.add_argument("--bundle", type=Path, required=True)
    restore.add_argument("--output", type=Path, required=True)

    publish = subparsers.add_parser("publish-s3")
    publish.add_argument("--bundle", type=Path, required=True)
    publish.add_argument("--bucket", required=True)
    publish.add_argument("--prefix", default="handsfree-portfolio")
    publish.add_argument("--endpoint-url")
    publish.add_argument("--region")

    restore_s3 = subparsers.add_parser("restore-s3")
    restore_s3.add_argument("--artifact-id", required=True)
    restore_s3.add_argument("--output", type=Path, required=True)
    restore_s3.add_argument("--bucket", required=True)
    restore_s3.add_argument("--prefix", default="handsfree-portfolio")
    restore_s3.add_argument("--endpoint-url")
    restore_s3.add_argument("--region")

    args = parser.parse_args()
    if args.command == "materialize":
        _print(materialize_public_pack(args.output, args.schema_root, observed_at=args.observed_at))
        return
    if args.command == "bundle":
        _print(create_deterministic_bundle(args.pack_root, args.output))
        return
    if args.command == "restore":
        _print(restore_deterministic_bundle(args.bundle, args.output))
        return
    if args.command == "publish-s3":
        store = _s3_store(args)
        manifest = store.put_file(args.bundle, media_type="application/zip")
        store.verify(manifest["artifact_id"])
        _print(
            {
                "status": "PASS",
                "artifactId": manifest["artifact_id"],
                "contentHash": manifest["content_hash"],
                "byteSize": manifest["byte_size"],
            }
        )
        return
    if args.command == "restore-s3":
        store = _s3_store(args)
        if not store.verify(args.artifact_id):
            raise SystemExit("remote bundle verification failed")
        with tempfile.TemporaryDirectory(prefix="g7-s3-restore-") as directory:
            bundle_path = Path(directory) / "portfolio-public.zip"
            bundle_path.write_bytes(store.read_bytes(args.artifact_id))
            result = restore_deterministic_bundle(bundle_path, args.output)
        result["status"] = "PASS"
        result["artifactId"] = args.artifact_id
        _print(result)
        return
    raise SystemExit(f"unsupported command: {args.command}")


if __name__ == "__main__":
    main()
