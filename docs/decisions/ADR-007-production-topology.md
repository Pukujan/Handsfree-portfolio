# ADR-007 — Minimal production topology and durable recovery

Status: Accepted for G7 candidate implementation

## Context

G0–G6 qualified a Slice-1 runtime whose factual authority is the FOSSIL public pack. Exact/sparse retrieval is the default factual path, cache is derived-only, and Neo4j/Graphiti are rebuildable projections rather than authority.

G7 must productionize that qualified behavior without turning optional infrastructure into a new correctness dependency.

## Decision

The default production topology is:

```text
Internet
  -> Caddy :80/:443
       -> static Vite/React build
       -> /health and /v1/* -> FastAPI api:8000 on an internal Docker network

FastAPI
  -> read-only materialized FOSSIL public pack
  -> in-memory conversation sessions
  -> in-memory derived answer cache
```

No Neo4j/Graphiti service is deployed by default. The `neo4j` Python dependency is removed from the default API dependency set and retained only in the explicit `projection`/development extras for historical projection tests and optional experiments.

The public API container receives no S3/R2/AWS credentials. Durable object-store operations are an operator/recovery-plane concern, not a public request-path concern.

## Durable pack lifecycle

`scripts/g7_public_pack.py` is the executable pack lifecycle:

1. `materialize` reconstructs the FOSSIL filesystem pack from reviewed, versioned Slice-1 inputs and pinned public source revisions.
2. `bundle` writes a deterministic ZIP_STORED bundle with fixed member metadata.
3. `restore` recreates the filesystem pack from the bundle while rejecting unsafe paths.
4. `publish-s3` stores the bundle through the pinned `fossil_core.adapters.s3.S3ArtifactStore` content-addressed immutable object contract.
5. `restore-s3` verifies the remote artifact before restoring it locally.

Cloudflare R2 is compatible through its S3 endpoint. Provider credentials are supplied by the standard boto3 credential chain to the operator process only; credentials are not CLI arguments, committed configuration, frontend variables, or API container environment.

## Recovery invariant

The G7 recovery oracle requires all of the following:

- two independent materializations from the same reviewed inputs and pinned source bytes produce the same canonical pack tree SHA-256;
- the materialized pack produces a grounded completed answer through the real runtime composition;
- the pack is bundled and published through FOSSIL's S3-compatible artifact adapter;
- local materialized state and the local bundle are destroyed;
- the bundle is restored from the remote-object interface;
- restored tree SHA-256 equals the independently materialized reference;
- the grounded answer text, claim IDs and evidence IDs are unchanged after restore;
- remote object-store read/write outages fail closed;
- an already-restored local public pack continues serving public reads during a remote object-store outage.

The object-store outage behavior is intentionally asymmetric: the public read path does not need remote credentials or live remote availability, while authority-changing/recovery operations require the durable store and fail closed when it is unavailable.

## Security boundary

The production compose contract requires:

- only Caddy publishes host ports, exactly 80 and 443;
- API port 8000 is internal-only;
- the backend Docker network is `internal: true`;
- the API root filesystem is read-only;
- all Linux capabilities are dropped and `no-new-privileges` is enabled;
- the FOSSIL pack bind mount is read-only;
- frontend build/runtime variables are limited to the public API base URL;
- no Neo4j/Graphiti/database port is present in the public edge configuration;
- no object-store credential/config names are present in the public API environment.

## Rejected alternatives

### Neo4j/Graphiti in the default production stack
Rejected. G2 and G6 did not establish a factual hot-path or conversational benefit that earns this operational dependency. Destructive graph recovery is therefore satisfied more strongly by not requiring the graph at all.

### Public API reads directly from R2/S3
Rejected for Slice 1. It would increase latency, credential exposure, and outage coupling without a measured need. The runtime consumes a read-only restored pack instead.

### A new portfolio-specific object-store adapter
Rejected. The pinned FOSSIL dependency already provides immutable S3-compatible artifact/event adapters with explicit remote-unavailable semantics.

## Consequences

The deployed system is smaller than the originally sketched VPS + graph topology. Graph infrastructure can only be added later if a named G7/G8 requirement demonstrates a benefit that outweighs its attack surface and recovery cost.
