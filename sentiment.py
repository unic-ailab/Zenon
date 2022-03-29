from rasa.nlu.components import Component
from rasa.nlu import utils
from rasa.nlu.model import Metadata

import requests

# import nltk
# from nltk.sentiment.vader import SentimentIntensityAnalyzer
# nltk.download("vader_lexicon")

import spacy
from spacytextblob.spacytextblob import SpacyTextBlob

import os


class SentimentAnalyzer(Component):
    """A pre-trained sentiment component"""

    name = "sentiment"
    provides = ["entities"]
    requires = []
    defaults = {}
    language_list = ["en", "el"]

    def __init__(self, component_config=None):
        super(SentimentAnalyzer, self).__init__(component_config)
        self.nlp = spacy.load("en_core_web_sm")
        self.nlp.add_pipe("spacytextblob")

    def train(self, training_data, cfg, **kwargs):
        """Not needed, because the the model is pretrained"""
        pass

    def convert_to_rasa(self, value, confidence):
        """Convert model output into the Rasa NLU compatible output format."""

        entity = {
            "value": value,
            "confidence": confidence,
            "entity": "sentiment",
            "extractor": "sentiment_extractor",
        }

        return entity

    def process(self, message, **kwargs):
        """Retrieve the text message, pass it to the classifier
            and append the prediction results to the message class."""

        nlp = self.nlp
        doc = nlp(str(message.get("text")))

        if doc._.polarity < 0:
            sentiment = "neg"
        elif doc._.polarity > 0:
            sentiment = "pos"
        else:
            sentiment = "neu"

        entity = self.convert_to_rasa(sentiment, doc._.polarity)

        message.set("entities", [entity], add_to_output=True)

    def persist(self, file_name, dir_name):
        """Pass because a pre-trained model is already persisted"""

        pass

