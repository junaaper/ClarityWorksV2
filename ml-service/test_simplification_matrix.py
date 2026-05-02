import argparse
import contextlib
import io
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from models.readability_model import ReadabilityModel
from models.simplifier import TextSimplifier


TOLERANCE = 1.0


def expected_grade(path: Path) -> int:
    return 13 if path.name == 'college.txt' else int(path.stem.split('_')[1])


def grade_from_label(label: str) -> int:
    return 13 if label == 'College' else int(label.replace('Grade ', ''))


def load_test_text(path: Path) -> str:
    text = path.read_text(encoding='utf-8')
    return '\n'.join(line for line in text.splitlines() if not line.startswith('#')).strip()


def grade_label(g: int) -> str:
    return 'College' if g >= 13 else f'Grade {g}'


def passes(predicted: float, target: int, tolerance: float = TOLERANCE) -> bool:
    return abs(predicted - target) <= tolerance


def target_band(target: int) -> tuple[float, float]:
    if target <= 3:
        return float('-inf'), 4.0
    if target >= 13:
        return 13.0, float('inf')
    return float(target), float(target + 1)


def in_target_band(raw_score: float, target: int) -> bool:
    lower, upper = target_band(target)
    return lower <= raw_score < upper


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Run the readability rewrite matrix across all calibrated test files.'
    )
    parser.add_argument(
        '--mode',
        choices=['interactive', 'auto'],
        default='auto',
        help='Rewrite mode to test. Default: auto.'
    )
    parser.add_argument(
        '--targets',
        default='3,5,8,10,12,13',
        help='Comma-separated target grades. Default: 3,5,8,10,12,13 (representative subset).'
    )
    parser.add_argument(
        '--sources',
        default=None,
        help='Comma-separated source filenames (e.g. grade_3.txt,grade_12.txt). Default: all.'
    )
    parser.add_argument(
        '--tolerance',
        type=float,
        default=TOLERANCE,
        help=f'Grade tolerance for pass/fail. Default: {TOLERANCE}.'
    )
    parser.add_argument(
        '--no-llm',
        action='store_true',
        help='Disable LLM (test rule-based fallback only).'
    )
    parser.add_argument(
        '--no-datamuse',
        action='store_true',
        help='Disable Datamuse API calls.'
    )
    parser.add_argument(
        '--llm-primary',
        action='store_true',
        help='Legacy alias kept for compatibility. Matrix runs are LLM-primary by default when an LLM is available.'
    )
    parser.add_argument(
        '--rule-primary',
        action='store_true',
        help='Force deterministic rule-based candidate generation as the primary authoring path.'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output raw JSON instead of table.'
    )
    parser.add_argument(
        '--repeat',
        type=int,
        default=1,
        help='Run each case N times to check determinism. Default: 1.'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0,
        help='Seconds to wait between test cases (avoids API rate limits). Default: 0.'
    )
    return parser


def print_table(rows, targets, tolerance, mode, llm_enabled):
    col_w = 10
    src_w = max(14, *(len(source_name) for source_name in rows))

    print()
    print(f"  Rewrite Matrix -- mode={mode}, llm={'ON' if llm_enabled else 'OFF'}, tolerance=+/-{tolerance}")
    print(f"  {'-' * (src_w + len(targets) * col_w + 4)}")

    header = f"  {'Source':<{src_w}}"
    for t in targets:
        header += f"{'>' + grade_label(t):>{col_w}}"
    print(header)
    print(f"  {'-' * (src_w + len(targets) * col_w + 4)}")

    for source_name, source_results in rows.items():
        line = f"  {source_name:<{src_w}}"
        for t in targets:
            result = source_results.get(t)
            if result is None:
                line += f"{'--':>{col_w}}"
            elif result['skip']:
                line += f"{'(same)':>{col_w}}"
            elif result['pass']:
                pred = result['predicted']
                line += f"{'OK ' + f'{pred:.1f}':>{col_w}}"
            else:
                pred = result['predicted']
                line += f"{'MISS ' + f'{pred:.1f}':>{col_w}}"
        print(line)

    print(f"  {'-' * (src_w + len(targets) * col_w + 4)}")


