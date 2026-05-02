import re
import unicodedata


class TextCleaner:
    """Clean extracted text from PDFs/DOCX/OCR"""

    @staticmethod
    def normalize_unicode_text(text):
        """Normalize PDF/OCR Unicode without silently dropping real letters."""
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

        # Step 1: Remove null bytes and control characters (except newlines/tabs)
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', text)

        # Step 2: Normalize Unicode while preserving real extracted letters.
        # PDFs often encode ligatures/private glyphs as non-ASCII text; dropping
        # them can turn "time" into "me" or "mentioned" into "menoned".
        text = TextCleaner.normalize_unicode_text(text)

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
