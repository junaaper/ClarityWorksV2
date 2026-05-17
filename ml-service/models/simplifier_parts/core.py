from .authoring import AuthoringMixin
from .base import BaseSimplifierMixin
from .candidate import CandidateSelectionMixin
from .diffing import DiffingMixin
from .finalize import FinalizeMixin
from .llm_fallback import LlmFallbackMixin
from .metrics_review import MetricsReviewMixin
from .paragraph import ParagraphPipelineMixin
from .public import PublicSimplifierMixin
from .rules import RuleRewriteMixin
from .sanity import SanityPolishMixin
from .sentence_ops import SentenceOpsMixin


class TextSimplifier(
    PublicSimplifierMixin,
    SanityPolishMixin,
    FinalizeMixin,
    AuthoringMixin,
    CandidateSelectionMixin,
    MetricsReviewMixin,
    RuleRewriteMixin,
    SentenceOpsMixin,
    DiffingMixin,
    ParagraphPipelineMixin,
    LlmFallbackMixin,
    BaseSimplifierMixin,
):
    """Simplify text to a target grade level.

    This compatibility class preserves the historic models.simplifier.TextSimplifier
    import while the implementation lives in focused mixins.
    """

    pass
