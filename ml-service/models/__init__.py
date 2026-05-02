import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / '.env')

os.environ['THINC_NO_TORCH'] = '1'

from .text_processor import TextProcessor
from .feature_extractor import FeatureExtractor
from .readability_model import ReadabilityModel

__all__ = ['TextProcessor', 'FeatureExtractor', 'ReadabilityModel']
