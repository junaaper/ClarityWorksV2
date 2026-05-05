import difflib
import os
import re
import time
from collections import Counter
from pathlib import Path

import nltk
import spacy
from models.datamuse_synonyms import DatamuseSynonymFinder
from models.llm_validator import LLMValidator
from models.synonym_lookup import SynonymLookup
from models.text_processor import TextProcessor
from utils.change_patches import apply_changes_by_span

from nltk.corpus import wordnet as wn
from wordfreq import zipf_frequency

# Try to import OpenAI (used for Fireworks AI), but don't fail if not available
try:
    from openai import OpenAI
    FIREWORKS_AVAILABLE = True
except ImportError:
    FIREWORKS_AVAILABLE = False
    print("Warning: openai package not installed. Advanced simplification will be limited.")

FIREWORKS_MODEL = "accounts/fireworks/models/llama-v3p3-70b-instruct"

nlp = spacy.load('en_core_web_sm')

# Minimum Zipf frequency improvement required for a synonym to be accepted.
# Candidate must be at least this many Zipf units more common than the original.
# Prevents borderline or semantically wrong replacements.
MIN_FREQ_IMPROVEMENT = 0.8

# Words that must NEVER be used as synonyms regardless of frequency.
# Includes vulgar terms, slang that would be inappropriate or semantically wrong.
BLOCKED_SYNONYMS = {
    # Vulgar / offensive
    'dick', 'dicks', 'cock', 'ass', 'arse', 'bastard', 'bitch', 'shit',
    'crap', 'damn', 'hell', 'prick', 'twat', 'wanker', 'bollocks',
    # Common wrong replacements seen in the wild
    'but', 'frame-up', 'frame-ups', 'hold', 'holds', 'lamb', 'lambs',
    'line', 'lines', 'stool', 'stools', 'tool',
    # Single-letter or very short that are meaningless in context
}

# Phrases that often signal an LLM has drifted into writing a concluding
# wrap-up instead of staying inside the source paragraph's scope.
SUMMARY_WRAPUP_PHRASES = (
    'through this experience',
    'through this process',
    'we learn',
    'we learned',
    'we find the value of',
    'importance of',
    'value of',
    'sense of',
    'essential for',
    'appreciation for',
    'develop an appreciation',
    'develop a sense of',
    'sense of accomplishment',
    'sense of satisfaction',
    'teaches us',
    'shows the importance',
    'demonstrates the importance',
    'overall,',
    'rewarding experience',
    'collective effort',
    'collective efforts',
    'brings our family together',
    'family together',
    'fulfillment',
    'dedication',
)

# Zipf frequency thresholds for grade estimation
# Higher zipf = more common word. Scale is roughly 0-7.
# 7 = "the", 6 = "is", 5 = "know", 4 = "allow", 3 = "magnificent", 2 = "trepidation"
GRADE_ZIPF_THRESHOLDS = {
    3: 5.5,   # Grade 3: only very common words (zipf >= 5.5)
    4: 5.2,
    5: 4.9,
    6: 4.6,
    7: 4.3,
    8: 4.0,
    9: 3.7,
    10: 3.4,
    11: 3.1,
    12: 2.8,
    13: 2.5,  # College: allows rare academic terminology
}

# Precise target metrics per grade — these are the two levers that drive the ML model.
# The ML model formula approximates: grade ≈ -21.16 + 14.33*(avg_syl) + 0.6*(avg_wps)
# Values are empirically calibrated: Grade 5 (syl=1.32, wps=12) and Grade 9 (syl=1.45, wps=19)
# have been validated to predict correctly. Others are interpolated.
#
#   target_syl  - target average syllables per word
#   target_wps  - target average words per sentence
#   min_wps     - minimum sentence length to avoid choppy text
#   max_wps     - maximum sentence length
GRADE_TARGET_METRICS = {
    3:  {'target_syl': 1.20, 'target_wps': 8,  'min_wps': 5,  'max_wps': 10},
    4:  {'target_syl': 1.26, 'target_wps': 10, 'min_wps': 7,  'max_wps': 13},
    5:  {'target_syl': 1.32, 'target_wps': 12, 'min_wps': 8,  'max_wps': 16},
    6:  {'target_syl': 1.35, 'target_wps': 14, 'min_wps': 10, 'max_wps': 18},
    7:  {'target_syl': 1.38, 'target_wps': 16, 'min_wps': 11, 'max_wps': 21},
    8:  {'target_syl': 1.41, 'target_wps': 17, 'min_wps': 12, 'max_wps': 22},
    9:  {'target_syl': 1.45, 'target_wps': 19, 'min_wps': 13, 'max_wps': 25},
    10: {'target_syl': 1.48, 'target_wps': 21, 'min_wps': 14, 'max_wps': 28},
    11: {'target_syl': 1.51, 'target_wps': 23, 'min_wps': 16, 'max_wps': 30},
    12: {'target_syl': 1.55, 'target_wps': 25, 'min_wps': 18, 'max_wps': 33},
    13: {'target_syl': 1.60, 'target_wps': 28, 'min_wps': 20, 'max_wps': 38},
}

AUTO_GREEDY_TOLERANCE = 0.5
AUTO_GREEDY_MAX_MEASUREMENTS = 40

GRADE_PROFILES = {
    3: (
        "Grade 3 reads like a story for 8-year-olds. "
        "Very short sentences (5-10 words). Only common 1-syllable words (cat, run, big, like). "
        "Simple subject-verb-object structure. No subordinate clauses. "
        "Concrete topics only — no abstract ideas. Connected with 'and', 'but', 'then'."
    ),
    4: (
        "Grade 4 reads like a chapter book for 9-year-olds. "
        "Short sentences (7-13 words). Mostly 1-syllable words with occasional 2-syllable words (happy, began, person). "
        "Simple sentences, sometimes joined with 'and' or 'but'. No subordinate clauses. "
        "Concrete descriptions with some basic cause-effect (because, so)."
    ),
    5: (
        "Grade 5 reads like a textbook for 10-year-olds. "
        "Medium-short sentences (8-16 words). Mix of 1 and 2-syllable words (become, children, important, different). "
        "Occasional compound sentences with 'and', 'but', 'or'. "
        "At most one simple connector per sentence. Factual, clear descriptions."
    ),
    6: (
        "Grade 6 reads like a middle-school textbook. "
        "Medium sentences (10-18 words). Common 2-syllable vocabulary (create, between, certain, measure, provide). "
        "Compound sentences are common. At most one subordinate clause per sentence (using 'which', 'that', 'because'). "
        "Clear paragraph structure with topic sentences."
    ),
    7: (
        "Grade 7 reads like a 7th-grade classroom text. "
        "Medium sentences (11-21 words). Frequent 2-syllable words with some academic terms (establish, develop, significant). "
        "AT MOST one subordinate clause per sentence — keep sentences clear and direct. "
        "Cause-effect and comparison structures. No complex clause nesting."
    ),
    8: (
        "Grade 8 reads like an 8th-grade academic text. "
        "Medium-long sentences (12-22 words). Academic vocabulary (demonstrate, generate, fundamental, environment). "
        "One subordinate clause per sentence is typical. Occasional use of 'although', 'however', 'furthermore'. "
        "Logical argument structure with evidence and reasoning."
    ),
    9: (
        "Grade 9 reads like a high-school freshman textbook. "
        "Longer sentences (13-25 words). Academic and semi-formal vocabulary (consequently, substantial, predominantly, acquisition). "
        "1-2 subordinate clauses per sentence. Transitions between ideas (moreover, nevertheless, consequently). "
        "Analytical writing with claims and supporting evidence."
    ),
    10: (
        "Grade 10 reads like a 10th-grade literature or science text. "
        "Long sentences (14-28 words). Formal academic vocabulary with domain terms (constitute, inherent, theoretical, methodology). "
        "1-2 clauses per sentence with varied connectors. "
        "Abstract concepts, nuanced arguments, and formal tone throughout."
    ),
    11: (
        "Grade 11 reads like an advanced high-school text — NOT college level. "
        "Long sentences (16-30 words). Sophisticated vocabulary (juxtaposition, paradigm, encompass, dichotomy). "
        "2-3 clauses per sentence maximum. Complex argument structure with qualifications and counter-arguments. "
        "Formal academic register but still accessible to a high-school student."
    ),
    12: (
        "Grade 12 reads like AP/IB-level academic writing — the ceiling of high-school prose. "
        "Long sentences (18-33 words). Advanced vocabulary (epistemological, multifaceted, synthesize, extrapolate). "
        "2-3 clauses per sentence. Layered arguments with hedging and nuance. "
        "Formal, authoritative tone. NOT graduate-level or journal prose."
    ),
    13: (
        "College level reads like a university textbook or academic journal. "
        "Very long sentences (20-38 words). Professional academic vocabulary with discipline-specific terminology. "
        "Multiple clauses per sentence with complex subordination. "
        "Dense, information-rich prose with citations-style reasoning and abstract theoretical discussion."
    ),
}

# Kept for backward-compat with upgrade complexification code
GRADE_TARGET_SYLLABLES = {g: m['target_syl'] for g, m in GRADE_TARGET_METRICS.items()}

# High-signal rule-based overrides for academic language that WordNet often
# misses or filters out. These are used before any LLM rescue path.
SUPPLEMENTAL_SIMPLIFICATIONS = {
    'abstract': 'general',
    'accurate': 'right',
    'additional': 'more',
    'analysis': 'study',
    'approach': 'way',
    'argument': 'claim',
    'basis': 'core',
    'belief': 'idea',
    'broader': 'wider',
    'capture': 'take in',
    'certain': 'some',
    'challenge': 'test',
    'claim': 'point',
    'claims': 'points',
    'complex': 'hard',
    'concept': 'idea',
    'confirm': 'check',
    'contested': 'debate',
    'contrary': 'opposite',
    'convert': 'change',
    'critical': 'careful',
    'debate': 'argument',
    'debates': 'arguments',
    'discipline': 'field',
    'diverse': 'many',
    'depends': 'needs',
    'evidence': 'proof',
    'extended': 'long',
    'findings': 'results',
    'grasp': 'knowledge',
    'habitat': 'home',
    'harmful': 'bad',
    'hypothesis': 'idea',
    'identify': 'find',
    'issue': 'problem',
    'issues': 'problems',
    'linked': 'joined',
    'major': 'big',
    'method': 'way',
    'methods': 'ways',
    'motion': 'movement',
    'movement': 'flow',
    'networks': 'systems',
    'observe': 'watch',
    'ongoing': 'current',
    'perspective': 'view',
    'pose': 'create',
    'process': 'way',
    'processes': 'ways',
    'produce': 'make',
    'profound': 'deep',
    'proposed': 'suggested',
    'prove': 'show',
    'purposeful': 'planned',
    'research': 'study',
    'review': 'check',
    'rigor': 'care',
    'scholars': 'experts',
    'scholarly': 'expert',
    'shift': 'change',
    'significant': 'big',
    'standard': 'rule',
    'structured': 'organized',
    'sustained': 'long',
    'theory': 'idea',
    'trait': 'feature',
    'transform': 'change',
    'truly': 'really',
    'upheaval': 'big change',
    'useful': 'helpful',
    'valid': 'true',
    'vital': 'key',
    'widely': 'often',
    'widespread': 'wide',
    'within': 'in',
}

SUPPLEMENTAL_COMPLEXIFICATIONS = {
    'after': ['following'],
    'ask': ['inquire'],
    'area': ['region'],
    'argument': ['debate'],
    'back': ['return'],
    'base': ['foundation'],
    'book': ['volume'],
    'careful': ['systematic', 'deliberate'],
    'change': ['transform', 'modify', 'alter'],
    'check': ['evaluate', 'assess', 'verify'],
    'claim': ['assertion', 'argument'],
    'end': ['conclude'],
    'expert': ['scholar'],
    'field': ['discipline'],
    'find': ['discover', 'identify', 'determine'],
    'general': ['abstract'],
    'grow': ['expand', 'develop'],
    'hard': ['complex', 'challenging'],
    'home': ['residence'],
    'house': ['residence', 'building'],
    'idea': ['concept', 'theory', 'hypothesis'],
    'key': ['vital', 'essential'],
    'make': ['produce', 'generate', 'construct'],
    'many': ['numerous', 'multiple'],
    'more': ['additional', 'further'],
    'move': ['shift', 'transition'],
    'people': ['individuals', 'citizens'],
    'place': ['position', 'situate'],
    'proof': ['evidence'],
    'read': ['examine', 'review'],
    'real': ['authentic', 'valid'],
    'right': ['accurate', 'valid'],
    'say': ['state', 'assert'],
    'see': ['observe', 'perceive'],
    'show': ['demonstrate', 'illustrate'],
    'some': ['certain'],
    'study': ['research', 'analysis'],
    'systems': ['networks'],
    'test': ['challenge', 'evaluate'],
    'think': ['consider', 'contemplate'],
    'town': ['community', 'settlement'],
    'understanding': ['knowledge'],
    'use': ['utilize', 'employ'],
    'walk': ['stroll'],
    'wide': ['widespread'],
}

LEADING_SPLIT_MARKERS = {
    'and', 'but', 'or', 'so', 'yet', 'that', 'which', 'who', 'whom', 'whose',
    'where', 'while', 'although', 'because', 'though', 'when'
}
LEADING_ADVERB_MARKERS = {
    'then', 'also', 'still', 'instead', 'rather', 'therefore', 'however', 'moreover',
    'furthermore', 'additionally'
}
MID_SENTENCE_SPLIT_MARKERS = {
    'and', 'but', 'so', 'yet', 'while'
}
BAD_FRAGMENT_ENDINGS = {
    'a', 'an', 'and', 'at', 'by', 'for', 'from', 'in', 'into', 'of', 'on',
    'or', 'rather', 'that', 'the', 'then', 'to', 'while', 'with',
    'also', 'however', 'instead', 'therefore', 'moreover', 'furthermore',
    'additionally', 'still', 'can', 'could', 'may', 'might', 'must',
    'shall', 'should', 'will', 'would'
}
ALLOWED_CARRY_REPAIR_MARKERS = {'and', 'but', 'so', 'yet'}
BAD_FRAGMENT_OPENING_PAIRS = {
    ('in', 'what'),
    ('in', 'which'),
    ('in', 'that'),
    ('of', 'which'),
    ('of', 'that'),
    ('by', 'which'),
    ('for', 'which'),
    ('to', 'which'),
    ('with', 'which'),
    ('from', 'which'),
}
FINITE_VERB_TAGS = {'VBD', 'VBP', 'VBZ', 'MD'}
DETERMINER_HINTS = {
    'a', 'an', 'the', 'this', 'that', 'these', 'those', 'my', 'your',
    'our', 'their', 'his', 'her', 'its'
}
PREPOSITION_HINTS = {
    'about', 'above', 'across', 'after', 'against', 'along', 'among', 'around',
    'at', 'before', 'behind', 'below', 'beneath', 'beside', 'between', 'beyond',
    'by', 'during', 'for', 'from', 'in', 'inside', 'into', 'near', 'of', 'off',
    'on', 'over', 'through', 'to', 'toward', 'under', 'until', 'up', 'with',
    'within', 'without'
}
AUXILIARY_HINTS = {
    'am', 'are', 'be', 'been', 'being', 'can', 'could', 'did', 'do', 'does',
    'had', 'has', 'have', 'is', 'may', 'might', 'must', 'shall', 'should',
    'was', 'were', 'will', 'would'
}
WORD_QUALITY_DELTA = 0.15
STRUCTURAL_REVIEW_SENTENCE_LIMIT = 2

REWRITE_RESCUE_GRADE_GAP = 1.25
LOCAL_REPAIR_GRADE_GAP = 1.0
BEAM_WIDTH = 3

DOWNGRADE_TARGET_BUCKET_POLICIES = {
    '3-5': {
        'label': 'down-3-5',
        'beam_width': BEAM_WIDTH,
        'lexical_rounds': 2,
        'lexical_max': 8,
        'split_rounds': 2,
        'split_changes': None,
        'combine_rounds': 0,
        'combine_changes': 0,
        'discourse_mode': 'downgrade_strong',
        'syllable_weight': 1.4,
        'wps_weight': 0.22,
        'paragraph_penalty': 0.8,
    },
    '6-8': {
        'label': 'down-6-8',
        'beam_width': BEAM_WIDTH,
        'lexical_rounds': 1,
        'lexical_max': 5,
        'split_rounds': 1,
        'split_changes': 2,
        'combine_rounds': 0,
        'combine_changes': 0,
        'discourse_mode': 'downgrade_light',
        'syllable_weight': 1.2,
        'wps_weight': 0.16,
        'paragraph_penalty': 0.55,
    },
    '9-10': {
        'label': 'down-9-10',
        'beam_width': BEAM_WIDTH,
        'lexical_rounds': 1,
        'lexical_max': 4,
        'split_rounds': 1,
        'split_changes': 1,
        'combine_rounds': 0,
        'combine_changes': 0,
        'discourse_mode': 'downgrade_light',
        'syllable_weight': 1.25,
        'wps_weight': 0.18,
        'paragraph_penalty': 0.45,
    },
    '11-13': {
        'label': 'down-11-13',
        'beam_width': BEAM_WIDTH,
        'lexical_rounds': 1,
        'lexical_max': 3,
        'split_rounds': 1,
        'split_changes': 1,
        'combine_rounds': 0,
        'combine_changes': 0,
        'discourse_mode': 'downgrade_light',
        'syllable_weight': 1.15,
        'wps_weight': 0.14,
        'paragraph_penalty': 0.35,
    },
}

UPGRADE_TARGET_BUCKET_POLICIES = {
    '3-5': {
        'label': 'up-3-5',
        'beam_width': BEAM_WIDTH,
        'lexical_rounds': 1,
        'lexical_max': 2,
        'split_rounds': 0,
        'split_changes': 0,
        'combine_rounds': 0,
        'combine_changes': 0,
        'discourse_mode': 'upgrade_light',
        'syllable_weight': 1.0,
        'wps_weight': 0.12,
        'paragraph_penalty': 0.5,
    },
    '6-8': {
        'label': 'up-6-8',
        'beam_width': BEAM_WIDTH,
        'lexical_rounds': 1,
        'lexical_max': 4,
        'split_rounds': 0,
        'split_changes': 0,
        'combine_rounds': 1,
        'combine_changes': 1,
        'discourse_mode': 'upgrade_light',
        'syllable_weight': 1.15,
        'wps_weight': 0.14,
        'paragraph_penalty': 0.45,
    },
    '9-10': {
        'label': 'up-9-10',
        'beam_width': BEAM_WIDTH,
        'lexical_rounds': 1,
        'lexical_max': 4,
        'split_rounds': 0,
        'split_changes': 0,
        'combine_rounds': 1,
        'combine_changes': 2,
        'discourse_mode': 'upgrade_light',
        'syllable_weight': 1.3,
        'wps_weight': 0.16,
        'paragraph_penalty': 0.45,
    },
    '11-13': {
        'label': 'up-11-13',
        'beam_width': BEAM_WIDTH,
        'lexical_rounds': 2,
        'lexical_max': 6,
        'split_rounds': 0,
        'split_changes': 0,
        'combine_rounds': 2,
        'combine_changes': 3,
        'discourse_mode': 'upgrade_strong',
        'syllable_weight': 1.45,
        'wps_weight': 0.2,
        'paragraph_penalty': 0.35,
    },
}

DISCOURSE_DOWNGRADE_MAP = {
    'additionally': 'also',
    'approximately': 'about',
    'consequently': 'so',
    'furthermore': 'also',
    'however': 'but',
    'moreover': 'also',
    'nevertheless': 'still',
    'nonetheless': 'still',
    'regarding': 'about',
    'therefore': 'so',
}

DISCOURSE_UPGRADE_MAP = {
    'about': 'regarding',
    'also': 'furthermore',
    'still': 'nevertheless',
    'then': 'subsequently',
}

DOMAIN_TERM_SUFFIXES = (
    'ology', 'onomy', 'graphy', 'metry', 'physis', 'tosis', 'genesis',
    'lysis', 'pathy', 'morphism'
)


