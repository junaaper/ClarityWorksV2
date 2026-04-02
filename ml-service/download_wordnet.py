import nltk
import ssl

# Fix SSL certificate issue (if any)
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Download WordNet
print("Downloading WordNet...")
nltk.download('wordnet')
nltk.download('omw-1.4')  # Open Multilingual WordNet
print("WordNet downloaded successfully!")
