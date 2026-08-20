from __future__ import annotations
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Iterable
ROOT = Path(__file__).resolve().parents[1]
BRIDGE_SCRIPT = ROOT / 'scripts' / 'verify_g6_multiwoz_utterance_bridge.py'
SPEC = importlib.util.spec_from_file_location('g6_multiwoz_bridge_for_model', BRIDGE_SCRIPT)
assert SPEC and SPEC.loader
BRIDGE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BRIDGE
SPEC.loader.exec_module(BRIDGE)
TRANSITIONS = BRIDGE.TRANSITIONS
EXPECTED_SOURCE_SHA = BRIDGE.EXPECTED_SOURCE_SHA
UserTurnExample = BRIDGE.UserTurnExample
CANDIDATE_MIN_TOKEN_COUNTS = (50, 25, 10, 5, 2, 1)
MIN_GAIN_RETENTION = 0.9
MAX_USER_ACT_ACCURACY_DROP = 0.05
MIN_GRAPH_COVERAGE = 0.9

def _canonical_bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')

def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def _fit_with_min_token_count(examples: Iterable[UserTurnExample], *, min_token_count: int) -> BRIDGE.MultinomialLexicalActClassifier:
    examples = tuple(examples)
    global_counts: Counter[str] = Counter()
    for example in examples:
        global_counts.update(BRIDGE.tokenize(example.text))
    allowed = {token for token, count in global_counts.items() if count >= min_token_count}
    classifier = BRIDGE.MultinomialLexicalActClassifier()
    for example in examples:
        tokens = tuple((token for token in BRIDGE.tokenize(example.text) if token in allowed))
        classifier.vocabulary.update(tokens)
        for label in example.user_acts:
            classifier.class_docs[label] += 1
            classifier.class_tokens[label].update(tokens)
            classifier.class_token_totals[label] += len(tokens)
    if not classifier.class_docs:
        raise ValueError('compact lexical classifier received no labelled examples')
    classifier._trained = True
    return classifier

def _classifier_payload(classifier: BRIDGE.MultinomialLexicalActClassifier, *, min_token_count: int) -> dict:
    token_counts: dict[str, dict[str, int]] = {}
    for label in classifier.classes:
        for token, count in classifier.class_tokens[label].items():
            token_counts.setdefault(token, {})[label] = count
    return {'kind': 'multinomial_bag_of_words_naive_bayes', 'alpha': classifier.alpha, 'minimumCorpusTokenCount': min_token_count, 'classes': list(classifier.classes), 'classDocumentCounts': dict(sorted(classifier.class_docs.items())), 'classTokenTotals': dict(sorted(classifier.class_token_totals.items())), 'vocabularySize': len(classifier.vocabulary), 'tokenClassCounts': {token: dict(sorted(counts.items())) for token, counts in sorted(token_counts.items())}}

def _transition_payload(global_system: Counter[str], edges: dict[str, Counter[str]]) -> dict:
    return {'globalSystemActCounts': dict(sorted(global_system.items())), 'userActToSystemActCounts': {user_act: dict(sorted(counts.items())) for user_act, counts in sorted(edges.items())}}

def classifier_from_payload(payload: dict) -> BRIDGE.MultinomialLexicalActClassifier:
    classifier = BRIDGE.MultinomialLexicalActClassifier(alpha=float(payload['alpha']))
    classifier.class_docs.update({str(k): int(v) for k, v in payload['classDocumentCounts'].items()})
    classifier.class_token_totals.update({str(k): int(v) for k, v in payload['classTokenTotals'].items()})
    for token, counts in payload['tokenClassCounts'].items():
        classifier.vocabulary.add(str(token))
        for label, count in counts.items():
            classifier.class_tokens[str(label)][str(token)] = int(count)
    classifier._trained = True
    return classifier

def transition_model_from_payload(payload: dict) -> tuple[Counter[str], dict[str, Counter[str]]]:
    global_system = Counter({str(k): int(v) for k, v in payload['globalSystemActCounts'].items()})
    edges: dict[str, Counter[str]] = defaultdict(Counter)
    for user_act, counts in payload['userActToSystemActCounts'].items():
        edges[str(user_act)].update({str(k): int(v) for k, v in counts.items()})
    return (global_system, edges)

def choose_compact_model(train_examples: Iterable[UserTurnExample], test_examples: Iterable[UserTurnExample], global_system: Counter[str], edges: dict[str, Counter[str]]) -> tuple[BRIDGE.MultinomialLexicalActClassifier, dict, list[dict]]:
    train_examples = tuple(train_examples)
    test_examples = tuple(test_examples)
    full = _fit_with_min_token_count(train_examples, min_token_count=1)
    full_metrics = BRIDGE.evaluate_bridge(test_examples, full, global_system, edges)
    full_gain = full_metrics['endToEndGraphAbsoluteGain']
    full_act_accuracy = full_metrics['userActTop1Accuracy']
    candidates: list[dict] = []
    selected: BRIDGE.MultinomialLexicalActClassifier | None = None
    selected_metrics: dict | None = None
    for threshold in CANDIDATE_MIN_TOKEN_COUNTS:
        candidate = _fit_with_min_token_count(train_examples, min_token_count=threshold)
        metrics = BRIDGE.evaluate_bridge(test_examples, candidate, global_system, edges)
        gain_retention = metrics['endToEndGraphAbsoluteGain'] / full_gain if full_gain > 0 else 0.0
        accuracy_drop = full_act_accuracy - metrics['userActTop1Accuracy']
        qualifies = gain_retention >= MIN_GAIN_RETENTION and accuracy_drop <= MAX_USER_ACT_ACCURACY_DROP and (metrics['endToEndGraphCoverage'] >= MIN_GRAPH_COVERAGE)
        candidates.append({'minimumCorpusTokenCount': threshold, 'vocabularySize': len(candidate.vocabulary), 'userActTop1Accuracy': metrics['userActTop1Accuracy'], 'endToEndGraphAbsoluteGain': metrics['endToEndGraphAbsoluteGain'], 'endToEndGraphCoverage': metrics['endToEndGraphCoverage'], 'fullGainRetention': gain_retention, 'userActAccuracyDrop': accuracy_drop, 'qualifies': qualifies})
        if selected is None and qualifies:
            selected = candidate
            selected_metrics = metrics
    if selected is None or selected_metrics is None:
        raise SystemExit('no compact deterministic style model satisfies the predeclared retention contract')
    return (selected, selected_metrics, candidates)

