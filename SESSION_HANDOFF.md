# Session handoff — G8 terminal qualification

Updated: 2026-08-20

## Start here

Repository: `Pukujan/Handsfree-portfolio`

Active branch: `g8-release-qualification`

Active PR: **#23 — G8 qualification — recruiter tasks, browser accessibility, explicit release decision**

Active gate issue: **#10 — G8 Qualification**

Control ledger: **#1**

Before doing any write, fetch the live PR head. This handoff was written on top of pre-handoff working head:

`7c038b7f0bf1b6c75b2f9ab6ecafed46c6317279`

The handoff commit itself advances the branch, so the live branch head after this file is created is authoritative.

## Engineering rule

> **Complexity must earn admission through measured failure, security requirement, or correctness property.**

Do not reopen G0–G7 architecture unless a current test exposes a real defect. Do not add graph/vector/style/model complexity merely to make G8 look sophisticated.

The user wants the work continued autonomously. Prefer execution over clarification when the repository state can answer the question.

---

## Gate state

### G0–G6

Complete and previously merged. Do not reopen.

### G7

**PASS, merged, closed.**

PR #22 was squash-merged to `main` as:

`8d51498f5d67842bc0cc56204307bfccf7058496`

Its exact qualified head was:

`50eea7f7cd4176c835dd70ade62f0a43f982927a`

G7 exact-head runs all passed:

- G0 `32329746410`
- G1 `32329746444`
- G2 `32329746425`
- G3 `32329746439`
- G4 `32329746412`
- G5 `32329746436`
- G6 `32329746395`
- G7 `32329746405`

G7 artifact:

- artifact ID `9392637962`
- ZIP SHA-256 `445d8198be26019dfd9986cfe862466eb89fb3a3ead13233515c26243979fff2`

Important G7 production decisions:

- Caddy is the only public service; only 80/443 published.
- FastAPI is internal-only.
- FOSSIL public pack is mounted read-only.
- Production API image contains no Neo4j client.
- No Neo4j/Graphiti service is deployed.
- S3/R2 credentials stay in the operator/recovery plane, not the public API process.
- Deterministic destructive FOSSIL recovery passed.
- Active-turn process restart passed: killed generation cannot publish stale answer output.
- CI/build inputs are frozen: committed pnpm lock, pnpm `10.15.1`, digest-pinned production bases.

Issue #9 is closed.

### G8

**ACTIVE. Not qualified. Do not merge PR #23 yet.**

PR #23 is currently draft and mergeable.

Pre-handoff branch head:

`7c038b7f0bf1b6c75b2f9ab6ecafed46c6317279`

PR base is G7 merge commit:

`8d51498f5d67842bc0cc56204307bfccf7058496`

---

## G8 evaluation policy

The stale “recruit real human testers” assumption was explicitly removed from Issue #10.

G8 release authority is:

1. deterministic recruiter/hiring-manager task journeys;
2. inherited G6 direct production-surface naturalness qualification;
3. real-browser accessibility/mobile/static-fallback checks;
4. text-vs-hands-free semantic/evidence equivalence;
5. exact-head preservation of G0–G7;
6. explicit terminal decision: `RELEASE`, `REVISE`, or `KILL_COMPLEXITY`.

Human dialogue corpora/research remain naturalness reference evidence only. Synthetic personas are workload-only. LLM judges are auxiliary-only. Do not fabricate human preference scores.

---

## What is already on the G8 branch

The first G8 implementation commit was:

`1858096af93ae82f94d0e0e06a74bc66e0b08645`

It added:

- Playwright Chromium release qualification;
- `@axe-core/playwright` accessibility checks;
- keyboard traversal and visible-focus checks;
- 360px mobile overflow/touch-target checks;
- reduced-motion checks;
- microphone-denial → text/static fallback proof;
- browser-level text-vs-hands-free answer/evidence equivalence;
- deterministic recruiter-task receipt using the real conversation kernel;
- corrected recruiter scenario wording to match the already-qualified one-spoken-claim behavior.

One real product defect was found and fixed:

- composer input had `outline:none` with no replacement focus indicator;
- G8 adds a shared high-contrast `:focus-visible` treatment.

No retrieval, grounding, answer semantics, cache, speech authority, or factual behavior was intentionally changed.

