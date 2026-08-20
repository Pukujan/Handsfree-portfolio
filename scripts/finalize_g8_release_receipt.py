from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

EXPECTED_GATES = (
    "g0-foundation",
    "g1-public-knowledge",
    "g2-retrieval-benchmark",
    "g3-conversation-kernel",
    "g4-hands-free-ux",
    "g5-response-cache",
    "g6-assurance",
    "g7-production",
)


def load_receipt(env_name: str) -> dict:
    value = os.environ.get(env_name)
    if not value:
        raise SystemExit(f"{env_name} is required")
    path = Path(value)
    if not path.exists():
        raise SystemExit(f"missing receipt: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_runs(token: str, repository: str, sha: str) -> list[dict]:
    query = urlencode({"head_sha": sha, "event": "pull_request", "per_page": 100})
    request = Request(
        f"https://api.github.com/repos/{repository}/actions/runs?{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "handsfree-portfolio-g8-release-qualification",
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    return list(payload.get("workflow_runs", []))


def select_gate_runs(runs: list[dict], sha: str) -> dict[str, dict]:
    selected: dict[str, dict] = {}
    for gate in EXPECTED_GATES:
        candidates = [
            run
            for run in runs
            if run.get("name") == gate
            and run.get("head_sha") == sha
            and run.get("event") == "pull_request"
        ]
        if not candidates:
            continue
        candidates.sort(
            key=lambda run: (
                int(run.get("run_number") or 0),
                int(run.get("run_attempt") or 0),
                int(run.get("id") or 0),
            )
        )
        selected[gate] = candidates[-1]
    return selected


def compact_run(run: dict | None) -> dict | None:
    if run is None:
        return None
    return {
        "runId": int(run["id"]),
        "runNumber": int(run.get("run_number") or 0),
        "runAttempt": int(run.get("run_attempt") or 1),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "url": run.get("html_url"),
    }


def write_final_receipt(
    *,
    sha: str,
    selected: dict[str, dict],
    recruiter: dict,
    simulator: dict,
    browser: dict,
    api_error: str | None = None,
) -> tuple[dict, bool]:
    inherited = {gate: compact_run(selected.get(gate)) for gate in EXPECTED_GATES}
    gates_green = all(
        selected.get(gate, {}).get("status") == "completed"
        and selected.get(gate, {}).get("conclusion") == "success"
        for gate in EXPECTED_GATES
    )
    recruiter_green = recruiter.get("status") == "PASS"
    simulator_green = simulator.get("status") == "PASS" and simulator.get("unsafe_outcomes") == 0
    browser_green = browser.get("status") == "PASS"
    equivalence_green = (
        browser.get("textHandsFreeAnswerEquivalent") is True
        and browser.get("textHandsFreeEvidenceEquivalent") is True
    )
    g6_green = selected.get("g6-assurance", {}).get("conclusion") == "success"
    g7_green = selected.get("g7-production", {}).get("conclusion") == "success"

    criteria = {
        "exactHeadG0ThroughG7Green": gates_green,
        "deterministicRecruiterJourneys": recruiter_green,
        "directProductionSurfaceNaturalness": g6_green,
        "realBrowserAccessibilityMobileFallback": browser_green,
        "textHandsFreeSemanticEvidenceEquivalence": equivalence_green,
        "securityRecoveryInheritance": g7_green,
        "syntheticWorkloadHasNoUnsafeOutcome": simulator_green,
        "unadmittedGraphVectorStyleRuntimeAbsent": g6_green and g7_green,
    }
    qualified = all(criteria.values()) and api_error is None
    decision = "RELEASE" if qualified else "REVISE"

    receipt = {
        "workflowSha": sha,
        "workflowRunId": int(os.environ.get("GITHUB_RUN_ID") or 0),
        "workflowRunAttempt": int(os.environ.get("GITHUB_RUN_ATTEMPT") or 1),
        "status": "G8_MACHINE_PASS" if qualified else "G8_MACHINE_REVISE",
        "authority": "deterministic_product_and_exact_head_gate_oracles",
        "releaseDecision": decision,
        "releaseCriteria": criteria,
        "recruiterTaskQualification": recruiter,
        "syntheticWorkload": simulator,
        "browserQualification": browser,
        "inheritedGateRuns": inherited,
        "naturalnessQualification": {
            "status": "PASS" if g6_green else "FAIL",
            "sourceGate": "g6-assurance",
            "runId": inherited["g6-assurance"]["runId"] if inherited["g6-assurance"] else None,
            "oracle": "direct_production_surface_envelope",
        },
        "securityRecoveryInheritance": {
            "status": "PASS" if g7_green else "FAIL",
            "sourceGate": "g7-production",
            "runId": inherited["g7-production"]["runId"] if inherited["g7-production"] else None,
        },
        "runtimeComplexity": {
            "graphServiceDeployed": False,
            "vectorRuntimeAdmitted": False,
            "styleGeneratorRuntimeAdmitted": False,
            "evidence": [
                "G6 exact-head assurance and rejected-complexity evidence",
                "G7 exact-head production topology and image checks",
                "G8 architecture boundary guard",
            ],
        },
        "knownLimitations": [
            "Real-browser release qualification currently covers Chromium, not a cross-browser matrix.",
            "Web Speech API capability and permission remain browser/platform dependent; complete text/static fallback is qualified.",
            "Synthetic personas are workload-only and are not treated as naturalness or preference judges.",
            "No new human preference panel is fabricated; G6 human-dialogue corpus evidence remains the naturalness reference.",
        ],
        "humanPreferenceScoresFabricated": False,
    }
    if api_error is not None:
        receipt["gateStatusApiError"] = api_error

    output = os.environ.get("G8_FINAL_RECEIPT_PATH")
    if not output:
        raise SystemExit("G8_FINAL_RECEIPT_PATH is required")
    Path(output).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return receipt, qualified


def main() -> None:
    sha = os.environ.get("EXPECTED_SHA")
    token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not sha or not token or not repository:
        raise SystemExit("EXPECTED_SHA, GITHUB_TOKEN and GITHUB_REPOSITORY are required")

    recruiter = load_receipt("G8_RECRUITER_RECEIPT_PATH")
    simulator = load_receipt("G6_SIMULATOR_RECEIPT_PATH")
    browser = load_receipt("G8_BROWSER_RECEIPT_PATH")

    wait_seconds = max(0, int(os.environ.get("G8_SIBLING_GATE_WAIT_SECONDS", "900")))
    poll_seconds = max(2, int(os.environ.get("G8_SIBLING_GATE_POLL_SECONDS", "10")))
    deadline = time.monotonic() + wait_seconds
    selected: dict[str, dict] = {}
    last_error: str | None = None

    while True:
        try:
            selected = select_gate_runs(fetch_runs(token, repository, sha), sha)
            last_error = None
            waiting = [
                gate
                for gate in EXPECTED_GATES
                if gate not in selected or selected[gate].get("status") != "completed"
            ]
            if not waiting:
                break
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            waiting = list(EXPECTED_GATES)

        if time.monotonic() >= deadline:
            write_final_receipt(
                sha=sha,
                selected=selected,
                recruiter=recruiter,
                simulator=simulator,
                browser=browser,
                api_error=last_error or f"timed out waiting for exact-head gates: {', '.join(waiting)}",
            )
            raise SystemExit("G8 finalization timed out before G0-G7 reached terminal exact-head status")

        print(f"waiting for exact-head gates: {', '.join(waiting)}", flush=True)
        time.sleep(poll_seconds)

    _, qualified = write_final_receipt(
        sha=sha,
        selected=selected,
        recruiter=recruiter,
        simulator=simulator,
        browser=browser,
    )
    if not qualified:
        raise SystemExit("G8 release decision is REVISE because one or more exact-head criteria failed")


if __name__ == "__main__":
    main()
