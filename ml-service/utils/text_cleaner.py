import re
import unicodedata

try:
    from wordfreq import zipf_frequency
except Exception:
    zipf_frequency = None


class TextCleaner:
    """Clean extracted text from PDFs/DOCX/OCR"""

    PDF_REPLACEMENT_CHAR = '\ufffd'
    SUSPICIOUS_WORD_GLYPHS = (
        PDF_REPLACEMENT_CHAR,
        '\u00d4',  # Ô, sometimes emitted for "ti" or "ft" ligatures.
        '\u019f',  # Ɵ, commonly emitted for "ti".
        '\u014c',  # Ō, commonly emitted for "ft".
        '\u014d',  # ō, lowercase variant of the same extraction artifact.
        '\u019e',  # ƞ, commonly emitted for "tf".
    )
    GLYPH_REPAIR_OPTIONS = {
        PDF_REPLACEMENT_CHAR: ('ti', 'ft', 'tf'),
        '\u00d4': ('ti', 'ft', 'tf'),
        '\u019f': ('ti',),
        '\u014c': ('ft',),
        '\u014d': ('ft',),
        '\u019e': ('tf',),
    }

    @staticmethod
    def repair_utf8_mojibake(text):
        """
        Repair common UTF-8-as-Latin-1 mojibake before control stripping.

        This catches broken forms of ligatures/smart punctuation such as the
        bytes for "ﬁ" being decoded as "ï¬\x81". If we remove C1 controls
        first, the broken sequence becomes unrecoverable.
        """
        if not text:
            return ""

        replacements = {
            '\ufb00': 'ff',
            '\ufb01': 'fi',
            '\ufb02': 'fl',
            '\ufb03': 'ffi',
            '\ufb04': 'ffl',
            '\ufb05': 'st',
            '\ufb06': 'st',
            '\u2018': "'",
            '\u2019': "'",
            '\u201a': "'",
            '\u201b': "'",
            '\u201c': '"',
            '\u201d': '"',
            '\u201e': '"',
            '\u201f': '"',
            '\u2013': '-',
            '\u2014': '--',
            '\u00a0': ' ',
        }

        for source, replacement in list(replacements.items()):
            try:
                replacements[source.encode('utf-8').decode('latin-1')] = replacement
            except UnicodeError:
                pass

        for source, replacement in replacements.items():
            text = text.replace(source, replacement)

        return text

    @staticmethod
    def normalize_unicode_text(text):
        """Normalize PDF/OCR Unicode without silently dropping real letters."""
        text = TextCleaner.repair_utf8_mojibake(text)
        replacements = {
            '\ufb00': 'ff',
            '\ufb01': 'fi',
            '\ufb02': 'fl',
            '\ufb03': 'ffi',
            '\ufb04': 'ffl',
            '\ufb05': 'st',
            '\ufb06': 'st',
            '\u0398': 'ti',
            '\u2018': "'",
            '\u2019': "'",
            '\u201a': "'",
            '\u201b': "'",
            '\u201c': '"',
            '\u201d': '"',
            '\u201e': '"',
            '\u201f': '"',
            '\u2013': '-',
            '\u2014': '--',
            '\u2212': '-',
            '\u00a0': ' ',
            '\u2007': ' ',
            '\u202f': ' ',
        }

        text = ''.join(replacements.get(ch, ch) for ch in text)
        text = unicodedata.normalize('NFKC', text)
        text = re.sub(r'[\u200b-\u200f\u202a-\u202e\ufeff]', '', text)
        return text

    @staticmethod
    def repair_extracted_glyphs(text):
        """
        Repair high-confidence extracted glyph failures inside English words.
        Some PDFs/DOCX conversions expose custom-font ligatures as U+FFFD or
        Latin glyphs such as Ô. The same glyph can mean "ti" or "ft", so score
        candidate repairs instead of applying one global mapping.

        Returns:
            tuple[str, int]: repaired text and number of suspicious glyphs fixed.
        """
        if not text:
            return "", 0

        suspicious_pattern = '[' + ''.join(re.escape(ch) for ch in TextCleaner.SUSPICIOUS_WORD_GLYPHS) + ']'
        before = sum(text.count(ch) for ch in TextCleaner.SUSPICIOUS_WORD_GLYPHS)
        if before == 0:
            return text, 0

        def word_score(word):
            lookup = re.sub(r"[^A-Za-z'-]", '', word).lower()
            if len(lookup) < 3:
                return 0.0
            if zipf_frequency:
                return zipf_frequency(lookup, 'en')
            return 1.0 if re.search(r'[aeiouy]', lookup) else 0.0

        def preserve_case(original, candidate):
            ascii_letters = re.sub(r'[^A-Za-z]', '', original)
            if ascii_letters and ascii_letters.isupper():
                return candidate.upper()
            first = original[:1]
            if first.isascii() and first.isupper():
                return candidate[:1].upper() + candidate[1:]
            return candidate

        def best_repair(match):
            token = match.group(0)
            glyph_count = sum(token.count(ch) for ch in TextCleaner.SUSPICIOUS_WORD_GLYPHS)
            if glyph_count == 0:
                return token

            base_score = word_score(re.sub(suspicious_pattern, '', token))
            candidates = ['']
            for char in token:
                if char in TextCleaner.SUSPICIOUS_WORD_GLYPHS:
                    candidates = [
                        prefix + option
                        for prefix in candidates
                        for option in TextCleaner.GLYPH_REPAIR_OPTIONS.get(char, ('ti', 'ft', 'tf'))
                    ]
                else:
                    candidates = [prefix + char for prefix in candidates]

            scored = []
            for candidate in candidates:
                candidate_score = word_score(candidate)
                scored.append((candidate_score, candidate))

            score, candidate = max(scored, key=lambda item: item[0])
            # Require the repaired token to look like a real word. Very short
            # words such as "After" still score above this floor in wordfreq.
            if score >= max(2.0, base_score + 0.5):
                return preserve_case(token, candidate.lower())
            return token

        glyph_chars = ''.join(re.escape(ch) for ch in TextCleaner.SUSPICIOUS_WORD_GLYPHS)
        token_pattern = re.compile(rf"\b[A-Za-z{glyph_chars}]*{suspicious_pattern}[A-Za-z{glyph_chars}]*\b")
        repaired = token_pattern.sub(best_repair, text)
        after = sum(repaired.count(ch) for ch in TextCleaner.SUSPICIOUS_WORD_GLYPHS)
        return repaired, before - after

    @staticmethod
    def repair_pdf_replacement_glyphs(text):
        """Backward-compatible wrapper for the shared extracted glyph repair."""
        return TextCleaner.repair_extracted_glyphs(text)

    @staticmethod
    def pdf_extraction_quality_metrics(text):
        """Return lightweight quality metrics for extracted PDF text."""
        normalized = TextCleaner.normalize_unicode_text(text or "")
        repaired, repaired_count = TextCleaner.repair_extracted_glyphs(normalized)
        repaired = TextCleaner._fix_common_extraction_artifacts(repaired)
        words = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", repaired)
        char_count = len(repaired)
        letter_count = sum(1 for ch in repaired if ch.isalpha())
        private_use_count = sum(1 for ch in repaired if '\ue000' <= ch <= '\uf8ff')
        replacement_count = repaired.count(TextCleaner.PDF_REPLACEMENT_CHAR)
        suspicious_glyph_count = sum(repaired.count(ch) for ch in TextCleaner.SUSPICIOUS_WORD_GLYPHS)
        control_count = len(re.findall(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', repaired))
        excessive_space_runs = len(re.findall(r' {3,}', repaired))
        suspicious_pattern = '[' + ''.join(re.escape(ch) for ch in TextCleaner.SUSPICIOUS_WORD_GLYPHS) + ']'
        broken_word_count = len(re.findall(rf"\b[A-Za-z]*{suspicious_pattern}[A-Za-z]*\b", repaired))
        suspicious_vowelless_words = sum(
            1 for word in words
            if len(word) >= 5 and not re.search(r'[aeiouyAEIOUY]', word)
        )

        replacement_density = (suspicious_glyph_count / max(char_count, 1)) * 1000
        quality_score = (
            letter_count
            + len(words) * 4
            - private_use_count * 120
            - suspicious_glyph_count * 250
            - broken_word_count * 120
            - control_count * 50
            - suspicious_vowelless_words * 8
            - excessive_space_runs * 2
        )

        if suspicious_glyph_count or private_use_count or broken_word_count:
            quality_label = 'degraded'
        elif len(words) < 20 and char_count > 0:
            quality_label = 'limited'
        else:
            quality_label = 'clean'

        return {
            'text': repaired,
            'quality_score': quality_score,
            'quality_label': quality_label,
            'char_count': char_count,
            'letter_count': letter_count,
            'word_count': len(words),
            'replacement_char_count': replacement_count,
            'suspicious_glyph_count': suspicious_glyph_count,
            'replacement_density_per_1000_chars': round(replacement_density, 2),
            'repaired_replacement_count': repaired_count,
            'repaired_suspicious_glyph_count': repaired_count,
            'private_use_char_count': private_use_count,
            'control_char_count': control_count,
            'broken_word_count': broken_word_count,
            'suspicious_vowelless_word_count': suspicious_vowelless_words,
            'excessive_space_run_count': excessive_space_runs,
        }

    @staticmethod
    def pdf_extraction_warnings(metrics):
        """Build user-facing warnings from PDF extraction quality metrics."""
        warnings = []
        if metrics.get('repaired_replacement_count', 0) > 0:
            warnings.append(
                f"Repaired {metrics['repaired_replacement_count']} likely PDF font glyph issue"
                f"{'' if metrics['repaired_replacement_count'] == 1 else 's'}."
            )
        if metrics.get('suspicious_glyph_count', metrics.get('replacement_char_count', 0)) > 0:
            count = metrics.get('suspicious_glyph_count', metrics.get('replacement_char_count', 0))
            warnings.append(
                f"{count} unreadable or suspicious glyph"
                f"{'' if count == 1 else 's'} remain; review extracted text before using it."
            )
        if metrics.get('private_use_char_count', 0) > 0:
            warnings.append(
                "The PDF uses custom font glyphs that may not map cleanly to text."
            )
        if metrics.get('word_count', 0) < 20 and metrics.get('char_count', 0) > 0:
            warnings.append("This page produced very little extractable text.")
        return warnings

    @staticmethod
    def clean_extracted_text(text):
        """
        Clean text extracted from files:
        - Remove excessive whitespace
        - Remove nonsensical characters/symbols
        - Fix common OCR errors
        - Preserve paragraph structure
        - Make text editable and readable

        Args:
            text: Raw extracted text

        Returns:
            str: Cleaned, formatted text
        """
        if not text:
            return ""

        text = TextCleaner.repair_utf8_mojibake(text)

        # Step 1: Remove null bytes and control characters (except newlines/tabs)
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', text)

        # Step 2: Normalize Unicode while preserving real extracted letters.
        # PDFs often encode ligatures/private glyphs as non-ASCII text; dropping
        # them can turn "time" into "me" or "mentioned" into "menoned".
        text = TextCleaner.normalize_unicode_text(text)
        text, _ = TextCleaner.repair_extracted_glyphs(text)

        # Step 3: Remove repeated special characters (e.g., "------", "======")
        text = re.sub(r'([^\w\s])\1{3,}', r'\1\1', text)

        # Step 4: Fix excessive whitespace within lines
        text = re.sub(r'[ \t]{2,}', ' ', text)

        # Step 5: Fix excessive newlines (preserve paragraph breaks)
        text = re.sub(r'\n{4,}', '\n\n\n', text)

        # Step 6: Remove lines with only whitespace
        lines = text.split('\n')
        lines = [line.strip() for line in lines]

        # Step 7: Remove nonsensical short lines (likely artifacts), but keep
        # legitimate short headings such as "Letter of Motivation".
        cleaned_lines = []
        for line in lines:
            word_like_tokens = re.findall(r'[A-Za-z]{2,}', line)
            alpha_count = sum(1 for ch in line if ch.isalpha())
            is_short_heading = (
                8 <= len(line) <= 60
                and len(word_like_tokens) >= 2
                and alpha_count >= max(6, len(line) * 0.45)
            )

            if len(line) > 20 or re.search(r'[.!?]$', line) or is_short_heading:
                cleaned_lines.append(line)
            elif len(line) == 0:
                cleaned_lines.append('')

        # Step 8: Rejoin with proper spacing
        text = '\n'.join(cleaned_lines)

        # Step 9: Fix common OCR errors
        text = TextCleaner._fix_ocr_errors(text)
        text = TextCleaner._fix_common_extraction_artifacts(text)
        text = TextCleaner.reflow_extracted_line_wraps(text)

        # Step 10: Final cleanup - collapse multiple blank lines to max 2
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Step 11: Trim leading/trailing whitespace
        text = text.strip()

        return text

    @staticmethod
    def _fix_ocr_errors(text):
        """Fix common OCR misreadings"""
        replacements = {
            r'\bl\b': 'I',
            r'\bO\b': '0',
            r'\|': 'I',
            r'~': '-',
            r'\u2014': '--',
            r'\u2018': "'",
            r'\u2019': "'",
            r'\u201c': '"',
            r'\u201d': '"',
        }

        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text)

        return text

    @staticmethod
    def _fix_common_extraction_artifacts(text):
        """Fix narrow, high-confidence text extraction artifacts."""
        replacements = {
            r'\bLeter of Motivation\b': 'Letter of Motivation',
            r'\bLeter of Mo[tƟ]ivation\b': 'Letter of Motivation',
        }
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def reflow_extracted_line_wraps(text):
        """
        Join visual PDF/OCR line wraps back into editable paragraphs.

        PDFs expose positioned page lines, not real paragraph objects. This
        keeps blank-line boundaries, headings, and list/table rows while
        reflowing prose blocks so the frontend textarea can wrap naturally.
        """
        if not text:
            return ""

        def word_count(line):
            return len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", line or ''))

        def is_heading(line):
            stripped = line.strip()
            if not stripped:
                return False
            words = word_count(stripped)
            alpha_count = sum(1 for ch in stripped if ch.isalpha())
            return (
                1 <= words <= 8 and
                len(stripped) <= 72 and
                alpha_count >= max(4, len(stripped) * 0.35) and
                not re.search(r'[.!?;]$', stripped)
            )

        def is_list_or_table_line(line):
            stripped = line.strip()
            if not stripped:
                return False
            return bool(
                re.match(r'^[-*•▪○►◆◇■□▸▹‣⁃]\s+', stripped) or
                re.match(r'^\d+[\.)]\s+', stripped) or
                re.match(r'^[A-Za-z][\.)]\s+', stripped) or
                stripped.count('\t') >= 1 or
                re.search(r'\s{3,}', stripped)
            )

        def flush_block(block):
            block = [line.strip() for line in block if line.strip()]
            if not block:
                return []
            if len(block) == 1:
                return block

            list_like_count = sum(1 for line in block if is_list_or_table_line(line))
            if list_like_count >= max(2, len(block) // 2):
                return block

            output = []
            while len(block) > 1 and is_heading(block[0]) and word_count(block[1]) >= 7:
                output.append(block.pop(0))
                output.append('')

            if not block:
                return output

            total_words = sum(word_count(line) for line in block)
            has_wrapped_line = any(len(line) >= 50 for line in block)
            if total_words >= 18 or has_wrapped_line:
                joined = ' '.join(block)
                joined = re.sub(r'\s+([,.;:!?])', r'\1', joined)
                joined = re.sub(r'\(\s+', '(', joined)
                joined = re.sub(r'\s+\)', ')', joined)
                output.append(joined)
            else:
                output.extend(block)

            return output

        result = []
        current_block = []
        for line in text.splitlines():
            if line.strip():
                current_block.append(line)
                continue
            result.extend(flush_block(current_block))
            current_block = []
            if result and result[-1] != '':
                result.append('')

        result.extend(flush_block(current_block))
        reflowed = '\n'.join(result)
        return re.sub(r'\n{3,}', '\n\n', reflowed).strip()

    @staticmethod
    def remove_images_markers(text):
        """Remove image placeholder text (e.g., [Image], Figure 1, etc.)"""
        patterns = [
            r'\[Image:?.*?\]',
            r'\[Figure:?.*?\]',
            r'\[Photo:?.*?\]',
            r'Figure \d+:?.*?(?=\n|$)',
            r'Image \d+:?.*?(?=\n|$)',
            r'\[Graphic\]',
        ]

        for pattern in patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        return text

    @staticmethod
    def clean_textbook_text(text):
        """
        Clean textbook-specific artifacts from extracted text (PDF/DOCX).
        Designed for RAG pipeline — removes noise that hurts retrieval quality.

        Handles:
        - Page numbers (standalone, "Page X of Y", "- X -")
        - Repeating headers/footers
        - Broken line breaks (mid-sentence hard wraps)
        - Bullet and list normalization
        - Table of contents (dot leaders, page refs)
        - Orphaned figure/table captions
        - Excessive whitespace
        """
        if not text:
            return ""

        lines = text.split('\n')

        # --- Pass 1: Remove page numbers ---
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            # Standalone page numbers: "42", "- 42 -", "Page 42", "Page 42 of 100"
            if re.match(r'^-?\s*\d{1,4}\s*-?$', stripped):
                continue
            if re.match(r'^[Pp]age\s+\d{1,4}(\s+of\s+\d{1,4})?\.?$', stripped):
                continue
            # Page numbers at end of line (common in PDF extraction): "some text 42"
            # Only strip if line is short (likely a header/footer)
            if len(stripped) < 80 and re.match(r'^.+\s+\d{1,4}$', stripped):
                # Check if it looks like a header/footer (short, no sentence punctuation)
                if not re.search(r'[.!?;:]', stripped):
                    continue
            cleaned_lines.append(line)

        # --- Pass 2: Detect and remove repeating headers/footers ---
        # Lines that appear 3+ times are likely headers/footers
        if len(cleaned_lines) > 20:
            from collections import Counter
            line_counts = Counter(l.strip() for l in cleaned_lines if l.strip())
            repeat_lines = {l for l, count in line_counts.items() if count >= 3 and len(l) < 100}
            if repeat_lines:
                cleaned_lines = [l for l in cleaned_lines if l.strip() not in repeat_lines]

        # --- Pass 3: Remove table of contents entries ---
        toc_free_lines = []
        for line in cleaned_lines:
            stripped = line.strip()
            # TOC pattern: "Chapter 1 ......... 5" or "Introduction ... 12"
            if re.match(r'^.{3,60}\s*[.·]{3,}\s*\d{1,4}\s*$', stripped):
                continue
            # TOC pattern: "1.2 Section Name    45" (text followed by big gap then page number)
            if re.match(r'^[\d.]+\s+.{3,50}\s{4,}\d{1,4}\s*$', stripped):
                continue
            toc_free_lines.append(line)
        cleaned_lines = toc_free_lines

        # --- Pass 4: Remove orphaned figure/table captions ---
        caption_free_lines = []
        for line in cleaned_lines:
            stripped = line.strip()
            # "Figure 3.2", "Table 1", "Fig. 4", "TABLE 2.1" on their own line
            if re.match(r'^(Fig(ure)?|Table|Exhibit|Chart|Diagram|Illustration)\.?\s+[\d.]+\.?$', stripped, re.IGNORECASE):
                continue
            # "Source: ..." standalone attribution lines
            if re.match(r'^Source\s*:\s*.+$', stripped, re.IGNORECASE) and len(stripped) < 120:
                continue
            caption_free_lines.append(line)
        cleaned_lines = caption_free_lines

        text = '\n'.join(cleaned_lines)

        # --- Pass 5: Normalize bullets and lists ---
        # Various bullet characters → standard "- "
        text = re.sub(r'^[\s]*[•▪○►◆◇■□▸▹–—‣⁃]\s*', '- ', text, flags=re.MULTILINE)
        # Parenthesized numbers: "(1) text" → "1. text"
        text = re.sub(r'^\s*\((\d+)\)\s*', r'\1. ', text, flags=re.MULTILINE)
        # Lettered lists: "a)" or "a." at line start → "- "
        text = re.sub(r'^\s*[a-z]\)\s+', '- ', text, flags=re.MULTILINE)

        # --- Pass 6: Fix broken line breaks (join mid-sentence wraps) ---
        # A line ending without sentence-ending punctuation, followed by a line
        # starting with a lowercase letter, indicates a broken wrap
        text = re.sub(
            r'([a-zA-Z,;])\n([a-z])',
            r'\1 \2',
            text
        )

        # --- Pass 7: Collapse excessive whitespace ---
        # 3+ blank lines → 2
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Multiple spaces → single space (within lines)
        text = re.sub(r'[ \t]{2,}', ' ', text)
        # Trailing whitespace per line
        text = re.sub(r' +\n', '\n', text)

        return text.strip()

    @staticmethod
    def ensure_editable(text):
        """
        Ensure text is editable (no read-only artifacts)
        This is mainly for frontend display
        """
        text = text.replace('\u200b', '')  # Zero-width space
        text = text.replace('\ufeff', '')  # Zero-width no-break space
        text = text.replace('\u200c', '')  # Zero-width non-joiner
        text = text.replace('\u200d', '')  # Zero-width joiner

        return text
