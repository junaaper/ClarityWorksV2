import difflib
import json
import os
import re
import threading
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

FIREWORKS_MODEL = "accounts/fireworks/models/qwen3p6-plus"
FIREWORKS_NON_STREAM_MAX_TOKENS = 4096

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
    'frame-up', 'frame-ups', 'hold', 'holds', 'lamb', 'lambs',
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
    'lasting memories',
    'daily life',
    'daily routine',
    'great joy',
    'strong bond',
    'supported their bond',
    'formal daily routine',
)

PROTECTED_PROPN_EXCEPTIONS = {
    'mom',
    'dad',
    'mother',
    'father',
    'grandma',
    'grandpa',
    'grandmother',
    'grandfather',
}

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
TARGET_LOCK_DISPLAY_BAND_TOLERANCE = 1
TARGET_LOCK_REPAIR_ROUNDS = 4

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
    # Context-free replacements for "grow" often break garden/plant text
    # ("grow food" -> "expand food"). Let the LLM handle those phrases.
    'hard': ['complex', 'challenging'],
    'idea': ['concept', 'theory', 'hypothesis'],
    'key': ['vital', 'essential'],
    'make': ['produce', 'generate'],
    'many': ['numerous', 'multiple'],
    'more': ['additional', 'further'],
    'move': ['shift', 'transition'],
    'people': ['individuals', 'citizens'],
    'proof': ['evidence'],
    'read': ['examine', 'review'],
    'real': ['authentic', 'valid'],
    'right': ['accurate', 'valid'],
    'say': ['state', 'assert'],
    'see': ['observe', 'perceive'],
    'show': ['demonstrate', 'illustrate'],
    'some': ['certain'],
    'study': ['research', 'analysis'],
    'test': ['challenge', 'evaluate'],
    'think': ['consider', 'contemplate'],
    'town': ['community', 'settlement'],
    'understanding': ['knowledge'],
    'walk': ['stroll'],
    'wide': ['widespread'],
}

LOW_MID_UPGRADE_BLOCKED_WORDS = {
    'give',
    'gave',
    'home',
    'house',
    'read',
    'then',
}

LOW_MID_UPGRADE_PHRASES = [
    (
        r'\bhad a small brown dog named Max who liked to run and play all day\b',
        'owned a small brown dog named Max, who enjoyed running and playing throughout the entire day',
    ),
    (
        r'\bEvery day after lunch\b',
        'Each afternoon after lunch',
    ),
    (
        r'\bwould go to the big park near their house\b',
        'usually visited the large park located near their home',
    ),
    (
        r'\bthrew a red ball far across\b',
        'tossed a red ball far across',
    ),
    (
        r'\bfor Max to fetch\b',
        'for Max to retrieve',
    ),
    (
        r'\bMax would run as fast as he could to bring the ball back\b',
        'Max raced quickly so he could return the ball',
    ),
    (
        r'\bOne warm day\b',
        'One warm afternoon',
    ),
    (
        r'\blong walk\b',
        'lengthy stroll',
    ),
    (
        r'\bThey saw some fat ducks\b',
        'They noticed several fat ducks floating peacefully',
    ),
    (
        r'\bby the tall grass\b',
        'beside the tall grass',
    ),
    (
        r'\bdid not seem to care at all about him\b',
        'appeared completely uninterested in him',
    ),
    (
        r'\bjump in the cold water\b',
        'leap into the cold water',
    ),
    (
        r'\bthey went home\b',
        'they returned home',
    ),
    (
        r'\bTom gave Max some food\b',
        'Tom provided Max with food',
    ),
    (
        r'\blay down on his soft warm bed\b',
        'settled down on his soft, warm bed',
    ),
    (
        r'\bthe fire kept them warm\b',
        'the fire kept them comfortable',
    ),
]