def main() -> int:
    args = build_parser().parse_args()

    targets = [int(t.strip()) for t in args.targets.split(',') if t.strip()]
    test_dir = ROOT / 'data' / 'test_files'
    all_files = sorted(test_dir.glob('*.txt'), key=expected_grade)

    if args.sources:
        source_names = {s.strip() for s in args.sources.split(',')}
        files = [f for f in all_files if f.name in source_names]
    else:
        files = all_files

    print("Loading models...", file=sys.stderr)
    with contextlib.redirect_stdout(io.StringIO()):
        model = ReadabilityModel()
        model.load_models()
        simplifier = TextSimplifier(readability_model=model)
        if args.no_llm:
            simplifier.llm_validator.client = None
            simplifier.llm_client = None
        if args.no_datamuse:
            simplifier.datamuse_finder.get_simpler_synonym = lambda _word: None

    total = 0
    passed = 0
    failed_cases = []
    table_rows = {}
    source_baselines = {}

    for file_path in files:
        source_expected_grade = expected_grade(file_path)
        text = load_test_text(file_path)
        with contextlib.redirect_stdout(io.StringIO()):
            source_prediction = model.predict(text)['predictions']
        source_raw = float(source_prediction['raw_score'])
        source_model_label = source_prediction['predicted_grade_level']
        source_model_grade = grade_from_label(source_model_label)
        source_label = f"{file_path.name} ({source_model_label} {source_raw:.1f})"
        source_baselines[source_label] = {
            'file': file_path.name,
            'expected_grade': source_expected_grade,
            'expected_label': grade_label(source_expected_grade),
            'model_raw_score': source_raw,
            'model_label': source_model_label,
            'model_grade': source_model_grade,
        }
        table_rows[source_label] = {}

        for target in targets:
            if in_target_band(source_raw, target):
                table_rows[source_label][target] = {
                    'skip': True,
                    'pass': True,
                    'predicted': source_raw,
                    'label': source_model_label,
                    'source_file': file_path.name,
                    'source_expected_grade': source_expected_grade,
                    'source_model_raw_score': source_raw,
                    'source_model_label': source_model_label,
                }
                continue

            if args.delay and total > 0:
                time.sleep(args.delay)

            total += 1
            predictions = []

            for run in range(args.repeat):
                print(f"  {source_label} -> {grade_label(target)} (run {run + 1}/{args.repeat})...", file=sys.stderr)
                t0 = time.time()

                with contextlib.redirect_stdout(io.StringIO()):
                    result = simplifier.simplify_to_grade(
                        text,
                        target,
                        mode=args.mode,
                        prefer_rule_based=args.rule_primary,
                    )
                    prediction = model.predict(result['simplified_text'])['predictions']
                raw_score = float(prediction['raw_score'])
                elapsed = time.time() - t0

                predictions.append({
                    'raw_score': raw_score,
                    'label': prediction['predicted_grade_level'],
                    'elapsed': round(elapsed, 1),
                    'changes': len(result.get('changes', [])),
                    'target_distance': result.get('target_distance'),
                    'generation_mode': (result.get('selection_summary') or {}).get('generation_mode'),
                })

                print(f"    -> predicted {raw_score:.1f} ({prediction['predicted_grade_level']}) "
                      f"in {elapsed:.1f}s, {len(result.get('changes', []))} changes", file=sys.stderr)

            best = min(predictions, key=lambda p: abs(p['raw_score'] - target))
            hit = passes(best['raw_score'], target, args.tolerance)

            if hit:
                passed += 1

            deterministic = len(set(round(p['raw_score'], 1) for p in predictions)) == 1 if args.repeat > 1 else None

            entry = {
                'skip': False,
                'pass': hit,
                'predicted': best['raw_score'],
                'label': best['label'],
                'distance': round(abs(best['raw_score'] - target), 2),
                'deterministic': deterministic,
                'runs': predictions,
                'source_file': file_path.name,
                'source_expected_grade': source_expected_grade,
                'source_model_raw_score': source_raw,
                'source_model_label': source_model_label,
            }
            table_rows[source_label][target] = entry

            if not hit:
                failed_cases.append({
                    'source': source_label,
                    'source_file': file_path.name,
                    'source_expected_grade': source_expected_grade,
                    'source_model_raw_score': source_raw,
                    'source_model_label': source_model_label,
                    'target': grade_label(target),
                    'predicted': best['raw_score'],
                    'predicted_label': best['label'],
                    'distance': entry['distance'],
                })

    if args.json:
        payload = {
            'mode': args.mode,
            'llm_enabled': not args.no_llm,
            'rewrite_authoring': (
                'llm_disabled' if args.no_llm
                else 'rule_primary' if args.rule_primary
                else 'llm_augmented_single_pass'
            ),
            'tolerance': args.tolerance,
            'source_baselines': source_baselines,
            'summary': {
                'total': total,
                'passed': passed,
                'failed': total - passed,
                'pass_rate': round(passed / max(total, 1), 3),
            },
            'results': table_rows,
            'failed_cases': failed_cases,
        }
        print(json.dumps(payload, indent=2))
    else:
        print_table(table_rows, targets, args.tolerance, args.mode, not args.no_llm)

        print()
        print(f"  Results: {passed}/{total} passed (+/-{args.tolerance} tolerance)")
        if failed_cases:
            print(f"  Failed cases:")
            for fc in failed_cases:
                print(f"    {fc['source']} -> {fc['target']}: predicted {fc['predicted']:.1f} (off by {fc['distance']:.1f})")
        print()

    return 0 if passed == total else 1


if __name__ == '__main__':
    raise SystemExit(main())
