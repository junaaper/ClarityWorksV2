import argparse
import contextlib
import io
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / 'ml-service'
sys.path.insert(0, str(ROOT))

from models.readability_model import ReadabilityModel
from models.simplifier import TextSimplifier


def expected_grade(path: Path) -> int:
    return 13 if path.name == 'college.txt' else int(path.stem.split('_')[1])


def load_test_text(path: Path) -> str:
    text = path.read_text(encoding='utf-8')
    return '\n'.join(line for line in text.splitlines() if not line.startswith('#')).strip()


def in_target_band(predicted: float, target: int) -> bool:
    if target >= 13:
        return predicted >= 13.0
    return target <= predicted < target + 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Inspect simplification accuracy by direction, gap, and structural validity.'
    )
    parser.add_argument(
        '--mode',
        choices=['interactive', 'auto'],
        default='interactive',
        help='Rewrite mode to test. Default: interactive.'
    )
    parser.add_argument(
        '--targets',
        default='3,4,5,6,7,8,9,10,11,12,13',
        help='Comma-separated target grades to test. Default: 3-13.'
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    targets = [int(token.strip()) for token in args.targets.split(',') if token.strip()]
    test_dir = ROOT / 'data' / 'test_files'
    files = sorted(test_dir.glob('*.txt'), key=expected_grade)

    rows = []
    with contextlib.redirect_stdout(io.StringIO()):
        model = ReadabilityModel()
        model.load_models()

        simplifier = TextSimplifier(readability_model=model)
        simplifier.llm_validator.client = None
        simplifier.llm_client = None
        simplifier.datamuse_finder.get_simpler_synonym = lambda _word: None

        for file_path in files:
            source_grade = expected_grade(file_path)
            text = load_test_text(file_path)

            for target in targets:
                result = simplifier.simplify_to_grade(text, target, mode=args.mode)
                prediction = model.predict(result['simplified_text'])['predictions']
                raw_score = float(prediction['raw_score'])
                invalid_sentences = simplifier._collect_invalid_sentences(result['simplified_text'])
                gap = abs(target - source_grade)
                if target > source_grade:
                    direction = 'upgrade'
                elif target < source_grade:
                    direction = 'downgrade'
                else:
                    direction = 'same_grade'

                rows.append({
                    'source': file_path.name,
                    'source_grade': source_grade,
                    'target': target,
                    'direction': direction,
                    'gap': gap,
                    'predicted': round(raw_score, 2),
                    'distance': round(abs(raw_score - target), 2),
                    'hit': in_target_band(raw_score, target),
                    'changes': len(result['changes']),
                    'invalid_sentence_count': len(invalid_sentences),
                    'invalid_sentences': invalid_sentences[:3],
                })

    by_bucket = {}
    for row in rows:
        bucket_key = f"{row['direction']}_gap_{row['gap']}"
        bucket = by_bucket.setdefault(bucket_key, {
            'cases': 0,
            'hits': 0,
            'avg_distance_total': 0.0,
            'avg_changes_total': 0.0,
            'invalid_cases': 0,
            'invalid_sentence_total': 0,
        })
        bucket['cases'] += 1
        bucket['hits'] += 1 if row['hit'] else 0
        bucket['avg_distance_total'] += row['distance']
        bucket['avg_changes_total'] += row['changes']
        bucket['invalid_cases'] += 1 if row['invalid_sentence_count'] else 0
        bucket['invalid_sentence_total'] += row['invalid_sentence_count']

    summary = {}
    for key, bucket in sorted(by_bucket.items()):
        cases = max(1, bucket['cases'])
        summary[key] = {
            'cases': bucket['cases'],
            'hits': bucket['hits'],
            'hit_rate': round(bucket['hits'] / cases, 3),
            'avg_distance': round(bucket['avg_distance_total'] / cases, 2),
            'avg_changes': round(bucket['avg_changes_total'] / cases, 2),
            'invalid_cases': bucket['invalid_cases'],
            'invalid_sentence_total': bucket['invalid_sentence_total'],
        }

    payload = {
        'mode': args.mode,
        'summary_by_gap': summary,
        'worst_distance_cases': sorted(rows, key=lambda row: row['distance'], reverse=True)[:15],
        'invalid_cases': [row for row in rows if row['invalid_sentence_count']][:15],
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
