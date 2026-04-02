from groq import Groq
import os
import json


class GroqValidator:
    """Use Groq to validate rule-based simplification changes"""

    def __init__(self):
        api_key = os.getenv('GROQ_API_KEY')

        if not api_key:
            print("Warning: GROQ_API_KEY not found in .env - Groq validation disabled")
            self.client = None
        else:
            self.client = Groq(api_key=api_key)
            print("Groq API initialized for validation")

    def validate_changes(self, original_text, simplified_text, changes):
        """
        Ask Groq: Are these simplification changes correct?

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
1. Do the changes preserve the original meaning?
2. Are the word replacements appropriate?
3. Are there any errors or awkward phrasings?

Respond ONLY with valid JSON (no markdown, no code blocks):
{{"valid": true or false, "issues": ["issue1", "issue2"], "suggestions": ["suggestion1", "suggestion2"]}}"""

            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
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
            print(f"Groq validation error: {e}")
            return {
                'valid': True,
                'issues': [],
                'suggestions': []
            }

    def fix_with_groq(self, text, target_grade, issues):
        """
        Let Groq fix the simplification if validation found issues

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
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Groq fix error: {e}")
            return text


def test_groq_validator():
    """Test Groq validator"""
    validator = GroqValidator()

    if not validator.client:
        print("Groq API not configured. Add GROQ_API_KEY to .env")
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
    print("TESTING GROQ VALIDATOR")
    print("=" * 60)

    result = validator.validate_changes(original, simplified, changes)

    print(f"\nValid: {result['valid']}")
    print(f"Issues: {result['issues']}")
    print(f"Suggestions: {result['suggestions']}")

if __name__ == "__main__":
    test_groq_validator()