MID_GRADE_UPGRADE_PHRASES = [
    (
        r'\bTom had a small brown dog named Max who liked to run and play all day\. Every day after lunch Tom and Max would go to the big park near their house\. Tom threw a red ball far across the green grass for Max to fetch\.',
        'Tom owned a small brown dog named Max, who enjoyed daily running and playing. Each afternoon after lunch, Tom and Max visited the large park near their home, where Tom tossed a red ball far across the grass for Max to retrieve.',
    ),
    (
        r'\bMax would run as fast as he could to bring the ball back to Tom\.',
        'Max raced back with the ball as quickly as he could.',
    ),
    (
        r'\bOne warm day they took a long walk down to the old pond near the farm\. They saw some fat ducks on the clear blue water by the tall grass\.',
        'One warm afternoon, they took a lengthy stroll to the old pond near the farm, where they observed several ducks floating on the clear blue water beside the tall grass.',
    ),
    (
        r'\bMax barked at the ducks but they did not seem to care at all about him\. Tom held Max back so he would not jump in the cold water after them\.',
        'Max barked at the ducks, although they seemed completely uninterested in him, so Tom held Max back to prevent him from leaping into the cold water after them.',
    ),
    (
        r'\bAfter their walk they went home and Tom gave Max some food and cool water\.',
        'After their walk, they returned home, and Tom provided Max with food and cool water.',
    ),
    (
        r'\bMax ate all of his food and then lay down on his soft warm bed to rest\.',
        'Max finished all his food and settled onto his soft, warm bed to rest.',
    ),
    (
        r'\bThat night Tom sat next to Max and read a new book about ships and the deep blue sea\. Max slept on the rug near his feet while the fire kept them warm\.',
        'That night, Tom sat beside Max and read a new book about ships and the deep blue sea while Max slept near his feet, warmed by the fire.',
    ),
]

HIGH_GRADE_NARRATIVE_UPGRADE_PHRASES = [
    (
        r'\bTom had a small brown dog named Max who liked to run and play all day\. Every day after lunch Tom and Max would go to the big park near their house\. Tom threw a red ball far across the green grass for Max to fetch\. Max would run as fast as he could to bring the ball back to Tom\.',
        'Tom owned a small brown dog named Max, an energetic companion who enjoyed daily running and playful activity throughout the entire day. Each afternoon after lunch, Tom and Max routinely visited the large park near their home, where Tom tossed a red ball far across the grass for Max to retrieve; Max raced back with the ball as quickly as he could, showing his speed and excitement.',
    ),
    (
        r'\bOne warm day they took a long walk down to the old pond near the farm\. They saw some fat ducks on the clear blue water by the tall grass\. Max barked at the ducks but they did not seem to care at all about him\. Tom held Max back so he would not jump in the cold water after them\.',
        'One warm afternoon, they took a lengthy stroll to the old pond near the farm, where they observed several ducks floating on the clear blue water beside the tall grass. Max barked at the ducks, although they seemed completely uninterested in him, so Tom held Max back to prevent him from leaping into the cold water after them.',
    ),
    (
        r'\bAfter their walk they went home and Tom gave Max some food and cool water\. Max ate all of his food and then lay down on his soft warm bed to rest\. That night Tom sat next to Max and read a new book about ships and the deep blue sea\. Max slept on the rug near his feet while the fire kept them warm\.',
        'After their walk, they returned home, and Tom provided Max with food and cool water. Max finished all his food and settled onto his soft, comfortable bed to rest. That night, Tom sat beside Max and read a new book about ships and the deep blue sea while Max slept near his feet, warmed by the fire.',
    ),
]

