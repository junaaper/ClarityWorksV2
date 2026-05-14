from openai import OpenAI
import os
import json

FIREWORKS_MODEL = "accounts/fireworks/models/qwen3p6-plus"


class LLMValidator:
    """Use Fireworks AI to validate rule-based simplification changes"""

    def __init__(self):
        api_key = os.getenv('FIREWORKS_API_KEY')

        if not api_key:
            print("Warning: FIREWORKS_API_KEY not found in .env - LLM validation disabled")
            self.client = None
        else:
            self.client = OpenAI(
                base_url="https://api.fireworks.ai/inference/v1",
                api_key=api_key,
            )
            print("Fireworks API initialized for validation")

    def validate_changes(self, original_text, simplified_text, changes):
        """
        Ask LLM: Are these simplification changes correct?

        Args:
            original_text: Original text
            simplified_text: Simplified text
            changes: List of change objects

        Returns:
            {
                'valid': bool,
                'issues': [list of issues],
                'suggestions': [list of suggestions]
            }
        """

        if not self.client:
            return {
                'valid': True,
                'issues': [],
                'suggestions': []
            }

        try:
            changes_summary = "\n".join([
                f"- Changed '{c['original']}' to '{c['simplified']}': {c['reason']}"
                for c in changes[:10]
            ])

            prompt = f"""You are a text simplification validator. Review these changes.

ORIGINAL TEXT:
{original_text[:500]}

SIMPLIFIED TEXT:
{simplified_text[:500]}

CHANGES MADE:
{changes_summary}

TASK:
1. Check that the simplified text preserves the original facts, actors, and causality.
2. Flag any sentence that becomes incomplete, misleading, or unnatural.
3. Flag any word replacement that changes meaning, even slightly.
4. Flag subject/object swaps or causal errors such as changing what becomes what.

Respond ONLY with valid JSON (no markdown, no code blocks):
{{"valid": true or false, "issues": ["issue1", "issue2"], "suggestions": ["suggestion1", "suggestion2"]}}"""

            response = self.client.chat.completions.create(
                model=FIREWORKS_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=500,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )

            content = response.choices[0].message.content.strip()

            # Remove markdown code blocks if present
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]

            result = json.loads(content)

            return {
                'valid': result.get('valid', True),
                'issues': result.get('issues', []),
                'suggestions': result.get('suggestions', [])
            }

        except Exception as e:
            print(f"LLM validation error: {e}")
            return {
                'valid': True,
                'issues': [],
                'suggestions': []
            }

    def _parse_json_response(self, content, fallback):
        if not content:
            return fallback

        cleaned = content.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('```')[1]
            if cleaned.startswith('json'):
                cleaned = cleaned[4:]
        try:
            return json.loads(cleaned)
        except Exception:
            return fallback

    def critic_candidates(self, original_text, target_grade, candidates):
        """
        Review top deterministic candidates and return bounded JSON feedback.
        LLM is a critic here, not the author.
        """
        if not self.client or not candidates:
            return {
                'preferred_index': 0,
                'reviews': [],
            }

        try:
            summarized_candidates = []
            for index, candidate in enumerate(candidates[:3]):
                summarized_candidates.append({
                    'index': index,
                    'score': candidate.get('score', candidate.get('candidate_score')),
                    'raw_score': candidate.get('raw_score'),
                    'selection_path': candidate.get('selection_path', candidate.get('rule_history', [])),
                    'text': candidate.get('text', '')[:1600],
                })

            prompt = f"""You are reviewing deterministic text rewrite candidates.

ORIGINAL TEXT:
{original_text[:1800]}

TARGET GRADE:
{target_grade}

CANDIDATES:
{json.dumps(summarized_candidates, ensure_ascii=True)}

Return ONLY valid JSON with this shape:
{{
  "preferred_index": 0,
  "reviews": [
    {{
      "index": 0,
      "meaning_drift": false,
      "awkward_phrase": false,
      "grade_too_low": false,
      "grade_too_high": false,
      "citation_needed": false,
      "reject_candidate": false,
      "notes": ["short note"]
    }}
  ]
}}

Rules:
- Prefer the candidate that best preserves meaning.
- Reject a candidate if it changes meaning or becomes awkward.
- Do not propose a new rewrite.
"""

            response = self.client.chat.completions.create(
                model=FIREWORKS_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=900,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            content = response.choices[0].message.content
            return self._parse_json_response(content, {'preferred_index': 0, 'reviews': []})
        except Exception as e:
            print(f"LLM critic error: {e}")
            return {
                'preferred_index': 0,
                'reviews': [],
            }

    def local_repair(self, original_text, candidate_text, target_grade, issues):
        """
        Repair only the current candidate. This stays bounded to the current
        text and fixes semantics/flow without replacing the whole rule-based pass.
        """
        if not self.client:
            return candidate_text

        issue_lines = "\n".join(f"- {issue}" for issue in (issues or [])) or "- Improve local flow only"

        try:
            prompt = f"""You are repairing a deterministic rewrite candidate.

ORIGINAL TEXT:
{original_text}

CURRENT CANDIDATE:
{candidate_text}

ISSUES:
{issue_lines}

Rules:
- Keep the repaired text close to the current candidate, but you MAY rewrite the affected sentence
  or short paragraph when that is required to restore correct grammar or meaning.
- Fix meaning drift, incomplete sentences, broken references, and awkward phrasing.
- Preserve the original facts exactly.
- Do not change who did what, what causes what, or what turns into what.
- Do not rewrite the full passage from scratch.
- Keep the grade close to Grade {target_grade}.
- If the current candidate is already good, return it unchanged.
- Return ONLY the repaired text.
"""

            response = self.client.chat.completions.create(
                model=FIREWORKS_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=2200,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            repaired = response.choices[0].message.content.strip()
            return repaired or candidate_text
        except Exception as e:
            print(f"LLM local repair error: {e}")
            return candidate_text

    def polish_text(self, original_text, rewritten_text, target_grade, issues=None, going_up=False):
        """
        Do the final bounded repair pass on top of a rule-based rewrite.
        The model may fix semantics, flow, and sentence integrity, including
        rewriting the affected sentence(s) or short paragraph(s) when needed.
        """
        if not self.client:
            return rewritten_text

        issues = issues or []
        issue_lines = "\n".join(f"- {issue}" for issue in issues) or "- Improve flow only where needed"
        direction = "upgrade" if going_up else "simplification"

        try:
            prompt = f"""You are polishing a RULE-BASED text {direction}.

ORIGINAL TEXT:
{original_text}

CURRENT REWRITTEN TEXT:
{rewritten_text}

FOCUS AREAS:
{issue_lines}

RULES:
1. Keep the rewritten text close to the current version, but you MAY rewrite the affected sentence(s)
   or a short paragraph when needed to restore proper English and preserve meaning.
2. Preserve all facts and meaning from the original text.
3. Fix semantic drift, incomplete sentences, broken references, and awkward phrasing.
4. Do NOT change who did what, what carries what, or what turns into what.
5. Do NOT rewrite the full passage from scratch.
6. Do NOT add new ideas, examples, or commentary.
7. Do NOT add a conclusion, takeaway, moral, or reflective summary. Do NOT broaden one paragraph into a summary of the whole passage.
8. Keep the same paragraph count and paragraph order as the original. If you repair the final paragraph, keep it within the same local scope instead of making it more general.
9. Keep the result aligned with Grade {target_grade}.
10. If the current rewritten text is already good, return it unchanged.
11. Return ONLY the polished text.
"""

            response = self.client.chat.completions.create(
                model=FIREWORKS_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=2500,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )

            polished = response.choices[0].message.content.strip()
            return polished or rewritten_text

        except Exception as e:
            print(f"LLM polish error: {e}")
            return rewritten_text

    def fix_issues(self, text, target_grade, issues):
        """
        Let LLM fix the simplification if validation found issues

        Args:
            text: Current simplified text (with issues)
            target_grade: Target grade level
            issues: List of issues from validation

        Returns:
            str: Improved simplified text
        """

        if not self.client:
            return text

        try:
            issues_text = "\n".join([f"- {issue}" for issue in issues])

            prompt = f"""Simplify this text to Grade {target_grade} level.

CURRENT TEXT:
{text}

ISSUES TO FIX:
{issues_text}

RULES:
- Fix the issues mentioned above
- Use simple words and short sentences
- Preserve the original meaning
- Target: Grade {target_grade} reading level

Respond with ONLY the improved text (no explanations):"""

            response = self.client.chat.completions.create(
                model=FIREWORKS_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=2000,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"LLM fix error: {e}")
            return text


def test_llm_validator():
    """Test LLM validator"""
    validator = LLMValidator()

    if not validator.client:
        print("Fireworks API not configured. Add FIREWORKS_API_KEY to .env")
        return

    original = "The comprehensive implementation of this methodology necessitates careful consideration."
    simplified = "The complete use of this method needs careful thought."
    changes = [
        {
            'original': 'comprehensive',
            'simplified': 'complete',
            'reason': 'Simpler word'
        },
        {
            'original': 'implementation',
            'simplified': 'use',
            'reason': 'More direct'
        }
    ]

    print("=" * 60)
    print("TESTING LLM VALIDATOR")
    print("=" * 60)

    result = validator.validate_changes(original, simplified, changes)

    print(f"\nValid: {result['valid']}")
    print(f"Issues: {result['issues']}")
    print(f"Suggestions: {result['suggestions']}")

if __name__ == "__main__":
    test_llm_validator()