A one-time GitHub Actions bootstrap then committed the updated browser-test lockfile as:

`7c038b7f0bf1b6c75b2f9ab6ecafed46c6317279`

That lockfile commit is already durable. **Do not run another lockfile self-push bootstrap.**

---

## Evidence already obtained from the first G8 run

Initial G8 workflow run on head `1858096...`:

`32330628350`

The following passed before the browser test plumbing failure:

- exact candidate checkout;
- architecture boundary guard;
- contract validation;
- deterministic recruiter task qualification;
- selected backend property/adversarial/API suite: **18 passed**;
- synthetic workload simulator: **9 personas / 59 turns / 13 abstentions / 0 unsafe outcomes**.

The recruiter receipt reported:

- `status=PASS`
- `authority=deterministic_product_oracles`
- 6 named recruiter scenarios
- supported first contact PASS
- follow-up referent carry PASS
- follow-up evidence/grounding correspondence PASS
- unsupported abstention PASS
- private request remains public-only PASS
- retrieved instruction-like text remains inert PASS
- no fabricated human preference score

This is useful evidence, but it is **not final exact-head G8 qualification** because the branch moved afterward and the browser suite did not run.

---

## Current blocker: test-runner namespace collision

The first G8 run failed at **Web unit tests and production build** before Chromium installation.

Cause:

`vitest run` auto-discovered:

`apps/web/e2e/release-qualification.spec.ts`

and attempted to execute Playwright's `test()` API inside Vitest.

Observed failure:

> `Playwright Test did not expect test() to be called here.`

The failure is test-runner plumbing, not a product failure.

### Recommended minimal fix

Keep unit and E2E namespaces separate.

Prefer the smallest explicit change, for example:

- change the web unit-test command to run only `src`, e.g. `vitest run src`; **or**
- add a dedicated Vitest config that includes only `src/**/*.test.{ts,tsx}` and excludes `e2e/**`.

Do not weaken or remove the Playwright browser assertions.

After this fix, run Chromium and let actual browser failures drive product changes.

---

## Current blocker: temporary G8 workflow write permission must be removed

Current branch file:

`.github/workflows/g8-qualification.yml`

still contains the one-time bootstrap state:

```yaml
permissions:
  contents: write
```

and still contains the step that can commit/push `pnpm-lock.yaml` from CI.

The lockfile was already committed successfully. Before treating any head as a G8 qualification candidate:

1. change G8 workflow permissions back to:

```yaml
permissions:
  contents: read
```

2. remove the `Bootstrap exact G8 lockfile` mutation behavior if it can modify the lock;
3. remove the `Persist G8 test-tool lockfile on PR branch` commit/push step;
4. use only `pnpm install --frozen-lockfile` / lock verification on qualification heads.

Do not leave a self-mutating qualification workflow in the final release gate.

---

## `action_required` runs on the bot lockfile head

After GitHub Actions committed the lockfile as `7c038b7...`, the PR-triggered workflows associated with that exact bot-authored head are recorded as `action_required`, including G8 run:

`32330658983`

Treat this as **no valid exact-head qualification evidence**.

Do not try to interpret those entries as PASS.

A normal follow-up repository commit that fixes runner separation and returns G8 CI to read-only should produce the next candidate head. Evaluate that head from scratch across G0–G8.

---

## Immediate next actions

Execute in this order:

1. Fetch PR #23 live head and confirm no unexpected branch movement.
2. Inspect the current branch versions of:
   - `apps/web/package.json`
   - `apps/web/vite.config.ts`
   - `apps/web/e2e/release-qualification.spec.ts`
   - `.github/workflows/g8-qualification.yml`
3. Fix Vitest/Playwright discovery separation only.
4. Return G8 workflow to `contents: read` and delete the lockfile self-push/bootstrap write step.
5. Commit those changes as a normal branch commit.
6. Run/observe exact-head G0–G8.
7. If Playwright now reaches Chromium, inspect every failing assertion individually.
8. Fix only measured browser/product defects; do not loosen thresholds to obtain green.
9. Once browser qualification is green, produce a final G8 machine receipt bound to exact `workflowSha` and explicit decision.
10. Require exact-head G0–G8 all green before PR promotion/merge.