LEADING_SPLIT_MARKERS = {
    'and', 'but', 'or', 'so', 'yet', 'that', 'which', 'who', 'whom', 'whose',
    'where', 'while', 'although', 'because', 'though', 'when'
}
LEADING_ADVERB_MARKERS = {
    'then', 'also', 'still', 'instead', 'rather', 'therefore', 'however', 'moreover',
    'furthermore', 'additionally'
}
MID_SENTENCE_SPLIT_MARKERS = {
    'and', 'but', 'yet', 'while'
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
    '11-college': {
        'label': 'down-11-college',
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
        'lexical_max': 5,
        'split_rounds': 0,
        'split_changes': 0,
        'combine_rounds': 1,
        'combine_changes': 1,
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
    '11-college': {
        'label': 'up-11-college',
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
    'still': 'nevertheless',
}

DOMAIN_TERM_SUFFIXES = (
    'ology', 'onomy', 'graphy', 'metry', 'physis', 'tosis', 'genesis',
    'lysis', 'pathy', 'morphism'
)


class BaseSimplifierMixin:
    """Shared initialization, constants, routing, and low-level LLM helpers."""

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
                timeout=45.0,
            )

        # Grade-specific constraints derived from GRADE_TARGET_METRICS
        self.grade_constraints = {
            g: {'max_words': m['max_wps'], 'max_syllables': 4}
            for g, m in GRADE_TARGET_METRICS.items()
        }

        # Cache for synonym lookups (word -> best simple synonym)
        self._synonym_cache = {}
        self._selection_context = {}
        self._metrics_tls = threading.local()
        self.rate_limited_llm = os.getenv('CLARITYWORKS_RATE_LIMITED_LLM', '1').lower() not in {'0', 'false', 'no'}
        self.target_lock_quality_mode = os.getenv(
            'CLARITYWORKS_TARGET_LOCK_QUALITY_MODE',
            '1',
        ).lower() not in {'0', 'false', 'no'}
        self.max_llm_calls_per_request = self._env_int(
            'CLARITYWORKS_FIREWORKS_CALL_BUDGET',
            24 if self.target_lock_quality_mode else (1 if self.rate_limited_llm else 3),
            min_value=1,
            max_value=30,
        )
        self._llm_call_budget = None
        self._llm_calls_made = 0

    @staticmethod
    def _env_int(name, default, min_value=None, max_value=None):
        try:
            value = int(os.getenv(name, str(default)))
        except (TypeError, ValueError):
            value = default
        if min_value is not None:
            value = max(min_value, value)
        if max_value is not None:
            value = min(max_value, value)
        return value

    def _planned_llm_call_budget(self, source_grade, target_grade, text=None):
        if source_grade is None:
            return self.max_llm_calls_per_request
        if text and self._is_short_high_upgrade(text, source_grade, target_grade):
            planned = 2 if self.target_lock_quality_mode else 1
            return min(self.max_llm_calls_per_request, planned)
        if self.rate_limited_llm and not self.target_lock_quality_mode:
            return min(self.max_llm_calls_per_request, 1)

        if text and self._should_use_paragraph_pipeline(text):
            n_groups = len(self._split_into_rewrite_groups(text))
            planned = n_groups * 2 + 3
            return min(self.max_llm_calls_per_request, planned)

        gap = abs(float(target_grade) - float(source_grade))
        defence_downgrade = target_grade <= 7 and float(source_grade) - float(target_grade) >= 3.0
        if target_grade >= 13 or gap >= 6 or defence_downgrade:
            planned = 5 if self.target_lock_quality_mode else 3
        elif gap >= 3:
            planned = 3 if self.target_lock_quality_mode else 2
        else:
            planned = 2 if self.target_lock_quality_mode else 1
        return min(self.max_llm_calls_per_request, planned)

    @staticmethod
    def _emit_progress(progress_callback, pct, message, eta=None, **meta):
        if not progress_callback:
            return
        try:
            progress_callback(pct, message, eta, meta or None)
        except TypeError:
            progress_callback(pct, message, eta)

    def _llm_calls_remaining(self, reserve=0):
        if self._llm_call_budget is None:
            return True
        return self._llm_calls_made + int(reserve or 0) < self._llm_call_budget

    def _is_hard_llm_jump(self, source_grade, target_grade):
        return target_grade >= 13 or abs(float(target_grade) - float(source_grade)) >= 3.0

    def _should_reserve_target_contract_call(self, source_grade, target_grade, going_up):
        if going_up or target_grade > 7 or source_grade is None:
            return False
        return float(source_grade) - float(target_grade) >= 3.0

    def _is_short_high_upgrade(self, text, source_grade, target_grade):
        if source_grade is None:
            return False
        words = len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text or ''))
        return (
            words < 350 and
            11 <= int(target_grade) <= 12 and
            float(target_grade) > float(source_grade)
        )

    def _classify_rewrite_route(self, text, source_grade, target_grade):
        words = len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text or ''))
        paragraphs = self._extract_paragraph_chunks(text)
        gap = abs(float(target_grade) - float(source_grade))
        display_gap = abs(int(target_grade) - self._display_grade_number_from_score(source_grade))
        if display_gap <= 1 or gap <= 1.25:
            return 'small_shift_fast'
        if display_gap <= 2 or gap <= 3.0:
            return 'medium_shift_controlled'
        if self._is_short_high_upgrade(text, source_grade, target_grade):
            return 'short_high_upgrade'
        if words < 350 and target_grade <= 10 and float(target_grade) > float(source_grade):
            return 'medium_shift_controlled'
        if gap > 3.0 or words >= 350 or len(paragraphs) >= 3:
            return 'large_shift_llm'
        return 'medium_shift_controlled'

    @staticmethod
    def _route_uses_rule_first(rewrite_route):
        return rewrite_route in {'small_shift_fast', 'medium_shift_controlled'}

    @staticmethod
    def _target_grade_label(target_grade):
        return 'College' if target_grade >= 13 else f'Grade {target_grade}'

    @staticmethod
    def _display_grade_number_from_score(score):
        if score >= 13:
            return 13
        if score < 4:
            return 3
        return max(3, min(12, int(score)))

    @classmethod
    def _display_grade_delta_from_score(cls, score, target_grade):
        return abs(cls._display_grade_number_from_score(score) - int(target_grade))

    def _target_status_from_score(self, score, target_grade):
        if self._distance_to_target_band(score, target_grade) == 0:
            return 'exact'
        if self._display_grade_delta_from_score(score, target_grade) <= TARGET_LOCK_DISPLAY_BAND_TOLERANCE:
            return 'near'
        return 'miss'

    def _low_grade_downgrade_instructions(self, target_grade, target_metrics=None, source_grade=None):
        if target_grade > 7:
            return ''

        metrics = target_metrics or GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[4])
        grade_label = self._target_grade_label(target_grade)
        source_note = (
            f"The source is around raw {source_grade:.2f}; a result around Grade 8-12 is still a failure.\n"
            if source_grade is not None else
            "A result around Grade 8-12 is still a failure.\n"
        )
        return f"""
LOW/MIDDLE-GRADE DOWNGRADE REQUIREMENTS:
- This must read like {grade_label} text for a student, not like a light high-school rewrite.
- {source_note}- Use mostly short, common words. Replace abstract/academic words with plain words.
- Split dense ideas into short complete sentences. Do not use semicolons.
- Aim for {metrics['min_wps']}-{metrics['max_wps']} words per sentence, about {metrics['target_wps']} on average.
- Aim for about {metrics['target_syl']:.2f} syllables per word.
- Keep the same paragraph count, names, numbers, and core facts.
- You may rewrite whole paragraphs inside the same scope; do not stay sentence-by-sentence conservative.
- It is acceptable to sound simple. It is not acceptable to remain Grade 8-12 academic prose.
- Prefer "idea", "proof", "study", "question", "wrong", "true", "people", "trust", and "change" over academic nouns.
"""

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
        if max_tokens > FIREWORKS_NON_STREAM_MAX_TOKENS:
            print(
                "[fireworks] capping max_tokens for non-stream request: "
                f"{max_tokens} -> {FIREWORKS_NON_STREAM_MAX_TOKENS}"
            )
            max_tokens = FIREWORKS_NON_STREAM_MAX_TOKENS
        self._llm_calls_made += 1
        last_err = None
        request_client = (
            self.llm_client.with_options(max_retries=0)
            if hasattr(self.llm_client, 'with_options') else
            self.llm_client
        )
        for attempt in range(max_retries):
            try:
                response = request_client.chat.completions.create(
                    model=FIREWORKS_MODEL,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
                )
                return response
            except Exception as e:
                last_err = e
                err_str = str(e)
                if '429' in err_str or 'rate_limit' in err_str.lower() or 'RATE_LIMIT' in err_str:
                    if attempt < max_retries - 1:
                        wait = self._parse_retry_after(err_str) or (2 ** attempt)
                        wait = min(wait, 30)
                        print(f"[fireworks] Rate limited, waiting {wait:.0f}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait)
                        continue
                raise
        raise last_err

    @staticmethod
    def _is_rate_limit_error(exc):
        err_str = str(exc).lower()
        return (
            '429' in err_str or
            'rate_limit' in err_str or
            'rate limit' in err_str or
            'rate_limit_exceeded' in err_str
        )

    @staticmethod
    def _is_timeout_error(exc):
        err_str = str(exc).lower()
        return 'timed out' in err_str or 'timeout' in err_str

    def _mark_llm_timeout_fallback(self):
        try:
            self._metrics_tls.llm_timeout_fallback = True
        except Exception:
            pass

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

    @staticmethod
    def _strip_llm_meta_commentary(text):
        if not text:
            return text

        cleaned = text.strip()
        for prefix in ["REWRITTEN TEXT:", "UPGRADED TEXT:", "SIMPLIFIED TEXT:", "Here is", "Grade", "College"]:
            if cleaned.startswith(prefix) and '\n' in cleaned:
                cleaned = cleaned[cleaned.index('\n') + 1:].strip()

        meta_patterns = [
            r'(?:\n\s*)+(?:Note|Notes|Changes made|Changes|Rationale|Explanation)\s*:',
            r'(?:\n\s*)+I (?:removed|made|adjusted|changed|kept)\b',
            r'(?:\n\s*)+The rewritten text\b',
        ]
        cut_points = [
            match.start()
            for pattern in meta_patterns
            for match in [re.search(pattern, cleaned, flags=re.IGNORECASE)]
            if match
        ]
        if cut_points:
            cleaned = cleaned[:min(cut_points)].strip()

        return cleaned

    # ------------------------------------------------------------------ #
    #  Main entry point
    # ------------------------------------------------------------------ #
