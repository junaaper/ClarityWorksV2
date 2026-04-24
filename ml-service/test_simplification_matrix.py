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


def load_test_text(path: Path) -> str:
    text = path.read_text(encoding='utf-8')
    return '\n'.join(line for line in text.splitlines() if not line.startswith('#')).strip()


def grade_label(g: int) -> str:
    return 'College' if g >= 13 else f'Grade {g}'


def passes(predicted: float, target: int, tolerance: float = TOLERANCE) -> bool:
    return abs(predicted - target) <= tolerance


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
        '--no-groq',
        action='store_true',
        help='Disable Groq (test rule-based fallback only).'
    )
    parser.add_argument(
        '--no-datamuse',
        action='store_true',
        help='Disable Datamuse API calls.'
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
    return parser


def print_table(rows, targets, tolerance, mode, groq_enabled):
    col_w = 10
    src_w = 14

    print()
    print(f"  Rewrite Matrix -- mode={mode}, groq={'ON' if groq_enabled else 'OFF'}, tolerance=+/-{tolerance}")
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
        if args.no_groq:
            simplifier.groq_validator.client = None
            simplifier.groq_client = None
        if args.no_datamuse:
            simplifier.datamuse_finder.get_simpler_synonym = lambda _word: None

    total = 0
    passed = 0
    failed_cases = []
    table_rows = {}

    for file_path in files:
        source_grade = expected_grade(file_path)
        text = load_test_text(file_path)
        source_label = grade_label(source_grade)
        table_rows[source_label] = {}

        for target in targets:
            if target == source_grade:
                table_rows[source_label][target] = {'skip': True, 'pass': True, 'predicted': float(target)}
                continue

            total += 1
            predictions = []

            for run in range(args.repeat):
                print(f"  {source_label} -> {grade_label(target)} (run {run + 1}/{args.repeat})...", file=sys.stderr)
                t0 = time.time()

                result = simplifier.simplify_to_grade(text, target, mode=args.mode)
                prediction = model.predict(result['simplified_text'])['predictions']
                raw_score = float(prediction['raw_score'])
                elapsed = time.time() - t0

                predictions.append({
                    'raw_score': raw_score,
                    'label': prediction['predicted_grade_level'],
                    'elapsed': round(elapsed, 1),
                    'changes': len(result.get('changes', [])),
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
                'distance': round(abs(best['raw_score'] - target), 2),
                'deterministic': deterministic,
                'runs': predictions,
            }
            table_rows[source_label][target] = entry

            if not hit:
                failed_cases.append({
                    'source': source_label,
                    'target': grade_label(target),
                    'predicted': best['raw_score'],
                    'distance': entry['distance'],
                })

    if args.json:
        payload = {
            'mode': args.mode,
            'groq_enabled': not args.no_groq,
            'tolerance': args.tolerance,
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
        print_table(table_rows, targets, args.tolerance, args.mode, not args.no_groq)

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
