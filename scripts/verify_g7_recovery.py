from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fossil_core.adapters.s3 import RemoteStoreUnavailable, S3ArtifactStore

from g7_public_pack import (
    create_deterministic_bundle,
    materialize_public_pack,
    restore_deterministic_bundle,
    tree_sha256,
    validate_materialized_pack,
)
from handsfree_portfolio.delivery.composition import runtime_kernel


class FakeS3Error(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class MemoryS3Client:
    """Small S3-compatible fixture used only to prove this repository's FOSSIL boundary."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.fail_reads = False
        self.fail_writes = False

    def _read_guard(self) -> None:
        if self.fail_reads:
            raise FakeS3Error("ServiceUnavailable")

    def _write_guard(self) -> None:
        if self.fail_writes:
            raise FakeS3Error("ServiceUnavailable")

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        self._read_guard()
        key = (Bucket, Key)
        if key not in self.objects:
            raise FakeS3Error("404")
        return {"ContentLength": len(self.objects[key])}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        self._read_guard()
        key = (Bucket, Key)
        if key not in self.objects:
            raise FakeS3Error("NoSuchKey")
        return {"Body": io.BytesIO(self.objects[key])}

    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        IfNoneMatch: str | None = None,
    ) -> dict[str, Any]:
        self._write_guard()
        key = (Bucket, Key)
        if IfNoneMatch == "*" and key in self.objects:
            raise FakeS3Error("PreconditionFailed")
        self.objects[key] = bytes(Body)
        return {}

    def delete_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        self._write_guard()
        self.objects.pop((Bucket, Key), None)
        return {}

    def list_objects_v2(self, *, Bucket: str, Prefix: str, ContinuationToken: str | None = None) -> dict[str, Any]:
        self._read_guard()
        if ContinuationToken is not None:
            raise AssertionError("fixture never paginates")
        keys = sorted(key for bucket, key in self.objects if bucket == Bucket and key.startswith(Prefix))
        return {
            "Contents": [{"Key": key} for key in keys],
            "IsTruncated": False,
        }


def runtime_answer_signature(pack_root: Path, schema_root: Path, conversation_id: str) -> dict[str, Any]:
    previous = {
        "PORTFOLIO_PACK_ROOT": os.environ.get("PORTFOLIO_PACK_ROOT"),
        "FOSSIL_SCHEMA_ROOT": os.environ.get("FOSSIL_SCHEMA_ROOT"),
        "PORTFOLIO_RETRIEVAL_POLICY": os.environ.get("PORTFOLIO_RETRIEVAL_POLICY"),
    }
    os.environ["PORTFOLIO_PACK_ROOT"] = str(pack_root)
    os.environ["FOSSIL_SCHEMA_ROOT"] = str(schema_root)
    os.environ.pop("PORTFOLIO_RETRIEVAL_POLICY", None)
    runtime_kernel.cache_clear()
    try:
        events = list(
            runtime_kernel().stream_turn(
                conversation_id=conversation_id,
                question="What is FOSSIL?",
            )
        )
    finally:
        runtime_kernel.cache_clear()
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    event_types = [event.type for event in events]
    if "answer.grounded" not in event_types or "turn.complete" not in event_types:
        raise ValueError(f"restored runtime did not publish a grounded complete answer: {event_types}")
    delta = next(event for event in events if event.type == "answer.delta")
    grounded = next(event for event in events if event.type == "answer.grounded")
    return {
        "text": delta.payload["text"],
        "claimIds": list(grounded.payload["claimIds"]),
        "evidenceIds": list(grounded.payload["evidenceIds"]),
    }


def verify(schema_root: Path) -> dict[str, Any]:
    schema_root = Path(schema_root)
    with tempfile.TemporaryDirectory(prefix="handsfree-g7-recovery-") as directory:
        root = Path(directory)
        first = root / "materialized-a"
        second = root / "materialized-b"
        restored = root / "restored"
        bundle = root / "portfolio-public.zip"
        remote_bundle = root / "portfolio-public-from-store.zip"

        first_receipt = materialize_public_pack(first, schema_root)
        second_receipt = materialize_public_pack(second, schema_root)
        first_digest = tree_sha256(first)
        second_digest = tree_sha256(second)
        if first_digest != second_digest:
            raise ValueError("same reviewed inputs did not materialize an identical canonical pack tree")

        before_signature = runtime_answer_signature(first, schema_root, "g7-before-loss")
        bundle_receipt = create_deterministic_bundle(first, bundle)
        if bundle_receipt["treeSha256"] != first_digest:
            raise ValueError("bundle receipt does not bind the materialized pack tree")

        client = MemoryS3Client()
        store = S3ArtifactStore(bucket="g7-recovery", prefix="handsfree-portfolio", client=client)
        remote_manifest = store.put_file(bundle, media_type="application/zip")
        artifact_id = remote_manifest["artifact_id"]
        if not store.verify(artifact_id):
            raise ValueError("FOSSIL S3 artifact verification failed")

        shutil.rmtree(first)
        bundle.unlink()
        if first.exists() or bundle.exists():
            raise ValueError("destructive local loss fixture did not remove materialized state")

        remote_bundle.write_bytes(store.read_bytes(artifact_id))
        restore_receipt = restore_deterministic_bundle(remote_bundle, restored)
        restored_validation = validate_materialized_pack(restored, schema_root)
        if restore_receipt["treeSha256"] != second_digest:
            raise ValueError("restored pack digest differs from independently materialized durable state")
        if restored_validation["treeSha256"] != second_digest:
            raise ValueError("restored FOSSIL validation digest differs from expected durable state")

        after_signature = runtime_answer_signature(restored, schema_root, "g7-after-loss")
        if after_signature != before_signature:
            raise ValueError("grounded runtime answer changed after destructive restore")

        client.fail_reads = True
        try:
            store.read_bytes(artifact_id)
        except RemoteStoreUnavailable:
            remote_read_failed_closed = True
        else:
            raise ValueError("object-store read outage did not fail closed")

        local_answer_during_remote_outage = runtime_answer_signature(
            restored,
            schema_root,
            "g7-object-store-outage",
        )
        if local_answer_during_remote_outage != before_signature:
            raise ValueError("public read path changed while remote object store was unavailable")

        client.fail_reads = False
        client.fail_writes = True
        try:
            store.put_bytes(b"authority-changing-write-must-fail")
        except RemoteStoreUnavailable:
            remote_write_failed_closed = True
        else:
            raise ValueError("object-store write outage did not fail closed")

        return {
            "status": "PASS",
            "packId": first_receipt["packId"],
            "claimCount": first_receipt["claimCount"],
            "eventCount": first_receipt["eventCount"],
            "independentMaterializationTreeSha256": second_digest,
            "deterministicMaterialization": True,
            "bundleSha256": bundle_receipt["bundleSha256"],
            "remoteBundleArtifactId": artifact_id,
            "destructiveLocalLoss": True,
            "restoredTreeSha256": restore_receipt["treeSha256"],
            "groundedAnswerStableAfterRestore": True,
            "remoteReadOutageFailedClosed": remote_read_failed_closed,
            "localPublicReadWorksDuringRemoteOutage": True,
            "remoteWriteOutageFailedClosed": remote_write_failed_closed,
            "objectStoreAdapter": "fossil_core.adapters.s3.S3ArtifactStore",
            "objectStoreCredentialsInPublicRuntime": False,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    result = verify(args.schema_root)
    encoded = json.dumps(result, sort_keys=True)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