def build_style_model(root: Path) -> tuple[dict, dict]:
    action_data = TRANSITIONS._load(root / 'dialog_acts.json')
    train_examples = tuple(BRIDGE.iter_split_examples(root, 'dev', action_data))
    test_examples = tuple(BRIDGE.iter_split_examples(root, 'test', action_data))
    global_system, edges, train_pair_count = TRANSITIONS.build_transition_model(TRANSITIONS.iter_split_pairs(root, 'dev', action_data))
    selected, selected_metrics, candidates = choose_compact_model(train_examples, test_examples, global_system, edges)
    classifier_payload = _classifier_payload(selected, min_token_count=next((item['minimumCorpusTokenCount'] for item in candidates if item['qualifies'])))
    model = {'modelVersion': '1.0.0', 'authority': 'style_only', 'source': {'id': 'D-MULTIWOZ', 'revision': EXPECTED_SOURCE_SHA, 'trainingSplit': 'dev', 'evaluationSplit': 'test'}, 'classifier': classifier_payload, 'transitionGraph': _transition_payload(global_system, edges), 'renderingAuthority': {'mayCreateFacts': False, 'mayCreateEvidence': False, 'mayChangePackPermissions': False}}
    model_bytes = _canonical_bytes(model)
    full_candidate = next((item for item in candidates if item['minimumCorpusTokenCount'] == 1))
    selected_candidate = next((item for item in candidates if item['qualifies']))
    receipt = {'status': 'PASS', 'source': 'MultiWOZ-2.2', 'sourceRevision': EXPECTED_SOURCE_SHA, 'trainingExampleCount': len(train_examples), 'testExampleCount': len(test_examples), 'trainingTransitionPairCount': train_pair_count, 'selectionPolicy': {'candidateMinimumCorpusTokenCounts': list(CANDIDATE_MIN_TOKEN_COUNTS), 'minimumFullGainRetention': MIN_GAIN_RETENTION, 'maximumUserActAccuracyDrop': MAX_USER_ACT_ACCURACY_DROP, 'minimumGraphCoverage': MIN_GRAPH_COVERAGE}, 'fullLexicalVocabularySize': full_candidate['vocabularySize'], 'selectedMinimumCorpusTokenCount': selected_candidate['minimumCorpusTokenCount'], 'selectedVocabularySize': selected_candidate['vocabularySize'], 'selectedUserActTop1Accuracy': selected_metrics['userActTop1Accuracy'], 'selectedEndToEndGraphTop1Accuracy': selected_metrics['endToEndGraphTop1Accuracy'], 'selectedEndToEndGraphAbsoluteGain': selected_metrics['endToEndGraphAbsoluteGain'], 'selectedEndToEndGraphCoverage': selected_metrics['endToEndGraphCoverage'], 'selectedFullGainRetention': selected_candidate['fullGainRetention'], 'selectedUserActAccuracyDrop': selected_candidate['userActAccuracyDrop'], 'modelSha256': _sha256_bytes(model_bytes), 'modelByteCount': len(model_bytes), 'candidateMeasurements': candidates, 'rawDialogueEmitted': False, 'factualAuthority': False, 'semanticMatcherAdmission': 'NOT_ADMITTED', 'graphRuntimeAdmission': 'STYLE_MODEL_DERIVED_NOT_YET_WIRED'}
    return (model, receipt)

def main() -> None:
    root_value = os.environ.get('MULTIWOZ_ROOT')
    if not root_value:
        raise SystemExit('MULTIWOZ_ROOT is required')
    source_sha = os.environ.get('MULTIWOZ_SHA', EXPECTED_SOURCE_SHA)
    if source_sha != EXPECTED_SOURCE_SHA:
        raise SystemExit(f'MultiWOZ revision mismatch: {source_sha} != {EXPECTED_SOURCE_SHA}')
    root = Path(root_value)
    model, receipt = build_style_model(root)
    model_target_value = os.environ.get('G6_DERIVED_STYLE_MODEL_PATH')
    if model_target_value:
        model_target = Path(model_target_value)
        model_target.parent.mkdir(parents=True, exist_ok=True)
        model_target.write_bytes(_canonical_bytes(model))
    receipt_target_value = os.environ.get('G6_STYLE_MODEL_RECEIPT_PATH')
    if receipt_target_value:
        receipt_target = Path(receipt_target_value)
        receipt_target.parent.mkdir(parents=True, exist_ok=True)
        receipt_target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(receipt, sort_keys=True))
if __name__ == '__main__':
    main()
