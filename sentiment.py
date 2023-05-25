from rasa.nlu.components import Component
from rasa.nlu import utils
from rasa.nlu.model import Metadata

import requests

import os

class SentimentAnalyzer(Component):
    """A pre-trained sentiment component"""

    name = "sentiment"
    provides = ["entities"]
    requires = []
    defaults = {}
    language_list = ["en", "el", "ro", "it"]

    def __init__(self, component_config=None):
        super(SentimentAnalyzer, self).__init__(component_config)

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

    def convert_to_rasa_classes(self, value):
        """Convert model output into the Rasa NLU compatible output format."""

        entity = {
            "value": value,
            "entity": "sentiment_classes",
            "extractor": "sentiment_extractor",
        }

        return entity        

    def process(self, message, **kwargs):
        """Retrieve the text message, pass it to the classifier
            and append the prediction results to the message class."""

        try:
            user_text = message.data['text']
            accessToken = message.data["metadata"]["accessToken"]

            data = {"text": user_text, "accessToken": accessToken}
            response = requests.post(
                "https://csat.alamedaproject.eu/classes", json=data
            )   
            resp = response.json()  # This returns {"sentiment_classes":[{"sentiment_class":"positive","sentiment_score":<score>}, {"sentiment_class":"neutral","sentiment_score":<score>}, {"sentiment_class":"negative","sentiment_score":<score>}]}
            response.close()
            
            sentiment_classes = resp.get("sentiment_classes")
            
            max_score = sentiment_classes[0].get("sentiment_score")
            max_sentiment = sentiment_classes[0].get("sentiment_class")
            for sentiment in sentiment_classes:
                if sentiment.get("sentiment_score") > max_score:
                    max_score = sentiment.get("sentiment_score")
                    max_sentiment = sentiment.get("sentiment_class")

            if max_sentiment == "positive":
                max_sentiment = "pos"
            elif max_sentiment == "negative":
                max_sentiment = "neg"
            else:
                max_sentiment = "neu"

            sentiment_entity = self.convert_to_rasa(max_sentiment, max_score)
            sentiment_classes_entity = self.convert_to_rasa_classes(sentiment_classes)
            message.set("entities", [sentiment_entity, sentiment_classes_entity], add_to_output=True)  
        except KeyError:
            pass


    def persist(self, file_name, dir_name):
        """Pass because a pre-trained model is already persisted"""

        pass