---

## Browser qualification expectations

Current Playwright suite is intended to prove:

- no serious/critical axe violations on primary shipped states;
- keyboard can reach primary controls;
- focus indicator is visibly rendered;
- 360px viewport has no horizontal overflow;
- primary touch targets meet the intended 44px floor;
- reduced-motion preference disables nonessential animation;
- microphone denial leaves text/static portfolio fully usable;
- text mode and hands-free mode preserve the same grounded answer text;
- text mode and hands-free mode preserve the same evidence set.

If these fail because the product is defective, make the smallest product fix that satisfies the named property.

If the test itself is wrong, repair the oracle without weakening the underlying property.

---

## Naturalness must not be reopened

G6 already qualified the direct production surface after the minimal renderer fix.

Final G6 surface evidence:

- 46 supported responses
- median/p90/p95 response length: **11 / 11 / 11 words**
- production normalized p90 response/question ratio: **2.2**
- human-derived max: **2.5454545454545454**
- assistantese prefix rate: **0**
- unsolicited closing rate: **0**
- heading/list rate: **0**
- misapplied correction rate: **0**

Admitted realization remains extractive and deterministic:

- first-contact spoken plan realizes only the highest-ranked supported claim;
- neutral `Why not...?` uses explanatory framing;
- explicit false-premise challenges may use `Not quite.`;
- long reviewed propositions may shorten only to a grammatical contiguous reviewed-claim prefix at a known clause boundary, <=12 words;
- no free paraphrase/style generator.

Rejected G6 complexity remains rejected unless a new measured failure earns reconsideration:

- MiniLM semantic bridge;
- vector runtime;
- shared dialogue ontology classifier;
- runtime discourse graph;
- Neo4j/style KG.

---

## Final G8 receipt / release decision

The current G8 workflow emits only a **diagnostic** browser receipt with:

`releaseDecision=NOT_YET_FINAL`

Do not call G8 complete with that receipt.

For terminal qualification, create/finalize a machine-readable G8 receipt that includes at least:

- exact `workflowSha`;
- recruiter-task receipt status;
- browser/accessibility/mobile/fallback status;
- text-vs-hands-free semantic/evidence equivalence status;
- inherited naturalness status/reference to G6 direct production-surface oracle;
- confirmation that graph/vector/style runtime complexity remains absent;
- known limitations;
- one explicit decision: `RELEASE`, `REVISE`, or `KILL_COMPLEXITY`.

Only emit `RELEASE` when the same exact PR head has G0–G8 green and no unresolved critical qualification defect.

---

## Merge/closure discipline

When G8 qualifies:

1. verify PR #23 live head still equals the exact qualified SHA;
2. verify G0–G8 workflow runs for that SHA are all successful;
3. verify final G8 artifact/receipt digest;
4. check submitted reviews and inline review threads;
5. update PR #23 description with exact run IDs, artifact ID/digest, final receipt and decision;
6. update Issue #10 with exact evidence and explicit decision;
7. update control Issue #1 from `G8 QUALIFICATION ACTIVE` to final release state;
8. mark PR #23 ready only after qualification;
9. merge with an expected-head SHA guard;
10. close Issue #10 only after the qualified PR merges;
11. inspect Issue #12 (Slice 1 end-to-end target) and close it only if its own acceptance criteria are actually satisfied.

Do not merge a draft or a moved head simply because an older candidate was green.

---

## Files most relevant to the next session

- `SESSION_HANDOFF.md` — this file
- `.github/workflows/g8-qualification.yml`
- `apps/web/package.json`
- `apps/web/vite.config.ts`
- `apps/web/e2e/release-qualification.spec.ts`
- `apps/web/src/styles.css`
- `apps/web/src/ui/App.tsx`
- `apps/web/src/application/HandsFreeController.ts`
- `scripts/verify_g8_recruiter_tasks.py`
- `assurance/scenarios/recruiter-journeys-v1.json`
- `pnpm-lock.yaml`

## Final instruction to the next session

Do not redesign the system. Finish the terminal evidence chain.

The shortest valid path is:

**separate Vitest/Playwright → return CI to read-only → run real Chromium → repair measured defects only → exact-head G0–G8 → explicit release receipt → guarded merge.**