class TextSimplifier:
    """Simplify text to target grade level using dynamic NLP-based word replacement."""

    def __init__(self, readability_model=None):
        self.synonym_lookup = SynonymLookup()
        self.text_processor = TextProcessor()
        self.datamuse_finder = DatamuseSynonymFinder()
        self.llm_validator = LLMValidator()
        self.readability_model = readability_model
        self._register_local_nltk_data_path()
        self.wordnet_available = self._check_wordnet_available()

        # Initialize Fireworks AI client if available
        self.llm_client = None
        if FIREWORKS_AVAILABLE and os.getenv('FIREWORKS_API_KEY'):
            self.llm_client = OpenAI(
                base_url="https://api.fireworks.ai/inference/v1",
                api_key=os.getenv('FIREWORKS_API_KEY'),
            )

        # Grade-specific constraints derived from GRADE_TARGET_METRICS
        self.grade_constraints = {
            g: {'max_words': m['max_wps'], 'max_syllables': 4}
            for g, m in GRADE_TARGET_METRICS.items()
        }

        # Cache for synonym lookups (word -> best simple synonym)
        self._synonym_cache = {}
        self._selection_context = {}
        self.rate_limited_llm = os.getenv('CLARITYWORKS_RATE_LIMITED_LLM', '1').lower() not in {'0', 'false', 'no'}
        self._llm_call_budget = None
        self._llm_calls_made = 0

    def _register_local_nltk_data_path(self):
        """Prefer repo-local NLTK assets so sandboxed runs can see them."""
        local_nltk_dir = Path(__file__).resolve().parents[1] / 'nltk_data'
        local_nltk_path = str(local_nltk_dir)
        if local_nltk_dir.exists() and local_nltk_path not in nltk.data.path:
            nltk.data.path.insert(0, local_nltk_path)

    def _check_wordnet_available(self):
        """WordNet is optional at runtime; missing corpora should not crash rewrites."""
        try:
            nltk.data.find('corpora/wordnet')
            return True
        except LookupError:
            try:
                nltk.data.find('corpora/wordnet.zip')
                return True
            except LookupError:
                print("Warning: NLTK WordNet corpus not found. Falling back to curated maps and non-WordNet rules.")
                return False

    def _llm_chat(self, messages, temperature=0, max_tokens=4000, max_retries=3):
        """Fireworks AI API call with automatic retry on rate-limit (429) errors."""
        if not self.llm_client:
            return None
        if self._llm_call_budget is not None and self._llm_calls_made >= self._llm_call_budget:
            print("[fireworks] LLM call budget exhausted for this request; using deterministic fallback.")
            return None
        if self.rate_limited_llm:
            max_retries = min(max_retries, 1)
        self._llm_calls_made += 1
        last_err = None
        for attempt in range(max_retries):
            try:
                response = self.llm_client.chat.completions.create(
                    model=FIREWORKS_MODEL,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response
            except Exception as e:
                last_err = e
                err_str = str(e)
                if '429' in err_str or 'rate_limit' in err_str.lower() or 'RATE_LIMIT' in err_str:
                    if attempt < max_retries - 1:
                        wait = self._parse_retry_after(err_str) or (10 * (attempt + 1))
                        wait = min(wait, 120)
                        print(f"[fireworks] Rate limited, waiting {wait:.0f}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait)
                        continue
                raise
        raise last_err

    @staticmethod
    def _parse_retry_after(err_str):
        """Extract retry-after seconds from API error message."""
        import re as _re
        m = _re.search(r'try again in (\d+)m([\d.]+)s', err_str)
        if m:
            return int(m.group(1)) * 60 + float(m.group(2))
        m = _re.search(r'try again in ([\d.]+)s', err_str)
        if m:
            return float(m.group(1))
        return None

    # ------------------------------------------------------------------ #
    #  Main entry point
    # ------------------------------------------------------------------ #

    def simplify_to_grade(self, text, target_grade, mode='auto', prefer_rule_based=False):
        """
        Rewrite pipeline:
          1. Build a candidate pool for the requested target grade.
          2. When LLM authoring is enabled, spend one rewrite call, mix that
             draft with deterministic rule candidates, and score them together.
          3. Finalize the winning text into anchored word/sentence patches so
             Auto and Interactive expose the same reviewable change set.
        """
        previous_budget = self._llm_call_budget
        previous_calls = self._llm_calls_made
        self._llm_call_budget = 1 if (self.rate_limited_llm and self.llm_client) else None
        self._llm_calls_made = 0

        try:
            selection = self._select_authoring_candidate(
                text=text,
                target_grade=target_grade,
                mode=mode,
                prefer_rule_based=prefer_rule_based,
            )
        finally:
            llm_calls_used = self._llm_calls_made
            self._llm_call_budget = previous_budget
            self._llm_calls_made = previous_calls

        current_text = selection['text']
        going_up = selection['going_up']
        critic_review = None

        self._selection_context = {
            'candidate_score': selection['score'],
            'selection_summary': selection['selection_summary'],
            'top_candidates': selection['top_candidates'],
        }

        current_text, changes, final_metrics = self._finalize_preview_candidate(
            original_text=text,
            candidate_text=current_text,
            target_grade=target_grade,
            going_up=going_up,
        )

        if mode == 'auto' and changes and final_metrics.get('target_distance', 0) > 0:
            greedy_changes, greedy_text, greedy_metrics = self._greedy_select_changes_for_target(
                original_text=text,
                changes=changes,
                target_grade=target_grade,
                going_up=going_up,
            )
            if greedy_metrics['target_distance'] <= final_metrics['target_distance']:
                changes = greedy_changes
                current_text = greedy_text
                final_metrics = greedy_metrics

        post_review_allowed = not self.rate_limited_llm
        validation = (
            self.llm_validator.validate_changes(text, current_text, changes)
            if post_review_allowed
            else self._local_validation_result(current_text, final_metrics)
        )
        if self.llm_validator.client and post_review_allowed:
            critic_review = self.llm_validator.critic_candidates(
                original_text=text,
                target_grade=target_grade,
                candidates=selection['top_candidates'],
            )
            current_text, changes, validation, final_metrics, final_review_summary = self._apply_llm_repair_pass(
                original_text=text,
                current_text=current_text,
                target_grade=target_grade,
                going_up=going_up,
                changes=changes,
                validation=validation,
                critic_review=critic_review,
            )
        else:
            final_review_summary = {
                'final_review_applied': False,
                'review_adjusted_change_count': 0,
                'llm_calls_used': llm_calls_used,
                'llm_review_skipped_for_rate_limit': self.rate_limited_llm and bool(self.llm_validator.client),
            }

        selection_summary = dict(selection['selection_summary'])
        candidate_score = selection['score']

        if mode == 'interactive' and not validation['valid'] and validation['issues']:
            print(f"[interactive] Validation issues (not auto-fixing): {validation['issues']}")

        selection_summary = {
            **selection_summary,
            'confidence_label': self._confidence_label(
                candidate_score,
                final_metrics['invalid_sentence_count'],
                final_metrics['semantic_similarity_score'],
                final_metrics['target_distance'],
            ),
            'invalid_sentence_count': final_metrics['invalid_sentence_count'],
            'semantic_similarity_score': final_metrics['semantic_similarity_score'],
            'llm_calls_used': llm_calls_used,
            **final_review_summary,
        }
        if critic_review:
            selection_summary['critic_review'] = critic_review
        self._selection_context['selection_summary'] = selection_summary

        current_text = re.sub(r'\n +', '\n', current_text).strip()

        display_items = self._build_display_changes(text, current_text, target_grade, going_up)
        if display_items:
            self._enrich_changes_with_display_items(changes, display_items)

        return {
            'simplified_text': current_text,
            'changes': changes,
            'original_text': text,
            'validation': validation,
            'preview_metrics': final_metrics,
            'target_distance': final_metrics['target_distance'],
            'selection_summary': selection_summary,
        }

    def _local_validation_result(self, current_text, final_metrics):
        issues = []
        if final_metrics.get('invalid_sentence_count', 0):
            issues.append('Local sentence-structure check flagged a possible incomplete or awkward sentence.')
        if final_metrics.get('semantic_similarity_score', 1.0) < 0.82:
            issues.append('Local overlap check suggests possible meaning drift.')

        return {
            'valid': not issues,
            'issues': issues,
            'suggestions': [],
            'skipped_llm_validation': True,
        }

    def _finalize_preview_candidate(
        self,
        original_text,
        candidate_text,
        target_grade,
        going_up,
        prefer_sentence_level=False,
    ):
        desired_candidate_text = candidate_text

        def exact_fallback():
            fallback_change = self._build_exact_rebuild_change(
                original_text,
                desired_candidate_text,
                target_grade,
                going_up,
            )
            if not fallback_change:
                return [], desired_candidate_text
            fallback_change['id'] = 0
            fallback_changes = self._assign_dependency_groups([fallback_change])
            fallback_rebuilt = apply_changes_by_span(
                original_text,
                fallback_changes,
                [change['id'] for change in fallback_changes],
            )
            return fallback_changes, fallback_rebuilt

        changes = self._diff_changes(
            original_text,
            desired_candidate_text,
            target_grade,
            going_up,
            prefer_sentence_level=prefer_sentence_level,
        )
        changes = self._assign_dependency_groups(changes)
        if changes:
            rebuilt_candidate_text = apply_changes_by_span(
                original_text,
                changes,
                [change['id'] for change in changes],
            )

            if rebuilt_candidate_text != desired_candidate_text and not prefer_sentence_level:
                changes = self._diff_changes(
                    original_text,
                    desired_candidate_text,
                    target_grade,
                    going_up,
                    prefer_sentence_level=True,
                )
                changes = self._assign_dependency_groups(changes)
                if changes:
                    rebuilt_candidate_text = apply_changes_by_span(
                        original_text,
                        changes,
                        [change['id'] for change in changes],
                    )
                else:
                    rebuilt_candidate_text = original_text

            if rebuilt_candidate_text != desired_candidate_text:
                if rebuilt_candidate_text.split() == desired_candidate_text.split():
                    pass
                else:
                    # Per-sentence fallback: pair each original sentence with the
                    # closest rewritten sentence instead of collapsing to one patch.
                    fuzzy = self._fuzzy_sentence_diff(
                        original_text, desired_candidate_text, target_grade, going_up,
                    )
                    if fuzzy and len(fuzzy) >= 2:
                        fuzzy = self._assign_dependency_groups(fuzzy)
                        fuzzy_rebuilt = apply_changes_by_span(
                            original_text,
                            fuzzy,
                            [c['id'] for c in fuzzy],
                        )
                        if fuzzy_rebuilt.split() == desired_candidate_text.split():
                            changes = fuzzy
                            rebuilt_candidate_text = fuzzy_rebuilt
                        else:
                            changes, rebuilt_candidate_text = exact_fallback()
                    else:
                        changes, rebuilt_candidate_text = exact_fallback()

            candidate_text = rebuilt_candidate_text
        else:
            changes, candidate_text = exact_fallback()

        final_metrics = self._measure_preview_metrics(candidate_text)
        final_metrics['semantic_similarity_score'] = round(
            self._semantic_similarity_score(original_text, candidate_text),
            2,
        )
        final_metrics['target_distance'] = round(
            self._distance_to_target_band(final_metrics['raw_score'], target_grade),
            2,
        )
        return candidate_text, changes, final_metrics

    def _build_exact_rebuild_change(self, original_text, desired_candidate_text, target_grade, going_up):
        """
        Last-resort review patch for cases where granular anchors cannot
        reconstruct the selected candidate exactly. The selected text has
        already been scored, so finalization must not silently deliver a
        different grade because a smaller diff dropped a split sentence.
        """
        if original_text == desired_candidate_text:
            return None

        fallback_change = self._build_patch_change(
            original_text,
            desired_candidate_text,
            0,
            len(original_text),
            0,
            target_grade,
            going_up,
            allow_fallback=True,
        )
        if fallback_change:
            validation_flags = list(fallback_change.get('validation_flags') or [])
            if 'exact_preview_rebuild' not in validation_flags:
                validation_flags.append('exact_preview_rebuild')
            fallback_change['validation_flags'] = validation_flags
            return fallback_change

        original_display = original_text.strip() or original_text
        replacement_display = desired_candidate_text.strip() or desired_candidate_text
        original_stats = self._fragment_stats(original_display)
        replacement_stats = self._fragment_stats(replacement_display)
        candidate_score = self._selection_context.get('candidate_score', 0.0)
        change_type = 'phrase_rewrite'
        explanation_items = self._extract_explanation_items(
            original_display,
            replacement_display,
            going_up,
        )
        clauses_before = self._approx_clause_count(original_display)
        clauses_after = self._approx_clause_count(replacement_display)
        examples = "; ".join(item.get('text', '') for item in explanation_items[:3] if item.get('text'))
        if examples:
            reason = (
                f"Rebuilt this broad paragraph rewrite exactly while preserving word-level evidence: "
                f"{examples} Clause complexity changed {clauses_before} -> {clauses_after} for Grade {target_grade}."
            )
        else:
            reason = (
                f"Rebuilt this broad paragraph rewrite exactly so the delivered text matches the selected "
                f"Grade {target_grade} candidate (avg syllables {original_stats['avg_syllables']:.2f} -> "
                f"{replacement_stats['avg_syllables']:.2f}, clauses {clauses_before} -> {clauses_after})."
            )

        return {
            'type': change_type,
            'original': original_display,
            'simplified': replacement_display,
            'original_text': original_text,
            'replacement_text': desired_candidate_text,
            'position': 0,
            'start': 0,
            'end': len(original_text),
            'preview_start': 0,
            'preview_end': len(desired_candidate_text),
            'review_scope': 'paragraph',
            'direction': 'up' if going_up else 'down',
            'quality_score': 0.35,
            'quality_flags': ['coarse_review', 'forced_exact_rebuild'],
            'rule_id': 'selection.exact_preview_rebuild',
            'reason_code': 'reshape_text_for_target',
            'evidence': {
                'target_grade': target_grade,
                'direction': 'up' if going_up else 'down',
                'review_scope': 'paragraph',
                'word_count_before': original_stats['word_count'],
                'word_count_after': replacement_stats['word_count'],
                'sentence_count_before': original_stats['sentence_count'],
                'sentence_count_after': replacement_stats['sentence_count'],
                'boundary_count_before': len(re.findall(r'[.!?]+', original_display or '')),
                'boundary_count_after': len(re.findall(r'[.!?]+', replacement_display or '')),
                'clause_count_before': clauses_before,
                'clause_count_after': clauses_after,
                'avg_syllables_before': round(original_stats['avg_syllables'], 2),
                'avg_syllables_after': round(replacement_stats['avg_syllables'], 2),
                'candidate_score': candidate_score,
                'explanation_items': explanation_items,
            },
            'candidate_score': candidate_score,
            'validation_flags': ['exact_preview_rebuild'],
            'explanation_items': explanation_items,
            'reason': reason,
        }

    def _iterative_rule_rewrite(self, text, target_grade):
        """
        Preserve the old pass-based rule engine as one deterministic candidate.
        This remains useful when a single linear strategy outperforms beam
        combinations for a specific source/target pair.
        """
        current_text = text
        target_metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        initial_grade, _, _ = self._measure_text_metrics(text)
        best_text = text
        best_grade = initial_grade
        best_score = self._alignment_score(initial_grade, target_grade)
        pass_budget = 5 + min(3, int(abs(float(target_grade) - float(initial_grade)) // 2))

        for pass_index in range(pass_budget):
            estimated_grade, current_syl, current_wps = self._measure_text_metrics(current_text)
            direction = self._get_target_direction(estimated_grade, target_grade)
            going_up = direction > 0
            near_target = self._distance_to_target_band(estimated_grade, target_grade) <= 0.75

            print(f"[rewrite] pass={pass_index + 1} estimated={estimated_grade:.1f} "
                  f"(syl={current_syl:.2f}, wps={current_wps:.1f}) "
                  f"-> target={target_grade} (syl={target_metrics['target_syl']:.2f}, "
                  f"wps={target_metrics['target_wps']}) going_up={going_up}")

            if direction == 0:
                break

            previous_text = current_text

            if going_up:
                if near_target:
                    if current_wps < target_metrics['target_wps'] - 0.5:
                        structure_base_text = current_text
                        current_text, combine_changes = self._combine_short_sentences(
                            current_text,
                            target_grade,
                            max_combinations=1
                        )
                        current_text, _ = self._accept_structural_rewrite(
                            structure_base_text,
                            current_text,
                            combine_changes
                        )
                    else:
                        current_text, _ = self._complexify_text(
                            current_text,
                            target_grade,
                            max_changes=2
                        )
                else:
                    current_text, _ = self._complexify_text(current_text, target_grade)
                    structure_base_text = current_text
                    current_text, combine_changes = self._combine_short_sentences(current_text, target_grade)
                    current_text, _ = self._accept_structural_rewrite(
                        structure_base_text,
                        current_text,
                        combine_changes
                    )
            else:
                if near_target:
                    if current_wps > target_metrics['target_wps'] + 0.5:
                        structure_base_text = current_text
                        current_text, split_changes = self._split_long_sentences(
                            current_text,
                            target_grade,
                            max_sentence_changes=1
                        )
                        current_text, _ = self._accept_structural_rewrite(
                            structure_base_text,
                            current_text,
                            split_changes
                        )
                    else:
                        current_text, _ = self._replace_difficult_words(
                            current_text,
                            target_grade,
                            max_changes=3
                        )
                else:
                    current_text, _ = self._replace_difficult_words(current_text, target_grade)
                    structure_base_text = current_text
                    current_text, split_changes = self._split_long_sentences(current_text, target_grade)
                    current_text, _ = self._accept_structural_rewrite(
                        structure_base_text,
                        current_text,
                        split_changes
                    )

            candidate_grade, _, _ = self._measure_text_metrics(current_text)
            candidate_score = self._alignment_score(candidate_grade, target_grade)
            if candidate_score < best_score:
                best_text = current_text
                best_grade = candidate_grade
                best_score = candidate_score

            if current_text == previous_text:
                break

        if best_score <= self._alignment_score(self._measure_text_metrics(current_text)[0], target_grade) + 1e-9:
            current_text = best_text

        return {
            'text': current_text,
            'rule_history': ['selection.legacy_iterative'],
            'stage_notes': ['legacy_iterative'],
        }

    def _select_authoring_candidate(self, text, target_grade, mode, prefer_rule_based=False):
        source_grade, _, _ = self._measure_text_metrics(text)
        direction = self._get_target_direction(source_grade, target_grade)
        going_up = direction > 0
        policy = self._get_target_policy(target_grade, going_up, source_grade=source_grade)

        rule_selection = self._select_rewrite_candidate(text, target_grade, mode)
        if prefer_rule_based or not self.llm_client or direction == 0:
            summary = {
                **dict(rule_selection['selection_summary']),
                'generation_mode': 'rule_primary',
                'candidate_pool': {
                    'rule': len(rule_selection['top_candidates']),
                    'llm': 0,
                },
            }
            return {
                **rule_selection,
                'selection_summary': summary,
            }

        rule_candidates = []
        for candidate in rule_selection['top_candidates']:
            rule_candidates.append({
                'text': candidate['text'],
                'rule_history': candidate.get('selection_path', ['selection.rule_candidate']),
                'stage_notes': candidate.get('selection_path', ['rule']),
            })

        llm_candidates = self._generate_llm_candidates(
            original_text=text,
            target_grade=target_grade,
            source_grade=source_grade,
            going_up=going_up,
            mode=mode,
            policy=policy,
            rule_selection=rule_selection,
        )
        if not llm_candidates:
            summary = {
                **dict(rule_selection['selection_summary']),
                'generation_mode': 'rule_primary_fallback',
                'candidate_pool': {
                    'rule': len(rule_candidates),
                    'llm': 0,
                },
            }
            return {
                **rule_selection,
                'selection_summary': summary,
            }

        ranked = self._rank_candidates(
            original_text=text,
            candidates=rule_candidates + llm_candidates,
            target_grade=target_grade,
            mode=mode,
            source_grade=source_grade,
            policy=policy,
        )
        selected = self._select_preferred_candidate(ranked, target_grade=target_grade)
        summary = self._build_selection_summary(
            policy=policy,
            source_grade=source_grade,
            target_grade=target_grade,
            selected_candidate=selected,
            top_candidates=ranked[:policy['beam_width']],
        )
        summary.update({
            'generation_mode': 'llm_augmented_single_pass' if self.rate_limited_llm else 'llm_augmented',
            'candidate_pool': {
                'rule': len(rule_candidates),
                'llm': len(llm_candidates),
            },
        })

        return {
            'text': selected['text'],
            'score': selected['candidate_score'],
            'going_up': going_up,
            'selection_summary': summary,
            'top_candidates': summary['top_candidates'],
        }

    def _generate_llm_candidates(
        self,
        original_text,
        target_grade,
        source_grade,
        going_up,
        mode,
        policy,
        rule_selection,
    ):
        if not self.llm_client:
            return []

        generated = []

        # Single LLM draft seeded from the best rule-based candidate. Free-tier
        # Fireworks runs cannot afford staged passes; the rule-based beam search
        # provides the competitive baselines around this one draft.
        rule_seed_text = rule_selection.get('text')
        seed = rule_seed_text if (rule_seed_text and rule_seed_text != original_text) else original_text
        seed_label = 'llm.rule_seeded' if seed != original_text else 'llm.direct_balanced'

        llm_text, _ = self._llm_full_rewrite(
            seed,
            target_grade,
            going_up=going_up,
            rewrite_style='balanced',
            reference_text=original_text,
            plan_label=seed_label,
            include_diff=False,
        )
        if llm_text and llm_text.strip():
            generated.append({
                'text': llm_text,
                'rule_history': [seed_label],
                'stage_notes': [seed_label],
            })

        return generated

    @staticmethod
    def _candidate_has_summary_wrapup(candidate):
        flags = candidate.get('validation_flags', []) or []
        return any(flag.startswith('summary_wrapup:') for flag in flags)

    @classmethod
    def _candidate_has_paragraph_scope_drift(cls, candidate):
        flags = candidate.get('validation_flags', []) or []
        return (
            cls._candidate_has_summary_wrapup(candidate) or
            'final_paragraph_expanded' in flags or
            'final_paragraph_sentence_growth' in flags or
            'paragraph_count_changed' in flags
        )

    @staticmethod
    def _select_preferred_candidate(ranked_candidates, target_grade=None):
        if not ranked_candidates:
            return None

        best_overall = ranked_candidates[0]
        if target_grade is not None and target_grade >= 11:
            clean_valid_directional = [
                candidate for candidate in ranked_candidates
                if (
                    candidate.get('invalid_sentence_delta', candidate.get('invalid_sentence_count', 0)) == 0 and
                    candidate.get('direction_hit') and
                    not TextSimplifier._candidate_has_paragraph_scope_drift(candidate)
                )
            ]
            exact_valid = [
                candidate for candidate in ranked_candidates
                if (
                    candidate.get('invalid_sentence_delta', candidate.get('invalid_sentence_count', 0)) == 0 and
                    candidate.get('direction_hit') and
                    candidate.get('target_distance', 999) == 0
                )
            ]
            clean_exact_valid = [
                candidate for candidate in exact_valid
                if not TextSimplifier._candidate_has_paragraph_scope_drift(candidate)
            ]
            if clean_exact_valid:
                return min(
                    clean_exact_valid,
                    key=lambda candidate: (
                        candidate['candidate_score'],
                        -candidate['semantic_similarity_score'],
                        candidate['paragraph_rewrite_count'],
                    ),
                )
            if exact_valid:
                best_exact = min(
                    exact_valid,
                    key=lambda candidate: (
                        candidate['candidate_score'],
                        -candidate['semantic_similarity_score'],
                        candidate['paragraph_rewrite_count'],
                    ),
                )
                if clean_valid_directional:
                    best_clean = min(
                        clean_valid_directional,
                        key=lambda candidate: (
                            candidate['target_distance'],
                            candidate['candidate_score'],
                            -candidate['semantic_similarity_score'],
                            candidate['paragraph_rewrite_count'],
                        ),
                    )
                    if (
                        best_clean['target_distance'] <= best_exact['target_distance'] + 0.35 or
                        best_clean['candidate_score'] <= best_exact['candidate_score'] + 2.0
                    ):
                        return best_clean
                return best_exact

        valid_directional = [
            candidate for candidate in ranked_candidates
            if (
                candidate.get('invalid_sentence_delta', candidate.get('invalid_sentence_count', 0)) == 0 and
                candidate.get('direction_hit')
            )
        ]
        valid_any = [
            candidate for candidate in ranked_candidates
            if candidate.get('invalid_sentence_delta', candidate.get('invalid_sentence_count', 0)) == 0
        ]

        for pool in (valid_directional, valid_any):
            if not pool:
                continue
            if target_grade is not None and target_grade >= 11:
                clean_pool = [
                    candidate for candidate in pool
                    if not TextSimplifier._candidate_has_paragraph_scope_drift(candidate)
                ]
                if clean_pool:
                    pool = clean_pool
                return min(
                    pool,
                    key=lambda candidate: (
                        candidate['target_distance'],
                        candidate['candidate_score'],
                        -candidate['semantic_similarity_score'],
                        candidate['paragraph_rewrite_count'],
                    ),
                )
            return min(
                pool,
                key=lambda candidate: (
                    candidate['target_distance'],
                    candidate['candidate_score'],
                    -candidate['semantic_similarity_score'],
                    candidate['paragraph_rewrite_count'],
                ),
            )

        return best_overall

    def _select_rewrite_candidate(self, text, target_grade, mode):
        source_grade, _, _ = self._measure_text_metrics(text)
        direction = self._get_target_direction(source_grade, target_grade)
        going_up = direction > 0
        policy = self._get_target_policy(target_grade, going_up, source_grade=source_grade)

        if direction == 0:
            base_metrics = self._score_candidate(
                original_text=text,
                candidate_text=text,
                target_grade=target_grade,
                mode=mode,
                source_grade=source_grade,
                policy=policy,
            )
            summary = self._build_selection_summary(
                policy=policy,
                source_grade=source_grade,
                target_grade=target_grade,
                selected_candidate={
                    'text': text,
                    'rule_history': ['selection.identity'],
                    **base_metrics,
                },
                top_candidates=[{
                    'text': text,
                    'rule_history': ['selection.identity'],
                    **base_metrics,
                }],
            )
            return {
                'text': text,
                'score': base_metrics['candidate_score'],
                'going_up': going_up,
                'selection_summary': summary,
                'top_candidates': summary['top_candidates'],
            }

        beam = [{
            'text': text,
            'rule_history': ['selection.identity'],
            'stage_notes': ['original'],
        }]

        stage_order = ['lexical', 'syntactic', 'discourse']
        for stage in stage_order:
            stage_candidates = []
            for candidate in beam:
                stage_candidates.extend(
                    self._generate_stage_candidates(
                        candidate=candidate,
                        stage=stage,
                        target_grade=target_grade,
                        going_up=going_up,
                        policy=policy,
                    )
                )
            beam = self._rank_candidates(
                original_text=text,
                candidates=stage_candidates,
                target_grade=target_grade,
                mode=mode,
                source_grade=source_grade,
                policy=policy,
            )

        beam.append(self._iterative_rule_rewrite(text, target_grade))
        ranked = self._rank_candidates(
            original_text=text,
            candidates=beam,
            target_grade=target_grade,
            mode=mode,
            source_grade=source_grade,
            policy=policy,
        )
        selected = ranked[0]
        summary = self._build_selection_summary(
            policy=policy,
            source_grade=source_grade,
            target_grade=target_grade,
            selected_candidate=selected,
            top_candidates=ranked[:policy['beam_width']],
        )

        return {
            'text': selected['text'],
            'score': selected['candidate_score'],
            'going_up': going_up,
            'selection_summary': summary,
            'top_candidates': summary['top_candidates'],
        }

    def _get_target_policy(self, target_grade, going_up, source_grade=None):
        policy_map = UPGRADE_TARGET_BUCKET_POLICIES if going_up else DOWNGRADE_TARGET_BUCKET_POLICIES
        if target_grade <= 5:
            policy = policy_map['3-5']
        elif target_grade <= 8:
            policy = policy_map['6-8']
        elif target_grade <= 10:
            policy = policy_map['9-10']
        else:
            policy = policy_map['11-13']

        policy = dict(policy)
        if source_grade is None:
            return policy

        gap = abs(float(target_grade) - float(source_grade))
        if gap < 3.5:
            return policy

        policy['beam_width'] = max(policy['beam_width'], BEAM_WIDTH + 1)
        policy['lexical_rounds'] += 1
        policy['lexical_max'] += 3

        if going_up:
            policy['combine_rounds'] += 1
            if policy['combine_changes'] is not None:
                policy['combine_changes'] += 2
        else:
            policy['split_rounds'] += 1
            if policy['split_changes'] is not None:
                policy['split_changes'] += 2

        if gap >= 6.5:
            policy['beam_width'] = max(policy['beam_width'], BEAM_WIDTH + 2)
            policy['lexical_rounds'] += 1
            policy['lexical_max'] += 3
            if going_up:
                policy['combine_rounds'] += 1
                if policy['combine_changes'] is not None:
                    policy['combine_changes'] += 2
            else:
                policy['split_rounds'] += 1
                if policy['split_changes'] is not None:
                    policy['split_changes'] += 2

        return policy

    def _generate_stage_candidates(self, candidate, stage, target_grade, going_up, policy):
        variants = [{
            'text': candidate['text'],
            'rule_history': candidate.get('rule_history', []) + [f'{stage}.identity'],
            'stage_notes': candidate.get('stage_notes', []) + [f'{stage}:identity'],
        }]

        if stage == 'lexical':
            for intensity in ('balanced', 'strong'):
                rewritten = self._apply_lexical_stage(
                    candidate['text'],
                    target_grade,
                    going_up,
                    policy,
                    intensity=intensity,
                )
                if rewritten != candidate['text']:
                    variants.append({
                        'text': rewritten,
                        'rule_history': candidate.get('rule_history', []) + [f'lexical.{intensity}'],
                        'stage_notes': candidate.get('stage_notes', []) + [f'lexical:{intensity}'],
                    })
        elif stage == 'syntactic':
            for intensity in ('balanced', 'strong'):
                rewritten = self._apply_syntactic_stage(
                    candidate['text'],
                    target_grade,
                    going_up,
                    policy,
                    intensity=intensity,
                )
                if rewritten != candidate['text']:
                    variants.append({
                        'text': rewritten,
                        'rule_history': candidate.get('rule_history', []) + [f'syntactic.{intensity}'],
                        'stage_notes': candidate.get('stage_notes', []) + [f'syntactic:{intensity}'],
                    })
        elif stage == 'discourse':
            for intensity in ('balanced', 'strong'):
                rewritten = self._apply_discourse_stage(
                    candidate['text'],
                    target_grade,
                    going_up,
                    policy,
                    intensity=intensity,
                )
                if rewritten != candidate['text']:
                    variants.append({
                        'text': rewritten,
                        'rule_history': candidate.get('rule_history', []) + [f'discourse.{intensity}'],
                        'stage_notes': candidate.get('stage_notes', []) + [f'discourse:{intensity}'],
                    })

        return variants

    def _apply_lexical_stage(self, text, target_grade, going_up, policy, intensity='balanced'):
        rounds = policy['lexical_rounds'] + (1 if intensity == 'strong' else 0)
        max_changes = policy['lexical_max'] + (2 if intensity == 'strong' else 0)
        current_text = text

        for round_index in range(rounds):
            per_round_max = max(2, max_changes - round_index)
            if going_up:
                next_text, _ = self._complexify_text(current_text, target_grade, max_changes=per_round_max)
            else:
                next_text, _ = self._replace_difficult_words(current_text, target_grade, max_changes=per_round_max)

            if next_text == current_text:
                break
            current_text = next_text

        return current_text

    def _apply_syntactic_stage(self, text, target_grade, going_up, policy, intensity='balanced'):
        current_text = text
        base_rounds = policy['combine_rounds'] if going_up else policy['split_rounds']
        extra_rounds = 0
        if intensity == 'strong':
            # Mild downgrades like Grade 12 -> 10 need an in-between option:
            # more structural edits than "balanced", but not an entire extra
            # simplification round that drops the text a full grade too far.
            if going_up or target_grade <= 8:
                extra_rounds = 1
        rounds = base_rounds + extra_rounds
        if rounds <= 0:
            return text

        for _ in range(rounds):
            structure_base_text = current_text
            if going_up:
                max_combinations = policy['combine_changes'] or None
                if intensity == 'strong' and max_combinations is not None:
                    max_combinations += 1
                next_text, structural_changes = self._combine_short_sentences(
                    current_text,
                    target_grade,
                    max_combinations=max_combinations,
                )
            else:
                max_sentence_changes = policy['split_changes']
                if intensity == 'strong' and max_sentence_changes is not None:
                    max_sentence_changes += 1
                next_text, structural_changes = self._split_long_sentences(
                    current_text,
                    target_grade,
                    max_sentence_changes=max_sentence_changes,
                )

            next_text, _ = self._accept_structural_rewrite(
                structure_base_text,
                next_text,
                structural_changes,
            )
            if next_text == current_text:
                break
            current_text = next_text

        return current_text

    def _apply_discourse_stage(self, text, target_grade, going_up, policy, intensity='balanced'):
        current_text = self._rewrite_discourse_markers(text, going_up, intensity=intensity)
        if current_text != text:
            return current_text

        if not going_up and target_grade <= 5 and intensity == 'strong':
            softened = re.sub(r'\s*;\s*', '. ', text)
            softened = re.sub(r'\s*:\s*', '. ', softened)
            if softened != text:
                return softened

        return text

    def _rewrite_discourse_markers(self, text, going_up, intensity='balanced'):
        mapping = DISCOURSE_UPGRADE_MAP if going_up else DISCOURSE_DOWNGRADE_MAP
        if not text.strip():
            return text

        current_text = text
        replacements = 0
        max_replacements = 2 if intensity == 'balanced' else 4

        doc = nlp(text)
        offset = 0
        for token in doc:
            if replacements >= max_replacements:
                break

            lookup = token.text.lower()
            replacement = mapping.get(lookup)
            if not replacement:
                continue

            if token.pos_ not in ('ADV', 'CCONJ', 'SCONJ'):
                continue

            start = token.idx + offset
            end = start + len(token.text)
            rendered = replacement.capitalize() if token.text[:1].isupper() else replacement
            current_text = current_text[:start] + rendered + current_text[end:]
            offset += len(rendered) - len(token.text)
            replacements += 1

        return current_text

    def _rank_candidates(self, original_text, candidates, target_grade, mode, source_grade, policy):
        ranked = {}
        for candidate in candidates:
            normalized_key = re.sub(r'\s+', ' ', candidate['text']).strip().lower()
            metrics = self._score_candidate(
                original_text=original_text,
                candidate_text=candidate['text'],
                target_grade=target_grade,
                mode=mode,
                source_grade=source_grade,
                policy=policy,
            )
            enriched = {
                **candidate,
                **metrics,
            }
            existing = ranked.get(normalized_key)
            if existing is None or enriched['candidate_score'] < existing['candidate_score']:
                ranked[normalized_key] = enriched

        ordered = sorted(
            ranked.values(),
            key=lambda candidate: (
                candidate.get('invalid_sentence_delta', candidate['invalid_sentence_count']) > 0,
                candidate.get('invalid_sentence_delta', candidate['invalid_sentence_count']),
                candidate['invalid_sentence_count'],
                candidate['candidate_score'],
                candidate['target_distance'],
                -candidate['semantic_similarity_score'],
                len(candidate.get('rule_history', [])),
            )
        )
        return ordered[:policy['beam_width']]

    def _score_candidate(self, original_text, candidate_text, target_grade, mode, source_grade, policy):
        candidate_grade, avg_syl, avg_wps = self._measure_text_metrics(candidate_text)
        _, source_avg_syl, source_avg_wps = self._measure_text_metrics(original_text)
        target_metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        target_distance = self._distance_to_target_band(candidate_grade, target_grade)
        source_distance = self._distance_to_target_band(source_grade, target_grade)
        invalid_sentences = self._collect_invalid_sentences(candidate_text)
        baseline_invalid_count = len(self._collect_invalid_sentences(original_text))
        invalid_sentence_delta = max(0, len(invalid_sentences) - baseline_invalid_count)
        semantic_similarity = self._semantic_similarity_score(original_text, candidate_text)
        lexical_flags = self._lexical_sanity_flags(original_text, candidate_text)
        directional_flags = self._directional_candidate_flags(
            source_grade=source_grade,
            target_grade=target_grade,
            source_avg_syl=source_avg_syl,
            source_avg_wps=source_avg_wps,
            candidate_avg_syl=avg_syl,
            candidate_avg_wps=avg_wps,
            semantic_similarity=semantic_similarity,
        )
        paragraph_rewrites = self._count_heavy_paragraph_rewrites(original_text, candidate_text)
        summary_wrapup_flags = []
        paragraph_scope_flags = []
        final_paragraph_scope_penalty = 0.0
        if target_grade >= 11:
            summary_wrapup_flags = self._summary_wrapup_flags(original_text, candidate_text)
            final_paragraph_scope_penalty, paragraph_scope_flags = self._final_paragraph_scope_penalty(
                original_text,
                candidate_text,
            )
        moving_up = target_grade > source_grade
        direction_hit = (
            (moving_up and candidate_grade >= source_grade - 0.05) or
            ((not moving_up) and candidate_grade <= source_grade + 0.05)
        )

        score = target_distance * 6.0
        score += abs(avg_syl - target_metrics['target_syl']) * policy['syllable_weight']
        score += abs(avg_wps - target_metrics['target_wps']) * policy['wps_weight']
        score += invalid_sentence_delta * 24.0
        score += min(len(invalid_sentences), baseline_invalid_count) * 1.5
        score += max(0.0, 0.88 - semantic_similarity) * 6.0
        score += len(lexical_flags) * 3.5
        score += len(directional_flags) * 3.0
        score += len(summary_wrapup_flags) * 4.5
        if len(summary_wrapup_flags) >= 2:
            score += 8.0
        if not direction_hit:
            score += 9.0
        score += paragraph_rewrites * policy['paragraph_penalty']
        score += final_paragraph_scope_penalty
        if target_grade <= 5 and avg_wps > target_metrics['target_wps']:
            score += (avg_wps - target_metrics['target_wps']) * 0.35
        if target_grade >= 11 and avg_wps < target_metrics['target_wps']:
            score += (target_metrics['target_wps'] - avg_wps) * 0.25
        if target_grade >= 11 and candidate_grade < target_grade:
            score += (target_grade - candidate_grade) * 4.0
        if target_distance > source_distance + 0.1:
            score += (target_distance - source_distance) * 2.5
        if abs(source_grade - target_grade) <= 2.5 and semantic_similarity < 0.9:
            score += (0.9 - semantic_similarity) * 12.0

        return {
            'candidate_score': round(score, 2),
            'raw_score': round(candidate_grade, 2),
            'target_distance': round(target_distance, 2),
            'direction_hit': direction_hit,
            'invalid_sentence_count': len(invalid_sentences),
            'invalid_sentence_delta': invalid_sentence_delta,
            'semantic_similarity_score': round(semantic_similarity, 2),
            'avg_syllables_per_word': round(avg_syl, 2),
            'avg_words_per_sentence': round(avg_wps, 2),
            'validation_flags': (
                lexical_flags +
                directional_flags +
                summary_wrapup_flags +
                paragraph_scope_flags +
                (['new_invalid_sentence_structure'] if invalid_sentence_delta else []) +
                (['inherited_invalid_sentence_structure'] if invalid_sentences and not invalid_sentence_delta else [])
            ),
            'paragraph_rewrite_count': paragraph_rewrites,
            'summary_wrapup_flag_count': len(summary_wrapup_flags),
            'final_paragraph_scope_penalty': round(final_paragraph_scope_penalty, 2),
        }

    def _directional_candidate_flags(
        self,
        source_grade,
        target_grade,
        source_avg_syl,
        source_avg_wps,
        candidate_avg_syl,
        candidate_avg_wps,
        semantic_similarity,
    ):
        flags = []
        going_up = target_grade > source_grade

        if going_up:
            if candidate_avg_syl < source_avg_syl - 0.03:
                flags.append('lexical_direction_mismatch')
            if candidate_avg_wps < source_avg_wps - 0.5 and target_grade >= 9:
                flags.append('sentence_length_direction_mismatch')
        else:
            if candidate_avg_syl > source_avg_syl + 0.03:
                flags.append('lexical_direction_mismatch')
            if candidate_avg_wps > source_avg_wps + 0.75:
                flags.append('sentence_length_direction_mismatch')

        if semantic_similarity < 0.82:
            flags.append('meaning_drift_risk')

        return flags

    def _semantic_similarity_score(self, original_text, candidate_text):
        original_norm = re.sub(r'\s+', ' ', original_text or '').strip().lower()
        candidate_norm = re.sub(r'\s+', ' ', candidate_text or '').strip().lower()
        if not original_norm and not candidate_norm:
            return 1.0

        original_doc = nlp(original_text or '')
        candidate_doc = nlp(candidate_text or '')
        original_lemmas = {
            token.lemma_.lower()
            for token in original_doc
            if token.is_alpha and not token.is_stop
        }
        candidate_lemmas = {
            token.lemma_.lower()
            for token in candidate_doc
            if token.is_alpha and not token.is_stop
        }

        lemma_union = original_lemmas | candidate_lemmas
        lemma_overlap = (
            len(original_lemmas & candidate_lemmas) / len(lemma_union)
            if lemma_union else 1.0
        )
        sequence_ratio = difflib.SequenceMatcher(
            None,
            original_norm,
            candidate_norm,
            autojunk=False,
        ).ratio()
        length_ratio = (
            min(len(original_norm), len(candidate_norm)) / max(len(original_norm), len(candidate_norm))
            if original_norm and candidate_norm else 1.0
        )
        return max(0.0, min(1.0, 0.45 * lemma_overlap + 0.35 * sequence_ratio + 0.2 * length_ratio))

    def _lexical_sanity_flags(self, original_text, candidate_text):
        flags = []
        original_words = Counter(
            re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", (original_text or '').lower())
        )
        candidate_words = Counter(
            re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", (candidate_text or '').lower())
        )

        for blocked in BLOCKED_SYNONYMS:
            if len(blocked) <= 2:
                continue
            if candidate_words[blocked] > original_words[blocked]:
                flags.append(f'blocked_substitution:{blocked}')

        return flags

    def _summary_wrapup_flags(self, original_text, candidate_text):
        original_norm = re.sub(r'\s+', ' ', (original_text or '').lower())
        candidate_norm = re.sub(r'\s+', ' ', (candidate_text or '').lower())
        flags = []
        for marker in SUMMARY_WRAPUP_PHRASES:
            if candidate_norm.count(marker) > original_norm.count(marker):
                marker_slug = re.sub(r'[^a-z0-9]+', '_', marker).strip('_')
                flags.append(f'summary_wrapup:{marker_slug}')
        return flags

    def _final_paragraph_scope_penalty(self, original_text, candidate_text):
        original_paragraphs = self._extract_paragraph_chunks(original_text)
        candidate_paragraphs = self._extract_paragraph_chunks(candidate_text)
        if not original_paragraphs or not candidate_paragraphs:
            return 0.0, []

        penalty = 0.0
        flags = []

        if len(original_paragraphs) != len(candidate_paragraphs):
            penalty += abs(len(original_paragraphs) - len(candidate_paragraphs)) * 2.5
            flags.append('paragraph_count_changed')

        original_last = original_paragraphs[-1]['raw']
        candidate_last = candidate_paragraphs[-1]['raw']
        original_stats = self._fragment_stats(original_last)
        candidate_stats = self._fragment_stats(candidate_last)

        original_words = max(1, original_stats['word_count'])
        word_ratio = candidate_stats['word_count'] / original_words
        word_ratio_threshold = 1.3 if original_stats['sentence_count'] <= 1 else 1.6
        if word_ratio > word_ratio_threshold:
            penalty += min(7.5, (word_ratio - word_ratio_threshold) * 4.5)
            flags.append('final_paragraph_expanded')

        sentence_growth = candidate_stats['sentence_count'] - original_stats['sentence_count']
        sentence_growth_threshold = 0 if original_stats['sentence_count'] <= 1 else 1
        if sentence_growth > sentence_growth_threshold:
            penalty += min(4.0, (sentence_growth - sentence_growth_threshold) * 2.0)
            flags.append('final_paragraph_sentence_growth')

        return penalty, flags

    def _count_heavy_paragraph_rewrites(self, original_text, candidate_text):
        original_paragraphs = self._extract_paragraph_chunks(original_text)
        candidate_paragraphs = self._extract_paragraph_chunks(candidate_text)
        if not original_paragraphs or not candidate_paragraphs:
            return 0

        heavy_rewrites = 0
        for original_paragraph, candidate_paragraph in zip(original_paragraphs, candidate_paragraphs):
            if original_paragraph['normalized'] == candidate_paragraph['normalized']:
                continue
            ratio = difflib.SequenceMatcher(
                None,
                original_paragraph['normalized'],
                candidate_paragraph['normalized'],
                autojunk=False,
            ).ratio()
            if ratio < 0.45 and self._fragment_stats(original_paragraph['raw'])['word_count'] >= 20:
                heavy_rewrites += 1

        heavy_rewrites += abs(len(original_paragraphs) - len(candidate_paragraphs))
        return heavy_rewrites

    def _build_selection_summary(self, policy, source_grade, target_grade, selected_candidate, top_candidates):
        return {
            'policy_bucket': policy['label'],
            'beam_width': policy['beam_width'],
            'source_grade': round(source_grade, 2),
            'target_grade': target_grade,
            'selected_score': selected_candidate['candidate_score'],
            'selected_path': selected_candidate.get('rule_history', []),
            'direction_hit': selected_candidate['direction_hit'],
            'target_distance': selected_candidate['target_distance'],
            'invalid_sentence_count': selected_candidate['invalid_sentence_count'],
            'invalid_sentence_delta': selected_candidate.get('invalid_sentence_delta', 0),
            'semantic_similarity_score': selected_candidate['semantic_similarity_score'],
            'top_candidates': [
                {
                    'index': index,
                    'score': candidate['candidate_score'],
                    'raw_score': candidate['raw_score'],
                    'target_distance': candidate['target_distance'],
                    'direction_hit': candidate['direction_hit'],
                    'invalid_sentence_count': candidate['invalid_sentence_count'],
                    'invalid_sentence_delta': candidate.get('invalid_sentence_delta', 0),
                    'semantic_similarity_score': candidate['semantic_similarity_score'],
                    'selection_path': candidate.get('rule_history', []),
                    'validation_flags': candidate.get('validation_flags', []),
                    'text': candidate['text'],
                }
                for index, candidate in enumerate(top_candidates)
            ],
        }

    def _grade_label_from_score(self, score):
        if score < 4:
            return 'Grade 3'
        if score < 5:
            return 'Grade 4'
        if score < 6:
            return 'Grade 5'
        if score < 7:
            return 'Grade 6'
        if score < 8:
            return 'Grade 7'
        if score < 9:
            return 'Grade 8'
        if score < 10:
            return 'Grade 9'
        if score < 11:
            return 'Grade 10'
        if score < 12:
            return 'Grade 11'
        if score < 13:
            return 'Grade 12'
        return 'College'

    def _grade_complexity_from_label(self, label):
        if label == 'College':
            return 'Expert'
        number = int(label.replace('Grade ', ''))
        if number <= 6:
            return 'Beginner'
        if number <= 9:
            return 'Intermediate'
        if number <= 12:
            return 'Advanced'
        return 'Expert'

    def _measure_preview_metrics(self, text):
        raw_score, avg_syl, avg_wps = self._measure_text_metrics(text)
        predicted_grade_level = self._grade_label_from_score(raw_score)
        predicted_complexity = self._grade_complexity_from_label(predicted_grade_level)

        if self.readability_model is not None:
            try:
                prediction = self.readability_model.predict(text)['predictions']
                raw_score = float(prediction.get('raw_score', raw_score))
                predicted_grade_level = prediction.get('predicted_grade_level', predicted_grade_level)
                predicted_complexity = prediction.get('predicted_complexity', predicted_complexity)
            except Exception as exc:
                print(f"Preview metrics fallback in simplifier: {exc}")

        return {
            'raw_score': round(raw_score, 2),
            'predicted_grade_level': predicted_grade_level,
            'predicted_complexity': predicted_complexity,
            'avg_syllables_per_word': round(avg_syl, 2),
            'avg_words_per_sentence': round(avg_wps, 2),
            'invalid_sentence_count': len(self._collect_invalid_sentences(text)),
            'semantic_similarity_score': round(self._semantic_similarity_score(text, text), 2),
            'target_distance': 0.0,
        }

    def _greedy_select_changes_for_target(self, original_text, changes, target_grade, going_up):
        """Auto-mode optimization: incrementally apply changes, keep only the subset that hits the target."""
        if not changes:
            metrics = self._measure_preview_metrics(original_text)
            metrics['target_distance'] = self._distance_to_target_band(metrics['raw_score'], target_grade)
            return changes, original_text, metrics

        units = self._build_change_units(changes, going_up)
        units.sort(key=lambda u: u['sort_key'], reverse=True)

        baseline_grade, _, _ = self._measure_text_metrics(original_text)
        baseline_distance = self._distance_to_target_band(baseline_grade, target_grade)
        measurements = 1

        best_ids = set()
        best_text = original_text
        best_distance = baseline_distance
        applied_ids = set()

        for unit in units:
            if measurements >= AUTO_GREEDY_MAX_MEASUREMENTS:
                break

            candidate_ids = applied_ids | set(unit['change_ids'])
            rebuilt = apply_changes_by_span(original_text, changes, list(candidate_ids))
            grade, _, _ = self._measure_text_metrics(rebuilt)
            measurements += 1
            distance = self._distance_to_target_band(grade, target_grade)

            if distance < best_distance:
                best_ids = set(candidate_ids)
                best_text = rebuilt
                best_distance = distance
                applied_ids = set(candidate_ids)
                if distance == 0:
                    break
            elif distance <= best_distance + AUTO_GREEDY_TOLERANCE:
                applied_ids = set(candidate_ids)

        selected_changes = [c for c in changes if c['id'] in best_ids]
        final_metrics = self._measure_preview_metrics(best_text)
        final_metrics['semantic_similarity_score'] = round(
            self._semantic_similarity_score(original_text, best_text), 2
        )
        final_metrics['target_distance'] = round(best_distance, 2)
        return selected_changes, best_text, final_metrics

    def _build_change_units(self, changes, going_up):
        """Group changes into atomic units respecting dependency groups."""
        groups = {}
        ungrouped = []

        for change in changes:
            dep_id = change.get('dependency_group_id')
            if dep_id:
                groups.setdefault(dep_id, []).append(change)
            else:
                ungrouped.append(change)

        units = []
        for change in ungrouped:
            impact = self._estimate_change_grade_impact(change, going_up)
            units.append({
                'change_ids': [change['id']],
                'sort_key': impact,
            })

        for dep_id, group_changes in groups.items():
            total_impact = sum(self._estimate_change_grade_impact(c, going_up) for c in group_changes)
            units.append({
                'change_ids': [c['id'] for c in group_changes],
                'sort_key': total_impact,
            })

        return units

    def _estimate_change_grade_impact(self, change, going_up):
        """Heuristic: estimate how much this patch moves the grade toward the target."""
        original_text = change.get('original_text', change.get('original', ''))
        replacement_text = change.get('replacement_text', change.get('simplified', ''))

        orig_words = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", original_text)
        repl_words = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", replacement_text)

        if not orig_words and not repl_words:
            return 0.0

        orig_syls = sum(self.text_processor.count_syllables(w.lower()) for w in orig_words) if orig_words else 0
        repl_syls = sum(self.text_processor.count_syllables(w.lower()) for w in repl_words) if repl_words else 0
        syl_impact = (repl_syls - orig_syls) * 0.5

        orig_sents = len(re.findall(r'[.!?]+', original_text)) if original_text.strip() else 0
        repl_sents = len(re.findall(r'[.!?]+', replacement_text)) if replacement_text.strip() else 0
        sent_delta = repl_sents - orig_sents
        wps_impact = -sent_delta * 2.0 + (len(repl_words) - len(orig_words)) * 0.1

        raw_impact = syl_impact + wps_impact
        return raw_impact if going_up else -raw_impact

    def _confidence_label(self, candidate_score, invalid_sentence_count, semantic_similarity_score, target_distance):
        if invalid_sentence_count:
            return 'Low'
        if target_distance <= 0.5 and semantic_similarity_score >= 0.9 and candidate_score <= 2.5:
            return 'High'
        if target_distance <= 1.0 and semantic_similarity_score >= 0.82 and candidate_score <= 5.0:
            return 'Medium'
        return 'Low'

    def _should_use_local_repair(self, target_grade, final_metrics, validation):
        if not validation.get('issues'):
            return False
        return final_metrics['target_distance'] <= LOCAL_REPAIR_GRADE_GAP

    def _repair_is_safe(self, original_text, current_text, repaired_text, target_grade):
        if not repaired_text or repaired_text == current_text:
            return False

        current_grade, _, _ = self._measure_text_metrics(current_text)
        repaired_grade, _, _ = self._measure_text_metrics(repaired_text)
        current_distance = self._distance_to_target_band(current_grade, target_grade)
        repaired_distance = self._distance_to_target_band(repaired_grade, target_grade)
        if repaired_distance > current_distance + 0.25:
            return False

        repaired_similarity = self._semantic_similarity_score(original_text, repaired_text)
        current_similarity = self._semantic_similarity_score(original_text, current_text)
        if repaired_similarity + 0.03 < current_similarity:
            return False

        return True

    @staticmethod
    def _dedupe_preserve_order(values):
        seen = set()
        ordered = []
        for value in values:
            normalized = (value or '').strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered

    def _collect_final_review_issues(self, validation, critic_review):
        issues = list(validation.get('issues', [])) if validation else []
        for review in (critic_review or {}).get('reviews', []):
            if review.get('meaning_drift'):
                issues.append("Preserve the original meaning more accurately.")
            if review.get('awkward_phrase'):
                issues.append("Fix awkward or unnatural wording.")
            if review.get('grade_too_low'):
                issues.append("Keep the result closer to the requested grade instead of oversimplifying.")
            if review.get('grade_too_high'):
                issues.append("Keep the result closer to the requested grade instead of staying too difficult.")
            for note in review.get('notes', []):
                if isinstance(note, str):
                    issues.append(note)
        return self._dedupe_preserve_order(issues)

    def _collect_preview_diff_ranges(self, original_text, revised_text):
        import difflib

        if original_text == revised_text:
            return []

        original_chunks = self._extract_diff_chunks(original_text)
        revised_chunks = self._extract_diff_chunks(revised_text)
        if not original_chunks or not revised_chunks:
            return [(0, len(revised_text))]

        matcher = difflib.SequenceMatcher(
            None,
            [chunk['normalized'] for chunk in original_chunks],
            [chunk['normalized'] for chunk in revised_chunks],
            autojunk=False,
        )

        ranges = []
        revised_length = len(revised_text)
        for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                continue

            if j1 < len(revised_chunks):
                start = revised_chunks[j1]['start']
            else:
                start = revised_length

            if j2 > j1 and (j2 - 1) < len(revised_chunks):
                end = revised_chunks[j2 - 1]['end']
            else:
                end = start

            if end < start:
                end = start
            ranges.append((start, end))

        return ranges

    @staticmethod
    def _ranges_overlap(left_start, left_end, right_start, right_end):
        return left_start < right_end and right_start < left_end

    @staticmethod
    def _overlap_length(left_start, left_end, right_start, right_end):
        return max(0, min(left_end, right_end) - max(left_start, right_start))

    def _build_final_review_reason(self, change, target_grade):
        change_type = change.get('type')
        scope = change.get('review_scope', 'sentence')
        scope_label = 'wording' if scope == 'word' else scope

        if change_type in {'word_replacement', 'word_upgrade'}:
            return (
                f"Adjusted this {scope_label} during the final meaning check so it stays accurate "
                f"and reads naturally at Grade {target_grade}."
            )
        if change_type == 'sentence_split':
            return (
                f"Adjusted this sentence break during the final meaning check so the shorter version "
                f"still says the same thing at Grade {target_grade}."
            )
        if change_type == 'sentence_combine':
            return (
                f"Adjusted this sentence combination during the final meaning check so the denser version "
                f"still says the same thing at Grade {target_grade}."
            )
        return (
            f"Adjusted this {scope_label} during the final meaning check to keep the wording clear, "
            f"natural, and faithful to the original text at Grade {target_grade}."
        )

    def _should_mark_final_reviewed(self, change, revised_ranges):
        preview_start = change.get('preview_start', change.get('start', 0))
        preview_end = change.get('preview_end', preview_start)
        patch_length = max(1, preview_end - preview_start)
        total_overlap = sum(
            self._overlap_length(preview_start, preview_end, range_start, range_end)
            for range_start, range_end in revised_ranges
        )
        overlap_ratio = total_overlap / patch_length

        scope = change.get('review_scope', 'sentence')
        threshold = 0.55 if scope == 'paragraph' else 0.35 if scope == 'sentence' else 0.2
        return total_overlap > 0 and overlap_ratio >= threshold

    def _annotate_final_reviewed_changes(self, changes, revised_ranges, target_grade, issues):
        if not changes:
            return []

        issue_summary = " | ".join(self._dedupe_preserve_order(issues)[:3])
        annotated = []
        for change in changes:
            updated = dict(change)
            updated['change_origin'] = 'rule'
            updated['final_reviewed'] = False
            updated['final_review_note'] = None

            touched = self._should_mark_final_reviewed(updated, revised_ranges)

            if touched:
                updated['change_origin'] = 'rule+final_review'
                updated['final_reviewed'] = True
                updated['final_review_note'] = self._build_final_review_reason(updated, target_grade)
                validation_flags = list(updated.get('validation_flags') or [])
                if 'final_review_adjusted' not in validation_flags:
                    validation_flags.append('final_review_adjusted')
                updated['validation_flags'] = validation_flags

                evidence = dict(updated.get('evidence') or {})
                if updated.get('rule_id'):
                    evidence['base_rule_id'] = updated['rule_id']
                if updated.get('reason_code'):
                    evidence['base_reason_code'] = updated['reason_code']
                if updated.get('reason'):
                    evidence['base_reason'] = updated['reason']
                evidence['final_reviewed'] = True
                if issue_summary:
                    evidence['review_focus'] = issue_summary
                updated['evidence'] = evidence

            annotated.append(updated)

        return annotated

    def _apply_llm_repair_pass(
        self,
        original_text,
        current_text,
        target_grade,
        going_up,
        changes,
        validation,
        critic_review,
    ):
        summary = {
            'final_review_applied': True,
            'review_adjusted_change_count': 0,
        }
        if not self.llm_validator.client:
            summary['final_review_applied'] = False
            final_metrics = self._measure_preview_metrics(current_text)
            final_metrics['semantic_similarity_score'] = round(
                self._semantic_similarity_score(original_text, current_text),
                2,
            )
            final_metrics['target_distance'] = round(
                self._distance_to_target_band(final_metrics['raw_score'], target_grade),
                2,
            )
            return current_text, changes, validation, final_metrics, summary

        review_issues = self._collect_final_review_issues(validation, critic_review)
        revised_text = self.llm_validator.polish_text(
            original_text=original_text,
            rewritten_text=current_text,
            target_grade=target_grade,
            issues=review_issues,
            going_up=going_up,
        )

        if self._repair_is_safe(original_text, current_text, revised_text, target_grade):
            revised_ranges = self._collect_preview_diff_ranges(current_text, revised_text)
            current_text, changes, final_metrics = self._finalize_preview_candidate(
                original_text=original_text,
                candidate_text=revised_text,
                target_grade=target_grade,
                going_up=going_up,
                prefer_sentence_level=True,
            )
            changes = self._annotate_final_reviewed_changes(
                changes=changes,
                revised_ranges=revised_ranges,
                target_grade=target_grade,
                issues=review_issues,
            )
            summary['review_adjusted_change_count'] = sum(
                1 for change in changes if change.get('final_reviewed')
            )
        else:
            current_text, changes, final_metrics = self._finalize_preview_candidate(
                original_text=original_text,
                candidate_text=current_text,
                target_grade=target_grade,
                going_up=going_up,
            )

        validation = self.llm_validator.validate_changes(original_text, current_text, changes)
        if validation.get('issues') and self._should_use_local_repair(target_grade, final_metrics, validation):
            repaired_text = self.llm_validator.local_repair(
                original_text=original_text,
                candidate_text=current_text,
                target_grade=target_grade,
                issues=validation.get('issues', []),
            )
            if self._repair_is_safe(original_text, current_text, repaired_text, target_grade):
                repaired_ranges = self._collect_preview_diff_ranges(current_text, repaired_text)
                current_text, changes, final_metrics = self._finalize_preview_candidate(
                    original_text=original_text,
                    candidate_text=repaired_text,
                    target_grade=target_grade,
                    going_up=going_up,
                    prefer_sentence_level=True,
                )
                changes = self._annotate_final_reviewed_changes(
                    changes=changes,
                    revised_ranges=repaired_ranges,
                    target_grade=target_grade,
                    issues=validation.get('issues', []),
                )
                summary['review_adjusted_change_count'] = sum(
                    1 for change in changes if change.get('final_reviewed')
                )
                validation = self.llm_validator.validate_changes(original_text, current_text, changes)

        return current_text, changes, validation, final_metrics, summary

    def _maybe_adopt_critic_candidate(
        self,
        preferred_index,
        selection,
        original_text,
        target_grade,
        current_text,
        changes,
        validation,
        final_metrics,
    ):
        top_candidates = selection.get('top_candidates', [])
        if preferred_index < 0 or preferred_index >= len(top_candidates):
            return current_text, changes, validation, final_metrics

        preferred = top_candidates[preferred_index]
        preferred_text = preferred.get('text')
        if not preferred_text or preferred_text == current_text:
            return current_text, changes, validation, final_metrics
        if not self._repair_is_safe(original_text, current_text, preferred_text, target_grade):
            return current_text, changes, validation, final_metrics

        current_text = preferred_text
        changes = self._diff_changes(original_text, current_text, target_grade, selection['going_up'])
        changes = self._assign_dependency_groups(changes)
        if changes:
            current_text = apply_changes_by_span(
                original_text,
                changes,
                [change['id'] for change in changes]
            )
        final_metrics = self._measure_preview_metrics(current_text)
        final_metrics['semantic_similarity_score'] = round(
            self._semantic_similarity_score(original_text, current_text),
            2,
        )
        final_metrics['target_distance'] = round(
            self._distance_to_target_band(final_metrics['raw_score'], target_grade),
            2,
        )
        validation = self.llm_validator.validate_changes(original_text, current_text, changes)
        return current_text, changes, validation, final_metrics

    def _get_target_band(self, target_grade):
        """
        Convert a target display grade into the raw-score band that produces that label.
        This keeps rewrite control aligned with what users actually see in the UI.
        """
        if target_grade <= 3:
            return float('-inf'), 4.0
        if target_grade >= 13:
            return 13.0, float('inf')
        return float(target_grade), float(target_grade + 1)

    def _get_target_direction(self, estimated_grade, target_grade):
        """
        Return:
          1  -> keep upgrading until the score enters the target display-grade band
          0  -> already in the target display-grade band
         -1  -> downgrade until the score re-enters the band
        """
        lower, upper = self._get_target_band(target_grade)
        if estimated_grade < lower:
            return 1
        if estimated_grade >= upper:
            return -1
        return 0

    def _should_use_full_rewrite_rescue(self, text, target_grade, final_grade):
        """
        Decide when auto mode should escalate from the rule engine to a
        full-text rescue rewrite.
        """
        if not self.llm_client:
            return False

        if self._get_target_direction(final_grade, target_grade) != 0:
            return True

        if abs(final_grade - target_grade) >= REWRITE_RESCUE_GRADE_GAP:
            return True

        return self._needs_llm_help(text, target_grade)

    def _distance_to_target_band(self, estimated_grade, target_grade):
        """Distance from the displayed target-grade band."""
        lower, upper = self._get_target_band(target_grade)
        if estimated_grade < lower:
            return lower - estimated_grade
        if estimated_grade >= upper:
            return estimated_grade - upper
        return 0.0

    def _alignment_score(self, estimated_grade, target_grade):
        """
        Lower is better. Being inside the displayed grade band wins; otherwise,
        prefer the closest grade to that band.
        """
        band_distance = self._distance_to_target_band(estimated_grade, target_grade)
        if band_distance == 0:
            center = target_grade + (0.25 if target_grade < 13 else 0.5)
            return abs(estimated_grade - center) * 0.01
        return band_distance

    def _accept_structural_rewrite(self, original_text, candidate_text, changes):
        """
        Keep structure-changing edits only when they still read as complete,
        standalone sentences after the rule-based pass.
        """
        if not changes:
            return candidate_text, changes

        baseline_invalid_count = len(self._collect_invalid_sentences(original_text))
        candidate_invalid_count = len(self._collect_invalid_sentences(candidate_text))
        local_replacements_are_valid = True
        for change in changes:
            replacement = (
                change.get('replacement_text') or
                change.get('simplified') or
                ''
            ).strip()
            if replacement and not self._text_has_valid_sentence_structure(replacement):
                local_replacements_are_valid = False
                break

        if local_replacements_are_valid and candidate_invalid_count <= baseline_invalid_count:
            return candidate_text, changes

        accepted = []
        best_invalid_count = baseline_invalid_count
        ordered_changes = sorted(
            changes,
            key=lambda change: (
                change.get('start', change.get('position', 0)),
                change.get('end', change.get('start', change.get('position', 0))),
                change.get('id', 0),
            )
        )

        for change in ordered_changes:
            replacement = (
                change.get('replacement_text') or
                change.get('simplified') or
                ''
            ).strip()
            if not replacement:
                continue
            if not self._text_has_valid_sentence_structure(replacement):
                continue

            candidate_changes = accepted + [change]
            candidate_ids = [accepted_change['id'] for accepted_change in candidate_changes]
            filtered_text = apply_changes_by_span(original_text, candidate_changes, candidate_ids)
            filtered_invalid_count = len(self._collect_invalid_sentences(filtered_text))
            if filtered_invalid_count <= best_invalid_count:
                accepted.append(change)
                best_invalid_count = filtered_invalid_count

        if not accepted:
            return original_text, []

        accepted_ids = [change['id'] for change in accepted]
        filtered_text = apply_changes_by_span(original_text, accepted, accepted_ids)
        if len(self._collect_invalid_sentences(filtered_text)) > baseline_invalid_count:
            return original_text, []

        return filtered_text, accepted

    def _measure_text_metrics(self, text):
        """
        Measure actual text metrics and estimate grade.
        Returns: (estimated_grade, avg_syllables_per_word, avg_words_per_sentence)

        Prefer the same readability model used by the rest of the app so
        targeting decisions match the grade shown to users. Fall back to the
        older syllable/words-per-sentence approximation when no model is wired in.
        """
        doc = nlp(text)
        words = [t for t in doc if t.is_alpha]
        sentences = list(doc.sents)

        if not words or not sentences:
            return 8.0, 1.4, 15.0  # safe defaults

        total_syl = sum(self.text_processor.count_syllables(w.text.lower()) for w in words)
        avg_syl = total_syl / len(words)
        avg_wps = len(words) / len(sentences)

        predicted = None
        if self.readability_model is not None:
            try:
                predicted = float(self.readability_model.predict(text)['predictions']['raw_score'])
            except Exception as e:
                print(f"Readability model scoring fallback in simplifier: {e}")

        if predicted is None:
            predicted = -21.16 + 14.33 * avg_syl + 0.6 * avg_wps

        # Do NOT clamp; targeting must match the raw_score the UI renders.
        return predicted, avg_syl, avg_wps

    def _estimate_current_grade(self, text):
        """Backward-compat wrapper."""
        grade, _, _ = self._measure_text_metrics(text)
        return grade

    def _is_domain_sensitive_term(self, word_lower, token, explicit_synonym=None):
        if explicit_synonym:
            return False
        if token.pos_ not in ('NOUN', 'PROPN'):
            return False
        if len(word_lower) < 8:
            return False
        if any(word_lower.endswith(suffix) for suffix in DOMAIN_TERM_SUFFIXES):
            return True
        if token.ent_type_:
            return True
        return False

    # ------------------------------------------------------------------ #
    #  Word difficulty assessment (data-driven)
    # ------------------------------------------------------------------ #

    def _is_word_too_hard(self, word, target_grade):
        """
        Determine if a word is too difficult for the target grade.
        Uses: zipf frequency, Dale-Chall list, syllable count.
        """
        word_lower = word.lower()

        # Dale-Chall easy words are fine for any grade
        if self.synonym_lookup.is_easy_word(word_lower):
            return False

        # Get the zipf frequency (higher = more common)
        freq = zipf_frequency(word_lower, 'en')

        # Get the threshold for this grade
        threshold = GRADE_ZIPF_THRESHOLDS.get(target_grade, 3.0)

        # Word is too hard if its frequency is below the grade threshold
        if freq < threshold:
            return True

        # Also flag words with many syllables even if somewhat frequent
        syllables = self.text_processor.count_syllables(word_lower)
        if syllables >= 4 and freq < threshold + 0.5:
            return True

        return False

    def _get_lookup_keys(self, *values):
        """Return de-duplicated lowercase lookup keys in priority order."""
        keys = []
        seen = set()

        for value in values:
            if not value:
                continue

            lowered = value.lower()
            if lowered in seen:
                continue

            seen.add(lowered)
            keys.append(lowered)

        return keys

    def _get_explicit_simplification(self, word, lemma=None):
        """Check curated and supplemental rule maps before dynamic synonym search."""
        for key in self._get_lookup_keys(word, lemma):
            curated = self.synonym_lookup.simplification_map.get(key)
            if curated:
                return curated['simple']

            supplemental = SUPPLEMENTAL_SIMPLIFICATIONS.get(key)
            if supplemental:
                return supplemental

        return None

    def _get_explicit_complex_options(self, word, lemma=None):
        """Merge curated and supplemental complexification options."""
        options = []
        seen = set()

        for key in self._get_lookup_keys(word, lemma):
            explicit_buckets = [
                self.synonym_lookup.get_complex_synonyms(key) or [],
                self.synonym_lookup.get_reverse_curated_complex_synonyms(key) or [],
            ]
            for bucket in explicit_buckets:
                for option in bucket:
                    lowered = option.lower()
                    if lowered not in seen:
                        seen.add(lowered)
                        options.append(option)

            for option in SUPPLEMENTAL_COMPLEXIFICATIONS.get(key, []):
                lowered = option.lower()
                if lowered not in seen:
                    seen.add(lowered)
                    options.append(option)

        return options

    def _is_explicit_simplification_candidate(self, word, lemma, candidate):
        """True when a replacement came from the deterministic rule maps."""
        explicit = self._get_explicit_simplification(word, lemma)
        return bool(explicit and explicit.lower() == candidate.lower())

    # ------------------------------------------------------------------ #
    #  Dynamic synonym finding via WordNet + frequency ranking
    # ------------------------------------------------------------------ #

    def _find_simpler_synonym(self, word, token, target_grade):
        """
        Find the simplest synonym for a word using WordNet + context disambiguation.

        Strategy:
        1. Check curated simplification_map first (highest quality)
        2. Use simplified Lesk algorithm to pick the best WordNet sense
        3. Only allow SINGLE-WORD replacements from WordNet
        4. Require candidate to be both more frequent AND fewer/equal syllables
        5. Pick the highest-frequency candidate from the best sense
        """
        word_lower = word.lower()
        lemma = token.lemma_.lower()
        cache_key = f"{lemma}_{target_grade}"

        if cache_key in self._synonym_cache:
            return self._synonym_cache[cache_key]

        original_freq = zipf_frequency(word_lower, 'en')
        original_syllables = self.text_processor.count_syllables(word_lower)
        target_threshold = GRADE_ZIPF_THRESHOLDS.get(target_grade, 3.0)

        candidates = []

        explicit_simple = self._get_explicit_simplification(word_lower, lemma)
        if explicit_simple:
            freq = zipf_frequency(explicit_simple.split()[0], 'en')
            candidates.append((explicit_simple, freq, self.text_processor.count_syllables(explicit_simple)))

        if self.wordnet_available:
            # Use simplified Lesk to pick the best synset
            best_synset, lesk_score = self._disambiguate_sense(token)
            lesk_identified_sense = False

            if best_synset and lesk_score > 0:
                self._collect_synset_candidates(
                    best_synset, word_lower, lemma, original_freq,
                    original_syllables, candidates, set()
                )
                lesk_identified_sense = True

            # Fall back to first synset (most common sense) ONLY when:
            # - Lesk didn't identify a specific sense, AND
            # - Word isn't a highly polysemous verb (too risky without context)
            if len(candidates) <= (1 if explicit_simple else 0) and not lesk_identified_sense:
                seen = set()
                for lookup_word in set([word_lower, lemma]):
                    synsets = wn.synsets(lookup_word)
                    matching = [s for s in synsets if self._pos_matches(token.pos_, s.pos())]
                    if matching:
                        if token.pos_ == 'VERB' and len(matching) >= 4:
                            continue
                        self._collect_synset_candidates(
                            matching[0], word_lower, lemma, original_freq,
                            original_syllables, candidates, seen
                        )

        # Datamuse API fallback (only if WordNet found nothing)
        # Datamuse uses "means like" which can return phonetically similar but semantically
        # unrelated words (e.g., "zone" -> "sun"). Apply much stricter checks:
        #   1. Must be significantly more common (>=1.5 Zipf units, not just 0.8)
        #   2. Must be in the Dale-Chall 3000 easy words list (proven simple vocabulary)
        if not candidates:
            datamuse_result = self.datamuse_finder.get_simpler_synonym(lemma)
            if datamuse_result:
                dm_freq = zipf_frequency(datamuse_result, 'en')
                dm_syl = self.text_processor.count_syllables(datamuse_result)
                dm_is_easy = self.synonym_lookup.is_easy_word(datamuse_result)
                if (dm_freq >= original_freq + 1.5 and
                        dm_syl <= original_syllables and
                        dm_is_easy):
                    candidates.append((datamuse_result, dm_freq, dm_syl))

        if not candidates:
            self._synonym_cache[cache_key] = None
            return None

        # Rank: prefer easy/common candidates that hit the target grade threshold.
        candidates.sort(key=lambda c: (
            0 if self.synonym_lookup.is_easy_word(c[0].split()[0]) else 1,
            0 if c[1] >= target_threshold else 1,
            c[2],
            -c[1],
            len(c[0])
        ))

        best = candidates[0][0]
        self._synonym_cache[cache_key] = best
        return best

    def _disambiguate_sense(self, token):
        """
        Simplified Lesk algorithm: pick the WordNet synset whose definition
        has the most overlap with the surrounding sentence context.

        Returns:
            (best_synset, overlap_score) - score of 0 means no context match (ambiguous)
        """
        if not self.wordnet_available:
            return None, 0

        word_lower = token.lemma_.lower()
        synsets = wn.synsets(word_lower)
        matching = [s for s in synsets if self._pos_matches(token.pos_, s.pos())]

        if not matching:
            return None, 0
        if len(matching) == 1:
            return matching[0], 1

        # Build context from surrounding tokens (nouns, verbs, adjectives)
        context_words = set()
        sent = token.sent
        for t in sent:
            if t.i != token.i and t.pos_ in ('NOUN', 'VERB', 'ADJ') and t.is_alpha:
                context_words.add(t.lemma_.lower())

        best_synset = None
        best_overlap = -1

        for synset in matching[:5]:
            # Words from the definition + examples
            definition_words = set(synset.definition().lower().split())
            for example in synset.examples():
                definition_words.update(example.lower().split())
            # Also add hypernym definitions for richer context
            for hypernym in synset.hypernyms():
                definition_words.update(hypernym.definition().lower().split())

            overlap = len(context_words & definition_words)
            if overlap > best_overlap:
                best_overlap = overlap
                best_synset = synset

        return best_synset, best_overlap

    def _collect_synset_candidates(self, synset, word_lower, lemma,
                                    original_freq, original_syllables,
                                    candidates, seen):
        """Extract valid simpler synonyms from a single synset."""
        for wn_lemma in synset.lemmas():
            candidate = wn_lemma.name().replace('_', ' ').lower()

            if candidate == word_lower or candidate == lemma:
                continue
            if candidate in seen:
                continue
            seen.add(candidate)

            # ONLY single-word replacements from WordNet, min 2 chars
            if ' ' in candidate or len(candidate) < 2:
                continue

            # Sense validation for verbs: the candidate's common meaning must
            # align with this synset. Reject if this synset is only a rare sense
            # of the candidate (e.g., "dig" meaning "understand" is rare).
            # Nouns/adjectives are safer - use broader tolerance.
            cand_synsets = wn.synsets(candidate, pos=synset.pos())
            if cand_synsets:
                if synset.pos() == wn.VERB:
                    max_senses = 4
                elif synset.pos() == wn.NOUN:
                    max_senses = 10
                else:
                    max_senses = 8
                if synset not in cand_synsets[:max_senses]:
                    continue

            # Never use blocked/inappropriate synonyms
            if candidate in BLOCKED_SYNONYMS:
                continue

            cand_freq = zipf_frequency(candidate, 'en')
            cand_syllables = self.text_processor.count_syllables(candidate)

            # Must be significantly more frequent (MIN_FREQ_IMPROVEMENT Zipf units) AND fewer/equal syllables.
            # The minimum improvement threshold prevents borderline or semantically wrong replacements.
            if cand_freq >= original_freq + MIN_FREQ_IMPROVEMENT and cand_syllables <= original_syllables:
                candidates.append((candidate, cand_freq, cand_syllables))

    def _pos_matches(self, spacy_pos, wordnet_pos):
        """Map spaCy POS to WordNet POS for filtering.
        Note: many English adjectives in WordNet use ADJ_SAT ('s'), not ADJ ('a').
        Both must match for spaCy ADJ tokens.
        """
        if spacy_pos == 'ADJ':
            return wordnet_pos in (wn.ADJ, wn.ADJ_SAT)  # 'a' or 's'
        mapping = {
            'NOUN': wn.NOUN,
            'VERB': wn.VERB,
            'ADV': wn.ADV,
        }
        return mapping.get(spacy_pos) == wordnet_pos

    # ------------------------------------------------------------------ #
    #  Inflection handling
    # ------------------------------------------------------------------ #

    IRREGULAR_VERBS = {
        'keep': {'VBD': 'kept', 'VBN': 'kept', 'VBG': 'keeping', 'VBZ': 'keeps'},
        'get': {'VBD': 'got', 'VBN': 'gotten', 'VBG': 'getting', 'VBZ': 'gets'},
        'give': {'VBD': 'gave', 'VBN': 'given', 'VBG': 'giving', 'VBZ': 'gives'},
        'show': {'VBD': 'showed', 'VBN': 'shown', 'VBG': 'showing', 'VBZ': 'shows'},
        'find': {'VBD': 'found', 'VBN': 'found', 'VBG': 'finding', 'VBZ': 'finds'},
        'make': {'VBD': 'made', 'VBN': 'made', 'VBG': 'making', 'VBZ': 'makes'},
        'take': {'VBD': 'took', 'VBN': 'taken', 'VBG': 'taking', 'VBZ': 'takes'},
        'see': {'VBD': 'saw', 'VBN': 'seen', 'VBG': 'seeing', 'VBZ': 'sees'},
        'come': {'VBD': 'came', 'VBN': 'come', 'VBG': 'coming', 'VBZ': 'comes'},
        'tell': {'VBD': 'told', 'VBN': 'told', 'VBG': 'telling', 'VBZ': 'tells'},
        'run': {'VBD': 'ran', 'VBN': 'run', 'VBG': 'running', 'VBZ': 'runs'},
        'build': {'VBD': 'built', 'VBN': 'built', 'VBG': 'building', 'VBZ': 'builds'},
        'buy': {'VBD': 'bought', 'VBN': 'bought', 'VBG': 'buying', 'VBZ': 'buys'},
        'send': {'VBD': 'sent', 'VBN': 'sent', 'VBG': 'sending', 'VBZ': 'sends'},
        'think': {'VBD': 'thought', 'VBN': 'thought', 'VBG': 'thinking', 'VBZ': 'thinks'},
        'know': {'VBD': 'knew', 'VBN': 'known', 'VBG': 'knowing', 'VBZ': 'knows'},
        'have': {'VBD': 'had', 'VBN': 'had', 'VBG': 'having', 'VBZ': 'has'},
        'do': {'VBD': 'did', 'VBN': 'done', 'VBG': 'doing', 'VBZ': 'does'},
        'go': {'VBD': 'went', 'VBN': 'gone', 'VBG': 'going', 'VBZ': 'goes'},
        'say': {'VBD': 'said', 'VBN': 'said', 'VBG': 'saying', 'VBZ': 'says'},
        'write': {'VBD': 'wrote', 'VBN': 'written', 'VBG': 'writing', 'VBZ': 'writes'},
        'read': {'VBD': 'read', 'VBN': 'read', 'VBG': 'reading', 'VBZ': 'reads'},
        'put': {'VBD': 'put', 'VBN': 'put', 'VBG': 'putting', 'VBZ': 'puts'},
        'set': {'VBD': 'set', 'VBN': 'set', 'VBG': 'setting', 'VBZ': 'sets'},
        'cut': {'VBD': 'cut', 'VBN': 'cut', 'VBG': 'cutting', 'VBZ': 'cuts'},
        'hold': {'VBD': 'held', 'VBN': 'held', 'VBG': 'holding', 'VBZ': 'holds'},
        'grow': {'VBD': 'grew', 'VBN': 'grown', 'VBG': 'growing', 'VBZ': 'grows'},
        'lead': {'VBD': 'led', 'VBN': 'led', 'VBG': 'leading', 'VBZ': 'leads'},
        'stand': {'VBD': 'stood', 'VBN': 'stood', 'VBG': 'standing', 'VBZ': 'stands'},
        'lose': {'VBD': 'lost', 'VBN': 'lost', 'VBG': 'losing', 'VBZ': 'loses'},
        'pay': {'VBD': 'paid', 'VBN': 'paid', 'VBG': 'paying', 'VBZ': 'pays'},
        'meet': {'VBD': 'met', 'VBN': 'met', 'VBG': 'meeting', 'VBZ': 'meets'},
        'feel': {'VBD': 'felt', 'VBN': 'felt', 'VBG': 'feeling', 'VBZ': 'feels'},
        'leave': {'VBD': 'left', 'VBN': 'left', 'VBG': 'leaving', 'VBZ': 'leaves'},
        'begin': {'VBD': 'began', 'VBN': 'begun', 'VBG': 'beginning', 'VBZ': 'begins'},
        'break': {'VBD': 'broke', 'VBN': 'broken', 'VBG': 'breaking', 'VBZ': 'breaks'},
        'bring': {'VBD': 'brought', 'VBN': 'brought', 'VBG': 'bringing', 'VBZ': 'brings'},
        'choose': {'VBD': 'chose', 'VBN': 'chosen', 'VBG': 'choosing', 'VBZ': 'chooses'},
        'draw': {'VBD': 'drew', 'VBN': 'drawn', 'VBG': 'drawing', 'VBZ': 'draws'},
        'drive': {'VBD': 'drove', 'VBN': 'driven', 'VBG': 'driving', 'VBZ': 'drives'},
        'fall': {'VBD': 'fell', 'VBN': 'fallen', 'VBG': 'falling', 'VBZ': 'falls'},
        'fly': {'VBD': 'flew', 'VBN': 'flown', 'VBG': 'flying', 'VBZ': 'flies'},
        'forget': {'VBD': 'forgot', 'VBN': 'forgotten', 'VBG': 'forgetting', 'VBZ': 'forgets'},
        'hide': {'VBD': 'hid', 'VBN': 'hidden', 'VBG': 'hiding', 'VBZ': 'hides'},
        'rise': {'VBD': 'rose', 'VBN': 'risen', 'VBG': 'rising', 'VBZ': 'rises'},
        'speak': {'VBD': 'spoke', 'VBN': 'spoken', 'VBG': 'speaking', 'VBZ': 'speaks'},
        'spend': {'VBD': 'spent', 'VBN': 'spent', 'VBG': 'spending', 'VBZ': 'spends'},
        'teach': {'VBD': 'taught', 'VBN': 'taught', 'VBG': 'teaching', 'VBZ': 'teaches'},
        'understand': {'VBD': 'understood', 'VBN': 'understood', 'VBG': 'understanding', 'VBZ': 'understands'},
        'win': {'VBD': 'won', 'VBN': 'won', 'VBG': 'winning', 'VBZ': 'wins'},
    }

    def _apply_inflection(self, simple_word, token):
        """Apply the original word's inflection (tense, plural, etc.) to the replacement."""
        tag = token.tag_
        morph = token.morph

        if token.pos_ == 'VERB':
            if ' ' in simple_word:
                # Inflect the first word of multi-word phrases (e.g., "take part" -> "took part")
                parts = simple_word.split()
                base = parts[0].lower()
                if base in self.IRREGULAR_VERBS and tag in self.IRREGULAR_VERBS[base]:
                    parts[0] = self.IRREGULAR_VERBS[base][tag]
                    return ' '.join(parts)
                return simple_word
            base = simple_word.lower()

            # Avoid double-inflecting replacements that are already in the
            # requested surface form (e.g. "suggested" -> "suggestedded").
            if tag in ('VBD', 'VBN') and base.endswith('ed'):
                return simple_word
            if tag == 'VBG' and base.endswith('ing'):
                return simple_word
            if tag == 'VBZ' and base.endswith('s'):
                return simple_word

            # Irregular verbs first
            if base in self.IRREGULAR_VERBS and tag in self.IRREGULAR_VERBS[base]:
                return self.IRREGULAR_VERBS[base][tag]

            # Regular inflection
            if tag in ('VBD', 'VBN'):
                if base.endswith('e'):
                    return base + 'd'
                elif base.endswith('y') and len(base) > 2 and base[-2] not in 'aeiou':
                    return base[:-1] + 'ied'
                elif self._should_double_final(base):
                    return base + base[-1] + 'ed'
                else:
                    return base + 'ed'
            elif tag == 'VBG':
                if base.endswith('e') and not base.endswith('ee'):
                    return base[:-1] + 'ing'
                elif self._should_double_final(base):
                    return base + base[-1] + 'ing'
                else:
                    return base + 'ing'
            elif tag == 'VBZ':
                if base.endswith(('s', 'sh', 'ch', 'x', 'z')):
                    return base + 'es'
                elif base.endswith('y') and len(base) > 2 and base[-2] not in 'aeiou':
                    return base[:-1] + 'ies'
                else:
                    return base + 's'

        elif token.pos_ == 'NOUN':
            if 'Number=Plur' in str(morph):
                last = simple_word.split()[-1] if ' ' in simple_word else simple_word
                # If the word already ends in 's', it is likely already in plural/invariant form.
                # Adding another 's' or 'es' would create non-words like "mechanicses".
                if last.endswith('s'):
                    plural = last  # already looks plural — use as-is
                elif last.endswith(('sh', 'ch', 'x', 'z')):
                    plural = last + 'es'
                elif last.endswith('y') and len(last) > 2 and last[-2] not in 'aeiou':
                    plural = last[:-1] + 'ies'
                else:
                    plural = last + 's'
                if ' ' in simple_word:
                    words = simple_word.split()
                    words[-1] = plural
                    return ' '.join(words)
                return plural

        elif token.pos_ == 'ADJ':
            if tag == 'JJR':
                if simple_word.endswith('e'):
                    return simple_word + 'r'
                elif self._should_double_final(simple_word):
                    return simple_word + simple_word[-1] + 'er'
                else:
                    return simple_word + 'er'
            elif tag == 'JJS':
                if simple_word.endswith('e'):
                    return simple_word + 'st'
                elif self._should_double_final(simple_word):
                    return simple_word + simple_word[-1] + 'est'
                else:
                    return simple_word + 'est'

        return simple_word

    @staticmethod
    def _should_double_final(word):
        """Check if final consonant should be doubled (CVC rule for 1-syllable words)."""
        vowels = set('aeiou')
        if len(word) < 3:
            return False
        # Don't double w, x, y
        if word[-1] in 'wxy':
            return False
        # Must end in consonant-vowel-consonant
        if word[-1] not in vowels and word[-2] in vowels and word[-3] not in vowels:
            return True
        return False

    # ------------------------------------------------------------------ #
    #  Word replacement (the core engine)
    # ------------------------------------------------------------------ #

    def _replace_difficult_words(self, text, target_grade, max_changes=None):
        """
        Replace difficult words using:
        1. Difficulty check via zipf_frequency + Dale-Chall + syllables
        2. Synonym lookup via WordNet, ranked by frequency
        3. Inflection preservation via spaCy POS tags
        """
        changes = []
        doc = nlp(text)
        new_text = text
        offset = 0

        for token in doc:
            if max_changes is not None and len(changes) >= max_changes:
                break

            if not token.is_alpha:
                continue

            # Skip proper nouns
            if token.pos_ == 'PROPN':
                continue

            # Skip ALL_CAPS tokens — these are acronyms/abbreviations (e.g., IDPS, TCP, HTML)
            if token.text.isupper() and len(token.text) > 1:
                continue

            word_lower = token.text.lower()
            explicit_synonym = self._get_explicit_simplification(word_lower, token.lemma_.lower())

            if self._is_domain_sensitive_term(word_lower, token, explicit_synonym=explicit_synonym):
                continue

            if token.is_stop and not explicit_synonym:
                continue

            # Skip short words
            if len(word_lower) < 4 and not explicit_synonym:
                continue

            # Skip words that are not too hard for target grade
            if not explicit_synonym and not self._is_word_too_hard(word_lower, target_grade):
                continue

            # Skip verbs in phrasal constructions (verb + preposition)
            # e.g., "attest to", "refer to" - replacing the verb often breaks the phrase
            if token.pos_ == 'VERB':
                next_token = doc[token.i + 1] if token.i + 1 < len(doc) else None
                if next_token and next_token.dep_ == 'prep' and next_token.head == token:
                    continue

            # Find a simpler synonym dynamically
            base_synonym = explicit_synonym or self._find_simpler_synonym(word_lower, token, target_grade)
            if not base_synonym:
                continue

            candidate_head = re.sub(r"^[^\w']+|[^\w']+$", '', base_synonym.split()[0].lower())
            if (
                not explicit_synonym and
                candidate_head and
                nlp.vocab[candidate_head].is_stop
            ):
                continue

            # Check the synonym is actually simpler (guard rail)
            orig_freq = zipf_frequency(word_lower, 'en')
            syn_freq = zipf_frequency(base_synonym.split()[0], 'en')
            if (not self._is_explicit_simplification_candidate(word_lower, token.lemma_.lower(), base_synonym) and
                    syn_freq < orig_freq + MIN_FREQ_IMPROVEMENT):
                continue

            # Never use blocked synonyms at the final step either
            base_lower = base_synonym.lower().split()[0]
            if base_lower in BLOCKED_SYNONYMS:
                continue

            # Apply inflection to match original form
            simple_word = self._apply_inflection(base_synonym, token)

            # Preserve capitalization
            if token.text[0].isupper():
                simple_word = simple_word[0].upper() + simple_word[1:]
            if token.text.isupper():
                simple_word = simple_word.upper()

            # Replace in text
            start = token.idx + offset
            end = start + len(token.text)
            new_text = new_text[:start] + simple_word + new_text[end:]
            offset += len(simple_word) - len(token.text)

            orig_zipf = zipf_frequency(word_lower, 'en')
            syn_zipf = zipf_frequency(base_synonym, 'en')
            syllables_before = self.text_processor.count_syllables(word_lower)
            syllables_after = self.text_processor.count_syllables(base_synonym)

            changes.append({
                'type': 'word_replacement',
                'original': token.text,
                'simplified': simple_word,
                'position': token.idx,
                'start': token.idx,
                'end': token.idx + len(token.text),
                'reason': f"'{token.text}' (freq {orig_zipf:.1f}, {syllables_before} syl) -> '{simple_word}' (freq {syn_zipf:.1f}, {syllables_after} syl). More common word for Grade {target_grade}.",
                'id': len(changes)
            })

        return new_text, changes

    # ------------------------------------------------------------------ #
    #  Upgrade path: complexification
    # ------------------------------------------------------------------ #

    def _complexify_text(self, text, target_grade, max_changes=None):
        """
        Replace simple/common words with more formal/academic alternatives.
        Used when upgrading text to a higher grade level.

        Strategy:
        1. Check complexification_map first (curated quality mappings)
        2. Use WordNet to find synonyms with MORE syllables + appropriate Zipf frequency
        3. Skip stop words, proper nouns, acronyms, very short words
        """
        changes = []
        doc = nlp(text)
        new_text = text
        offset = 0

        target_syl = GRADE_TARGET_SYLLABLES.get(target_grade, 1.55)
        target_threshold = GRADE_ZIPF_THRESHOLDS.get(target_grade, 3.0)

        for token in doc:
            if max_changes is not None and len(changes) >= max_changes:
                break

            if not token.is_alpha:
                continue
            if token.pos_ in ('PROPN', 'NUM'):
                continue
            if token.text.isupper() and len(token.text) > 1:
                continue
            if len(token.text) < 3:
                continue

            word_lower = token.text.lower()
            complex_options = self._get_explicit_complex_options(word_lower, token.lemma_.lower())

            # Most stop words should stay untouched, but curated discourse-marker
            # upgrades such as "also -> furthermore" help adjacent grade bumps
            # without changing the meaning of the sentence.
            if token.is_stop and not (complex_options and token.pos_ == 'ADV'):
                continue
            if token.pos_ == 'VERB':
                next_token = doc[token.i + 1] if token.i + 1 < len(doc) else None
                if next_token and next_token.head == token and next_token.dep_ in ('prep', 'acomp', 'oprd', 'xcomp'):
                    continue

            orig_freq = zipf_frequency(word_lower, 'en')
            orig_syl = self.text_processor.count_syllables(word_lower)

            # Skip words that are already complex enough for the target grade:
            #   - already has 3+ syllables, OR
            #   - already rare enough (freq below target threshold + small buffer)
            if orig_syl >= 3:
                continue
            if orig_freq <= target_threshold + 0.5:
                continue

            complex_syn = self._find_complex_synonym(
                token,
                target_grade,
                target_threshold,
                target_syl,
                complex_options=complex_options
            )
            if not complex_syn:
                continue

            # Check it's actually more complex (more syllables or lower freq)
            syn_freq = zipf_frequency(complex_syn.split()[0], 'en')
            syn_syl = self.text_processor.count_syllables(complex_syn)
            if syn_syl <= orig_syl and syn_freq >= orig_freq:
                continue  # Not actually more complex

            # Apply inflection
            inflected = self._apply_inflection(complex_syn, token)

            # Preserve capitalization
            if token.text[0].isupper():
                inflected = inflected[0].upper() + inflected[1:]

            # Replace in text
            start = token.idx + offset
            end = start + len(token.text)
            new_text = new_text[:start] + inflected + new_text[end:]
            offset += len(inflected) - len(token.text)

            changes.append({
                'type': 'word_upgrade',
                'original': token.text,
                'simplified': inflected,
                'position': token.idx,
                'start': token.idx,
                'end': token.idx + len(token.text),
                'reason': f"'{token.text}' → '{inflected}': More formal vocabulary for Grade {target_grade}.",
                'id': len(changes)
            })

        return new_text, changes

    def _find_complex_synonym(self, token, target_grade, target_threshold, target_syl, complex_options=None):
        """
        Find a more complex/formal synonym for vocabulary upgrading.

        Primarily uses the curated complexification_map. Falls back to WordNet
        only with strict POS matching and sanity checks to avoid nonsensical output.
        """
        word_lower = token.text.lower()
        lemma = token.lemma_.lower()
        orig_freq = zipf_frequency(word_lower, 'en')
        orig_syl = self.text_processor.count_syllables(word_lower)

        # --- Strategy 1: Curated complexification_map ---
        if complex_options is None:
            complex_options = (self.synonym_lookup.get_complex_synonyms(lemma) or
                               self.synonym_lookup.get_complex_synonyms(word_lower))
        if complex_options:
            # POS validation: curated map doesn't store POS, so verify the
            # complex synonym can function as the same POS as the original token.
            wn_pos_map = {'VERB': wn.VERB, 'NOUN': wn.NOUN, 'ADV': wn.ADV} if self.wordnet_available else {}
            wn_pos = wn_pos_map.get(token.pos_)  # ADJ checked separately (ADJ_SAT)

            best = None
            best_dist = float('inf')
            for opt in complex_options:
                first_word = opt.split()[0]
                freq = zipf_frequency(first_word, 'en')
                syllables = self.text_processor.count_syllables(first_word)
                if target_grade <= 6 and syllables > 2:
                    continue
                # Must be more formal (lower freq) and reasonably accessible
                if syllables <= orig_syl and freq >= orig_freq - 0.1:
                    continue
                if freq < target_threshold - (0.2 if target_grade <= 6 else 0.7):
                    continue
                # POS sanity: complex synonym must exist with same POS in WordNet.
                # If WordNet data is unavailable, fall back to curated-map trust.
                if self.wordnet_available and wn_pos and not wn.synsets(first_word, pos=wn_pos):
                    continue  # e.g. rejects "comparable" for a VERB token
                if self.wordnet_available and token.pos_ == 'ADJ':
                    if not (wn.synsets(first_word, pos=wn.ADJ) or
                            wn.synsets(first_word, pos=wn.ADJ_SAT)):
                        continue
                dist = abs(freq - target_threshold)
                if dist < best_dist:
                    best_dist = dist
                    best = opt
            if best:
                return best

        # Strategy 2: not used for upgrade — curated map is higher quality than
        # unconstrained WordNet reverse lookup, which produces semantic errors.
        # LLM handles vocabulary upgrade for words not in the curated map.
        return None

    def _combine_short_sentences(self, text, target_grade, max_combinations=None):
        """
        Combine consecutive short sentences to reach target avg words-per-sentence.
        Used for upgrading text to higher grades where longer sentences are expected.
        """
        metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        target_wps = metrics['target_wps']
        max_wps = metrics['max_wps']
        min_words = metrics['min_wps']  # Combine if sentence is shorter than this
        combine_trigger = min(max(min_words, target_wps - 4), max_wps - 3)
        combine_cap = max(max_wps + 6, target_wps + 11)

        changes = []
        result_paragraphs = []
        combinations_made = 0
        paragraphs = self._extract_paragraph_chunks(text) or [{
            'raw': text,
            'start': 0,
            'end': len(text),
        }]

        for paragraph in paragraphs:
            raw_paragraph = paragraph['raw']
            leading_ws = len(raw_paragraph) - len(raw_paragraph.lstrip())
            paragraph_text = raw_paragraph.strip()
            paragraph_start = paragraph['start'] + leading_ws

            if not paragraph_text:
                continue

            doc = nlp(paragraph_text)
            sentences = list(doc.sents)
            if not sentences:
                result_paragraphs.append(paragraph_text)
                continue

            result_sentences = []
            i = 0

            while i < len(sentences):
                sent = sentences[i]
                word_count = len([t for t in sent if t.is_alpha])

                if (
                    i + 1 < len(sentences) and
                    (max_combinations is None or combinations_made < max_combinations)
                ):
                    next_sent = sentences[i + 1]
                    next_words = len([t for t in next_sent if t.is_alpha])
                    combined_words = word_count + next_words
                    should_consider_pair = (
                        word_count <= combine_trigger or
                        (word_count <= target_wps + 1 and next_words <= target_wps + 1)
                    )

                    if should_consider_pair and combined_words <= combine_cap:
                        text1 = sent.text.rstrip('.!?')
                        text2 = next_sent.text[0].lower() + next_sent.text[1:]
                        if target_grade >= 9:
                            combined = f"{text1}; {text2}"
                        else:
                            combined = f"{text1}, and {text2}"

                        original_pair = sent.text + ' ' + next_sent.text
                        changes.append({
                            'type': 'sentence_combine',
                            'original': original_pair,
                            'simplified': combined,
                            'position': paragraph_start + sent.start_char,
                            'start': paragraph_start + sent.start_char,
                            'end': paragraph_start + next_sent.end_char,
                            'reason': (f"Combined short sentences ({word_count} + {next_words} = {combined_words} words). "
                                       f"Grade {target_grade} target: avg {target_wps} words/sentence."),
                            'id': len(changes)
                        })
                        result_sentences.append(combined)
                        combinations_made += 1
                        i += 2
                        continue

                result_sentences.append(sent.text)
                i += 1

            result_paragraphs.append(' '.join(result_sentences).strip())

        return '\n\n'.join(paragraph for paragraph in result_paragraphs if paragraph.strip()), changes

    # ------------------------------------------------------------------ #
    #  Sentence splitting (conservative, NLP-based)
    # ------------------------------------------------------------------ #

    def _split_long_sentences(self, text, target_grade, max_sentence_changes=None):
        """
        Split sentences that exceed the target range for the grade.
        Run recursively so large downscales do not stop after a single split.
        """
        metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        target_wps = metrics['target_wps']
        max_wps = metrics['max_wps']
        split_threshold = min(max_wps, target_wps + 2)

        changes = []
        new_paragraphs = []
        changed_sentence_count = 0
        paragraphs = self._extract_paragraph_chunks(text) or [{
            'raw': text,
            'start': 0,
            'end': len(text),
        }]

        for paragraph in paragraphs:
            raw_paragraph = paragraph['raw']
            leading_ws = len(raw_paragraph) - len(raw_paragraph.lstrip())
            paragraph_text = raw_paragraph.strip()
            paragraph_start = paragraph['start'] + leading_ws

            if not paragraph_text:
                continue

            doc = nlp(paragraph_text)
            new_sentences = []

            for sent in doc.sents:
                original_word_count = self._count_alpha_words(sent)
                fragments = [(sent.text.strip(), 0)]
                changed = False

                if max_sentence_changes is not None and changed_sentence_count >= max_sentence_changes:
                    new_sentences.append(sent.text)
                    continue

                for _ in range(4):
                    progress = False
                    updated_fragments = []

                    for fragment, depth in fragments:
                        fragment_doc = nlp(fragment)
                        fragment_sent = next(fragment_doc.sents, None)
                        if fragment_sent is None:
                            updated_fragments.append((fragment, depth))
                            continue

                        fragment_word_count = self._count_alpha_words(fragment_sent)
                        if fragment_word_count <= split_threshold:
                            normalized_fragment = self._normalize_split_fragment(fragment)
                            updated_fragments.append((normalized_fragment or fragment.strip(), depth))
                            continue

                        # Prevent over-splitting already shortened fragments. A
                        # single safe split is usually enough; repeated splits on
                        # medium-length fragments are where we start producing
                        # broken outputs such as "They forms ..." or "It ideas ...".
                        if depth > 0 and fragment_word_count <= max(split_threshold + 2, target_wps + 4):
                            normalized_fragment = self._normalize_split_fragment(fragment)
                            updated_fragments.append((normalized_fragment or fragment.strip(), depth))
                            continue

                        split_result = self._try_split_sentence(fragment_sent, target_wps)
                        if split_result and len(split_result) > 1:
                            updated_fragments.extend((piece, depth + 1) for piece in split_result)
                            progress = True
                            changed = True
                        else:
                            updated_fragments.append((fragment.strip(), depth))

                    fragments = updated_fragments
                    if not progress:
                        break

                if changed:
                    new_sentences.extend(fragment for fragment, _ in fragments)
                    changed_sentence_count += 1
                    changes.append({
                        'type': 'sentence_split',
                        'original': sent.text,
                        'simplified': ' '.join(fragment for fragment, _ in fragments),
                        'position': paragraph_start + sent.start_char,
                        'start': paragraph_start + sent.start_char,
                        'end': paragraph_start + sent.end_char,
                        'reason': (
                            f"Split long sentence ({original_word_count} words) into {len(fragments)} "
                            f"shorter sentences. Grade {target_grade} target: about {target_wps} "
                            f"words per sentence, max {max_wps}."
                        ),
                        'id': len(changes)
                    })
                else:
                    new_sentences.append(sent.text)

            new_paragraphs.append(' '.join(new_sentences).strip())

        return '\n\n'.join(paragraph for paragraph in new_paragraphs if paragraph.strip()), changes

    def _count_alpha_words(self, text_or_doc):
        if isinstance(text_or_doc, str):
            doc = nlp(text_or_doc)
            return len([t for t in doc if t.is_alpha])
        return len([t for t in text_or_doc if t.is_alpha])

    def _is_finite_verb_token(self, token):
        if token.pos_ not in ('VERB', 'AUX'):
            return False

        morph = str(token.morph)
        if 'VerbForm=Fin' in morph:
            return True
        if any(flag in morph for flag in ('VerbForm=Inf', 'VerbForm=Ger', 'VerbForm=Part')):
            return False
        return token.tag_ in FINITE_VERB_TAGS

    def _starts_with_bad_fragment_phrase(self, tokens):
        alpha_tokens = [token for token in tokens if token.is_alpha]
        if len(alpha_tokens) >= 2:
            pair = (alpha_tokens[0].lower_, alpha_tokens[1].lower_)
            if pair in BAD_FRAGMENT_OPENING_PAIRS:
                return True

        return False

    def _ends_with_bad_fragment_tail(self, text):
        words = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text or '')
        if not words:
            return False
        return words[-1].lower() in BAD_FRAGMENT_ENDINGS

    def _has_unfinished_clause_tail(self, text_or_doc):
        if isinstance(text_or_doc, str):
            doc = nlp(text_or_doc)
        else:
            doc = text_or_doc

        alpha_tokens = [token for token in doc if token.is_alpha]
        if not alpha_tokens:
            return False

        unfinished_markers = {
            'after', 'before', 'because', 'if', 'since', 'that',
            'until', 'when', 'where', 'which', 'while', 'who', 'whose',
        }

        for index, token in enumerate(alpha_tokens):
            if token.lower_ not in unfinished_markers:
                continue

            trailing_tokens = alpha_tokens[index + 1:]
            if any(self._is_finite_verb_token(trailing) for trailing in trailing_tokens):
                continue
            return True

        return False

    def _has_subject_and_verb(self, text_or_doc, min_words=4):
        if isinstance(text_or_doc, str):
            doc = nlp(text_or_doc)
        else:
            doc = text_or_doc

        tokens = [t for t in doc if not t.is_space]
        words = [t for t in doc if t.is_alpha]
        if len(words) < min_words or not tokens:
            return False

        if self._starts_with_bad_fragment_phrase(tokens):
            return False
        if self._has_unfinished_clause_tail(doc):
            return False

        root = next((t for t in doc if t.dep_ == 'ROOT'), None)
        if root is None:
            return False

        has_finite_verb = self._is_finite_verb_token(root)
        if not has_finite_verb:
            has_finite_verb = any(
                child.dep_ in ('aux', 'auxpass', 'cop') and self._is_finite_verb_token(child)
                for child in root.children
            )
        if not has_finite_verb:
            return False

        def attached_to_main_clause(token):
            if token.head == root:
                return True
            if token.head.dep_ in ('aux', 'auxpass', 'cop', 'conj') and token.head.head == root:
                return True
            return False

        has_subject = any(
            token.dep_ in ('nsubj', 'nsubjpass', 'expl') and attached_to_main_clause(token)
            for token in doc
        )
        if not has_subject and self._has_subordinate_and_main_clause(doc):
            return True
        return has_subject

    def _looks_like_complete_sentence(self, text_or_doc, min_words=3):
        if isinstance(text_or_doc, str):
            doc = nlp(text_or_doc)
        else:
            doc = text_or_doc

        tokens = [t for t in doc if not t.is_space]
        words = [t for t in doc if t.is_alpha]
        if len(words) < min_words or not tokens:
            return False

        if self._starts_with_bad_fragment_phrase(tokens):
            return False
        if self._has_unfinished_clause_tail(doc):
            return False

        alpha_words = [word.text.lower() for word in words]
        if self._has_simple_subject_agreement_error(alpha_words):
            return False

        has_finite_verb = any(self._is_finite_verb_token(token) for token in doc)
        has_subject = any(token.dep_ in ('nsubj', 'nsubjpass', 'expl') for token in doc)
        if has_finite_verb and has_subject:
            return True

        if self._has_subordinate_and_main_clause(doc):
            return True

        return self._has_surface_clause_cues(alpha_words)

    def _has_simple_subject_agreement_error(self, alpha_words):
        if len(alpha_words) < 2:
            return False

        subject = alpha_words[0]
        verb = alpha_words[1]
        if verb.endswith('ly') or verb in LEADING_ADVERB_MARKERS:
            return False
        if self.wordnet_available and verb not in AUXILIARY_HINTS and not wn.synsets(verb, pos=wn.VERB):
            return False

        if subject in {'they', 'we', 'you', 'i'} and re.fullmatch(r"[a-z]+s", verb):
            return verb not in {'is', 'was', 'has'}
        if subject in {'it', 'he', 'she'} and verb in {'be', 'do', 'go', 'have', 'make', 'say', 'see', 'work'}:
            return True
        if subject in {'it', 'he', 'she'} and verb in {'are', 'were', 'have', 'do'}:
            return True
        return False

    def _has_surface_clause_cues(self, alpha_words):
        """
        spaCy occasionally mis-tags long technical sentences as noun phrases.
        When that happens, fall back to a lightweight surface heuristic so we do
        not reject otherwise valid structure rewrites.
        """
        if len(alpha_words) < 8:
            return False
        if self._has_simple_subject_agreement_error(alpha_words):
            return False

        for index in range(1, len(alpha_words)):
            word = alpha_words[index]
            previous_word = alpha_words[index - 1]
            next_word = alpha_words[index + 1] if index + 1 < len(alpha_words) else ''

            if word in AUXILIARY_HINTS:
                return True

            if not self.wordnet_available:
                continue
            if not wn.synsets(word, pos=wn.VERB):
                continue
            if previous_word in DETERMINER_HINTS:
                continue
            if next_word and next_word not in PREPOSITION_HINTS and next_word not in DETERMINER_HINTS:
                continue

            return True

        return False

    def _has_subordinate_and_main_clause(self, doc):
        alpha_words = [token.text.lower() for token in doc if token.is_alpha]
        if not alpha_words:
            return False
        if alpha_words[0] not in {'when', 'while', 'if', 'because', 'although', 'though', 'since', 'after', 'before'}:
            return False

        finite_verbs = [token for token in doc if self._is_finite_verb_token(token)]
        subjects = [token for token in doc if token.dep_ in ('nsubj', 'nsubjpass', 'expl')]
        return len(finite_verbs) >= 2 and len(subjects) >= 2

    def _collect_invalid_sentences(self, text):
        invalid = []
        if not text or not text.strip():
            return invalid

        doc = nlp(text)
        for sent in doc.sents:
            sentence_text = sent.text.strip()
            if not sentence_text:
                continue
            word_count = len([token for token in sent if token.is_alpha])

            if self._ends_with_bad_fragment_tail(sentence_text) and word_count <= 12:
                invalid.append(sentence_text)
                continue

            if not self._looks_like_complete_sentence(sentence_text, min_words=3):
                invalid.append(sentence_text)
                continue

            # Short split fragments are where the dependency-based validation is
            # most reliable, so keep an extra guard here to catch outputs such as
            # "They forms in ..." without rejecting dense but valid long sentences.
            if word_count <= 12 and not self._has_subject_and_verb(sentence_text, min_words=3):
                invalid.append(sentence_text)

        return invalid

    def _text_has_valid_sentence_structure(self, text):
        return not self._collect_invalid_sentences(text)

    def _extract_subject_info(self, tokens):
        """Extract the main subject phrase and whether it is plural."""
        for token in tokens:
            if token.dep_ not in ('nsubj', 'nsubjpass'):
                continue

            subtree = sorted(list(token.subtree), key=lambda t: t.i)
            subject_text = ' '.join(
                t.text for t in subtree
                if t.dep_ not in ('relcl', 'acl', 'advcl')
            ).strip()
            if not subject_text:
                continue

            is_plural = (
                token.tag_ in ('NNS', 'NNPS') or
                'Number=Plur' in str(token.morph) or
                token.lower_ in ('they', 'we', 'these', 'those')
            )
            return subject_text, is_plural

        return None, False

    def _get_main_subject(self, tokens):
        """Backward-compatible main subject extractor."""
        subject_text, _ = self._extract_subject_info(tokens)
        return subject_text

    def _get_carry_subject(self, tokens):
        """
        Pick a subject to reuse in split fragments. Long noun phrases become a
        pronoun so the split sentences stay readable.
        """
        subject_text, is_plural = self._extract_subject_info(tokens)
        if not subject_text:
            return None, False

        subject_doc = nlp(subject_text)
        alpha_words = [t.text for t in subject_doc if t.is_alpha]
        first_word = alpha_words[0].lower() if alpha_words else ''
        if len(alpha_words) > 4 and first_word not in ('he', 'she', 'they', 'it', 'we', 'you', 'i'):
            return ('They' if is_plural else 'It'), is_plural

        return subject_text, is_plural

    def _conjugate_present(self, lemma, subject_plural):
        """Convert a lemma into a simple present-tense verb for repaired clauses."""
        lemma = lemma.lower()

        if lemma == 'be':
            return 'are' if subject_plural else 'is'
        if lemma == 'have':
            return 'have' if subject_plural else 'has'
        if lemma == 'do':
            return 'do' if subject_plural else 'does'
        if lemma in ('can', 'could', 'may', 'might', 'must', 'should', 'will', 'would'):
            return lemma

        if subject_plural:
            return lemma

        if lemma in self.IRREGULAR_VERBS and 'VBZ' in self.IRREGULAR_VERBS[lemma]:
            return self.IRREGULAR_VERBS[lemma]['VBZ']

        if lemma.endswith(('s', 'sh', 'ch', 'x', 'z')):
            return lemma + 'es'
        if lemma.endswith('y') and len(lemma) > 2 and lemma[-2] not in 'aeiou':
            return lemma[:-1] + 'ies'
        return lemma + 's'

    def _clean_sentence_fragment(self, text):
        text = re.sub(r'\s+', ' ', text or '')
        text = re.sub(r'\s+([,.;!?])', r'\1', text)
        return text.strip(" \t\r\n,;:")

    def _normalize_split_fragment(self, fragment_text, carry_subject=None, subject_plural=False):
        """
        Turn a clause fragment into a standalone sentence.
        Repair subject-less right-hand clauses such as "and then building..."
        into "They then build...".
        """
        text = self._clean_sentence_fragment(fragment_text)
        if not text:
            return None

        doc = nlp(text)
        tokens = [t for t in doc if not t.is_space]
        if not tokens:
            return None

        leading_markers = []
        leading_adverbs = []
        idx = 0
        while idx < len(tokens) and tokens[idx].lower_ in LEADING_ADVERB_MARKERS:
            leading_adverbs.append(tokens[idx].text.lower())
            idx += 1
        while idx < len(tokens) and (tokens[idx].is_punct or tokens[idx].lower_ in LEADING_SPLIT_MARKERS):
            if tokens[idx].lower_ in LEADING_SPLIT_MARKERS:
                leading_markers.append(tokens[idx].lower_)
            idx += 1
        while idx < len(tokens) and tokens[idx].lower_ in LEADING_ADVERB_MARKERS:
            leading_adverbs.append(tokens[idx].text.lower())
            idx += 1
        while idx < len(tokens) and carry_subject and tokens[idx].lower_ in {'by'}:
            idx += 1

        if idx >= len(tokens):
            return None

        text = self._clean_sentence_fragment(text[tokens[idx].idx:])
        if not text:
            return None

        parsed = nlp(text)
        prefix = ' '.join(leading_adverbs).strip()
        can_repair_with_carry = (
            carry_subject and
            bool(leading_markers or leading_adverbs) and
            (not leading_markers or set(leading_markers).issubset(ALLOWED_CARRY_REPAIR_MARKERS))
        )

        if not self._has_subject_and_verb(parsed) and can_repair_with_carry:
            core_tokens = [t for t in parsed if not t.is_space and not t.is_punct]
            if not core_tokens:
                return None

            first = core_tokens[0]
            if first.pos_ not in ('VERB', 'AUX') and first.tag_ != 'VBD':
                return None
            if first.tag_ in ('VB', 'VBG', 'VBN') and not prefix:
                return None

            remainder = text[first.idx + len(first.text):].lstrip()
            intro = f"{prefix}, " if prefix else ""
            carry_text = carry_subject
            carry_lower = (carry_text or '').strip().lower()
            subject_uses_base_form = subject_plural or carry_lower in {'i', 'we', 'they', 'you'}
            if intro and carry_text:
                carry_text = carry_text[0].lower() + carry_text[1:]
            if first.tag_ in ('VB', 'VBP', 'VBZ', 'VBG', 'VBN'):
                repaired = (
                    f"{intro}{carry_text} "
                    f"{self._conjugate_present(first.lemma_, subject_uses_base_form)}"
                )
                if remainder:
                    repaired += f" {remainder}"
                text = repaired
            elif first.tag_ == 'VBD':
                lowered = text[0].lower() + text[1:] if len(text) > 1 else text.lower()
                text = f"{intro}{carry_text} {lowered}"
            else:
                lowered = text[0].lower() + text[1:] if len(text) > 1 else text.lower()
                repaired = f"{intro}{carry_text} {lowered}"
                text = repaired
        elif prefix:
            text = f"{prefix}, {text}"
        elif leading_markers and not can_repair_with_carry:
            return None

        text = self._clean_sentence_fragment(text)
        if not text:
            return None
        if self._has_unfinished_clause_tail(text):
            return None

        text = text[0].upper() + text[1:]
        if text[-1] not in '.!?':
            text += '.'

        if self._ends_with_bad_fragment_tail(text):
            return None

        word_count = self._count_alpha_words(text)
        if not self._looks_like_complete_sentence(text, min_words=3):
            return None
        if word_count <= 18 and not self._has_subject_and_verb(text, min_words=3):
            return None

        return text

    def _normalize_split_pair(self, before_text, after_text, carry_subject, subject_plural):
        before_words = re.findall(r"[A-Za-z']+", before_text.lower())
        if before_words and before_words[-1] in BAD_FRAGMENT_ENDINGS:
            return None
        if self._has_unfinished_clause_tail(before_text):
            return None

        before = self._normalize_split_fragment(before_text)
        after = self._normalize_split_fragment(after_text, carry_subject, subject_plural)

        if not before or not after:
            return None

        if self._count_alpha_words(before) < 4 or self._count_alpha_words(after) < 4:
            return None

        if self._ends_with_bad_fragment_tail(before) or self._ends_with_bad_fragment_tail(after):
            return None

        return [before, after]

    def _select_best_split_candidate(self, sent, candidate_tokens, target_words):
        tokens = list(sent)
        if not candidate_tokens:
            return None

        carry_subject, subject_plural = self._get_carry_subject(tokens)
        sentence_text = sent.text.strip()
        candidates = []
        seen = set()

        for token in candidate_tokens:
            if token.i in seen:
                continue
            seen.add(token.i)

            if token.i <= sent.start + 1 or token.i >= sent.end - 2:
                continue

            split_char = token.idx - sent.start_char
            before_text = sentence_text[:split_char].strip().rstrip(',;:')
            after_text = sentence_text[split_char:].strip().lstrip(',;:')

            pair = self._normalize_split_pair(before_text, after_text, carry_subject, subject_plural)
            if not pair:
                continue

            left_words = self._count_alpha_words(pair[0])
            right_words = self._count_alpha_words(pair[1])
            score = (
                max(abs(left_words - target_words), abs(right_words - target_words)),
                abs(left_words - right_words),
                abs((left_words + right_words) - (2 * target_words))
            )
            candidates.append((score, pair))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def _try_split_sentence(self, sent, target_words):
        """Try strategies to split a long sentence safely."""
        sent_text = sent.text.strip()

        # Strategy 1: Split at semicolons
        if ';' in sent_text:
            parts = sent_text.split(';')
            result = []
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                part = part[0].upper() + part[1:]
                if part[-1] not in '.!?':
                    part += '.'
                result.append(part)
            if len(result) > 1 and all(len(p.split()) >= 3 for p in result):
                return result

        # Strategy 2: Split at safe clause boundaries
        split_result = self._split_at_clause_boundary(sent, target_words)
        if split_result:
            return split_result

        # Strategy 3: Split at conjunctions and markers, repairing the second
        # clause into a full sentence where needed.
        split_result = self._split_at_conjunction_safe(sent, target_words)
        if split_result:
            return split_result

        split_result = self._split_at_marker_boundary(sent, target_words)
        if split_result:
            return split_result

        return self._split_near_midpoint(sent, target_words)

    def _split_at_clause_boundary(self, sent, target_words):
        """Split at clause heads, then normalize each side into a sentence."""
        candidate_tokens = [
            token for token in sent
            if token.dep_ in ('ccomp', 'conj') and
            token.pos_ in ('VERB', 'AUX')
        ]
        return self._select_best_split_candidate(sent, candidate_tokens, target_words)

    def _split_at_conjunction_safe(self, sent, target_words):
        """Split at coordinating conjunctions and repair the right-hand clause."""
        candidate_tokens = [
            token for token in sent
            if (
                token.dep_ == 'cc' and
                token.text.lower() in ('and', 'but', 'yet', 'so') and
                token.head.pos_ in ('VERB', 'AUX')
            )
        ]
        return self._select_best_split_candidate(sent, candidate_tokens, target_words)

    def _split_at_marker_boundary(self, sent, target_words):
        """Split at a narrow set of mid-sentence markers when both sides stay valid."""
        candidate_tokens = [
            token for token in sent
            if token.is_alpha and token.text.lower() in MID_SENTENCE_SPLIT_MARKERS
        ]
        return self._select_best_split_candidate(sent, candidate_tokens, target_words)

    def _split_near_midpoint(self, sent, target_words):
        """
        Last-resort split near the target word count. This keeps large
        downscales moving even when dependency labels are not very helpful.
        """
        tokens = [t for t in sent if not t.is_space]
        alpha_tokens = [t for t in tokens if t.is_alpha]
        if len(alpha_tokens) < 10:
            return None

        preferred_alpha_count = min(max(target_words, 4), len(alpha_tokens) - 4)
        candidate_tokens = []
        alpha_count = 0
        for token in tokens:
            if token.is_alpha:
                alpha_count += 1

            remaining = len(alpha_tokens) - alpha_count
            if alpha_count < 4 or remaining < 4:
                continue

            if (
                token.text in {',', ';', ':'} or
                token.text.lower() in MID_SENTENCE_SPLIT_MARKERS or
                token.dep_ in ('conj', 'advcl', 'ccomp')
            ):
                candidate_tokens.append(token)

        if candidate_tokens:
            candidate_tokens.sort(
                key=lambda token: abs(
                    len([t for t in sent if t.is_alpha and t.i < token.i]) - preferred_alpha_count
                )
            )
            result = self._select_best_split_candidate(sent, candidate_tokens[:6], target_words)
            if result:
                return result

        return None

    # ------------------------------------------------------------------ #
    #  Change diffing: stable original->preview patches
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_diff_chunks(text):
        chunks = []
        for match in re.finditer(r'\S+\s*', text):
            raw = match.group(0)
            stripped = raw.strip()
            core = re.sub(r"^[^\w']+|[^\w']+$", '', stripped)
            if not core:
                core = stripped
            chunks.append({
                'raw': raw,
                'display': stripped,
                'normalized': core.lower(),
                'normalized_cased': core,
                'start': match.start(),
                'end': match.end(),
            })
        return chunks

    def _extract_sentence_chunks(self, text):
        if not text.strip():
            return []

        doc = nlp(text)
        chunks = []
        for sent in doc.sents:
            raw = sent.text
            normalized = re.sub(r'\s+', ' ', raw).strip().lower()
            chunks.append({
                'raw': raw,
                'normalized': normalized,
                'start': sent.start_char,
                'end': sent.end_char,
            })

        if chunks:
            return chunks

        return [{
            'raw': text,
            'normalized': re.sub(r'\s+', ' ', text).strip().lower(),
            'start': 0,
            'end': len(text),
        }]

    def _extract_paragraph_chunks(self, text):
        if not text.strip():
            return []

        chunks = []
        for match in re.finditer(r'.*?(?:\n\s*\n|$)', text, flags=re.S):
            raw = match.group(0)
            if not raw or not raw.strip():
                continue
            chunks.append({
                'raw': raw,
                'normalized': re.sub(r'\s+', ' ', raw).strip().lower(),
                'start': match.start(),
                'end': match.end(),
            })

        if chunks:
            return chunks

        return [{
            'raw': text,
            'normalized': re.sub(r'\s+', ' ', text).strip().lower(),
            'start': 0,
            'end': len(text),
        }]

    @staticmethod
    def _extract_single_word(raw_text):
        stripped = (raw_text or '').strip()
        if not stripped:
            return None

        words = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", stripped)
        if len(words) != 1:
            return None

        candidate = words[0]
        cleaned = re.sub(rf"^[^A-Za-z']*{re.escape(candidate)}[^A-Za-z']*$", candidate, stripped)
        if cleaned != candidate:
            return None
        return candidate

    def _fragment_stats(self, text):
        words = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text or '')
        if not words:
            return {'word_count': 0, 'avg_syllables': 0.0, 'sentence_count': 0}

        avg_syllables = (
            sum(self.text_processor.count_syllables(word.lower()) for word in words) / len(words)
        )
        sentence_count = max(1, len(re.findall(r'[.!?]+', text or '')))
        return {
            'word_count': len(words),
            'avg_syllables': avg_syllables,
            'sentence_count': sentence_count,
        }

    @staticmethod
    def _normalize_visible_span(text):
        if not text:
            return 0, 0

        leading = len(text) - len(text.lstrip())
        trailing = len(text) - len(text.rstrip())
        start = leading
        end = len(text) - trailing
        if end < start:
            end = start
        return start, end

    def _word_complexity_delta(self, original_display, replacement_display):
        original_word = self._extract_single_word(original_display)
        replacement_word = self._extract_single_word(replacement_display)
        if not original_word or not replacement_word:
            return None

        original_lookup = re.sub(r"[^\w]", '', original_word).lower()
        replacement_lookup = re.sub(r"[^\w]", '', replacement_word).lower()
        if not original_lookup or not replacement_lookup:
            return None

        original_freq = zipf_frequency(original_lookup, 'en')
        replacement_freq = zipf_frequency(replacement_lookup, 'en')
        original_syllables = self.text_processor.count_syllables(original_lookup)
        replacement_syllables = self.text_processor.count_syllables(replacement_lookup)
        return (
            (original_freq - replacement_freq) +
            0.35 * (replacement_syllables - original_syllables)
        )

    def _get_review_scope(self, original_display, replacement_display, change_type):
        if change_type in ('word_replacement', 'word_upgrade'):
            return 'word'

        if '\n\n' in (original_display or '') or '\n\n' in (replacement_display or ''):
            return 'paragraph'

        original_stats = self._fragment_stats(original_display)
        replacement_stats = self._fragment_stats(replacement_display)
        sentence_count = max(original_stats['sentence_count'], replacement_stats['sentence_count'])
        return 'sentence' if sentence_count <= STRUCTURAL_REVIEW_SENTENCE_LIMIT else 'paragraph'

    def _assess_patch_change_quality(self, original_display, replacement_display, change_type, going_up):
        review_scope = self._get_review_scope(original_display, replacement_display, change_type)
        local_going_up = self._infer_patch_direction(original_display, replacement_display, going_up)
        flags = []
        quality_score = 0.75
        original_stats = self._fragment_stats(original_display)
        replacement_stats = self._fragment_stats(replacement_display)

        if change_type in ('word_replacement', 'word_upgrade'):
            delta = self._word_complexity_delta(original_display, replacement_display)
            if delta is not None:
                quality_score = min(1.0, abs(delta) / max(WORD_QUALITY_DELTA, 0.01))
                if abs(delta) < WORD_QUALITY_DELTA:
                    flags.append('low_impact')
            if local_going_up != going_up:
                flags.append('direction_mismatch')
        else:
            should_validate_fragment = True
            if change_type in {'sentence_split', 'sentence_combine'}:
                local_word_count = max(original_stats['word_count'], replacement_stats['word_count'])
                if local_word_count <= 8:
                    should_validate_fragment = False

            if should_validate_fragment:
                invalid_sentences = self._collect_invalid_sentences(replacement_display)
                if invalid_sentences:
                    flags.append('invalid_sentence_structure')
            sentence_delta = abs(
                replacement_stats['sentence_count'] -
                original_stats['sentence_count']
            )
            quality_score = min(1.0, 0.55 + 0.15 * sentence_delta)

        accepted = not any(
            flag in {'direction_mismatch', 'invalid_sentence_structure'}
            for flag in flags
        )
        return {
            'accepted': accepted,
            'review_scope': review_scope,
            'local_going_up': local_going_up,
            'quality_flags': flags,
            'quality_score': round(max(0.0, min(1.0, quality_score)), 2),
        }

    def _infer_patch_direction(self, original_display, replacement_display, fallback_going_up):
        original_word = self._extract_single_word(original_display)
        replacement_word = self._extract_single_word(replacement_display)

        if original_word and replacement_word:
            complexity_delta = self._word_complexity_delta(original_display, replacement_display)
            if complexity_delta is None:
                complexity_delta = 0.0
            if complexity_delta > 0.15:
                return True
            if complexity_delta < -0.15:
                return False

        original_stats = self._fragment_stats(original_display)
        replacement_stats = self._fragment_stats(replacement_display)
        if original_stats['word_count'] and replacement_stats['word_count']:
            complexity_delta = (
                (replacement_stats['avg_syllables'] - original_stats['avg_syllables']) +
                0.1 * (replacement_stats['word_count'] - original_stats['word_count']) -
                0.3 * (replacement_stats['sentence_count'] - original_stats['sentence_count'])
            )
            if complexity_delta > 0.2:
                return True
            if complexity_delta < -0.2:
                return False

        return fallback_going_up

    @staticmethod
    def _approx_clause_count(text):
        """
        Rough clause-count approximation from clause-level connectors and
        sentence-final punctuation. Good enough for reason text; we don't
        need parse-tree precision here.
        """
        if not text:
            return 0
        sentence_count = max(1, len(re.findall(r'[.!?]+', text)))
        subordinators = re.findall(
            r"\b(?:because|although|though|while|whereas|since|when|if|unless|until|"
            r"before|after|as|which|who|whom|whose|that)\b",
            text,
            re.IGNORECASE,
        )
        commas = len(re.findall(r',', text))
        semicolons = len(re.findall(r';', text))
        return sentence_count + len(subordinators) + commas + semicolons

    def _extract_key_word_swaps(self, original_display, replacement_display, max_swaps=5):
        """
        Find clean single-word substitutions between two spans via word-level
        difflib. Used to enrich paragraph- and phrase-level change reasons
        with the specific word swaps the reader can see at a glance.
        """
        import difflib

        if not original_display or not replacement_display:
            return []

        original_tokens = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", original_display)
        replacement_tokens = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", replacement_display)
        if not original_tokens or not replacement_tokens:
            return []

        matcher = difflib.SequenceMatcher(
            None,
            [token.lower() for token in original_tokens],
            [token.lower() for token in replacement_tokens],
            autojunk=False,
        )

        swaps = []
        seen_pairs = set()

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != 'replace':
                continue
            if (i2 - i1) != 1 or (j2 - j1) != 1:
                continue

            before = original_tokens[i1]
            after = replacement_tokens[j1]
            before_lower = before.lower()
            after_lower = after.lower()

            if before_lower == after_lower:
                continue

            before_freq = zipf_frequency(before_lower, 'en')
            after_freq = zipf_frequency(after_lower, 'en')

            # Skip function-word churn (e.g. "the" <-> "a") — not a meaningful swap.
            if before_freq >= 6.5 and after_freq >= 6.5:
                continue

            key = (before_lower, after_lower)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)

            swaps.append({
                'before': before,
                'after': after,
                'frequency_before': round(before_freq, 2),
                'frequency_after': round(after_freq, 2),
            })
            if len(swaps) >= max_swaps:
                break

        return swaps

    def _extract_explanation_items(self, original_display, replacement_display, going_up, max_items=6):
        """
        Pull old-style explanation evidence out of broad paragraph rewrites
        without creating overlapping apply patches. These items are display
        evidence only; the paragraph patch remains the single source of truth
        for applying the selected candidate exactly.
        """
        import difflib

        original_tokens = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", original_display or '')
        replacement_tokens = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", replacement_display or '')
        if not original_tokens or not replacement_tokens:
            return []

        matcher = difflib.SequenceMatcher(
            None,
            [token.lower() for token in original_tokens],
            [token.lower() for token in replacement_tokens],
            autojunk=False,
        )

        items = []
        seen_pairs = set()
        function_words = {
            'a', 'an', 'the', 'and', 'or', 'but', 'so', 'for', 'nor', 'yet',
            'to', 'of', 'in', 'on', 'at', 'by', 'with', 'from', 'into', 'over',
            'under', 'as', 'than', 'that', 'which', 'who', 'whom', 'whose',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'am', 'do',
            'does', 'did', 'has', 'have', 'had', 'will', 'would', 'can',
            'could', 'may', 'might', 'must', 'shall', 'should', 'it', 'its',
            'he', 'she', 'they', 'them', 'we', 'us', 'you', 'i', 'me', 'my',
            'his', 'her', 'their', 'our', 'your',
        }

        def token_stats(token):
            lookup = re.sub(r"[^\w]", '', token or '').lower()
            return {
                'lookup': lookup,
                'frequency': zipf_frequency(lookup, 'en') if lookup else 0.0,
                'syllables': self.text_processor.count_syllables(lookup) if lookup else 0,
            }

        def is_useful_pair(before, after):
            before_stats = token_stats(before)
            after_stats = token_stats(after)
            if not before_stats['lookup'] or not after_stats['lookup']:
                return None
            if before_stats['lookup'] == after_stats['lookup']:
                return None
            if (before_stats['lookup'], after_stats['lookup']) in seen_pairs:
                return None
            if before_stats['lookup'] in function_words or after_stats['lookup'] in function_words:
                return None
            # Skip tiny function-word churn. It is visible, but it is not the
            # old explanation users found valuable.
            if before_stats['frequency'] >= 6.2 and after_stats['frequency'] >= 6.2:
                return None

            freq_delta = before_stats['frequency'] - after_stats['frequency']
            syl_delta = after_stats['syllables'] - before_stats['syllables']
            direction_hit = (freq_delta > 0.25 or syl_delta > 0) if going_up else (freq_delta < -0.25 or syl_delta < 0)
            if not direction_hit:
                return None

            impact = abs(freq_delta) + 0.35 * abs(syl_delta)
            if impact < 0.25:
                return None

            return {
                'kind': 'word_upgrade' if going_up else 'word_replacement',
                'before': before,
                'after': after,
                'frequency_before': round(before_stats['frequency'], 2),
                'frequency_after': round(after_stats['frequency'], 2),
                'syllables_before': before_stats['syllables'],
                'syllables_after': after_stats['syllables'],
                'impact': round(impact, 2),
                'text': self._format_explanation_item(
                    before,
                    after,
                    before_stats['frequency'],
                    after_stats['frequency'],
                    before_stats['syllables'],
                    after_stats['syllables'],
                    going_up,
                ),
            }

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if len(items) >= max_items:
                break
            if tag == 'equal':
                continue
            if tag == 'insert':
                inserted = [
                    token for token in replacement_tokens[j1:j2]
                    if token.lower() in {
                        'consequently', 'subsequently', 'therefore', 'however',
                        'furthermore', 'moreover', 'although', 'during', 'while'
                    }
                ]
                for token in inserted:
                    if len(items) >= max_items:
                        break
                    items.append({
                        'kind': 'connector_added',
                        'before': '',
                        'after': token,
                        'text': f"Added connector '{token}' to make relationships between ideas more explicit.",
                    })
                continue
            if tag != 'replace':
                continue

            before_block = original_tokens[i1:i2]
            after_block = replacement_tokens[j1:j2]
            candidates = []
            used_after = set()

            if len(before_block) == len(after_block):
                for before, after in zip(before_block, after_block):
                    item = is_useful_pair(before, after)
                    if item:
                        candidates.append(item)
            else:
                for before in before_block:
                    best_item = None
                    best_index = None
                    for after_index, after in enumerate(after_block):
                        if after_index in used_after:
                            continue
                        item = is_useful_pair(before, after)
                        if not item:
                            continue
                        if best_item is None or item['impact'] > best_item['impact']:
                            best_item = item
                            best_index = after_index
                    if best_item:
                        used_after.add(best_index)
                        candidates.append(best_item)

            candidates.sort(key=lambda item: item.get('impact', 0), reverse=True)
            for item in candidates:
                if len(items) >= max_items:
                    break
                seen_pairs.add((item['before'].lower(), item['after'].lower()))
                items.append(item)

        return items

    def _enrich_changes_with_display_items(self, changes, display_items):
        """Copy explanation metadata from display items onto the composable patches."""
        word_items = [d for d in display_items if d.get('review_scope') == 'word']
        for change in changes:
            if change.get('review_scope') != 'word':
                continue
            for item in word_items:
                if item.get('start') == change.get('start') and item.get('end') == change.get('end'):
                    if item.get('explanation_items'):
                        change['explanation_items'] = item['explanation_items']
                    if item.get('reason') and not change.get('reason'):
                        change['reason'] = item['reason']
                    break

    def _build_display_changes(self, original_text, rewritten_text, target_grade, going_up):
        """
        Post-processing diff: compare original and final rewritten text
        paragraph-by-paragraph to extract granular display changes.
        Runs after all rewriting is complete — purely for UI display.
        Each word swap becomes its own top-level change.
        """
        orig_paragraphs = [p.strip() for p in re.split(r'\n\s*\n', original_text) if p.strip()]
        new_paragraphs = [p.strip() for p in re.split(r'\n\s*\n', rewritten_text) if p.strip()]

        if not orig_paragraphs or not new_paragraphs:
            return []

        pairs = list(zip(orig_paragraphs, new_paragraphs))
        if len(orig_paragraphs) > len(new_paragraphs):
            last_orig = '\n\n'.join(orig_paragraphs[len(new_paragraphs) - 1:])
            pairs[-1] = (last_orig, pairs[-1][1])
        elif len(new_paragraphs) > len(orig_paragraphs):
            last_new = '\n\n'.join(new_paragraphs[len(orig_paragraphs) - 1:])
            pairs[-1] = (pairs[-1][0], last_new)

        changes = []
        change_id = 0
        orig_offset = 0
        new_offset = 0
        grade_label = f"Grade {target_grade}" if target_grade <= 12 else "College"
        candidate_score = self._selection_context.get('candidate_score', 0.8)

        for orig_para, new_para in pairs:
            orig_start = original_text.find(orig_para, orig_offset)
            new_start = rewritten_text.find(new_para, new_offset)
            if orig_start == -1:
                orig_start = orig_offset
            if new_start == -1:
                new_start = new_offset

            if orig_para == new_para:
                orig_offset = orig_start + len(orig_para)
                new_offset = new_start + len(new_para)
                continue

            explanation_items = self._extract_explanation_items(
                orig_para, new_para, going_up, max_items=30
            )

            for item in explanation_items:
                word_before = item['before']
                word_after = item['after']
                word_pos = orig_para.lower().find(word_before.lower())
                preview_pos = new_para.lower().find(word_after.lower())

                abs_start = orig_start + (word_pos if word_pos != -1 else 0)
                abs_preview = new_start + (preview_pos if preview_pos != -1 else 0)

                reason = self._format_explanation_item(
                    word_before, word_after,
                    item.get('frequency_before', 0), item.get('frequency_after', 0),
                    item.get('syllables_before', 0), item.get('syllables_after', 0),
                    going_up,
                )

                changes.append({
                    'type': item['kind'],
                    'original': word_before,
                    'simplified': word_after,
                    'original_text': word_before,
                    'replacement_text': word_after,
                    'position': abs_start,
                    'start': abs_start,
                    'end': abs_start + len(word_before),
                    'preview_start': abs_preview,
                    'preview_end': abs_preview + len(word_after),
                    'review_scope': 'word',
                    'direction': 'up' if going_up else 'down',
                    'quality_score': 0.8,
                    'quality_flags': [],
                    'rule_id': 'display.word_upgrade' if going_up else 'display.word_swap',
                    'reason_code': 'raise_vocabulary_difficulty' if going_up else 'use_more_common_word',
                    'evidence': {
                        'target_grade': target_grade,
                        'direction': 'up' if going_up else 'down',
                        'review_scope': 'word',
                        'word_before': word_before,
                        'word_after': word_after,
                        'frequency_before': item.get('frequency_before', 0),
                        'frequency_after': item.get('frequency_after', 0),
                        'syllables_before': item.get('syllables_before', 0),
                        'syllables_after': item.get('syllables_after', 0),
                        'candidate_score': candidate_score,
                    },
                    'candidate_score': candidate_score,
                    'reason': reason,
                    'id': change_id,
                })
                change_id += 1

            orig_sentences = len(re.findall(r'[.!?]+', orig_para)) or 1
            new_sentences = len(re.findall(r'[.!?]+', new_para)) or 1
            if orig_sentences != new_sentences:
                struct_type = 'sentence_combine' if going_up else 'sentence_split'
                struct_details = []
                orig_semicolons = orig_para.count(';')
                new_semicolons = new_para.count(';')
                if new_semicolons > orig_semicolons:
                    struct_details.append(f"{new_semicolons - orig_semicolons} semicolon(s) inserted to join independent clauses")
                elif orig_semicolons > new_semicolons:
                    struct_details.append(f"{orig_semicolons - new_semicolons} semicolon(s) replaced with periods")
                if new_sentences < orig_sentences:
                    struct_details.append(f"{orig_sentences - new_sentences} sentence(s) combined into longer clauses")
                elif new_sentences > orig_sentences:
                    struct_details.append(f"{new_sentences - orig_sentences} sentence(s) split for shorter, clearer phrasing")
                struct_reason = "; ".join(struct_details) + f" ({orig_sentences} → {new_sentences} sentences)." if struct_details else f"Sentence structure changed ({orig_sentences} → {new_sentences} sentences)."

                changes.append({
                    'type': struct_type,
                    'original': '',
                    'simplified': '',
                    'original_text': orig_para,
                    'replacement_text': new_para,
                    'position': orig_start,
                    'start': orig_start,
                    'end': orig_start + len(orig_para),
                    'preview_start': new_start,
                    'preview_end': new_start + len(new_para),
                    'review_scope': 'sentence',
                    'direction': 'up' if going_up else 'down',
                    'quality_score': 0.8,
                    'quality_flags': [],
                    'rule_id': 'display.sentence_split' if not going_up else 'display.sentence_combine',
                    'reason_code': 'shorten_sentence_for_target' if not going_up else 'increase_clause_density',
                    'evidence': {
                        'target_grade': target_grade,
                        'direction': 'up' if going_up else 'down',
                        'review_scope': 'sentence',
                        'sentence_count_before': orig_sentences,
                        'sentence_count_after': new_sentences,
                        'candidate_score': candidate_score,
                    },
                    'candidate_score': candidate_score,
                    'reason': struct_reason,
                    'id': change_id,
                })
                change_id += 1

            orig_offset = orig_start + len(orig_para)
            new_offset = new_start + len(new_para)

        return changes

    @staticmethod
    def _format_explanation_item(before, after, freq_before, freq_after, syl_before, syl_after, going_up):
        if going_up:
            return (
                f"Replaced '{before}' with '{after}' — more formal/academic "
                f"(Zipf {freq_before:.1f} -> {freq_after:.1f}, "
                f"{syl_before} -> {syl_after} syllable(s))."
            )
        return (
            f"Replaced '{before}' with '{after}' — easier and more familiar "
            f"(Zipf {freq_before:.1f} -> {freq_after:.1f}, "
            f"{syl_before} -> {syl_after} syllable(s))."
        )

    def _build_reason_metadata(
        self,
        original_display,
        replacement_display,
        target_grade,
        going_up,
        change_type,
        review_scope,
        quality,
    ):
        original_stats = self._fragment_stats(original_display)
        replacement_stats = self._fragment_stats(replacement_display)
        local_going_up = quality['local_going_up']
        candidate_score = self._selection_context.get('candidate_score')

        metadata = {
            'rule_id': 'selection.patch_rewrite',
            'reason_code': 'reshape_text_for_target',
            'evidence': {
                'target_grade': target_grade,
                'direction': 'up' if local_going_up else 'down',
                'review_scope': review_scope,
                'word_count_before': original_stats['word_count'],
                'word_count_after': replacement_stats['word_count'],
                'sentence_count_before': original_stats['sentence_count'],
                'sentence_count_after': replacement_stats['sentence_count'],
                'boundary_count_before': len(re.findall(r'[.!?]+', original_display or '')),
                'boundary_count_after': len(re.findall(r'[.!?]+', replacement_display or '')),
                'clause_count_before': self._approx_clause_count(original_display),
                'clause_count_after': self._approx_clause_count(replacement_display),
                'avg_syllables_before': round(original_stats['avg_syllables'], 2),
                'avg_syllables_after': round(replacement_stats['avg_syllables'], 2),
                'candidate_score': candidate_score if candidate_score is not None else quality['quality_score'],
            },
        }

        if change_type in ('word_replacement', 'word_upgrade'):
            original_word = self._extract_single_word(original_display) or original_display.strip()
            replacement_word = self._extract_single_word(replacement_display) or replacement_display.strip()
            original_lookup = re.sub(r"[^\w]", '', original_word).lower()
            replacement_lookup = re.sub(r"[^\w]", '', replacement_word).lower()
            original_freq = zipf_frequency(original_lookup, 'en') if original_lookup else 0.0
            replacement_freq = zipf_frequency(replacement_lookup, 'en') if replacement_lookup else 0.0
            original_syllables = self.text_processor.count_syllables(original_lookup) if original_lookup else 0
            replacement_syllables = self.text_processor.count_syllables(replacement_lookup) if replacement_lookup else 0
            metadata.update({
                'rule_id': 'lexical.academic_upgrade' if local_going_up else 'lexical.common_word_swap',
                'reason_code': 'raise_vocabulary_difficulty' if local_going_up else 'use_more_common_word',
                'evidence': {
                    **metadata['evidence'],
                    'word_before': original_word,
                    'word_after': replacement_word,
                    'frequency_before': round(original_freq, 2),
                    'frequency_after': round(replacement_freq, 2),
                    'syllables_before': original_syllables,
                    'syllables_after': replacement_syllables,
                },
            })
            return metadata

        structural_explanation_items = self._extract_explanation_items(
            original_display,
            replacement_display,
            local_going_up,
        ) if review_scope == 'paragraph' else []

        if change_type == 'sentence_split':
            metadata.update({
                'rule_id': 'syntactic.sentence_split',
                'reason_code': 'shorten_sentence_for_target',
                'evidence': {
                    **metadata['evidence'],
                    'explanation_items': structural_explanation_items,
                },
            })
            return metadata

        if change_type == 'sentence_combine':
            metadata.update({
                'rule_id': 'syntactic.sentence_combine',
                'reason_code': 'increase_clause_density',
                'evidence': {
                    **metadata['evidence'],
                    'explanation_items': structural_explanation_items,
                },
            })
            return metadata

        key_swaps = self._extract_key_word_swaps(original_display, replacement_display)
        explanation_items = structural_explanation_items or self._extract_explanation_items(
            original_display,
            replacement_display,
            local_going_up,
        )
        metadata.update({
            'rule_id': 'discourse.connector_rewrite' if review_scope == 'sentence' else 'discourse.paragraph_reframe',
            'reason_code': 'improve_flow_for_target',
            'evidence': {
                **metadata['evidence'],
                'key_swaps': key_swaps,
                'explanation_items': explanation_items,
            },
        })
        return metadata

    def _build_patch_reason(self, metadata):
        evidence = metadata['evidence']
        target_grade = evidence['target_grade']
        reason_code = metadata['reason_code']
        review_scope = evidence.get('review_scope', 'sentence')
        scope_label = 'paragraph' if review_scope == 'paragraph' else 'sentence'
        direction = evidence.get('direction', 'down')

        if reason_code in {'use_more_common_word', 'raise_vocabulary_difficulty'}:
            word_before = evidence['word_before']
            word_after = evidence['word_after']
            freq_before = evidence.get('frequency_before', 0.0)
            freq_after = evidence.get('frequency_after', 0.0)
            syl_before = evidence.get('syllables_before', 0)
            syl_after = evidence.get('syllables_after', 0)

            if reason_code == 'use_more_common_word':
                return (
                    f"Replaced '{word_before}' with '{word_after}' — '{word_after}' is a more common, "
                    f"easier synonym (zipf frequency {freq_after:.1f} vs {freq_before:.1f}, "
                    f"{syl_after} syllable(s) vs {syl_before}) that Grade {target_grade} readers recognize quickly."
                )
            return (
                f"Replaced '{word_before}' with '{word_after}' — '{word_after}' is a more formal, academic "
                f"synonym (less common, zipf frequency {freq_after:.1f} vs {freq_before:.1f}, "
                f"{syl_after} syllable(s) vs {syl_before}) expected at Grade {target_grade}."
            )

        clauses_before = evidence.get('clause_count_before', evidence['sentence_count_before'])
        clauses_after = evidence.get('clause_count_after', evidence['sentence_count_after'])
        words_before = evidence.get('word_count_before', 0)

        if reason_code == 'shorten_sentence_for_target':
            if review_scope == 'paragraph':
                explanation_items = evidence.get('explanation_items') or []
                if explanation_items:
                    examples = "; ".join(item.get('text', '') for item in explanation_items[:3] if item.get('text'))
                    return (
                        f"Split and simplified this paragraph for Grade {target_grade}: "
                        f"sentence structure became easier ({clauses_before} -> {clauses_after} clause units), "
                        f"with concrete vocabulary evidence such as {examples}"
                    )
                return (
                    f"Restructured this paragraph into shorter sentence units so the ideas are easier "
                    f"to follow at Grade {target_grade}."
                )
            return (
                f"Split the sentence because it was long ({words_before} words with about "
                f"{clauses_before} clauses) — too much subordination to follow at Grade {target_grade}. "
                f"Shorter sentences with fewer clauses are easier to read."
            )

        if reason_code == 'increase_clause_density':
            if review_scope == 'paragraph':
                explanation_items = evidence.get('explanation_items') or []
                if explanation_items:
                    examples = "; ".join(item.get('text', '') for item in explanation_items[:3] if item.get('text'))
                    return (
                        f"Combined and upgraded this paragraph for Grade {target_grade}: "
                        f"sentence structure became denser ({clauses_before} -> {clauses_after} clause units), "
                        f"with concrete vocabulary evidence such as {examples}"
                    )
                return (
                    f"Restructured this paragraph into denser sentence groupings so the ideas read "
                    f"at Grade {target_grade} complexity."
                )
            return (
                f"Combined short sentences into one with about {clauses_after} clauses — "
                f"Grade {target_grade} expects denser subordination and longer sentences, "
                f"so merging related ideas raises the complexity to fit."
            )

        swaps = evidence.get('key_swaps') or []
        explanation_items = evidence.get('explanation_items') or []
        action = 'Raised' if direction == 'up' else 'Simplified'

        if explanation_items:
            examples = "; ".join(item.get('text', '') for item in explanation_items[:3] if item.get('text'))
            clause_delta = ''
            if clauses_before != clauses_after:
                direction_verb = 'raising' if clauses_after > clauses_before else 'reducing'
                clause_delta = (
                    f" Clause structure also changed ({clauses_before} -> {clauses_after}), "
                    f"{direction_verb} sentence complexity."
                )
            return (
                f"{action} this {scope_label} for Grade {target_grade} with visible word-level evidence: "
                f"{examples}{clause_delta}"
            )

        if swaps:
            def _format_swap(swap):
                fa = swap.get('frequency_after')
                fb = swap.get('frequency_before')
                if fa is not None and fb is not None:
                    return f"'{swap['before']}' -> '{swap['after']}' (freq {fb:.1f} -> {fa:.1f})"
                return f"'{swap['before']}' -> '{swap['after']}'"

            formatted = ", ".join(_format_swap(swap) for swap in swaps[:5])
            clause_delta = ''
            if clauses_before != clauses_after:
                direction_verb = 'raising' if clauses_after > clauses_before else 'reducing'
                clause_delta = (
                    f" Also restructured clauses ({clauses_before} -> {clauses_after}), "
                    f"{direction_verb} sentence complexity for the target."
                )
            synonym_rationale = (
                'more common, easier synonyms' if direction == 'down' else 'more formal, academic synonyms'
            )
            return (
                f"{action} the vocabulary in this {scope_label} with {synonym_rationale} for Grade {target_grade}. "
                f"Replaced: {formatted}.{clause_delta}"
            )

        if clauses_before != clauses_after:
            direction_verb = 'raising' if clauses_after > clauses_before else 'reducing'
            return (
                f"Restructured clauses in this {scope_label} ({clauses_before} -> {clauses_after}), "
                f"{direction_verb} sentence complexity to fit Grade {target_grade}."
            )

        avg_syl_before = evidence.get('avg_syllables_before', 0.0)
        avg_syl_after = evidence.get('avg_syllables_after', 0.0)
        words_after = evidence.get('word_count_after', words_before)
        if direction == 'up':
            return (
                f"Rephrased this {scope_label} to sound more formal and academically dense for Grade {target_grade} "
                f"(avg syllables {avg_syl_before:.2f} -> {avg_syl_after:.2f}, edited span {words_before} -> {words_after} words)."
            )
        return (
            f"Rephrased this {scope_label} to use clearer, more familiar wording for Grade {target_grade} "
            f"(avg syllables {avg_syl_before:.2f} -> {avg_syl_after:.2f}, edited span {words_before} -> {words_after} words)."
        )

    def _classify_patch_change(self, original_display, replacement_display, going_up):
        original_word = self._extract_single_word(original_display)
        replacement_word = self._extract_single_word(replacement_display)
        if original_word and replacement_word and original_word.lower() != replacement_word.lower():
            return (
                'word_upgrade'
                if self._infer_patch_direction(original_display, replacement_display, going_up)
                else 'word_replacement'
            )

        original_sentences = len(re.findall(r'[.!?]+', original_display or ''))
        replacement_sentences = len(re.findall(r'[.!?]+', replacement_display or ''))
        if replacement_sentences > original_sentences:
            return 'sentence_split'
        if replacement_sentences < original_sentences:
            return 'sentence_combine'

        return 'phrase_rewrite'

    @staticmethod
    def _extract_patch_words(text):
        return re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text or '')

    def _is_low_signal_patch_change(
        self,
        original_display,
        replacement_display,
        change_type,
        review_scope,
        allow_fallback=False,
    ):
        original_words = self._extract_patch_words(original_display)
        replacement_words = self._extract_patch_words(replacement_display)
        original_core = [word.lower() for word in original_words]
        replacement_core = [word.lower() for word in replacement_words]

        if original_core == replacement_core:
            return True

        max_words = max(len(original_words), len(replacement_words))
        min_words = min(len(original_words), len(replacement_words))

        if change_type == 'phrase_rewrite' and max_words <= 1:
            return True

        if not allow_fallback:
            return False

        if change_type == 'phrase_rewrite' and review_scope == 'paragraph':
            if max_words <= 4:
                return True
            if min_words <= 1 and max_words <= 6:
                return True
            if min_words == 0 and max_words <= 6:
                return True

        contentful_before = [
            word for word in original_words
            if zipf_frequency(word.lower(), 'en') < 5.8
        ]
        contentful_after = [
            word for word in replacement_words
            if zipf_frequency(word.lower(), 'en') < 5.8
        ]
        if not contentful_before and not contentful_after and max_words <= 4:
            return True

        return False

    def _build_patch_change(
        self,
        original_raw,
        replacement_raw,
        start,
        end,
        preview_start,
        target_grade,
        going_up,
        allow_fallback=False
    ):
        if original_raw == replacement_raw:
            return None

        original_display = original_raw.strip() or original_raw
        replacement_display = replacement_raw.strip() or replacement_raw

        if not original_display and not replacement_display:
            return None

        change_type = self._classify_patch_change(original_display, replacement_display, going_up)
        quality = self._assess_patch_change_quality(
            original_display,
            replacement_display,
            change_type,
            going_up
        )
        if not quality['accepted'] and not allow_fallback:
            return None
        if allow_fallback and not quality['accepted']:
            quality = {
                **quality,
                'review_scope': 'paragraph',
                'quality_flags': quality['quality_flags'] + ['coarse_review'],
                'quality_score': min(quality['quality_score'], 0.35),
            }

        if self._is_low_signal_patch_change(
            original_display,
            replacement_display,
            change_type,
            quality['review_scope'],
            allow_fallback=allow_fallback,
        ):
            return None

        visible_preview_start, visible_preview_end = self._normalize_visible_span(replacement_raw)
        metadata = self._build_reason_metadata(
            original_display,
            replacement_display,
            target_grade,
            going_up,
            change_type,
            quality['review_scope'],
            quality,
        )
        top_candidates = self._selection_context.get('selection_summary', {}).get('top_candidates', [])
        selection_flags = list((top_candidates[0] if top_candidates else {}).get('validation_flags', []))
        validation_flags = quality['quality_flags'] + [
            flag for flag in selection_flags if flag not in quality['quality_flags']
        ]

        return {
            'type': change_type,
            'original': original_display,
            'simplified': replacement_display,
            'original_text': original_raw,
            'replacement_text': replacement_raw,
            'position': start,
            'start': start,
            'end': end,
            'preview_start': preview_start + visible_preview_start,
            'preview_end': preview_start + visible_preview_end,
            'review_scope': quality['review_scope'],
            'direction': 'up' if quality['local_going_up'] else 'down',
            'quality_score': quality['quality_score'],
            'quality_flags': quality['quality_flags'],
            'rule_id': metadata['rule_id'],
            'reason_code': metadata['reason_code'],
            'evidence': metadata['evidence'],
            'candidate_score': metadata['evidence']['candidate_score'],
            'validation_flags': validation_flags,
            'explanation_items': metadata['evidence'].get('explanation_items', []),
            'reason': self._build_patch_reason(metadata),
        }

    def _assign_dependency_groups(self, changes):
        if not changes:
            return changes

        group_ids = {}
        structural_changes = sorted(
            [
                change for change in changes
                if change.get('type') in {'sentence_split', 'sentence_combine'}
            ],
            key=lambda change: (change.get('start', 0), change.get('end', 0), change.get('id', 0)),
        )
        current_group = []
        group_index = 0

        def flush_group():
            nonlocal group_index
            if len(current_group) <= 1:
                return
            group_index += 1
            group_id = f"struct-{group_index}"
            for grouped_change in current_group:
                group_ids[grouped_change['id']] = group_id

        for change in structural_changes:
            if not current_group:
                current_group = [change]
                continue

            previous = current_group[-1]
            overlaps = (
                change.get('start', 0) < previous.get('end', 0) and
                previous.get('start', 0) < change.get('end', 0)
            )
            if overlaps and change.get('direction') == previous.get('direction'):
                current_group.append(change)
                continue

            flush_group()
            current_group = [change]

        flush_group()

        grouped_changes = []
        for change in changes:
            updated = dict(change)
            dependency_group_id = group_ids.get(change['id'])
            if dependency_group_id:
                updated['dependency_group_id'] = dependency_group_id
            grouped_changes.append(updated)

        return grouped_changes

    @staticmethod
    def _chunk_pair_has_meaningful_diff(original_chunk, rewritten_chunk):
        if original_chunk['raw'] == rewritten_chunk['raw']:
            return False

        original_display = (original_chunk.get('display') or '').strip()
        rewritten_display = (rewritten_chunk.get('display') or '').strip()
        if original_display == rewritten_display:
            return False

        original_core = re.sub(r"[^A-Za-z0-9']+", '', original_display).lower()
        rewritten_core = re.sub(r"[^A-Za-z0-9']+", '', rewritten_display).lower()
        return original_core != rewritten_core

    def _collect_local_patch_segments(self, opcodes, original_chunks, rewritten_chunks):
        segments = []

        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'equal':
                chunk_count = min(i2 - i1, j2 - j1)
                run_start = None

                for offset in range(chunk_count):
                    if self._chunk_pair_has_meaningful_diff(
                        original_chunks[i1 + offset],
                        rewritten_chunks[j1 + offset],
                    ):
                        if run_start is None:
                            run_start = offset
                    elif run_start is not None:
                        segments.append((
                            i1 + run_start,
                            i1 + offset,
                            j1 + run_start,
                            j1 + offset,
                        ))
                        run_start = None

                if run_start is not None:
                    segments.append((
                        i1 + run_start,
                        i1 + chunk_count,
                        j1 + run_start,
                        j1 + chunk_count,
                    ))
                continue

            segments.append((i1, i2, j1, j2))

        if not segments:
            return []

        merged_segments = [list(segments[0])]
        for i1, i2, j1, j2 in segments[1:]:
            previous = merged_segments[-1]
            if i1 <= previous[1] + 1 and j1 <= previous[3] + 1:
                previous[1] = max(previous[1], i2)
                previous[3] = max(previous[3], j2)
            else:
                merged_segments.append([i1, i2, j1, j2])

        return [tuple(segment) for segment in merged_segments]

    def _diff_change_block(
        self,
        original_block,
        rewritten_block,
        target_grade,
        going_up,
        original_offset=0,
        rewritten_offset=0,
        prefer_sentence_level=False,
    ):
        import difflib

        if original_block == rewritten_block:
            return []

        original_chunks = self._extract_diff_chunks(original_block)
        rewritten_chunks = self._extract_diff_chunks(rewritten_block)

        if not original_chunks or not rewritten_chunks:
            change = self._build_patch_change(
                original_block,
                rewritten_block,
                original_offset,
                original_offset + len(original_block),
                rewritten_offset,
                target_grade,
                going_up,
                allow_fallback=True
            )
            return [change] if change else []

        matcher = difflib.SequenceMatcher(
            None,
            [chunk['normalized_cased'] for chunk in original_chunks],
            [chunk['normalized_cased'] for chunk in rewritten_chunks],
            autojunk=False
        )
        opcodes = matcher.get_opcodes()
        segments = self._collect_local_patch_segments(opcodes, original_chunks, rewritten_chunks)
        if not segments:
            change = self._build_patch_change(
                original_block,
                rewritten_block,
                original_offset,
                original_offset + len(original_block),
                rewritten_offset,
                target_grade,
                going_up,
                allow_fallback=True
            )
            return [change] if change else []

        changes = []
        original_length = len(original_block)
        rewritten_length = len(rewritten_block)

        for i1, i2, j1, j2 in segments:
            local_start = original_chunks[i1]['start'] if i1 < len(original_chunks) else original_length
            local_end = original_chunks[i2 - 1]['end'] if i2 > i1 else local_start
            local_preview_start = rewritten_chunks[j1]['start'] if j1 < len(rewritten_chunks) else rewritten_length
            local_preview_end = rewritten_chunks[j2 - 1]['end'] if j2 > j1 else local_preview_start

            change = self._build_patch_change(
                original_block[local_start:local_end],
                rewritten_block[local_preview_start:local_preview_end],
                original_offset + local_start,
                original_offset + local_end,
                rewritten_offset + local_preview_start,
                target_grade,
                going_up
            )
            if not change:
                change = self._build_patch_change(
                    original_block[local_start:local_end],
                    rewritten_block[local_preview_start:local_preview_end],
                    original_offset + local_start,
                    original_offset + local_end,
                    rewritten_offset + local_preview_start,
                    target_grade,
                    going_up,
                    allow_fallback=True
                )
            if change:
                changes.append(change)

        if not changes:
            change = self._build_patch_change(
                original_block,
                rewritten_block,
                original_offset,
                original_offset + len(original_block),
                rewritten_offset,
                target_grade,
                going_up,
                allow_fallback=True
            )
            return [change] if change else []

        return changes

    def _diff_sentence_changes(
        self,
        original_text,
        rewritten_text,
        target_grade,
        going_up,
        original_offset=0,
        rewritten_offset=0,
        prefer_sentence_level=False,
    ):
        """Diff a paragraph-sized block sentence-by-sentence."""
        import difflib

        if original_text == rewritten_text:
            return []

        original_sentences = self._extract_sentence_chunks(original_text)
        rewritten_sentences = self._extract_sentence_chunks(rewritten_text)

        if not original_sentences or not rewritten_sentences:
            return self._diff_change_block(
                original_text,
                rewritten_text,
                target_grade,
                going_up,
                original_offset=original_offset,
                rewritten_offset=rewritten_offset,
                prefer_sentence_level=prefer_sentence_level,
            )

        matcher = difflib.SequenceMatcher(
            None,
            [sentence['normalized'] for sentence in original_sentences],
            [sentence['normalized'] for sentence in rewritten_sentences],
            autojunk=False
        )

        changes = []
        original_length = len(original_text)
        rewritten_length = len(rewritten_text)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                continue

            if prefer_sentence_level:
                sentence_aligned_changes = self._diff_sentence_block_by_order(
                    original_text=original_text,
                    rewritten_text=rewritten_text,
                    original_sentences=original_sentences[i1:i2],
                    rewritten_sentences=rewritten_sentences[j1:j2],
                    target_grade=target_grade,
                    going_up=going_up,
                    original_offset=original_offset,
                    rewritten_offset=rewritten_offset,
                )
                if sentence_aligned_changes:
                    changes.extend(sentence_aligned_changes)
                    continue

            original_start = original_sentences[i1]['start'] if i1 < len(original_sentences) else original_length
            original_end = original_sentences[i2 - 1]['end'] if i2 > i1 else original_start
            rewritten_start = rewritten_sentences[j1]['start'] if j1 < len(rewritten_sentences) else rewritten_length
            rewritten_end = rewritten_sentences[j2 - 1]['end'] if j2 > j1 else rewritten_start
            original_span_count = i2 - i1
            rewritten_span_count = j2 - j1

            if original_span_count != rewritten_span_count:
                structural_change = self._build_patch_change(
                    original_text[original_start:original_end],
                    rewritten_text[rewritten_start:rewritten_end],
                    original_offset + original_start,
                    original_offset + original_end,
                    rewritten_offset + rewritten_start,
                    target_grade,
                    going_up,
                    allow_fallback=True,
                )
                if structural_change:
                    changes.append(structural_change)
                    continue

            block_changes = self._diff_change_block(
                original_text[original_start:original_end],
                rewritten_text[rewritten_start:rewritten_end],
                target_grade,
                going_up,
                original_offset=original_offset + original_start,
                rewritten_offset=rewritten_offset + rewritten_start,
                prefer_sentence_level=prefer_sentence_level,
            )

            if not block_changes:
                change = self._build_patch_change(
                    original_text[original_start:original_end],
                    rewritten_text[rewritten_start:rewritten_end],
                    original_offset + original_start,
                    original_offset + original_end,
                    rewritten_offset + rewritten_start,
                    target_grade,
                    going_up,
                    allow_fallback=True
                )
                if change:
                    block_changes = [change]

            changes.extend(block_changes)

        return changes

    def _diff_sentence_block_by_order(
        self,
        original_text,
        rewritten_text,
        original_sentences,
        rewritten_sentences,
        target_grade,
        going_up,
        original_offset=0,
        rewritten_offset=0,
    ):
        if not original_sentences or not rewritten_sentences:
            return None

        pairings = []
        original_count = len(original_sentences)
        rewritten_count = len(rewritten_sentences)

        if original_count == rewritten_count:
            for index in range(original_count):
                pairings.append((index, index, 1, 1))
        elif rewritten_count == original_count + 1 and original_count >= 2:
            for index in range(original_count - 1):
                pairings.append((index, index, 1, 1))
            pairings.append((original_count - 1, original_count - 1, 1, 2))
        elif original_count == rewritten_count + 1 and rewritten_count >= 2:
            for index in range(rewritten_count - 1):
                pairings.append((index, index, 1, 1))
            pairings.append((rewritten_count - 1, rewritten_count - 1, 2, 1))
        else:
            return None

        changes = []
        for original_index, rewritten_index, original_span_count, rewritten_span_count in pairings:
            original_start = original_sentences[original_index]['start']
            original_end = original_sentences[original_index + original_span_count - 1]['end']
            rewritten_start = rewritten_sentences[rewritten_index]['start']
            rewritten_end = rewritten_sentences[rewritten_index + rewritten_span_count - 1]['end']

            block_changes = self._diff_change_block(
                original_text[original_start:original_end],
                rewritten_text[rewritten_start:rewritten_end],
                target_grade,
                going_up,
                original_offset=original_offset + original_start,
                rewritten_offset=rewritten_offset + rewritten_start,
                prefer_sentence_level=True,
            )
            if not block_changes:
                change = self._build_patch_change(
                    original_text[original_start:original_end],
                    rewritten_text[rewritten_start:rewritten_end],
                    original_offset + original_start,
                    original_offset + original_end,
                    rewritten_offset + rewritten_start,
                    target_grade,
                    going_up,
                    allow_fallback=True,
                )
                if change:
                    block_changes = [change]

            changes.extend(block_changes)

        return changes or None

    def _fuzzy_sentence_diff(self, original_text, rewritten_text, target_grade, going_up):
        """Fallback diff using word-overlap similarity to align sentences.

        When SequenceMatcher fails because the LLM rewrote sentences too
        heavily, pair each original sentence with the most similar rewritten
        sentence and produce per-sentence changes.
        """
        orig_sents = self._extract_sentence_chunks(original_text)
        new_sents = self._extract_sentence_chunks(rewritten_text)
        if not orig_sents or not new_sents:
            return None

        def _word_set(text):
            return set(w.lower() for w in text.split() if len(w) > 2)

        orig_words = [_word_set(s['raw']) for s in orig_sents]
        new_words = [_word_set(s['raw']) for s in new_sents]

        used_new = set()
        pairings = []

        for i, ow in enumerate(orig_words):
            best_j, best_sim = -1, 0.0
            for j, nw in enumerate(new_words):
                if j in used_new or not ow or not nw:
                    continue
                overlap = len(ow & nw)
                sim = overlap / max(len(ow | nw), 1)
                if sim > best_sim:
                    best_sim = sim
                    best_j = j
            if best_j >= 0 and best_sim >= 0.25:
                pairings.append((i, best_j, best_sim))
                used_new.add(best_j)

        if not pairings:
            return None

        grade_label = 'College' if target_grade >= 13 else f'Grade {target_grade}'
        changes = []
        for orig_idx, new_idx, _sim in pairings:
            orig_sent = orig_sents[orig_idx]
            new_sent = new_sents[new_idx]
            if orig_sent['raw'].strip() == new_sent['raw'].strip():
                continue

            change = self._build_patch_change(
                orig_sent['raw'],
                new_sent['raw'],
                orig_sent['start'],
                orig_sent['end'],
                new_sent['start'],
                target_grade,
                going_up,
                allow_fallback=True,
            )
            if change:
                changes.append(change)

        matched_orig = {p[0] for p in pairings}
        unmatched_orig = [i for i in range(len(orig_sents)) if i not in matched_orig]
        for i in unmatched_orig:
            nearest_idx = None
            nearest_dist = float('inf')
            for ci, change in enumerate(changes):
                change_start = change.get('start', 0)
                change_end = change.get('end', 0)
                dist = min(
                    abs(orig_sents[i]['start'] - change_end),
                    abs(orig_sents[i]['end'] - change_start),
                )
                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest_idx = ci
            if nearest_idx is not None:
                neighbor = changes[nearest_idx]
                new_start = min(neighbor['start'], orig_sents[i]['start'])
                new_end = max(neighbor['end'], orig_sents[i]['end'])
                neighbor['start'] = new_start
                neighbor['position'] = new_start
                neighbor['end'] = new_end
                neighbor['original'] = original_text[new_start:new_end].strip()
                neighbor['original_text'] = original_text[new_start:new_end]

        if len(changes) >= 2:
            for idx, c in enumerate(changes):
                c['id'] = idx
            return changes

        return None

    def _diff_changes(
        self,
        original_text,
        rewritten_text,
        target_grade,
        going_up,
        prefer_sentence_level=False,
    ):
        """
        Build stable patches anchored to the ORIGINAL text.

        Diff paragraphs first, then sentences inside each changed paragraph,
        and only fall back to word-level patches when the local edit is a clean
        one-word substitution. This keeps previews reviewable instead of
        turning large structural rewrites into misleading micro-diffs.
        """
        import difflib

        if original_text == rewritten_text:
            return []

        original_paragraphs = self._extract_paragraph_chunks(original_text)
        rewritten_paragraphs = self._extract_paragraph_chunks(rewritten_text)

        if not original_paragraphs or not rewritten_paragraphs:
            changes = self._diff_sentence_changes(
                original_text,
                rewritten_text,
                target_grade,
                going_up,
                prefer_sentence_level=prefer_sentence_level,
            )
            for index, change in enumerate(changes):
                change['id'] = index
            return changes

        matcher = difflib.SequenceMatcher(
            None,
            [paragraph['normalized'] for paragraph in original_paragraphs],
            [paragraph['normalized'] for paragraph in rewritten_paragraphs],
            autojunk=False
        )

        changes = []
        original_length = len(original_text)
        rewritten_length = len(rewritten_text)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                continue

            if tag == 'replace' and (i2 - i1) == (j2 - j1) and (i2 - i1) > 1:
                for paragraph_index in range(i2 - i1):
                    original_paragraph = original_paragraphs[i1 + paragraph_index]
                    rewritten_paragraph = rewritten_paragraphs[j1 + paragraph_index]
                    paragraph_changes = self._diff_sentence_changes(
                        original_paragraph['raw'],
                        rewritten_paragraph['raw'],
                        target_grade,
                        going_up,
                        original_offset=original_paragraph['start'],
                        rewritten_offset=rewritten_paragraph['start'],
                        prefer_sentence_level=prefer_sentence_level,
                    )
                    if not paragraph_changes:
                        change = self._build_patch_change(
                            original_paragraph['raw'],
                            rewritten_paragraph['raw'],
                            original_paragraph['start'],
                            original_paragraph['end'],
                            rewritten_paragraph['start'],
                            target_grade,
                            going_up,
                            allow_fallback=True
                        )
                        if change:
                            paragraph_changes = [change]
                    changes.extend(paragraph_changes)
                continue

            original_start = original_paragraphs[i1]['start'] if i1 < len(original_paragraphs) else original_length
            original_end = original_paragraphs[i2 - 1]['end'] if i2 > i1 else original_start
            rewritten_start = rewritten_paragraphs[j1]['start'] if j1 < len(rewritten_paragraphs) else rewritten_length
            rewritten_end = rewritten_paragraphs[j2 - 1]['end'] if j2 > j1 else rewritten_start

            paragraph_changes = self._diff_sentence_changes(
                original_text[original_start:original_end],
                rewritten_text[rewritten_start:rewritten_end],
                target_grade,
                going_up,
                original_offset=original_start,
                rewritten_offset=rewritten_start,
                prefer_sentence_level=prefer_sentence_level,
            )

            if not paragraph_changes:
                change = self._build_patch_change(
                    original_text[original_start:original_end],
                    rewritten_text[rewritten_start:rewritten_end],
                    original_start,
                    original_end,
                    rewritten_start,
                    target_grade,
                    going_up,
                    allow_fallback=True
                )
                if change:
                    paragraph_changes = [change]

            changes.extend(paragraph_changes)

        for index, change in enumerate(changes):
            change['id'] = index

        if len(changes) <= 1 and original_text != rewritten_text:
            fuzzy = self._fuzzy_sentence_diff(original_text, rewritten_text, target_grade, going_up)
            if fuzzy and len(fuzzy) > len(changes):
                return fuzzy
            if not changes:
                fallback_change = self._build_patch_change(
                    original_text,
                    rewritten_text,
                    0,
                    len(original_text),
                    0,
                    target_grade,
                    going_up,
                    allow_fallback=True
                )
                if fallback_change:
                    fallback_change['id'] = 0
                    return [fallback_change]

        return changes

    # ------------------------------------------------------------------ #
    #  LLM rewrite candidate generation
    # ------------------------------------------------------------------ #

    def _llm_full_rewrite(
        self,
        original_text,
        target_grade,
        going_up=False,
        rewrite_style='balanced',
        reference_text=None,
        metric_feedback=None,
        plan_label='pass1',
        include_diff=True,
    ):
        """
        Generate one LLM rewrite candidate.

        The LLM remains the authoring engine here, but the chosen output is
        still diffed back into deterministic patches so the UI can explain
        lexical swaps, sentence splits, and sentence combinations.
        """
        if not self.llm_client:
            return None, []

        try:
            reference_text = reference_text or original_text
            metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
            target_wps = metrics['target_wps']
            min_wps = metrics['min_wps']
            max_wps = metrics['max_wps']
            target_syl = metrics['target_syl']
            grade_label = 'College' if target_grade >= 13 else f'Grade {target_grade}'

            style_rules = {
                'conservative': (
                    "Prefer local edits. Keep the same paragraph order and sentence order whenever possible. "
                    "Use word substitutions, sentence splits, and sentence combinations before broader paraphrasing."
                ),
                'balanced': (
                    "Keep the same paragraph order and overall idea order. Prefer local edits first, "
                    "but you may fully rewrite an individual sentence when needed to hit the target naturally."
                ),
                'aggressive': (
                    "You may rewrite sentences more strongly inside each paragraph to hit the target, "
                    "but keep paragraph order, factual content, and the order of main ideas unchanged."
                ),
                'corrective': (
                    "This is a correction pass on a near-miss. Stay very close to the current wording. "
                    "Change only the words or sentence boundaries needed to fix the target grade, grammar, or awkward phrasing."
                ),
            }
            style_rule = style_rules.get(rewrite_style, style_rules['balanced'])
            style_temperature = {
                'conservative': 0.0,
                'balanced': 0.2,
                'aggressive': 0.35,
                'corrective': 0.1,
            }.get(rewrite_style, 0.2)

            reference_block = ""
            if reference_text != original_text:
                reference_block = f"""

FACT REFERENCE:
{reference_text}

Use the fact reference to preserve who did what, what causes what, and every original fact. Do not copy its harder or easier wording blindly; only use it to keep meaning exact."""

            metric_hint = ""
            if metric_feedback:
                metric_hint = f"""

CURRENT CANDIDATE METRICS:
- Estimated grade: {metric_feedback.get('raw_score', 0):.2f}
- Target distance: {metric_feedback.get('target_distance', 0):.2f}
- Invalid sentence count: {metric_feedback.get('invalid_sentence_count', 0)}
- Semantic similarity: {metric_feedback.get('semantic_similarity_score', 0):.2f}

Use these numbers to correct the current wording instead of rewriting the full passage from scratch."""

            def _build_upgrade_prompt(text_to_rewrite):
                if target_grade <= 6:
                    vocab_level = "slightly more formal words with some two-syllable terms"
                    clause_rule = "Write clear, simple sentences. Use 'and', 'but', 'so' to combine ideas. AVOID complex clause nesting."
                elif target_grade <= 8:
                    vocab_level = "formal vocabulary with academic terms (utilize, demonstrate, significant, establish)"
                    clause_rule = "Use AT MOST one subordinate clause per sentence (e.g. one 'which', 'because', or 'while'). Keep sentences clear and direct."
                elif target_grade <= 10:
                    vocab_level = "academic vocabulary with clear transitions and logical connectors"
                    clause_rule = "You may use subordinate clauses and transitions. Aim for 1–2 clauses per sentence maximum."
                elif target_grade <= 12:
                    vocab_level = "sophisticated high-school academic vocabulary with argument structure — NOT college/graduate prose"
                    clause_rule = "Use 2–3 clauses per sentence maximum. Do NOT write at College level — keep it high-school."
                else:
                    vocab_level = "professional academic prose with domain-specific terminology"
                    clause_rule = "Use full academic sentence complexity with multiple clauses and transitions."

                return f"""Rewrite the following text at exactly {grade_label} writing level.

THIS IS AN UPGRADE — make it MORE COMPLEX than the original.

STRICT METRIC TARGETS (the readability grade depends on hitting these precisely):
  - Average words per sentence: {target_wps}  (HARD LIMIT: each sentence must be {min_wps}–{max_wps} words)
  - Average syllables per word: {target_syl:.2f}
  - Sentence count: approximately {ideal_sentence_count} sentences

RULES:
1. REWRITE SHAPE: {style_rule}
2. SENTENCE LENGTH: Write approximately {ideal_sentence_count} sentences. Every sentence must be {min_wps}–{max_wps} words. NO sentence may exceed {max_wps} words. Combine short sentences using conjunctions and connectors.
3. VOCABULARY: Use {vocab_level}. Replace simple words with formal 2-syllable alternatives:
   "use" → "utilize"  |  "show" → "demonstrate"  |  "need" → "require"
   "big" → "significant"  |  "start" → "begin" or "establish"  |  "help" → "support"
   "get" → "obtain"  |  "find" → "discover"  |  "make" → "create" or "produce"
4. CONTEXTUAL FIT: Every word replacement MUST make sense in the sentence's context. Do NOT use a word just because it is more complex — it must fit the noun/verb it modifies. "big park" → "large park" is OK. "big park" → "substantial park" is WRONG because parks are not "substantial". Always ask: would a native speaker naturally use this word here?
5. CLAUSE COMPLEXITY: {clause_rule}
6. SYLLABLE COUNT: Aim for avg {target_syl:.2f} syllables/word. Use 2-syllable words (per-son, com-plete, for-mal, dai-ly, of-ten).
7. PARAGRAPH SHAPE: Keep the SAME number of paragraphs as the original. Each rewritten paragraph must correspond to the same original paragraph and stay within that paragraph's scope.
8. ENDING DISCIPLINE: Do NOT add a conclusion, takeaway, moral, reflection, or whole-text summary. Do NOT turn the final paragraph into an academic wrap-up. If the original final paragraph is short, keep it proportionally short unless grammar forces a small adjustment.
9. PRESERVE MEANING: Keep all facts. Do not omit any information.
10. NAMES & ACRONYMS: Keep all proper nouns and abbreviations exactly as written.
11. NO REPETITION: Each idea appears once only.
12. OUTPUT: Write ONLY the rewritten text. No labels, headings, or commentary.{metric_hint}{reference_block}

TEXT TO REWRITE:
{text_to_rewrite}

REWRITTEN TEXT ({grade_label}):"""

            def _build_downgrade_prompt(text_to_rewrite):
                if target_grade <= 4:
                    vocab_level = "only very simple 1-syllable everyday words a young child knows"
                elif target_grade <= 6:
                    vocab_level = "simple common words (mostly 1 syllable), no jargon"
                elif target_grade <= 8:
                    vocab_level = "common vocabulary, avoid technical or academic terms"
                else:
                    vocab_level = "standard vocabulary"

                return f"""Rewrite the following text at exactly {grade_label} reading level.

THIS IS A SIMPLIFICATION — make it EASIER than the original.

STRICT METRIC TARGETS (the ML model grade is determined ONLY by these two numbers):
  - Average words per sentence: {target_wps}  (HARD LIMIT: each sentence must be {min_wps}–{max_wps} words)
  - Average syllables per word: {target_syl:.2f}  (use short, common words)
  - Sentence count: approximately {ideal_sentence_count} sentences

RULES:
1. REWRITE SHAPE: {style_rule}
2. SENTENCE LENGTH: Write approximately {ideal_sentence_count} sentences. Every sentence must be {min_wps}–{max_wps} words. Split any longer sentence into two shorter ones. Use a period, not a semicolon.
3. VOCABULARY: Use {vocab_level}. Replace difficult words with simpler ones that mean THE SAME THING:
   "utilize" → "use"  |  "demonstrate" → "show"  |  "require" → "need"
   "obtain" → "get"  |  "substantial" → "large"  |  "facilitate" → "help"
   NEVER change word meaning: "zones" → "areas" is OK, "zones" → "suns" is WRONG.
4. CONTEXTUAL FIT: Every word replacement MUST make sense in the sentence's context. A simpler word must fit naturally where the original word was used. Would a native speaker say this? If not, pick a different simpler word.
5. SYLLABLE COUNT: Aim for avg {target_syl:.2f} syllables/word. Prefer short words.
6. PARAGRAPH SHAPE: Keep the SAME number of paragraphs as the original. Each rewritten paragraph must correspond to the same original paragraph and stay within that paragraph's scope.
7. ENDING DISCIPLINE: Do NOT add a conclusion, takeaway, moral, reflection, or whole-text summary. Do NOT turn the final paragraph into an academic wrap-up. If the original final paragraph is short, keep it proportionally short unless grammar forces a small adjustment.
8. PRESERVE MEANING: Keep ALL facts. Do not skip any paragraphs.
9. NAMES & ACRONYMS: Keep all proper nouns and abbreviations exactly as written.
10. NO REPETITION: Each idea appears once only. Do NOT generate new content beyond what exists in the original.
11. OUTPUT: Write ONLY the simplified text. No labels or commentary.{metric_hint}{reference_block}

TEXT TO REWRITE:
{text_to_rewrite}

SIMPLIFIED TEXT ({grade_label}):"""

            def _strip_preamble(text):
                for prefix in ["REWRITTEN TEXT:", "UPGRADED TEXT:", "SIMPLIFIED TEXT:", "Here is", "Grade", "College"]:
                    if text.startswith(prefix) and '\n' in text:
                        text = text[text.index('\n') + 1:].strip()
                # Strip trailing meta-commentary the LLM sometimes appends
                for marker in ["\nI made the following", "\nI made no other", "\nNote:", "\nChanges made:", "\nChanges:"]:
                    idx = text.find(marker)
                    if idx != -1:
                        text = text[:idx].strip()
                return text

            # ---- Estimate ideal sentence count from the original text ----
            orig_doc = nlp(original_text)
            orig_word_count = len([t for t in orig_doc if t.is_alpha])
            ideal_sentence_count = max(2, round(orig_word_count / target_wps))

            def _do_llm_pass(text_to_rewrite, pass_label="pass1"):
                prompt = _build_upgrade_prompt(text_to_rewrite) if going_up else _build_downgrade_prompt(text_to_rewrite)
                resp = self._llm_chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=style_temperature,
                    max_tokens=4000,
                )
                if resp is None:
                    return None, 0.0, 0.0, 0.0
                text_out = _strip_preamble(resp.choices[0].message.content.strip())
                g, s, w = self._measure_text_metrics(text_out)
                print(f"[fireworks] {plan_label}/{pass_label}: actual grade={g:.1f}, syl={s:.2f}, wps={w:.1f} "
                      f"(targets: grade={target_grade}, syl={target_syl:.2f}, wps={target_wps}, range {min_wps}-{max_wps})")
                return text_out, g, s, w

            # ---- First pass ----
            rewritten, actual_grade, actual_syl, actual_wps = _do_llm_pass(original_text, "pass1")
            if rewritten is None:
                return None, []

            def _build_correction_prompt(text_to_fix, cur_grade, cur_syl, cur_wps, aggressive=False):
                syl_direction = ""
                if cur_syl < target_syl - 0.05:
                    syl_examples = ('use -> utilize, show -> demonstrate, help -> assist, '
                                    'get -> obtain, find -> discover, need -> require')
                    syl_direction = f"\nSYLLABLE FIX: Current avg is {cur_syl:.2f}, need {target_syl:.2f}. Replace 1-syllable words with 2-syllable equivalents:\n   {syl_examples}"
                elif cur_syl > target_syl + 0.05:
                    syl_examples = ('utilize -> use, demonstrate -> show, require -> need, '
                                    'obtain -> get, additional -> more, significant -> big')
                    syl_direction = f"\nSYLLABLE FIX: Current avg is {cur_syl:.2f}, need {target_syl:.2f}. Replace multi-syllable words with shorter equivalents:\n   {syl_examples}"

                wps_direction = ""
                if cur_wps > max_wps + 2:
                    wps_direction = (f"\nSENTENCE FIX: Sentences average {cur_wps:.0f} words but must be {min_wps}-{max_wps}. "
                                     f"The text should have approximately {ideal_sentence_count} sentences. "
                                     f"Split the longest sentences at natural breakpoints (periods, not semicolons).")
                elif cur_wps < min_wps - 1:
                    wps_direction = (f"\nSENTENCE FIX: Sentences average only {cur_wps:.0f} words but must be {min_wps}-{max_wps}. "
                                     f"The text should have approximately {ideal_sentence_count} sentences. "
                                     f"Combine the shortest adjacent sentences using 'and', 'but', 'which', or 'because'.")

                if aggressive:
                    intensity = (f"This is a MAJOR correction — the text is far from the target. "
                                 f"Rewrite freely to hit the targets. Split or combine as many sentences as needed. "
                                 f"The text MUST have approximately {ideal_sentence_count} sentences, "
                                 f"each {min_wps}-{max_wps} words.")
                else:
                    intensity = (f"Make ONLY the minimum changes needed. "
                                 f"Replace 3-6 words max for syllable adjustment. "
                                 f"Split or combine 1-2 sentences max for length adjustment.")

                return f"""The text below needs adjustments to reach {grade_label} level.

Current metrics: avg {cur_syl:.2f} syl/word, avg {cur_wps:.1f} words/sentence (estimated grade {cur_grade:.1f}).
Target metrics: avg {target_syl:.2f} syl/word, avg {target_wps} words/sentence (grade {target_grade}).
Target sentence count: approximately {ideal_sentence_count} sentences.
{syl_direction}{wps_direction}

{intensity}
Keep the same facts, paragraph order, and idea order. Prefer local edits over rewriting whole paragraphs.
Do NOT add a conclusion, takeaway, moral, or wrap-up summary. Do NOT expand the final paragraph beyond its original local scope.{reference_block}

TEXT:
{text_to_fix}

ADJUSTED TEXT:"""

            # ---- Rule-based metric correction (replaces LLM correction loop) ----
            def _rule_correct(text_to_fix, cur_grade, cur_syl, cur_wps, max_rounds=2):
                """Apply rule-based vocabulary and structure adjustments to move toward target."""
                adjusted = text_to_fix
                g, s, w = cur_grade, cur_syl, cur_wps
                for tune_round in range(max_rounds):
                    grade_ok = abs(g - target_grade) <= 1.0
                    wps_ok = min_wps - 2 <= w <= max_wps + 3
                    syl_ok = abs(s - target_syl) <= 0.10
                    if grade_ok and wps_ok and syl_ok:
                        break

                    if g > target_grade + 1.0:
                        adjusted, _ = self._replace_difficult_words(adjusted, target_grade)
                        if w > max_wps:
                            adjusted, _ = self._split_long_sentences(adjusted, target_grade)
                    elif g < target_grade - 1.0:
                        adjusted, _ = self._complexify_text(adjusted, target_grade)
                        if w < min_wps:
                            adjusted, _ = self._combine_short_sentences(adjusted, target_grade)

                    g, s, w = self._measure_text_metrics(adjusted)
                    print(f"[rule-correct] round {tune_round + 1}: grade={g:.1f}, syl={s:.2f}, wps={w:.1f}")
                return adjusted, g, s, w

            rewritten, actual_grade, actual_syl, actual_wps = _rule_correct(
                rewritten, actual_grade, actual_syl, actual_wps
            )

            # Safety net for paid/unrestricted environments only. Free-tier
            # runs keep one authoring call per request and rely on rule-based
            # metric correction after that draft.
            if not self.rate_limited_llm and abs(actual_grade - target_grade) > 2.0:
                correction_prompt = _build_correction_prompt(
                    rewritten,
                    actual_grade,
                    actual_syl,
                    actual_wps,
                    aggressive=(rewrite_style == 'aggressive'),
                )
                resp_corr = self._llm_chat(
                    messages=[{"role": "user", "content": correction_prompt}],
                    temperature=min(0.2, style_temperature),
                    max_tokens=4000,
                )
                if resp_corr is not None:
                    corrected = _strip_preamble(resp_corr.choices[0].message.content.strip())
                    c_grade, c_syl, c_wps = self._measure_text_metrics(corrected)
                    print(
                        f"[fireworks] {plan_label}/correction: grade={c_grade:.1f}, "
                        f"syl={c_syl:.2f}, wps={c_wps:.1f}"
                    )
                    if abs(c_grade - target_grade) < abs(actual_grade - target_grade):
                        rewritten, actual_grade, actual_syl, actual_wps = corrected, c_grade, c_syl, c_wps
                        rewritten, actual_grade, actual_syl, actual_wps = _rule_correct(
                            rewritten, actual_grade, actual_syl, actual_wps
                        )

            # Clamp extreme undershoot on downgrades to Grade 3-4
            if target_grade <= 4 and actual_grade < target_grade - 1.5:
                rewritten, _ = self._combine_short_sentences(rewritten, target_grade)
                actual_grade, actual_syl, actual_wps = self._measure_text_metrics(rewritten)
                print(f"[clamp] undershoot fix: grade={actual_grade:.1f}, syl={actual_syl:.2f}, wps={actual_wps:.1f}")

            if not include_diff:
                return rewritten, []

            # Extract granular word/sentence changes by diffing original vs rewritten.
            # These are shown in the changes panel without any AI branding.
            diff_changes = self._diff_changes(original_text, rewritten, target_grade, going_up)

            # If the diff found nothing meaningful (total rewrite), add one summary entry
            if not diff_changes:
                direction_label = 'upgraded' if going_up else 'simplified'
                diff_changes = [{
                    'type': 'sentence_combine' if going_up else 'sentence_split',
                    'original': original_text[:70] + ('...' if len(original_text) > 70 else ''),
                    'simplified': rewritten[:70] + ('...' if len(rewritten) > 70 else ''),
                    'position': 0,
                    'reason': f'Text {direction_label} to {grade_label} level (avg {GRADE_TARGET_METRICS[target_grade]["target_wps"]} words/sentence, {GRADE_TARGET_METRICS[target_grade]["target_syl"]:.2f} syl/word).',
                    'id': 0
                }]

            return rewritten, diff_changes

        except Exception as e:
            print(f"LLM full rewrite error: {e}")
            return None, []

    # ------------------------------------------------------------------ #
    #  LLM fallback (optional)
    # ------------------------------------------------------------------ #

    def _needs_llm_help(self, text, target_grade):
        if not self.llm_client:
            return False
        doc = nlp(text)
        constraints = self.grade_constraints.get(target_grade, {'max_words': 20})
        for sent in doc.sents:
            words = [t for t in sent if t.is_alpha]
            if len(words) > constraints['max_words'] + 5:
                return True
        return False

    def llm_fallback(self, text, target_grade):
        if not self.llm_client:
            return text, []
        try:
            prompt = f"""Simplify this text to Grade {target_grade} reading level.
Rules:
- Use shorter sentences (max {self.grade_constraints[target_grade]['max_words']} words)
- Replace difficult words with simpler alternatives
- Maintain the original meaning
- Be natural and clear

Text:
{text}

Simplified version:"""

            response = self._llm_chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=2000,
            )
            if response is None:
                return text, []
            simplified = response.choices[0].message.content.strip()
            for marker in ["\nI made the following", "\nI made no other", "\nNote:", "\nChanges made:", "\nChanges:"]:
                idx = simplified.find(marker)
                if idx != -1:
                    simplified = simplified[:idx].strip()
            return simplified, [{
                'type': 'ai_enhanced',
                'original': text,
                'simplified': simplified,
                'position': 0,
                'reason': 'AI-assisted simplification.',
                'id': 999
            }]
        except Exception as e:
            print(f"Fireworks API error: {e}")
            return text, []

    # Backward compatibility
    def replace_difficult_words(self, text, target_grade):
        return self._replace_difficult_words(text, target_grade)

    def split_long_sentences(self, text, target_grade):
        return self._split_long_sentences(text, target_grade)

    def convert_passive_to_active(self, text):
        return text, []
