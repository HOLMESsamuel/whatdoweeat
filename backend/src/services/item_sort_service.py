import spacy
from lingua import Language, LanguageDetectorBuilder

class ItemSortService:
    def __init__(self):
        self.categories = {
            "vegetable": {
                Language.ENGLISH: ["carrot", "broccoli"],
                Language.FRENCH: ["carotte", "brocoli"]
            },
            "pantry": {
                Language.ENGLISH: ["rice"],
                Language.FRENCH: ["riz"]
            }
        }
        self.supported_languages = [Language.FRENCH, Language.ENGLISH]
        self.detector = LanguageDetectorBuilder.from_languages(*self.supported_languages).build()

    def classify_grocery_item(self, item_name):
        try:
            language = self.detector.detect_language_of(item_name)
            print(f"Language: {language}")
            nlp = spacy.load("fr_core_news_sm" if language == Language.FRENCH else "en_core_web_sm")
            tokens = [token.lemma_ for token in nlp(item_name.lower())]
            for category, langs in self.categories.items():
                if language in langs:
                    for word in langs[language]:
                        if word in tokens:
                            return category
            return "other"
        except Exception as e:
            print(f"Error in classification: {e}")
            return "other"
