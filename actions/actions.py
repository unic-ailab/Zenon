from ast import Try
from dataclasses import dataclass
import random
import datetime
import time
import re
import os
import requests
import json
import pytz
import pandas as pd

from typing import Any, Dict, List, Text
from urllib import response
from matplotlib.pyplot import text
from numpy import true_divide
from pytz import timezone

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet, FollowupAction, UserUttered
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormValidationAction

import sys        
sys.path.append(os.getcwd().replace("\\","/"))
from custom_tracker_store import CustomSQLTrackerStore

customTrackerInstance = CustomSQLTrackerStore(dialect="sqlite", db="demo.db")
endpoints_df = pd.read_csv("alameda_endpoints.csv")                       

# Define this list as the values for the `language` slot. Arguments of the `get_..._lang` functions should respect this order.
lang_list = ["English", "Greek", "Italian", "Romanian"]  # Same as slot values

# Questionnaire names in different languages with their abbreviation
questionnaire_abbreviations = {"activLim": ["ACTIVLIM", "", "", "ACTIVLIM"], 
                                "psqi": ["PSQI", "", "", "PSQI"],
                                "eatinghabits": ["Eating Habits", "", "", "Obiceiuri alimentare"], 
                                "dizzNbalance": ["Dizziness and Balance", "", "", "Amețeli și echilibrului"], 
                                "muscletone": ["Muscle Tone", "", "", "Tonusului muscular"], 
                                "coast": ["COAST", "", "", "COAST"],
                                "STROKEdomainIII": ["Mental and Cognitive Ability", "", "", "Tulburari cognitive"],
                                "STROKEdomainIV": ["Emotional Status", "", "", "Statusul emotional"],
                                "STROKEdomainV": ["Quality of Life and daily living", "", "", "Calitatea vietii"],
                                "MSdomainI": ["Mobility and physical function", "", "Mobilità, funzioni motorie e fisiche", ""],
                                "MSdomainII_1M": ["Sleep Disorders", "", "Sonno", ""],
                                "MSdomainII_3M": ["Sleep Disorders", "", "Sonno", ""],
                                "MSdomainIII_1W": ["Mental and Cognitive Ability", "", "Abilità mentali e cognitive", ""],
                                "MSdomainIII_2W": ["Mental and Cognitive Ability", "", "Abilità mentali e cognitive", ""],
                                "MSdomainIV_1W": ["Emotional Status", "", "Stato emotivo", ""],
                                "MSdomainIV_Daily": ["Emotional Status", "", "Stato emotivo", ""],
                                "MSdomainV": ["Quality of Life", "", "Qualità di vita", ""],}

questionnaire_per_usecase = {
    "MS": ["MSdomainI", "MSdomainII_1M", "MSdomainII_3M", "MSdomainIII_1W", "MSdomainIII_2W", "MSdomainIV_Daily", "MSdomainIV_1W", "MSdomainV"],
    "STROKE": ["activLim", "muscletone", "dizzNbalance", "eatinghabits", "psqi", "coast", "STROKEdomainIII", "STROKEdomainIV", "STROKEdomainV"]
}


# cancel button
cancel_button = [
    "Cancel",
    " ",
    "Annulla",
    "Anulare",
]


# The main options the agent offers
options_menu_buttons = [
    ["Questionnaires", "Health Status update", "Tutorials"],
    ["", "", ""],
    ["Questionari", "Aggiornamento dello stato di salute", "Tutorial"],
    ["Chestionare", "Actualizare stare de sănătate", "Tutoriale"]
]

# The helath status update options the agent offers
health_update_menu_buttons = { "MS": [["Sleep Quality", "Mobility", "Quality of Life", "Cancel"],
                                      ["", "", "", ""],
                                      ["Qualità del Sonno", "Mobilità", "Qualità di Vita", "Annulla"],
                                      ["", "", "", ""]],
                               "STROKE": [["Sleep Quality", "Mobility", "Cancel"],
                                         ["", "", ""],
                                         ["", "", ""],
                                         ["Calitatii Somnului ", "Mobilitate", "Anulare"]] }

health_update_menu_payloads = { "MS": ["/sleep_status", "/mobility_status", "/qol_status", "/options_menu"],
                                "STROKE": ["/sleep_status", "/mobility_status", "/options_menu"]}


# PSQI Questionnaire
psqi_start_text = ["During the past month,", " ", " ", "In ultima luna,"]

buttons_psqi = [
    ["Not during the past month", "Less than once a week", "Once or twice a week", "Three or more times a week"],
    [" ", " "],
    [" ", " "],
    ["Nu in ultima luna", "Mai putin de o data pe saptamana", "O data sau de 2 ori pe saptamana", "De 3 sau mai multe ori pe saptamana"]
]

psqi_q5 = [
    "During the past month, how often have you had trouble sleeping because you",
    " ",
    " ",
    "In ultima luna cat de des ati avut probleme cu somnul deoarece nu"
    ]


# Muscle Tone Questionnaire Buttons
muscletone_buttons = [
    ["Yes", "No", "Don't know/ refused"],
    [" ", " "],
    [" ", " "],
    ["Da", "Nu", "Nu stiu/ refuz sa raspund"]
]

# COAST Questionnaire Buttons
coast_buttons_1 = [
    ["😒 Couldn't do it at all", "With a lot of difficulty", "With some difficulty", "Quite well", "🙂 Very well"],
    [" ", " ", " ", " ", " "],
    [" ", " ", " ", " ", " "],
    ["😒 Nu reusesc deloc", "Foarte dificil", "Destul de dificil", "Destul de usor", "🙂 Foarte usor"]
]

coast_buttons_2 = [
    ["😒 Can't do it at all", "With a lot of difficulty", "With some difficulty", "Quite well", "🙂 Very well"],
    [" ", " ", " ", " ", " "],
    [" ", " ", " ", " ", " "],
    ["😒 Nu reusesc deloc", "Foarte dificil", "Destul de dificil", "Destul de usor", "🙂 Foarte usor"]
]

coast_buttons_3 = [
    ["😒 Couldn't do it at all", "With a lot of difficulty", "With some difficulty", "Quite well", "🙂 As well as before my stroke"],
    [" ", " ", " ", " ", " "],
    [" ", " ", " ", " ", " "],
    ["😒 Nu reusesc deloc", "Foarte dificil", "Destul de dificil", "Destul de usor", "🙂 Foarte usor"]
]

coast_buttons_4 = [
    ["😒 Not changed at all", "A little bit beter", "Quite a bit better", "A lot better", "🙂 Completely better"],
    [" ", " ", " ", " ", " "],
    [" ", " ", " ", " ", " "],
    ["😒 Nu s-a schimbat deloc", "Putin mai bine", "Mai bine", "Mult mai bine", "🙂 Complet recuperat"]
]

coast_buttons_5 = [
    ["😒 The worst possible", "Quite poor", "Fair", "Quite good", "🙂 As good as before my stroke"],
    [" ", " ", " ", " ", " "],
    [" ", " ", " ", " ", " "],
    ["😒 Este foarte rau", "Destul de rau", "Acceptabil", "Destul de bine", "🙂 La fel de bine ca inainte de accidentul vascular cerebral"]
]

coast_buttons_6 = [
    ["😒 All the time", "Very often", "Sometimes", "Hardly ever", "🙂 Never"],
    [" ", " ", " ", " ", " "],
    [" ", " ", " ", " ", " "],
    ["😒 Tot timpul", "Destul de des", "Uneori", "Rareori", "🙂 Niciodata"]
]

coast_buttons_7 = [
    ["😒 The worst possible", "Quite poor", "Fair", "Quite good", "🙂 It's at least as good as before my stroke"],
    [" ", " ", " ", " ", " "],
    [" ", " ", " ", " ", " "],
    ["😒 Afecteaza foarte mult", "Destul de mult", "Moderat", "Destul de putin", "🙂 Nu afecteaza deloc"]
]

# Eating Habits Questionnaire Buttons
eatingHabits_buttons = [
    ["Never", "Rarely", "Sometimes", "Often", "Very often", "Always"],
    [" ", " ", " ", " ", " ", " "], #TODO might needs to add an extra line here
    ["Niciodată", "Rareori", "Uneori", "Adesea", "Foarte des", "Întotdeauna"]
]

####################################################################################################
# DEBUGGING                                                                                        #
####################################################################################################

def announce(action, tracker=None):
    output = ">>> Action: " + action.name()
    output = "=" * min(100, len(output)) + "\n" + output
    if tracker:
        try:
            msg = tracker.latest_message
            slots = tracker.slots
            filled_slots = {}
            output += "\n- Text:       " + str(msg["text"])
            output += "\n- Intent:     " + str(msg["intent"]["name"])
            output += "\n- Confidence: " + str(msg["intent"]["confidence"])

            # Add Entities section
            if "value" in msg["entities"][0].keys():
                output += (
                    "\n- Entities:   "
                    + str(msg["entities"][0]["entity"])
                    + ", Value: "
                    + str(msg["entities"][0]["value"])
                )
            else:
                output += "\n- Entities:   " + str(msg["entities"][0]["entity"])

            # Add Slots section
            output += "\n- Slots:      "
            for slot_key, slot_value in slots.items():
                if slot_value is not None:
                    filled_slots[slot_key] = slot_value
            if len(filled_slots) > 0:
                for slot_key, slot_value in filled_slots.items():
                    output += str(slot_key) + ": " + str(slot_value) + ", "
                output = output[:-2]    # clear the last ", "

        except Exception as e:
            print(f"\n> announce: [ERROR] {e}")
    print(output)

####################################################################################################
# SLOTS                                                                                            #
####################################################################################################

# def reset_slots(tracker, slots, exceptions=[]):
#     events = []
#     none_slots = []

#     for exception in exceptions:
#         if exception in slots:
#             slots.remove(exception)

#     for slot in slots:
#         if tracker.get_slot(slot) is not None:
#             none_slots.append(slot)

#     for slot in none_slots:
#         events.append(SlotSet(slot, None))

#     print("\n> reset_slots:", ", ".join(none_slots))
#     return events

def reset_form_slots(tracker, domain, list_questionnaire_abbreviation):
    #async def required_slots(self, domain_slots, dispatcher, tracker, domain):
    required = []

    if list_questionnaire_abbreviation is not None:
        for slot_name in domain['slots'].keys():
            if slot_name.split("_")[0] in list_questionnaire_abbreviation and tracker.get_slot(slot_name) is not None:
                print(slot_name)
                required.append(SlotSet(slot_name, None))
           
    return required

# def list_slots(tracker, slots, exceptions=[]):
#     filled_slots = ""

#     for exception in exceptions:
#         if exception in slots:
#             slots.remove(exception)

#     for slot in slots:
#         value = tracker.get_slot(slot)

#         if value is not None:
#             filled_slots += f"\t- {slot}: {value}\n"

#     # print(filled_slots[:-1])
#     return filled_slots[:-1]

####################################################################################################
# LANGUAGES                                                                                        #
####################################################################################################

def get_lang(tracker):
    try:
        lang = tracker.slots["language"].title()
        return lang
    except Exception as e:
        return "English"

def get_lang_index(tracker):
    return lang_list.index(get_lang(tracker))

""" utter_list is a list of outputs in multiple lanaguages, each output can be a string or a list of strings """

def get_text_from_lang(tracker, utter_list=[]):
    lang_index = get_lang_index(tracker)

    if not utter_list:  # No text was given for any language
        return "[NO TEXT DEFINED]"

    if lang_index >= len(utter_list):  # No text defined for current language
        lang_index = 0

    text = utter_list[lang_index]

    if isinstance(
        text, list
    ):  # If a list is given for the language, choose a random item
        text = str(text[random.randint(0, len(text) - 1)])
    else:
        text = str(text)

    return text

def get_response_from_lang(tracker, response):
    return response + "_" + get_lang(tracker)

def get_buttons_from_lang(tracker, titles=[], payloads=[]):
    lang_index = get_lang_index(tracker)
    buttons = []

    if lang_index >= len(titles):  # No text defined for current language
        lang_index = 0

    for i in range(min(len(titles[lang_index]), len(payloads))):
        buttons.append({"title": titles[lang_index][i], "payload": payloads[i]})
    return buttons

class ActionUtterAskLanguage(Action):
    def name(self):
        return "action_utter_ask_language"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Choose a language:",
                "Επιλέξτε γλώσσα:",
                "Scegli una lingua:",
                "Alegeți o limbă:",
            ],
        )

        buttons = [  # https://forum.rasa.com/t/slots-set-by-clicking-buttons/27629
            {"title": "English", "payload": '/set_language{"language": "English"}'},
            {"title": "Ελληνικά", "payload": '/set_language{"language": "Greek"}'},
            {"title": "Română", "payload": '/set_language{"language": "Romanian"}'},
            {"title": "Italian", "payload": '/set_language{"language": "Italian"}'},
        ]

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionUtterSetLanguage(Action):
    def name(self) -> Text:
        return "action_utter_set_language"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        current_language = tracker.slots["language"].title()

        if current_language == "English":
            text = "The language is now English."
        elif current_language == "Greek":
            text = "Η γλώσσα έχει τεθεί στα Ελληνικά"
        elif current_language == "Romanian":
            text = "Limba este acum Română."
        elif current_language == "Italian":
            text = "La lingua ora è l'italiano"
        else:
            text = "I only understand English, Greek, Italian and Romanian. The language is now English."

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return [SlotSet("language", current_language)]

####################################################################################################
# Onboarding                                                                                          #
####################################################################################################

class ActionOnboardUser(Action):
    def name(self) -> Text:
        return "action_onboard_user"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)
        language = customTrackerInstance.checkUserID(tracker.current_state()['sender_id'])
        dispatcher.utter_message(text=language)
        return [SlotSet("language", language)]

####################################################################################################
# General                                                                                          #
####################################################################################################

class ActionGetAvailableQuestions(Action):
    def name(self) -> Text:
        return "action_get_available_questionnaires"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)
        now = datetime.datetime.now(tz=pytz.utc).timestamp()
        # its better to not check the user id here as here it won't update the app languge
        # keep it here for now to avoid not onboarding users between database updates
        _ = customTrackerInstance.checkUserID(tracker.current_state()['sender_id'])
        available_questionnaires, reset_questionnaires = customTrackerInstance.getAvailableQuestionnaires(tracker.current_state()['sender_id'], now) 
        if len(available_questionnaires) == 0:
            text = get_text_from_lang(
                tracker, 
                [
                    "Currently there are no available questionnaires. Would you like to be redirected to the main menu?",
                    "",
                    "Al momento non ci sono questionari disponibili. Vuoi essere reindirizzato al menu principale?",
                    "Momentan nu este disponibil niciun chestionar. Dorești redirecționarea către meniul principal?"
                    ]
            )

            dispatcher.utter_message(text=text)
            return []
        else :
            text = get_text_from_lang(
                tracker,
                [
                    "You have the following questionnaire(s) available:",
                    " ",
                    "Hai a disposizione i seguenti questionari:",
                    "Ai la dispoziție următorul(ele) chestionar(e):",
                ]
            )
            
            slots_to_set = []
            if all(x in available_questionnaires for x in ["MSdomainII_1M", "MSdomainII_3M"]):
                available_questionnaires.remove("MSdomainII_3M")
                slots_to_set.append(SlotSet("MSdomainII_both", True))
            else:
                slots_to_set.append(SlotSet("MSdomainII_both", False))

            if all(x in available_questionnaires for x in ["MSdomainIII_1W", "MSdomainIII_2W"]):
                available_questionnaires.remove("MSdomainIII_2W")
                slots_to_set.append(SlotSet("MSdomainIII_both", True))
            else:
                slots_to_set.append(SlotSet("MSdomainIII_both", False))

            if all(x in available_questionnaires for x in ["MSdomainIV_1W", "MSdomainIV_Daily"]):
                available_questionnaires.remove("MSdomainIV_1W")
                slots_to_set.append(SlotSet("MSdomainIV_both", True))
            else:
                slots_to_set.append(SlotSet("MSdomainIV_both", False))

            buttons = []
            for questionnaire in available_questionnaires:
                button_title = get_text_from_lang(tracker, questionnaire_abbreviations[questionnaire])
                buttons.append({"title": button_title, "payload": "/"+questionnaire+"_start"})

            # add button for cancel that takes the user back to the general questions
            buttons.append({"title": get_text_from_lang(tracker, cancel_button), "payload": "/options_menu"})
            dispatcher.utter_message(text=text, buttons=buttons)
            return reset_form_slots(tracker, domain, reset_questionnaires)+slots_to_set

class ActionContinueLatestQuestionnaire(Action):
    def name(self) -> Text:
        return "action_utter_continue_latest_questionnaire"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)
        # check if there is currently an active questionnaire and ignore this action if there is
        if tracker.active_loop.get("name"):
            return []
        else:
            q_abbreviation = tracker.get_slot("questionnaire")
            isAvailable, _ = customTrackerInstance.getSpecificQuestionnaireAvailability(tracker.current_state()['sender_id'], datetime.datetime.now(tz=pytz.utc).timestamp(), q_abbreviation)

            if isAvailable: 
                q_name = get_text_from_lang(tracker, questionnaire_abbreviations[q_abbreviation])
                #TODO: fix translation
                text = get_text_from_lang(
                    tracker,
                    [
                        "Do you want to continue the {} questionnaire?".format(q_name),
                        " ",
                        "Vuoi continuare il questionario {}?".format(q_name),
                        "Doriți să continuați chestionarul {}?".format(q_name),
                    ]
                )
                buttons = []
                start_button_title = get_text_from_lang(
                    tracker,
                    [
                        "Continue",
                        " ", 
                        "Continua",
                        "Continua",
                    ]
                )
                buttons.append({"title": start_button_title, "payload": "/"+ q_abbreviation+"_start"})
                # add button for cancel that takes the user back to the general questions
                buttons.append({"title": get_text_from_lang(tracker, cancel_button), "payload": "/options_menu_extra"})
                dispatcher.utter_message(text=text, buttons=buttons)
                return []
            else:
                text = get_text_from_lang(
                    tracker,
                    [
                        "The latest questionnaire you were completing is not currently available",
                        " ",
                        "The latest questionnaire you were completing is not currently available",
                        "The latest questionnaire you were completing is not currently available",
                    ]
                )
                dispatcher.utter_message(text=text)
                return [FollowupAction("action_get_available_questionnaires")]

class ActionOptionsMenu(Action):
    def name(self) -> Text:
        return "action_options_menu"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)
        
        text = get_text_from_lang(
            tracker, 
            [
                "What can I do for you today?",
                "",
                "Cosa posso fare per te oggi?",
                "Ce pot face pentru tine azi?"]
            )
        buttons = get_buttons_from_lang(
            tracker,
            options_menu_buttons,
            # TODO: maybe add health_related_report as option
            ["/available_questionnaires", "/health_update_menu", "/tutorials"]
        )
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

# used when user ends up in the options menu more than once after greeting
class ActionOptionsMenuExtra(Action):
    def name(self) -> Text:
        return "action_options_menu_extra"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)
        
        #time.sleep(5) # 5 second delay before the next action
        #smthg missing here but i dont remember
        text = get_text_from_lang(
            tracker, 
            [
                "Is there anything else that I can help you with?",
                " ",
                "C'è qualcos'altro in cui posso aiutarti?",
                "Te mai pot ajuta cu ceva?",
            ]
            )
        buttons = get_buttons_from_lang(
            tracker,
            options_menu_buttons,
            ["/available_questionnaires", "/health_update_menu", "/tutorials"]
        )
        dispatcher.utter_message(text=text, buttons=buttons)
        return []


#TODO: translate
class ActionHealthUpdateMenu(Action):
    def name(self) -> Text:
        return "action_health_update_menu"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        usecase = customTrackerInstance.getUserUsecase(tracker.current_state()['sender_id'])
        if usecase in ["MS", "STROKE"]:
            text = get_text_from_lang(
                tracker, 
                [
                    "Choose domain:",
                    "",
                    "Scegli dominio:",
                    "Alege domeniul:"
                ]
            )
            buttons = get_buttons_from_lang(
                tracker,
                health_update_menu_buttons[usecase],
                health_update_menu_payloads[usecase],
                )
            dispatcher.utter_message(text=text, buttons=buttons)
        else:
            #TODO: translate
            text = get_text_from_lang(
                tracker, 
                [
                    "Something went wrong, you were not assigned a valid usecase.",
                    "",
                    "Qualcosa è andato storto, non ti è stato assegnato un caso d'uso valido. Per favore, dillo al tuo medico.",
                    "A apărut o eroare, nu vi s-a atribuit un caz de utilizare valid. Vă rugăm să spuneți acest lucru asistentului medical."
                ]
            )
            dispatcher.utter_message(text=text)
        return []


#TODO: translate
class ActionSleepStatus(Action):
    def name(self) -> Text:
        return "action_get_sleep_status_fitbit"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        try :
            today = datetime.datetime.now(tz=pytz.utc)
            seven_days_ago = (today - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
            today = today.strftime("%Y-%m-%dT%H:%M:%SZ")
            wcs_sleep_endpoint= endpoints_df[endpoints_df["name"]=="WCS_FITBIT_SLEEP_ENDPOINT"]["endpoint"].values[0]
            response = requests.get(wcs_sleep_endpoint, params={"userId": tracker.current_state()['sender_id'], "startDate":seven_days_ago, "endDate":today})
            response.close()
            sleep_efficiency_score = json.loads(response.text)[0]
            
            #High 60-100
            #Low 0-60 

            if int(sleep_efficiency_score) > 60:
                average_score_text = get_text_from_lang(
                    tracker, 
                    [
                        "high",
                        "",
                        "elevatp",
                        "ridicat"
                    ]
                )
                average_score_text2 = get_text_from_lang(
                    tracker, 
                    [
                        "not",
                        "",
                        "non",
                        "nu"
                    ]
                )
            else:
                average_score_text = get_text_from_lang(
                    tracker, 
                    [
                        "low",
                        "",
                        "basso",
                        "scăzut"
                    ]
                )
                average_score_text2 =""

            try :
                fourteen_days_ago = (today - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
                response = requests.get(wcs_sleep_endpoint, params={"userId": tracker.current_state()['sender_id'], "startDate":fourteen_days_ago, "endDate":seven_days_ago})
                response.close()
                previous_sleep_efficiency_score = json.loads(response.text)[0]

                if abs(previous_sleep_efficiency_score - sleep_efficiency_score) < 10:
                    comparison_text = get_text_from_lang(
                        tracker, 
                        [
                            "slightly",
                            "",
                            "leggermente",
                            "ușor"
                        ]
                    )
                elif abs(previous_sleep_efficiency_score - sleep_efficiency_score) > 21:
                    comparison_text = get_text_from_lang(
                        tracker, 
                        [
                            "significantly",
                            "",
                            "notevolmente",
                            "semnificativ"
                        ]
                    )
                else:
                    comparison_text = get_text_from_lang(
                        tracker, 
                        [
                            "moderately",
                            "",
                            "moderatamente",
                            "moderat"
                        ]
                    )

                if previous_sleep_efficiency_score > sleep_efficiency_score:
                    comparison_text2 = get_text_from_lang(
                        tracker, 
                        [
                            "decreased",
                            "",
                            "diminuita",
                            "scăzut"
                        ]
                    )
                elif previous_sleep_efficiency_score < sleep_efficiency_score:
                    comparison_text2 = get_text_from_lang(
                        tracker, 
                        [
                            "increased",
                            "",
                            "aumentata",
                            "crescut"
                        ]
                    )
                else:
                    comparison_text = ""
                    comparison_text2 = get_text_from_lang(
                        tracker, 
                        [
                            "remained the same",
                            "",
                            "rimasta la stessa",
                            "rămas aceeași"
                        ]
                    )
                text = get_text_from_lang(
                    tracker, 
                    [
                        "According to the Fitbit measurements, the last 7 days your average sleep duration score was %s. Meaning you were %s getting enough hours of sleep at night. Compared to the 7 days before that, your average sleep duration has %s %s.".format(average_score_text, average_score_text2, comparison_text, comparison_text2),
                        "",
                        "Secondo le misurazioni Fitbit, negli ultimi 7 giorni il punteggio medio della durata del sonno è stato %s. Significa che %s dormivi abbastanza ore di notte. Rispetto ai 7 giorni precedenti, la durata media del sonno è %s %s.".format(average_score_text, average_score_text2, comparison_text, comparison_text2),
                        "Conform măsurătorilor Fitbit, în ultimele 7 zile, scorul tău mediu al duratei de somn a fost %s. Înseamnă că %s dormi destule ore noaptea. Comparativ cu cele 7 zile de dinainte, durata medie de somn a %s %s.".format(average_score_text, average_score_text2, comparison_text2, comparison_text),
                    ]
                )
            except:
                text = get_text_from_lang(
                    tracker, 
                    [
                        "According to the Fitbit measurements, the last 7 days your average sleep duration score was %s. Meaning you were %s getting enough hours of sleep at night.".format(average_score_text, average_score_text2),
                        "",
                        "Secondo le misurazioni Fitbit, negli ultimi 7 giorni il punteggio medio della durata del sonno è stato %s. Significa che %s dormivi abbastanza ore di notte.".format(average_score_text, average_score_text2),
                        "Conform măsurătorilor Fitbit, în ultimele 7 zile, scorul tău mediu al duratei de somn a fost %s. Înseamnă că %s dormi destule ore noaptea.".format(average_score_text, average_score_text2),
                    ]
                )
        except:
            text = get_text_from_lang(
                tracker, 
                [
                    "There no update from the Fitbit sleep data.",
                    "",
                    "Non ci sono aggiornamenti dai dati sul sonno di Fitbit.",
                    "Nu există nicio actualizare de la datele de somn Fitbit."
                ]
            )

        dispatcher.utter_message(text=text)
        return []

class ActionUtterGreet(Action):
    def name(self):
        return "action_utter_greet"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                random.choice(["Hey there! I am Zenon, your ALAMEDA personal assistant bot.", 
                                "Welcome, I am your ALAMEDA personal assistant bot.", 
                                "Hi, I am Zenon.",
                                "Greetings!"
                                ]),
                " ",
                random.choice(["Ciao! Sono Zenon, il tuo assistente personale ALAMEDA.",
                                "Benvenuto, sono il tuo assistente personale ALAMEDA",
                                "Ciao, sono Zenon.",
                                "Saluti!"]),
                random.choice(["Salutare! Sunt Zenon, asistentul tău personal ALAMEDA.",
                                "Bine ai venit, sunt asistentul tău personal ALAMEDA.",
                                "Bună, sunt Zenon.",
                                "Salutări!"])
            ],
        )
        dispatcher.utter_message(text=text)
        # check if it is the first time of the day
        isFirstTime = customTrackerInstance.isFirstTimeToday(tracker.current_state()['sender_id'])
        if isFirstTime:
            print("This is the first time for today.")
            return [SlotSet("is_first_time", isFirstTime)]#, FollowupAction("action_utter_how_are_you")]
        else:
            return [SlotSet("is_first_time", isFirstTime)]#, FollowupAction("action_options_menu")]

class ActionUtterHowAreYou(Action):
    def name(self):
        return "action_utter_how_are_you"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        # query the ontology for meaa results of the previous day
        today = datetime.datetime.combine(datetime.datetime.now(tz=pytz.utc), datetime.datetime.min.time())
        yesterday = (today - datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        today = today.strftime("%Y-%m-%dT%H:%M:%SZ")
        try :
            ontology_meaa_endpoint= endpoints_df[endpoints_df["name"]=="ONTOLOGY_MEAA_ENDPOINT"]["endpoint"].values[0]
            response = requests.get(ontology_meaa_endpoint, params={"userId": tracker.current_state()['sender_id'], "startDate":yesterday, "endDate":today})
            response.close()
            average_score_per_mood = json.loads(response.text)[0]
            average_score_per_mood.pop("userId")
            # returned classes ["avgPos","avgNeg","avgNeut","avgOth"]
            max_mood = max(average_score_per_mood, key=average_score_per_mood.get)
        except:
            max_mood = ""
            print("Error: no such entry in the ontology.")

        if max_mood == "avgNeg":
            text = get_text_from_lang(
                tracker,
                [
                    "From you facial expressions, I have noticed you were feeling down yesterday. Is there something troubling you?",
                    " ",
                    " ",
                    " ",
                ],
            )
            meaa_mood = "neg"
        else: 
            text = get_text_from_lang(
                tracker,
                [
                    random.choice(["How are you?", "How are you feeling today?", "How are you today?", "How is it going?", "How is your day going?"]),
                    " ",
                    random.choice(["Come stai?", "Come ti senti oggi?", "Come stai oggi?", "Come va?", "Come va la tua giornata?"]),
                    random.choice(["Ce mai faci?", "Cum te simți azi?", "Ce mai faci azi?", "Cum merge?", "Cum îți merge ziua?"]),
                ],
            )
            meaa_mood = "non_neg"
        dispatcher.utter_message(text=text)
        return [SlotSet("meaa_mood", meaa_mood)]

class ActionUtterNotificationGreet(Action):
    def name(self):
        return "action_utter_notification_greet"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        # onboard the user here in case the first time users open the app from a notification
        _ = customTrackerInstance.checkUserID(tracker.current_state()['sender_id'])

        q_abbreviation = tracker.get_slot("questionnaire")
        try: 
            q_name = get_text_from_lang(
                tracker,
                questionnaire_abbreviations[q_abbreviation],
            )
        except:
            q_name = "None"

        isFirstTime = customTrackerInstance.isFirstTimeToday(tracker.current_state()['sender_id'])
        questionnaire_to_reset = []
        # check if questionnaire is still pending
        isAvailable, state = customTrackerInstance.getSpecificQuestionnaireAvailability(tracker.current_state()['sender_id'], datetime.datetime.now(tz=pytz.utc).timestamp(), q_abbreviation)
        if isAvailable:
            text = get_text_from_lang(
                tracker,
                [
                    "Hey there. Just to note that the '{}' questionnaire is available.".format(q_name),
                    " ",
                    "Ehilà. Solo per notare che il questionario '{}' è disponibile per rispondere.".format(q_name),
                    "Hei acolo. Doar să rețineți că chestionarul '{}' este disponibil pentru a răspunde.".format(q_name),
                ],
            )
            print("\nBOT:", text)
            dispatcher.utter_message(text=text)
            # might need to reset questionnaire slots here in case the user didn't go through getAvailableQuestionnaires after the questionnaire became available
            if state == "available": questionnaire_to_reset.append(q_abbreviation)
            return reset_form_slots(tracker, domain, questionnaire_to_reset) + [SlotSet("notification_questionnaire_start", True)]#+ [FollowupAction("action_utter_ask_questionnaire_start")]
        else:
            # normally it shouldn't get to this point
            text = get_text_from_lang(
                tracker,
                [
                    "Hey there! Apologies, this questionnaire is no longer available.",
                    "Χαίρεται!",
                    "Ciao! Mi scuso, questo questionario non è più disponibile.",
                    "Salut! Scuze, acest chestionar nu mai este disponibil.",
                ],
            )
            dispatcher.utter_message(text=text)
            return [SlotSet("questionnaire", None), SlotSet("is_first_time", isFirstTime), SlotSet("notification_questionnaire_start", False)]


class ActionQuestionnaireCompleted(Action):
    def name(self):
        return "action_questionnaire_completed"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        q_abbreviation = tracker.get_slot("questionnaire")
        MSdomainIII_both = tracker.get_slot("MSdomainIII_both")
        MSdomainII_both = tracker.get_slot("MSdomainII_both")
        MSdomainIV_both = tracker.get_slot("MSdomainIV_both")

        customTrackerInstance.setQuestionnaireTempState(tracker.current_state()['sender_id'], datetime.datetime.now(tz=pytz.utc).timestamp(), q_abbreviation)

        if q_abbreviation == "MSdomainIII_1W" and MSdomainIII_both:
            return [SlotSet("questionnaire", "MSdomainIII_2W"), FollowupAction("MSdomainIII_2W_form")] 
        elif q_abbreviation == "MSdomainII_1M" and MSdomainII_both:
            return [SlotSet("questionnaire", "MSdomainII_3M"), FollowupAction("MSdomainII_3M_form")] 
        elif q_abbreviation == "MSdomainIV_Daily" and MSdomainIV_both:
            return [SlotSet("questionnaire", "MSdomainIV_1W"), FollowupAction("MSdomainIV_1W_form")] 
        else:
            text = get_text_from_lang(
                tracker,
                [
                    "We are good. Thank you for your time.",
                    "Το ερωτηματολόγιο ολοκληρώθηκε. Ευχαριστώ.",
                    "A posto! Grazie per il tuo tempo.",
                    "Suntem buni! Mulțumesc pentru timpul acordat.",
                ],
            )  
            dispatcher.utter_message(text=text)
            return [SlotSet("questionnaire", None)]#, FollowupAction("action_options_menu")]

# class ActionQuestionnaireCompletedFirstPart(Action):
#     def name(self):
#         return "action_questionnaire_completed_first_part"

#     def run(self, dispatcher, tracker, domain):
#         announce(self, tracker)

#         q_abbreviation = tracker.get_slot("questionnaire")
#         customTrackerInstance.setQuestionnaireTempState(tracker.current_state()['sender_id'], datetime.datetime.now(tz=pytz.utc).timestamp(), q_abbreviation)

#         #fake_intent={"name": "/"+q_abbreviation+"_start", "confidence": 1.0}
#         #UserUttered("/MSdomainIII_2W_start", fake_intent)

#         if q_abbreviation == "MSdomainIII_1W":
#             return [SlotSet("questionnaire", "MSdomainIII_2W"), FollowupAction("MSdomainIII_2W_form")] #UserUttered("/MSdomainIII_2W_start", fake_intent)]
#         elif q_abbreviation == "MSdomainII_1M":
#             return [SlotSet("questionnaire", "MSdomainII_3M"), FollowupAction("MSdomainII_3M_form")] #UserUttered("/MSdomainII_3M_start")]
#         elif q_abbreviation == "MSdomainIV_Daily":
#             return [SlotSet("questionnaire", "MSdomainIV_1W"), FollowupAction("MSdomainIV_1W_form")] #UserUttered("/MSdomainII_3M_start")]
#         else:
#             text = get_text_from_lang(
#                 tracker,
#                 [
#                     "We are good. Thank you for your time.",
#                     "Το ερωτηματολόγιο ολοκληρώθηκε. Ευχαριστώ.",
#                     "A posto! Grazie per il tuo tempo.",
#                     "Suntem buni! Mulțumesc pentru timpul acordat.",
#                 ],
#             )  
#             dispatcher.utter_message(text=text)
#             return [SlotSet("questionnaire", None), FollowupAction("action_options_menu")]

class ActionOntologyStoreSentiment(Action):
    def name(self):
        return "action_ontology_store_sentiment"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)
        #customTrackerInstance.saveToOntology(tracker.current_state()['sender_id'])
        return [FollowupAction("action_options_menu")]

class ActionQuestionnaireCancelled(Action):
    def name(self):
        return "action_questionnaire_cancelled"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "I stopped the process. We can finish it later.",
                "Σταμάτησα το ερωτηματολόγιο, μπορούμε να συνεχίσουμε αργότερα.",
                "Ho interrotto il processo. Possiamo finirlo più tardi.",
                "Am oprit procesul. Putem termina mai târziu.",
            ],
        )
        dispatcher.utter_message(text=text)
        customTrackerInstance.setQuestionnaireTempState(tracker.current_state()['sender_id'], datetime.datetime.now(tz=pytz.utc).timestamp(), tracker.get_slot("questionnaire"))
        return[]

class ActionQuestionnaireCancelledApp(Action):
    def name(self):
        return "action_questionnaire_cancelled_app"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)
        return[]

class ActionUtterStartingQuestionnaire(Action):
    def name(self):
        return "action_utter_starting_questionnaire"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)
        
        q_abbreviation = tracker.latest_message["intent"].get("name").replace("_start", "")
        print("Q-abbrev:", q_abbreviation)
        if (q_abbreviation != None) & (q_abbreviation in questionnaire_abbreviations.keys()):
            q_name = get_text_from_lang(
                tracker,
                questionnaire_abbreviations[q_abbreviation],
            )
            text = get_text_from_lang(
                tracker,
                [
                    "Starting '{}' questionnaire...".format(q_name),
                    " ",
                    "Iniziamo il questionario {}...".format(q_name),
                    "Pornește chestionarul '{}' ...".format(q_name),
                ],
            )
            dispatcher.utter_message(text=text)
            if q_abbreviation == "activLim":
                return [FollowupAction("action_utter_ACTIVLIM_intro_question")]
            else:
                return [FollowupAction("{}_form".format(q_abbreviation))]
        else:
            #TODO: probably change this text
            text = get_text_from_lang(
                tracker,
                [
                    "Something is wrong and I am not sure how to deal with it.",
                    " ",
                    "Qualcosa non va e non so come affrontarlo." #, Puoi digitare 'menu principale' per riportare la conversazione a un livello che mi è più familiare?",
                    "Ceva nu este în regulă și nu sunt sigur cum să mă descurc.",# Poți, te rog, tasta 'meniu principal' pentru a readuce conversația la un nivel cu care sunt mai familiarizat?",
                ],
            )
            dispatcher.utter_message(text=text)
            return [SlotSet("questionnaire", None), FollowupAction("action_options_menu_extra")]

class ActionSetQuestionnaireSlot(Action):
    def name(self):
        return "action_set_questionnaire_slot"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)
        
        q_abbreviation = tracker.latest_message["intent"].get("name").replace("_start", "")
        usecase = customTrackerInstance.getUserUsecase(tracker.current_state()['sender_id'])
        print("usecase:", usecase)
        if (usecase != None) & (usecase in questionnaire_per_usecase.keys()):
            if q_abbreviation in questionnaire_per_usecase[usecase]:
                return [SlotSet("questionnaire", q_abbreviation)]
            else:
                return [SlotSet("questionnaire", None)]
        else:
            return [SlotSet("questionnaire", None)]


class ActionUtterStartQuestionnaire(Action):
    def name(self):
        return "action_utter_ask_questionnaire_start"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        q_abbreviation = tracker.get_slot("questionnaire")
        if q_abbreviation == None or q_abbreviation not in questionnaire_abbreviations:
            text = get_text_from_lang(
                tracker,
                [
                    "Something went wrong. Can you please type 'main menu' to return the conversation to a level I am more familiar with?",
                    " ",
                    "Qualcosa non va e non so come affrontarlo. Puoi digitare 'menu principale' per riportare la conversazione a un livello che mi è più familiare?",
                    "Ceva nu este în regulă și nu sunt sigur cum să mă descurc. Poți, te rog, tasta 'meniu principal' pentru a readuce conversația la un nivel cu care sunt mai familiarizat?",
                ],
            )
            dispatcher.utter_message(text=text)
            return []    
        q_name = get_text_from_lang(
            tracker,
            questionnaire_abbreviations[q_abbreviation],
        )

        if q_abbreviation[:2] == "MS":
            minutes = 5
        elif q_abbreviation[:6] == "STROKE":
            minutes = 3
        else:
            minutes = 7
        text = get_text_from_lang(
            tracker,
            [
                "Would you like to fill it? It shouldn't take more than {} minutes.".format(minutes),
                " ",
                "Ti piacerebbe compilarlo? Non dovrebbero volerci più di {} minuti.".format(minutes),
                "Dorești să-l completezi? Nu ar trebui să dureze mai mult de {} minute.".format(minutes),
            ],
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Start {} Questionnaire".format(q_name), "No"],
                [" ", " "],
                ["Inizio il questionario {}".format(q_name), "No"],
                ["Pornește chestionarul {}".format(q_name), "Nu"],
            ],
            ['/{}_start'.format(q_abbreviation), '/deny']
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

####################################################################################################
# ACTIVLIM Questionnaire                                                                               #
####################################################################################################

class ActionUtterACTIVLIMintro(Action):
    def name(self):
        return "action_utter_ACTIVLIM_intro_question"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Could you, please, indicate how difficult you perceive each of the following activities?",
                " ",
                "",
                "Ați putea, vă rog, să indicați cât de dificil percepeți fiecare dintre următoarele activități?"
            ],
        )
        dispatcher.utter_message(text=text)
        return [FollowupAction("activLim_form")]    

####################################################################################################
# PSQI Questionnaire                                                                               #
####################################################################################################

class CalculatePSQIScore(Action):
    def name(self) -> Text:
        return "action_calculate_psqi_score"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        # Calculate Component 1 Score
        psqi_comp_1_score = int(tracker.get_slot("psqi_Q6_score"))
        print(f"Component 1 Score: {psqi_comp_1_score}")

        # Calculate Component 2 Score
        psqi_comp_2_score = int(tracker.get_slot("psqi_Q2_score")) + int(tracker.get_slot("psqi_Q5a_score"))

        if 1 <= psqi_comp_2_score <= 2:
            psqi_comp_2_score = 1
        elif 3 <= psqi_comp_2_score <= 4:
            psqi_comp_2_score = 2
        elif 5 <= psqi_comp_2_score <= 6:
            psqi_comp_2_score = 3
        else:
            psqi_comp_2_score = 0
        print(f"Component 2 Score: {psqi_comp_2_score}")

        # Calculate Component 3 Score
        psqi_comp_3_score = int(tracker.get_slot("psqi_Q4_score"))
        print(f"Component 3 Score: {psqi_comp_3_score}")
        
        # Calcualte Component 4 Score
        start_time = datetime.datetime.strptime(tracker.get_slot("psqi_Q1"), "%H:%M:%S")
        end_time = datetime.datetime.strptime(tracker.get_slot("psqi_Q3"), "%H:%M:%S") + datetime.timedelta(1)

        dt = end_time - start_time
        print(f"Timedelta: {dt}")
        hours_spent_in_bed = dt.total_seconds() / 3600
        print(f"Hours spent in bed: {hours_spent_in_bed}")
        habitual_sleep_efficiency = (float(tracker.get_slot("psqi_Q4")) / hours_spent_in_bed) * 100
        print(f"Habitual Sleep Efficiency: {habitual_sleep_efficiency}")
        if habitual_sleep_efficiency < 65:
            psqi_comp_4_score = 3
        elif 65 <= habitual_sleep_efficiency <= 74:
            psqi_comp_4_score = 2
        elif 75 <= habitual_sleep_efficiency <= 84:
            psqi_comp_4_score = 1
        else:
            psqi_comp_4_score = 0
        print(f"Component 4 Score: {psqi_comp_4_score}")

        # Calculate Component 5 Score
        psqi_Q5b2j_sum = sum([int(tracker.get_slot("psqi_Q5"+i+"_score")) for i in ["b", "c", "d", "e", "f", "g", "h", "i", "k"]])

        if psqi_Q5b2j_sum == 0:
            psqi_comp_5_score = 0
        elif 1 <= psqi_Q5b2j_sum <= 9:
            psqi_comp_5_score = 1
        elif 10 <= psqi_Q5b2j_sum <= 18:
            psqi_comp_5_score = 2
        else:
            psqi_comp_5_score = 3
        print(f"Component 5 Score: {psqi_comp_5_score}")

        # Calculate Component 6 Score
        psqi_comp_6_score = int(tracker.get_slot("psqi_Q7_score"))
        print(f"Component 6 Score: {psqi_comp_6_score}")

        # Calculate Component 7 Score
        psqi_comp_7_score = int(tracker.get_slot("psqi_Q8_score")) + int(tracker.get_slot("psqi_Q9_score"))

        if psqi_comp_7_score == 0:
            psqi_comp_7_score = 0
        elif 1 <= psqi_comp_7_score <= 2:
            psqi_comp_7_score = 1
        elif 3 <= psqi_comp_7_score <= 4:
            psqi_comp_7_score = 2
        else:
            psqi_comp_7_score = 3
        print(f"Component 7 Score: {psqi_comp_7_score}")

        # Calculate Global PSQI score
        psqi_global_score = psqi_comp_1_score + psqi_comp_2_score + psqi_comp_3_score + psqi_comp_4_score + psqi_comp_5_score + psqi_comp_6_score + psqi_comp_7_score

        print(f"Global PSQI Score: {psqi_global_score}")
        return [SlotSet("psqi_score", psqi_global_score)]

        

class ActionAskPSQIQ1(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q1"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_start_text
        )

        text = get_text_from_lang(
            tracker,
            [
                " when have you usually go to bed at night?",
                " ",
                " ",
                " la ce ora ati adormit noaptea?",
            ],
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskPSQIQ2(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q4"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_start_text
        )

        text = get_text_from_lang(
            tracker,
            [
                " how many hours of actual sleep did you get at night? (This may be different than the number of hours you spend in bed.)",
                " ",
                " ",
                " cate ore de somn ati avut pe parcursul noptii? (poate fi diferit de numarul de ore pe care le petreceti doar stand intins in pat)",
            ],
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskPSQIQ3(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q3"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)
        
        entry_text = get_text_from_lang(
            tracker, psqi_start_text
        )
    
        text = get_text_from_lang(
            tracker,
            [
                " when have you usually gotten up in the morning?",
                " ",
                " ",
                " la ce ora v-ati trezit dimineata?",
            ],
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskPSQIQ4(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q2"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_start_text
        )

        text = get_text_from_lang(
            tracker,
            [
                " how long (in minutes) has it usually take you to fall asleep each night?",
                " ",
                " ",
                " cat de mult ati sesizat ca dureaza pana reusiti sa adormiti in fiecare noapte. ",
            ],
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskPSQIQ5a(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q5a"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_q5
        )

        text = get_text_from_lang(
            tracker,
            [
                " cannot get to sleep within 30 minutes?",
                " ",
                " ",
                " nu ati reusit sa adormiti in 30 minute?",
            ],
        )

        buttons = get_buttons_from_lang(
            tracker,
            buttons_psqi,
            [
                '/inform{"given_answer":"Not during the past month"}', 
                '/inform{"given_answer":"Less than once a week"}', 
                '/inform{"given_answer":"Once or twice a week"}', 
                '/inform{"given_answer":"Three or more times a week"}'
            ]
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskPSQIQ5b(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q5b"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_q5
        )

        text = get_text_from_lang(
            tracker,
            [
                " wake up in the middle of the night or early morning?",
                " ",
                " ",
                " v-ati trezit in mijlocul noptii sau dimineata devreme?",
            ],
        )

        buttons = get_buttons_from_lang(
            tracker,
            buttons_psqi,
            [
                '/inform{"given_answer":"Not during the past month"}', 
                '/inform{"given_answer":"Less than once a week"}', 
                '/inform{"given_answer":"Once or twice a week"}', 
                '/inform{"given_answer":"Three or more times a week"}'
            ]
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskPSQIQ5c(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q5c"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_q5
        )

        text = get_text_from_lang(
            tracker,
            [
                " have to get up to use the bathroom?",
                " ",
                " ",
                " a trebuit sa va treziti pentru a merge la baie ?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            buttons_psqi,
            [
                '/inform{"given_answer":"Not during the past month"}', 
                '/inform{"given_answer":"Less than once a week"}', 
                '/inform{"given_answer":"Once or twice a week"}', 
                '/inform{"given_answer":"Three or more times a week"}'
            ]
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskPSQIQ5d(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q5d"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_q5
        )

        text = get_text_from_lang(
            tracker,
            [
                " cannot breathe comfortably?",
                " ",
                " ",
                " nu ati putut respira confortabil?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            buttons_psqi,
            [
                '/inform{"given_answer":"Not during the past month"}', 
                '/inform{"given_answer":"Less than once a week"}', 
                '/inform{"given_answer":"Once or twice a week"}', 
                '/inform{"given_answer":"Three or more times a week"}'
            ]
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskPSQIQ5e(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q5e"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_q5
        )

        text = get_text_from_lang(
            tracker,
            [
                " cough or snore loudly?",
                " ",
                " ",
                " ati tusit sau sforait zgmotos?"
            ]
        )

        text = entry_text + text

        buttons = get_buttons_from_lang(
            tracker,
            buttons_psqi,
            [
                '/inform{"given_answer":"Not during the past month"}', 
                '/inform{"given_answer":"Less than once a week"}', 
                '/inform{"given_answer":"Once or twice a week"}', 
                '/inform{"given_answer":"Three or more times a week"}'
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskPSQIQ5f(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q5f"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_q5
        )

        text = get_text_from_lang(
            tracker,
            [
                " feel too cold?",
                " ",
                " ",
                " v-a fost frig?"
            ]
        )

        text = entry_text + text

        buttons = get_buttons_from_lang(
            tracker,
            buttons_psqi,
            [
                '/inform{"given_answer":"Not during the past month"}', 
                '/inform{"given_answer":"Less than once a week"}', 
                '/inform{"given_answer":"Once or twice a week"}', 
                '/inform{"given_answer":"Three or more times a week"}'
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskPSQIQ5g(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q5g"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_q5
        )

        text = get_text_from_lang(
            tracker,
            [
                " feel too hot?",
                " ",
                " ",
                " v-a fost cald?"
            ]
        )

        text = entry_text + text

        buttons = get_buttons_from_lang(
            tracker,
            buttons_psqi,
            [
                '/inform{"given_answer":"Not during the past month"}', 
                '/inform{"given_answer":"Less than once a week"}', 
                '/inform{"given_answer":"Once or twice a week"}', 
                '/inform{"given_answer":"Three or more times a week"}'
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskPSQIQ5h(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q5h"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_q5
        )

        text = get_text_from_lang(
            tracker,
            [
                " had bad dreams?",
                " ",
                " ",
                " ati avut cosmaruri?"
            ]
        )

        text = entry_text + text

        buttons = get_buttons_from_lang(
            tracker,
            buttons_psqi,
            [
                '/inform{"given_answer":"Not during the past month"}', 
                '/inform{"given_answer":"Less than once a week"}', 
                '/inform{"given_answer":"Once or twice a week"}', 
                '/inform{"given_answer":"Three or more times a week"}'
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskPSQIQ5i(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q5i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_q5
        )

        text = get_text_from_lang(
            tracker,
            [
                " have pain?",
                " ",
                " ",
                " ati avut dureri?"
            ]
        )

        text = entry_text + text

        buttons = get_buttons_from_lang(
            tracker,
            buttons_psqi,
            [
                '/inform{"given_answer":"Not during the past month"}', 
                '/inform{"given_answer":"Less than once a week"}', 
                '/inform{"given_answer":"Once or twice a week"}', 
                '/inform{"given_answer":"Three or more times a week"}'
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskPSQIQ5j(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q5j"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_q5
        )

        text = get_text_from_lang(
            tracker,
            [
                " other reason? (please describe)",
                " ",
                " ",
                " alte motive?"
            ]
        )

        text = entry_text[:-3] + "of" + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskPSQIQ5k(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q5k"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How often during the past month have you had trouble sleeping beacuse of this?",
                " ",
                " ",
                "Cat de des in ultima luna ati avut probleme cu somnul din cauza lucrurilor mai sus mentionate?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            buttons_psqi,
            [
                '/inform{"given_answer":"Not during the past month"}', 
                '/inform{"given_answer":"Less than once a week"}', 
                '/inform{"given_answer":"Once or twice a week"}', 
                '/inform{"given_answer":"Three or more times a week"}'
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskPSQIQ6(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q6"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_start_text
        )

        text = get_text_from_lang(
            tracker, [
                " how would you rate your sleep quality overall?",
                " ",
                " ",
                " ce calificativ ati putea da calitatii somnului dumneavoastra in general?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Very good", "Fairly good", "Fairly bad", "Very bad"],
                [" ", " "],
                [" ", " "],
                ["Foarte bun", "Satisfacator", "Nesatisfacator", "Foarte rau"],
            ],
            [
                '/inform{"given_answer":"Very good"}', 
                '/inform{"given_answer":"Fairly good"}', 
                '/inform{"given_answer":"Fairly bad"}', 
                '/inform{"given_answer":"Very bad"}'
            ]
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []
        
class ActionAskPSQIQ7(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q7"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_start_text
        )

        text = get_text_from_lang(
            tracker, [
                " how often have you taken medicine (prescribed or \"over the counter\") to help you sleep?",
                " ",
                " ",
                " cat de des ati avut nevoie de medicamente (luate fara recomandarea unui medic) pentru a va ajuta sa dormiti?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Not during the past month", "Less than once a week", "Once or twice a week", "Three or more times a week"],
                [" ", " "],
                [" ", " "],
                ["Nu in ultima luna", "Mai putin de o data pe saptamana", "O data sau de 2 ori pe saptamana", "De 3 sau mai multe ori pe saptamana"],
            ],
            [
                '/inform{"given_answer":"Not during the past month"}', 
                '/inform{"given_answer":"Less than once a week"}', 
                '/inform{"given_answer":"Once or twice a week"}', 
                '/inform{"given_answer":"Three or more times a week"}'
            ]
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskPSQIQ8(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q8"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_start_text
        )

        text = get_text_from_lang(
            tracker, [
                " how often have you had trouble staying awake while driving, eating meals, or engaging in social activity?",
                " ",
                " ",
                " cat de des ati intampinat probleme in a va mentine treaz in timp ce conduceati, mancati sau erati implicati in alte activitati sociale?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Not during the past month", "Less than once a week", "Once or twice a week", "Three or more times a week"],
                [" ", " "],
                [" ", " "],
                ["Nu in ultima luna", "Mai putin de o data pe saptamana", "O data sau de 2 ori pe saptamana", "De 3 sau mai multe ori pe saptamana"],
            ],
            [
                '/inform{"given_answer":"Not during the past month"}', 
                '/inform{"given_answer":"Less than once a week"}', 
                '/inform{"given_answer":"Once or twice a week"}', 
                '/inform{"given_answer":"Three or more times a week"}'
            ]
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskPSQIQ9(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q9"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_start_text
        )

        text = get_text_from_lang(
            tracker, [
                " how much of a problem has it been for you to keep up enough enthousiasm to get things done?",
                " ",
                " ",
                " cat de dificil a fost pentru dumneavoastra sa va mentineti entuziasmul pentru a rezolva problemele zilnice?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["No problem at all", "Only a very slight problem", "Somewhat of a problem", "A very big problem"],
                [" ", " "],
                [" ", " "],
                ["Nu a fost o problema", "A fost doar putin dificil", "A fost o problema intr-o oarecare masura", "A fost foarte dificil"],
            ],
            [
                '/inform{"given_answer":"No problem at all"}', 
                '/inform{"given_answer":"Only a very slight problem"}', 
                '/inform{"given_answer":"Somewhat of a problem"}', 
                '/inform{"given_answer":"A very big problem"}'
            ]
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskPSQIQ10(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q10"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker, [
                "If you have a roommate or bed partner, ask him/her how often in the past month you have had...",
                " ",
                " ",
                "Daca aveti un coleg de camera/partener intrebati-l cat de des in ultima luna"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["No bed partner or roommate", "Partner/roommate in other room", "Partner in same room, but not same bed", "Partner in same bed"],
                [" ", " "],
                [" ", " "],
                ["Nu am partener sau coleg de camera", "Partenerul sau colegul doarme intr-o alta camera", "Partenerul doarme in aceeasi camera, dar nu in acelasi pat", "Partenerul doarme in acelasi pat"],
            ],
            [
                '/inform{"given_answer":"No bed partner or roommate"}', 
                '/inform{"given_answer":"Partner/roommate in other room"}', 
                '/inform{"given_answer":"Partner in same room, but not same bed"}', 
                '/inform{"given_answer":"Partner in same bed"}'
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskPSQIQ10a(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q10a"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker, [
                "loud snoring",
                " ",
                " ",
                "Ati sforait foarte zgmotos ?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Not during the past month", "Less than once a week", "Once or twice a week", "Three or more times a week"],
                [" ", " "],
                [" ", " "],
                ["Nu in ultima luna", "Mai putin de o data pe saptamana", "O data sau de 2 ori pe saptamana", "De 3 sau mai multe ori pe saptamana"],
            ],
            [
                '/inform{"given_answer":"Not during the past month"}', 
                '/inform{"given_answer":"Less than once a week"}', 
                '/inform{"given_answer":"Once or twice a week"}', 
                '/inform{"given_answer":"Three or more times a week"}'
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskPSQIQ10b(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q10b"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker, [
                "long pauses between breath while asleep",
                " ",
                " ",
                "ati facut pauze lungi intre respiratii in timp ce dormeati ?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Not during the past month", "Less than once a week", "Once or twice a week", "Three or more times a week"],
                [" ", " "],
                [" ", " "],
                ["Nu in ultima luna", "Mai putin de o data pe saptamana", "O data sau de 2 ori pe saptamana", "De 3 sau mai multe ori pe saptamana"],
            ],
            [
                '/inform{"given_answer":"Not during the past month"}', 
                '/inform{"given_answer":"Less than once a week"}', 
                '/inform{"given_answer":"Once or twice a week"}', 
                '/inform{"given_answer":"Three or more times a week"}'
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskPSQIQ10c(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q10c"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker, [
                "legs twitching or jerking while you sleep",
                " ",
                " ",
                "ati avut tresariri ale picioarelor in timpul somnului?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Not during the past month", "Less than once a week", "Once or twice a week", "Three or more times a week"],
                [" ", " "],
                [" ", " "],
                ["Nu in ultima luna", "Mai putin de o data pe saptamana", "O data sau de 2 ori pe saptamana", "De 3 sau mai multe ori pe saptamana"],
            ],
            [
                '/inform{"given_answer":"Not during the past month"}', 
                '/inform{"given_answer":"Less than once a week"}', 
                '/inform{"given_answer":"Once or twice a week"}', 
                '/inform{"given_answer":"Three or more times a week"}'
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []  

class ActionAskPSQIQ10d(Action):
    def name(self) -> Text:
        return "action_ask_psqi_Q10d"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker, [
                "episodes of disorientation or confusion during sleep",
                " ",
                " ",
                "ati avut alte miscari agitate in timpul somnului (va rugam descrieti)"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Not during the past month", "Less than once a week", "Once or twice a week", "Three or more times a week"],
                [" ", " "],
                [" ", " "],
                ["Nu in ultima luna", "Mai putin de o data pe saptamana", "O data sau de 2 ori pe saptamana", "De 3 sau mai multe ori pe saptamana"],
            ],
            [
                '/inform{"given_answer":"Not during the past month"}', 
                '/inform{"given_answer":"Less than once a week"}', 
                '/inform{"given_answer":"Once or twice a week"}', 
                '/inform{"given_answer":"Three or more times a week"}'
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ValidatePSQIForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_psqi_form"

    def validate_psqi_Q1(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validation for the question 'when have you usually go to bed at night?' """

        try:
            if len(slot_value) > 8:
                slot_value = datetime.datetime.fromisoformat(slot_value)
                slot_value = slot_value.strftime("%Y-%m-%d %H:%M:%S")
                slot_value = datetime.datetime.strptime(slot_value, "%Y-%m-%d %H:%M:%S")
                slot_value = slot_value.time()  
                slot_value = slot_value.strftime("%H:%M:%S")                                  

                return {"psqi_Q1": slot_value}
            else:
                return {"psqi_Q1": slot_value}

        except:
            dispatcher.utter_message(text="Please give a valid answer")
            return {"psqi_Q1": None}

    def validate_psqi_Q2(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """
        Validation for the question 'how long (in minutes) has it usually take you to fall asleep each night?'
        """ 

        try:
            # slot_value = next(tracker.get_latest_entity_values("number"), None)
            if isinstance(slot_value, str):
                slot_value = int(slot_value)

            if slot_value <= 15:
                return {"psqi_Q2": slot_value, "psqi_Q2_score": "0"}
            elif slot_value <= 30:
                return {"psqi_Q2": slot_value, "psqi_Q2_score": "1"}
            elif slot_value <= 60:
                return {"psqi_Q2": slot_value, "psqi_Q2_score": "2"}
            else:
                return {"psqi_Q2": slot_value, "psqi_Q2_score": "3"}

        except:
            dispatcher.utter_message(text="Please give a valid answer")
            return {"psqi_Q2": None}      

    def validate_psqi_Q3(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validation for the question 'when have you usually gotten up in the morning?' """

        try:
            if len(slot_value) > 8:
                slot_value = datetime.datetime.fromisoformat(slot_value)
                slot_value = slot_value.strftime("%Y-%m-%d %H:%M:%S")
                slot_value = datetime.datetime.strptime(slot_value, "%Y-%m-%d %H:%M:%S")
                slot_value = slot_value.time()
                if slot_value < datetime.datetime.strptime("12:00:00", "%H:%M:%S").time():
                    slot_value = slot_value.strftime("%H:%M:%S")      
                    return {"psqi_Q3": slot_value}
                else:
                    dispatcher.utter_message(text="You can't give a time after noon.")
                    return {"psqi_Q3": None}
            else:
                return {"psqi_Q3": slot_value}

        except:
            dispatcher.utter_message(text="Please give a valid answer")
            return {"psqi_Q3": None}     

    def validate_psqi_Q4(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validation for the question  
        'how many hours of actual sleep did you get at night? 
        (This may be different than the number of hours you spend in bed.)' """

        try:
            # slot_value = next(tracker.get_latest_entity_values("number"), None)
            if isinstance(slot_value, str):
                slot_value = int(slot_value)

            if slot_value > 7:
                return {"psqi_Q4": slot_value, "psqi_Q4_score": "0"}
            elif 6 <= slot_value <= 7:
                return {"psqi_Q4": slot_value, "psqi_Q4_score": "1"}
            elif 5 <= slot_value < 6:
                return {"psqi_Q4": slot_value, "psqi_Q4_score": "2"}
            else:
                return {"psqi_Q4": slot_value, "psqi_Q4_score": "3"}
            
        except:
            dispatcher.utter_message(text="Please give a valid answer")
            return {"psqi_Q4": None}   

    def validate_psqi_Q6(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validation for the question 6"""

        if slot_value == "Very good":
            return{"psqi_Q6_score": "0"}
        elif slot_value == "Fairly good":
            return{"psqi_Q6_score": "1"}
        elif slot_value == "Fairly bad":
            return{"psqi_Q6_score": "2"}
        else:
            return{"psqi_Q6_score": "3"}

    def validate_psqi_Q5a(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validation for the question 5a"""

        if slot_value == "Not during the past month":
            return{"psqi_Q5a_score": "0"}
        elif slot_value == "Less than once a week":
            return{"psqi_Q5a_score": "1"}
        elif slot_value == "Once or twice a week":
            return{"psqi_Q5a_score": "2"}
        else:
            return{"psqi_Q5a_score": "3"}   

    def validate_psqi_Q5b(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validation for the question 5b"""

        if slot_value == "Not during the past month":
            return{"psqi_Q5b_score": "0"}
        elif slot_value == "Less than once a week":
            return{"psqi_Q5b_score": "1"}
        elif slot_value == "Once or twice a week":
            return{"psqi_Q5b_score": "2"}
        else:
            return{"psqi_Q5b_score": "3"}      

    def validate_psqi_Q5c(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validation for the question 5c"""

        if slot_value == "Not during the past month":
            return{"psqi_Q5c_score": "0"}
        elif slot_value == "Less than once a week":
            return{"psqi_Q5c_score": "1"}
        elif slot_value == "Once or twice a week":
            return{"psqi_Q5c_score": "2"}
        else:
            return{"psqi_Q5c_score": "3"}        

    def validate_psqi_Q5d(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validation for the question 5d"""

        if slot_value == "Not during the past month":
            return{"psqi_Q5d_score": "0"}
        elif slot_value == "Less than once a week":
            return{"psqi_Q5d_score": "1"}
        elif slot_value == "Once or twice a week":
            return{"psqi_Q5d_score": "2"}
        else:
            return{"psqi_Q5d_score": "3"}     

    def validate_psqi_Q5e(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validation for the question 5e"""

        if slot_value == "Not during the past month":
            return{"psqi_Q5e_score": "0"}
        elif slot_value == "Less than once a week":
            return{"psqi_Q5e_score": "1"}
        elif slot_value == "Once or twice a week":
            return{"psqi_Q5e_score": "2"}
        else:
            return{"psqi_Q5e_score": "3"}     

    def validate_psqi_Q5f(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validation for the question 5f"""

        if slot_value == "Not during the past month":
            return{"psqi_Q5f_score": "0"}
        elif slot_value == "Less than once a week":
            return{"psqi_Q5f_score": "1"}
        elif slot_value == "Once or twice a week":
            return{"psqi_Q5f_score": "2"}
        else:
            return{"psqi_Q5f_score": "3"}          

    def validate_psqi_Q5g(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validation for the question 5g"""

        if slot_value == "Not during the past month":
            return{"psqi_Q5g_score": "0"}
        elif slot_value == "Less than once a week":
            return{"psqi_Q5g_score": "1"}
        elif slot_value == "Once or twice a week":
            return{"psqi_Q5g_score": "2"}
        else:
            return{"psqi_Q5g_score": "3"}   

    def validate_psqi_Q5h(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validation for the question 5h"""

        if slot_value == "Not during the past month":
            return{"psqi_Q5h_score": "0"}
        elif slot_value == "Less than once a week":
            return{"psqi_Q5h_score": "1"}
        elif slot_value == "Once or twice a week":
            return{"psqi_Q5h_score": "2"}
        else:
            return{"psqi_Q5h_score": "3"}   

    def validate_psqi_Q5i(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validation for the question 5i"""

        if slot_value == "Not during the past month":
            return{"psqi_Q5i_score": "0"}
        elif slot_value == "Less than once a week":
            return{"psqi_Q5i_score": "1"}
        elif slot_value == "Once or twice a week":
            return{"psqi_Q5i_score": "2"}
        else:
            return{"psqi_Q5i_score": "3"}        

    def validate_psqi_Q5k(  # Q5j from real questionnaire corresponds to Q5k to our version
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validation for the question 5k"""

        if slot_value == "Not during the past month":
            return{"psqi_Q5k_score": "0"}
        elif slot_value == "Less than once a week":
            return{"psqi_Q5k_score": "1"}
        elif slot_value == "Once or twice a week":
            return{"psqi_Q5k_score": "2"}
        else:
            return{"psqi_Q5k_score": "3"}    

    def validate_psqi_Q7(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validation for the question 7"""

        if slot_value == "Not during the past month":
            return{"psqi_Q7_score": "0"}
        elif slot_value == "Less than once a week":
            return{"psqi_Q7_score": "1"}
        elif slot_value == "Once or twice a week":
            return{"psqi_Q7_score": "2"}
        else:
            return{"psqi_Q7_score": "3"}   

    def validate_psqi_Q8(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validation for the question 8"""

        if slot_value == "Not during the past month":
            return{"psqi_Q8_score": "0"}
        elif slot_value == "Less than once a week":
            return{"psqi_Q8_score": "1"}
        elif slot_value == "Once or twice each week":
            return{"psqi_Q8_score": "2"}
        else:
            return{"psqi_Q8_score": "3"}     

    def validate_psqi_Q9(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validation for the question 9"""

        if slot_value == "No problem at all":
            return{"psqi_Q9_score": "0"}
        elif slot_value == "Only a very slight problem":
            return{"psqi_Q9_score": "1"}
        elif slot_value == "Somewhat of a problem":
            return{"psqi_Q9_score": "2"}
        else:
            return{"psqi_Q9_score": "3"}                                                                                                                                                          


####################################################################################################
# Dizziness and Balance Questionnaire                                                              #
####################################################################################################

class ActionAskDnBQ1(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q1"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "When did your problem start (date)?",
                " ",
                " ",
                "Cand a inceput problema dumneavoastra (data)?"
            ]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBQ2(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q2"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Was it associated with a related event (e.g. head injury) ?",
                " ",
                " ",
                "A aparut in contextul unui alt eveniment (de exemplu, lovitura la cap) ?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            ['/affirm', '/deny']
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBQ2i(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q2i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            ["Please explain:", " ", " ", "Daca da, explicati...",],
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBQ3(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q3"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Was the onset of your symptoms:",
                " ",
                " ",
                "Simptomele au debutat :"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["sudden", "gradual", "overnight", "other"],
                [" ", " "],
                [" ", " "],
                ["brusc", "gradual", "peste noapte", "alt mod"]
            ],
            ['/affirm', '/affirm', '/affirm', '/deny']
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBQ3i(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q3i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            ["describe", " ", " ", "detaliati"]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBQ4(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q4"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Are your symptoms:",
                " ",
                " ",
                "Simptomele sunt :"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["constant", "variable i.e. come and go in attacks"],
                [" ", " "],
                [" ", " "],
                ["constante", "variabile de exemplu, apar si dispar"]
            ],
            ['/deny', '/affirm']
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBQ4a(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q4a"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "If variable, the spells occur every (# of hours/days/weeks/months/years)",
                " ",
                " ",
                "Daca variaza, crizele apar la fiecare.... dureaza .... (ore/zile/saptamani)"
            ]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBQ4b(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q4b"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "If variable, the spells last:",
                " ",
                " ",
                "Daca variaza, crizele dureaza :",
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["< 1 min.", "1-2 min.", "3-10 min.", "11-30 min.", "½-1 hr.", "2-6 hrs.", "7-24hrs.", "> 24 hrs."],
                [" ", " "],
                [" ", " "],
                ["mai putin de 1 minut", "intre 1-2 minute", "intre 3-10 minute", "11-30 minute", "1/2 ora-1 ora", "2-6 ore", "7-24 ore", ">24 ore"]
            ],
            [
                '/inform{"given_answer":"< 1 min."}', 
                '/inform{"given_answer":"1-2 min."}', 
                '/inform{"given_answer":"3-10 min."}', 
                '/inform{"given_answer":"11-30 min."}', 
                '/inform{"given_answer":"½-1 hr."}', 
                '/inform{"given_answer":"2-6 hrs."}', 
                '/inform{"given_answer":"7-24hrs."}', 
                '/inform{"given_answer":"> 24 hrs."}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBQ4c(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q4c"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "If variable, do you have any warning signs that an attack is about to happen?",
                " ",
                " ",
                "Daca variaza, aveti simptome care anunta inceputul unei crize?",
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["yes", "no"],
                [" ", " "],
                [" ", " "],
                ["da", "nu"]
            ],
            ['/affirm', '/deny']
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBQ4ci(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q4ci"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Please describe:",
                " ",
                " ",
                "Descrieti:"
            ]
        )
        
        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBQ4d(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q4d"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "If variable, are you completely free of symptoms between attacks?",
                " ",
                " ",
                "Daca variaza, intre crize nu exista niciun fel de simptom ?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["yes", "no"],
                [" ", " "],
                [" ", " "],
                ["da", "nu"]
            ],
            ['/affirm', '/deny']
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBSymptoms(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Symptoms"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)
        
        text = get_text_from_lang(
            tracker, [
                "SYMPTOMS: Please select all that apply and press send:",
                " ",
                " ",
                "Simptome: Te rog bifează tot ce se aplică și apasă 'Trimite':"
            ]
        )
        
        if tracker.get_slot("language") == "Romanian":
            data = {
                "choices": [
                    "Ameteala", "Senzatie de urechi infundate", "Tulburare de vedere", "Senzatie de ‘cap tulbure’",
                    "Caderi ", "Senzatia de rotire a lucrurilor din jur", "Pierdere a auzului", "Rau de miscare", "Durere de cap",
                    "Nesiguranta la mers", "Zgomote in urechi", "Oboseala", "Vedere dubla", "Tulburare de echilibru", "Brain fog",
                    "Imbalance/Disequilibrium"
                ]
            }
        # this shouldn't happen but just in case
        elif tracker.get_slot("language") == "Italian":
            data = {
                "choices": ["", ""]
            }
        else:
            data = {
                    "choices": [
                        "Dizziness", "Spinning/Vertigo", "Lightheadedness", "Rocking/tilting",
                        "Visual changes", "Headache", "Fatigue", "Unsteadiness", "Falling",
                        "Ringing/noise in ears", "Fullness in ears", "Motion sensitive",
                        "Hearing loss", "Double vision", "Brain fog", "Imbalance/Disequilibrium"
                    ]
                }

        print("\nBOT:", text + "\n" + str(data))
        dispatcher.utter_message(text=text, json_message=data)
        return []

class ActionAskDnBQ5(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q5"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Do your symptoms occur when changing positions?",
                " ",
                " ",
                "Simptomele pe care le descrieti apar cand schimbati pozitia corpului/a capului ?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            ['/affirm', '/deny']
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBQ5i(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q5i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)
        
        text = get_text_from_lang(
            tracker, [
                "Please select all that apply and press send:",
                " ",
                " ",
                "Te rog bifează tot ce va caracterizeaza și apasă 'Trimite':"
            ]
        )

        if tracker.get_slot("language") == "Romanian":
            data = {
                "choices": [
                    "Senzatia de rotire a corpului catre stanga", "Senzatia de rotire a corpului catre dreapta", 
                    "La trecerea din pozitia culcat in sezut", "La privirea in sus, cu capul pe spate",
                    "La intoarcerea capului", "La privirea in jos, cu capul in fata"
                ]
            }
        # this shouldn't happen but just in case
        elif tracker.get_slot("language") == "Italian":
            data = {
                "choices": ["", ""]
            }
        else :
            data = {
                    "choices": [
                        "Rolling your body to the left", "Rolling your body to the right", 
                        "Moving from a lying to a sitting position", "Looking up with your head back",
                        "Turning head side to side while sitting/standing", "Bending over with your head down"
                    ]
                }


        print("\nBOT:", text + "\n" + str(data))
        dispatcher.utter_message(text=text, json_message=data)
        return []

class ActionAskDnBQ6(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q6"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Is there anything that makes your symptoms worse?",
                " ",
                " ",
                "Exista lucruri care agraveaza simptomele ?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            ['/affirm', '/deny']
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBQ6i(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q6i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)
        
        text = get_text_from_lang(
            tracker, [
                "Please select all that apply and press send:",
                " ",
                " ",
                "Daca da, bifati ce va caracterizeaza :"
            ]
        )

        if tracker.get_slot("language") == "Romanian":
            data = {
                "choices": [
                    "Miscarea capului", "Activitatea fizica", "Condus masina", "Zone aglomerate",
                    "Zgomote puternice", "Tusea, suflatul nasului", "Stat in picioare", "Mancatul anumitor alimente", 
                    "Perioada din zi", "Perioada menstruala", "Altele (vă rugăm să introduceți răspunsul dvs.)"
                ]
            }
        # this shouldn't happen but just in case
        elif tracker.get_slot("language") == "Italian":
            data = {
                "choices": ["", ""]
            }
        else:
            data = {
                    "choices": [
                        "Moving my head", "Physical activity or exercise", "Riding or driving in the car", "Large crowds or a busy environment",
                        "Loud sounds", "Coughing, blowing the nose, or straining", "Standing up", "Eating certain foods", 
                        "Time of day", "Menstrual periods (if applicable)", "Other (please type your answer)"
                    ]
                }


        print("\nBOT:", text + "\n" + str(data))
        dispatcher.utter_message(text=text, json_message=data)
        return []

class ActionAskDnBQ7(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q7"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Is there anything that makes your symptoms better?",
                " ",
                " ",
                "Exista lucruri care amelioreaza simptomele ?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            ['/affirm', '/deny']
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBQ7i(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q7i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            ["Please explain:", " ", " ", "Detaliati:"]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBQ8(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q8"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Do you have difficulty walking in the dark or at dusk?",
                " ",
                " ",
                "Aveti dificultati in a merge pe intuneric ?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBQ9(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q9"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "When you have symptoms, do you need to support yourself to stand or walk?",
                " ",
                " ",
                "Cand apar simptomele aveti nevoie de sprijin pentru a sta in picioare sau a merge ?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            ['/affirm', '/deny']
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBQ9i(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q9i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How do you support yourself?",
                " ", 
                " ", 
                "Cum vă întrețineți?"
            ]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBQ10(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q10"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Do you have difficulty walking on uneven surfaces (e.g. grass or gravel) compared with smooth surfaces (e.g. concrete)?",
                " ",
                " ",
                "Aveti dificultati in a merge pe suprafete neregulate (pe iarba/pavaj) comparativ cu suprafetele netede (pe beton) ?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBQ11(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q11"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Have you ever fallen as a result of your current problem?",
                " ",
                " ",
                "Ati cazut vreodata in timpul crizelor ?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            ['/affirm', '/deny']
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBQ11i(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q11i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            ["How many times did you fall in the last 6 months?",
             " ", 
             " ", 
             "Cate caderi au fost pe parcursul a 6 luni?"]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBQ12(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q12"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Has there been a recent change in your vision, including contacts or glasses?",
                " ",
                " ",
                "S-a schimbat ceva in ceea ce priveste calitatea vederii dumneavoastra recent, inclusiv purtat/schimbat lentile de contact sau ochelari de vedere ?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBQ12i(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Q12i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            ["Explain:",
             " ", 
             " ", 
             "Explicati:"]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBPastMedicalHistory(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_PastMedicalHistory"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)
        
        text = get_text_from_lang(
            tracker, [
                "Past medical history - Please select all that apply and press send:",
                " ",
                " ",
                "Antecedente personale patologice - Te rog bifează tot ce va caracterizeaza și apasă 'Trimite':"
            ]
        )

        if tracker.get_slot("language") == "Romanian":
            data = {
                "choices": [
                    "Contuzie", "Hipertensiune/ Hipotensiune arteriala", "Ataxie", 
                    "Crize epileptice", "Diabet zaharat/Neuropatie", "Migrena", 
                    "Accident rutier", "Insuficienta cardiaca/Infarct", "Astm",
                    "AVC/AIT", "Cancer", "Istoric de infectie sau tromboze", 
                    "Scleroza multipla", "Boala vasculara periferica", "Interventie chirurgicala la nivelul coloanei vertebrale",
                    "Boala Parkinson", "Depresie/atac de panica", "Traumatism la nivelul coapsei, genunchiului/umarului/spatelui",
                    "Glaucom/degenerescenta maculara", "Afectare articulara la nivel cervical", "Nivel crescut colesterol",
                    "Fibromialgie", "Sindromul oboselii cronice", "Boala autoimuna"
                ]
            }
        # this shouldn't happen but just in case
        elif tracker.get_slot("language") == "Italian":
            data = {
                "choices": ["", ""]
            }
        else:
            data = {
                    "choices": [
                        "Concussion", "Hypertension/Hypotension", "Ataxia", 
                        "Seizures", "Diabetes/Neuropathy", "HA/Migraines", 
                        "Motor vehicle accident", "CABG/CAD/Heart attack/CHF", "Asthma/COPD",
                        "Stroke/TIA", "Cancer", "History of infection or blood clot",
                        "Multiple sclerosis", "Peripheral vascular disease", "THR/TKR/Spine surgery", 
                        "Parkinson’s disease", "Depression/Panic attacks", "Hip/knee/ankle/shoulder/back injury",
                        "Glaucoma/macular degeneration", "Neck arthritis/surgery", "High cholesterol/triglycerides",
                        "Fibromyalgia", "Chronic fatigue syndrome", "Auto immune disease"
                    ]
                }


        print("\nBOT:", text + "\n" + str(data))
        dispatcher.utter_message(text=text, json_message=data)
        return []

class ActionAskDnBPastMedicalHistoryOther(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_PastMedicalHistoryOther"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Past medical history - Other:",
                " ", 
                " ", 
                "Antecedente personale patologice - Altele (detaliati):"
            ]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBMedicalTests(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_MedicalTests"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)
        
        text = get_text_from_lang(
            tracker, [
                "Medical Tests:",
                " ",
                " ",
                "Teste medicale :"
            ]
        )

        if tracker.get_slot("language") == "Romanian":
            data = {
                "choices": [
                    "MRI", "MRA", "CT", "X-Ray", "Blood"    # TODO To be changed to romanian version
                ]
            }
         # this shouldn't happen but just in case
        elif tracker.get_slot("language") == "Italian":
            data = {
                "choices": ["", ""]
            }
        else:
            data = {
                    "choices": [
                        "MRI", "MRA", "CT", "X-Ray", "Blood"
                    ]
                }


        print("\nBOT:", text + "\n" + str(data))
        dispatcher.utter_message(text=text, json_message=data)
        return []

class ActionAskDnBMedicalTestsOther(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_MedicalTestsOther"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Medical Tests - Other:",
                " ", 
                " ", 
                "Teste medicale - Altele (detaliati):"
            ]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBOnSetType(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_OnSetType"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Onset Type:",
                " ", 
                " ", 
                "Tipul debutului simptomelor-alegeti dintre variantele urmatoare :"
            ]
        )

        if tracker.get_slot("language") == "Romanian":
            data = {
                "choices": [
                    "dupa interventie chirurgicala", "dupa un traumatism", "fara sa poata fi asociate cu un anumit eveniment"
                ]
            }
        # this shouldn't happen but just in case
        elif tracker.get_slot("language") == "Italian":
            data = {
                "choices": ["", ""]
            }
        else:
            data = {
                    "choices": [
                        "SURGICAL", "INJURY", "INSIDIOUS"
                    ]
                }


        print("\nBOT:", text + "\n" + str(data))
        dispatcher.utter_message(text=text, json_message=data)
        return []

class ActionAskDnBEarSymptomI(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomI"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Do you have difficulty with hearing?",
                " ",
                " ",
                "Aveti dificultăți cu auzul?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}'
            ]
        )

        intro_text = get_text_from_lang(
            tracker,
            [
                "Describe any ear related symptoms:",
                " ",
                " ",
                "Descrieți orice simptome legate de ureche:"
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=intro_text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBEarSymptomIa(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomIa"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Which ear(s):",
                " ",
                " ",
                "Care ureche(e):"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["left", "right", "both"],
                [" ", " "],
                [" ", " "],
                ["stânga", "dreapta", "ambele"]
            ],
            [
                '/inform{"given_answer":"Left"}', 
                '/inform{"given_answer":"Right"}',
                '/inform{"given_answer":"Both"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBEarSymptomIb(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomIb"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "When did this start?",
                " ",
                " ",
                "Când a început asta? Detaliati."
            ]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBEarSymptomII(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomII"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Do you wear hearing aids?",
                " ",
                " ",
                "Purtați aparate auditive?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBEarSymptomIIa(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomIIa"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Which ear(s):",
                " ",
                " ",
                "Care ureche(e):"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["left", "right", "both"],
                [" ", " "],
                [" ", " "],
                ["stânga", "dreapta", "ambele"]
            ],
            [
                '/inform{"given_answer":"Left"}', 
                '/inform{"given_answer":"Right"}',
                '/inform{"given_answer":"Both"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBEarSymptomIII(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomIII"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Do you experience noise or ringing in your ears?",
                " ",
                " ",
                "Simțiți zgomot sau zgomot în urechi?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBEarSymptomIIIa(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomIIIa"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Which ear(s):",
                " ",
                " ",
                "Care ureche(e):"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["left", "right", "both"],
                [" ", " "],
                [" ", " "],
                ["stânga", "dreapta", "ambele"]
            ],
            [
                '/inform{"given_answer":"Left"}', 
                '/inform{"given_answer":"Right"}',
                '/inform{"given_answer":"Both"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBEarSymptomIIIa1(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomIIIa1"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Describe the noise:",
                " ",
                " ",
                "Descrieți zgomotul:"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["ringing", "buzzing", "other (please type your answer)"],
                [" ", " "],
                [" ", " "],
                ["sunete", "bâzâit", "altele (vă rugăm să introduceți răspunsul dvs.)"]
            ],
            [
                '/inform{"given_answer":"Ringing"}', 
                '/inform{"given_answer":"Buzzing"}',
                '/inform{"given_answer":"Other"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBEarSymptomIIIa2(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomIIIa2"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Does the noise pulsate or is it steady?",
                " ",
                " ",
                "Pulsează zgomotul sau este constant?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["steady", "pulsate", "variable"],
                [" ", " "],
                [" ", " "],
                ["stabil", "pulsa", "variabil"]
            ],
            [
                '/inform{"given_answer":"Steady"}', 
                '/inform{"given_answer":"Pulsate"}',
                '/inform{"given_answer":"Variable"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBEarSymptomIIIa3(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomIIIa3"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Does anything stop the noise or make it better?",
                " ",
                " ",
                "Opreste ceva zgomotul sau il amelioreaza?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBEarSymptomIIIa3i(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomIIIa3i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Please explain:",
                " ",
                " ",
                "Explicați:"
            ]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBEarSymptomIV(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomIV"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Do you have pain, fullness, or pressure in your ears?",
                " ",
                " ",
                "Aveți durere, plenitudine sau presiune în urechi?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBEarSymptomV(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomV"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Do your ear symptoms occur at the same time as your dizziness/imbalance symptoms?",
                " ",
                " ",
                "Simptomele urechii apar în același timp cu simptomele de amețeală/dezechilibru?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBEarSymptomVI(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomVI"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Lightheadedness or a floating sensation?",
                " ",
                " ",
                "Amețeli sau senzație de plutire?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}'
            ]
        )

        intro_text = get_text_from_lang(
            tracker,
            [
                "When dizzy or imbalanced, do you experience any of the following:",
                " ",
                " ",
                "Când sunteți amețit sau apare tulburarea de echilibru, aveți oricare dintre următoarele:"
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=intro_text)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBEarSymptomVII(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomVII"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Objects or your environment turning around you?",
                " ",
                " ",
                "Obiectele din mediul se rotesc sau se întorc cu susul in jos în jurul tău?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}'
            ]
        )
        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBEarSymptomVIII(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomVIII"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "A sensation that you are turning or spinning while the environment remains stable?",
                " ",
                " ",
                "Aveti o senzație de invartire în timp ce mediul rămâne stabil?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}'
            ]
        )
        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBEarSymptomIX(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomIX"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Nausea or vomiting?",
                " ",
                " ",
                "Aveti greață sau vărsături?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}'
            ]
        )
        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBEarSymptomX(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomX"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Tingling of hands, feet or lips?",
                " ",
                " ",
                "Aveti furnicaturi la maini, picioare sau buze?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}'
            ]
        )
        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBEarSymptomXI(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_EarSymptomXI"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "When you are walking, do you:",
                " ",
                " ",
                "Când mergeti, aveti tendinta de deviere spre:"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["veer left?", "veer right?", "remain in a straight path?"],
                [" ", " "],
                [" ", " "],
                ["virați la stânga?", "vireaza nu?", "rămâne pe drum drept?"]
            ],
            [
                '/inform{"given_answer":"veer left"}', 
                '/inform{"given_answer":"veer right"}',
                '/inform{"given_answer":"remain in a straight path?"}'
            ]
        )
        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBSocial_a(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Social_a"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Please indicate your level of activity currently and prior to developing symptoms:\nCurrent activity level:",
                " ",
                " ",
                "Vă rugăm să indicați nivelul dvs. de activitate în prezent și înainte de apariția simptomelor:\nNivel de activitate curent:"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["inactive", "light", "moderate", "vigorous with/without walker/cane"],
                [" ", " "],
                [" ", " "],
                ["inactiv", "activitate usoara", "moderat", "intensa, cu/fara cadru/baston"]
            ],
            [
                '/inform{"given_answer":"inactive"}', 
                '/inform{"given_answer":"light"}',
                '/inform{"given_answer":"moderate"}',
                '/inform{"given_answer":"vigorous with/without walker/cane"}'
            ]
        )
        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBSocial_ai(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Social_ai"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "List activities/hobbies:",
                " ",
                " ",
                "Lista activități/hobby-uri:"
            ]
        )

        
        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBSocial_b(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Social_b"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Prior activity level:",
                " ",
                " ",
                "Nivel de activitate anterioară:"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["inactive", "light", "moderate", "vigorous with/without walker/cane"],
                [" ", " "],
                [" ", " "],
                ["inactiv", "activitate usoara", "moderat", "intensa, cu/fara cadru/baston"]
            ],
            [
                '/inform{"given_answer":"inactive"}', 
                '/inform{"given_answer":"light"}',
                '/inform{"given_answer":"moderate"}',
                '/inform{"given_answer":"vigorous with/without walker/cane"}'
            ]
        )
        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBSocial_bi(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Social_bi"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "List activities/hobbies:",
                " ",
                " ",
                "Lista activități/hobby-uri:"
            ]
        )

        
        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBSocial_c(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Social_c"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)
        
        text = get_text_from_lang(
            tracker, [
                "If your activity is light or inactive, what are the major barriers? (choose all that apply and press send):",
                " ",
                " ",
                "Dacă activitatea dumneavoastră este ușoară sau inactivă, care sunt barierele majore? (bifează tot ce se aplică și apasă 'Trimite'):"
            ]
        )

        if tracker.get_slot("language") == "Romanian":
            data = {
                "choices": [
                    "Amețeala", "Dezechilibru", "Teamă de cădere", "Lipsă de energie"
                ]
            }
        # this shouldn't happen but just in case
        elif tracker.get_slot("language") == "Italian":
            data = {
                "choices": ["", ""]
            }
        else:
            data = {
                    "choices": [
                        "Dizziness", "Imbalance", "Fear of falling", "Lack of energy"
                    ]
                }


        print("\nBOT:", text + "\n" + str(data))
        dispatcher.utter_message(text=text, json_message=data)
        return []

class ActionAskDnBHabitsCaffeine(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Habits_caffeine"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Please describe your habits in regards to the following substances:\nCaffeine",
                " ",
                " ",
                "Vă rugăm să descrieți obiceiurile dvs. în ceea ce privește următoarele substanțe:\nCofeina"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["I do not consume caffeine", "I consume caffeine"],
                [" ", " "],
                [" ", " "],
                ["nu consum cafeina", "consum cafeina"]
            ],
            [
                '/deny{"given_answer":"don\'t consume caffeine"}', 
                '/affirm{"given_answer":"consume caffeine"}'
            ]
        )
        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBHabitsCaffeineFollow(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Habits_caffeine_follow"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How much do you drink (hint: #cups per day/week/month)?",
                " ",
                " ",
                "Câtă cafea consumi? (răspunde în număr de cești pe zi/săptămâna/lună)?"
            ]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []        

class ActionAskDnBHabitsAlcohol(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Habits_alcohol"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Alcohol",
                " ",
                " ",
                "Alcool"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["I do not consume alcohol", "I consume alcohol"],
                [" ", " "],
                [" ", " "],
                ["nu consum alcool", "consum alcool"]
            ],
            [
                '/deny{"given_answer":"don\'t consume alcohol"}', 
                '/affirm{"given_answer":"consume alcohol"}'
            ]
        )
        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []     

class ActionAskDnBHabitsAlcoholFollow(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Habits_alcohol_follow"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How much do you drink (hint: type of alcohol(e.g. wine) per day/week/month)?",
                " ",
                " ",
                "Cât alcool (ex. vin) consumi (răspunde în număr de pahare pe zi/săptămână/lună)?"
            ]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []           

class ActionAskDnBHabitsTobacco(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Habits_tobacco"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Tobacco:",
                " ",
                " ",
                "Tutun:"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["I do not consume tobacco", "I consume tobacco"],
                [" ", " "],
                [" ", " "],
                ["nu consum tutun", "consum tutun"]
            ],
            [
                '/deny{"given_answer":"don\'t consume tobacco"}', 
                '/affirm{"given_answer":"consume tobacco"}'
            ]
        )
        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return [] 

class ActionAskDnBHabitsTobaccoFollow(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Habits_tobacco_follow"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How much do you smoke/chew (hint: #of product per day/week/month)?",
                " ",
                " ",
                "Cât de mult fumezi (răspunde în număr de țigări consumate pe zi/săptămână/lună)?"
            ]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []            

class ActionAskDnBMedications(Action):
    def name(self) -> Text:
        return "action_ask_dizzNbalance_Medications"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Please provide us with a list of current medications if not submitted before.\nIs there anything else you would like to tell us?",
                " ",
                " ",
                "Vă rugăm să ne furnizați o listă cu medicamentele curente, dacă nu ați trimis-o înainte.\nAți dori să ne spuneți altceva?"
            ]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []                          

class ValidateDnBForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_dizzNbalance_form"

    async def required_slots(
        self, slots_mapped_in_domain, dispatcher, tracker, domain,
    ) -> List[Text]:

        if not tracker.get_slot("dizzNbalance_Q2"):
            slots_mapped_in_domain.remove("dizzNbalance_Q2i")
        
        if tracker.get_slot("dizzNbalance_Q3"):
            slots_mapped_in_domain.remove("dizzNbalance_Q3i")
        
        if not tracker.get_slot("dizzNbalance_Q4"):
            slots_mapped_in_domain.remove("dizzNbalance_Q4a")
            slots_mapped_in_domain.remove("dizzNbalance_Q4b")
            slots_mapped_in_domain.remove("dizzNbalance_Q4c")
            slots_mapped_in_domain.remove("dizzNbalance_Q4ci")
            slots_mapped_in_domain.remove("dizzNbalance_Q4d")
        elif not tracker.get_slot("dizzNbalance_Q4c"):
            slots_mapped_in_domain.remove("dizzNbalance_Q4ci")

        if not tracker.get_slot("dizzNbalance_Q5"):
            slots_mapped_in_domain.remove("dizzNbalance_Q5i")

        if not tracker.get_slot("dizzNbalance_Q6"):
            slots_mapped_in_domain.remove("dizzNbalance_Q6i")

        if not tracker.get_slot("dizzNbalance_Q7"):
            slots_mapped_in_domain.remove("dizzNbalance_Q7i")

        if not tracker.get_slot("dizzNbalance_Q9"):
            slots_mapped_in_domain.remove("dizzNbalance_Q9i")

        if not tracker.get_slot("dizzNbalance_Q11"):
            slots_mapped_in_domain.remove("dizzNbalance_Q11i")

        if not tracker.get_slot("dizzNbalance_Q12"):
            slots_mapped_in_domain.remove("dizzNbalance_Q12i")

        if not tracker.get_slot("dizzNbalance_EarSymptomI"):
            slots_mapped_in_domain.remove("dizzNbalance_EarSymptomIa")
            slots_mapped_in_domain.remove("dizzNbalance_EarSymptomIb")

        if not tracker.get_slot("dizzNbalance_EarSymptomII"):
            slots_mapped_in_domain.remove("dizzNbalance_EarSymptomIIa")

        if not tracker.get_slot("dizzNbalance_EarSymptomIII"):
            slots_mapped_in_domain.remove("dizzNbalance_EarSymptomIIIa")
            slots_mapped_in_domain.remove("dizzNbalance_EarSymptomIIIa1")
            slots_mapped_in_domain.remove("dizzNbalance_EarSymptomIIIa2")
            slots_mapped_in_domain.remove("dizzNbalance_EarSymptomIIIa3")
            slots_mapped_in_domain.remove("dizzNbalance_EarSymptomIIIa3i")
        elif not tracker.get_slot("dizzNbalance_EarSymptomIIIa3"):
            slots_mapped_in_domain.remove("dizzNbalance_EarSymptomIIIa3i")

        if not tracker.get_slot("dizzNbalance_Habits_caffeine"):
            slots_mapped_in_domain.remove("dizzNbalance_Habits_caffeine_follow")

        if not tracker.get_slot("dizzNbalance_Habits_tobacco"):
            slots_mapped_in_domain.remove("dizzNbalance_Habits_tobacco_follow")

        if not tracker.get_slot("dizzNbalance_Habits_alcohol"):
            slots_mapped_in_domain.remove("dizzNbalance_Habits_alcohol_follow")                        

        return slots_mapped_in_domain

    def validate_dizzNbalance_Q1(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validate question 'When did your problem start (date)?' """

        today = datetime.datetime.today()
        # date_format = "%Y-%m-%d"    # This is the correct date format for Duckling to extract correct the date.
        # user_date = next(tracker.get_latest_entity_values("time"), None)

        user_input = datetime.datetime.fromisoformat(slot_value)
        user_input = user_input.strftime("%Y-%m-%d %H:%M:%S")
        user_input = datetime.datetime.strptime(user_input, "%Y-%m-%d %H:%M:%S")

        if isinstance(user_input, datetime.datetime):   # validation succeeded, answer has correct type
            if user_input <= today:
                # validation succeeded, provided answer is correct
                return {"dizzNbalance_Q1": slot_value}
            else:
                # validation failed, user provides a date after today.
                # user will be asked again
                text = get_text_from_lang(
                tracker,
                [
                    "You can't provide a date after today.",
                    " ",
                    " ",
                    "Nu poți furniza o dată care este după ziua de astăzi."
                ]
            )


                dispatcher.utter_message(text=text)
                return {"dizzNbalance_Q1": None}
        else:
            # validation failed, set this slot to None so that the
            # user will be asked for the slot again
            text = get_text_from_lang(
                tracker,
                [
                    "Please provide a valid date in the format YYYY-MM-DD.",
                    " ",
                    " ",
                    "Vă rugăm să furnizați o dată validă în formatul AAAA-LL-ZZ."
                ]
            )

            dispatcher.utter_message(text=text)
            return {"dizzNbalance_Q1": None}

    def validate_dizzNbalance_Q4a(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        """Validates the answer of question 'If variable, the spells occur every (# of hours/days/weeks/months/years)' """

        if len(slot_value) < 2:
            text = get_text_from_lang(
                tracker,
                [
                    "Please provide an answer in the form of '# hours/days/weeks/months'\ne.g. 3 days or 1 month",
                    " ",
                    " ",
                    "Te rog furnizează un răspuns sub forma „număr de ore/zile/săptămâni/luni” (de ex. 3 zile, 1 lună)"
                ]
            )

            dispatcher.utter_message(text="Please provide an answer in the form of '# hours/days/weeks/months'\ne.g. 3 days or 1 month")
            return {"dizzNbalance_Q4a": None}

    def validate_dizzNbalance_Q11i(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:  
        """Validates the answer for question 'If yes, # of falls in the last 6 months...'"""
        
        slot_value = next(tracker.get_latest_entity_values("number"), None)
        return {"dizzNbalance_Q11i": slot_value}

####################################################################################################
# Eating Habits Questionnaire                                                                      #
####################################################################################################

class ActionAskeatinghabitsQ1(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q1"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "When you eat chicken, how often did you prepare it in the oven or boiled?",
                " ",
                " ",
                "Cand mancati carne de pui, cat de des o pregatiti la cuptor sau fiarta?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ2(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q2"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "When you eat chicken, how often did you take off the skin?",
                " ",
                " ",
                "Cand mancati carne de pui, cat de des renuntati la piele?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ3(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q3"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "When you eat red meat, how frequently did you choose to eat only small portions?",
                " ",
                " ",
                "Cand mancati carne rosie, cat de frecvent alegeti sa mancati doar portii mici?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ4(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q4"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "When you eat red meat, how frequently did you trim all visible fat?",
                " ",
                " ",
                "Cand mancati carne rosie, cat de frecvent separati carnea de portiunile vizibile de grasime?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ5(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q5"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How often did you replace red meat with chicken or fish?",
                " ",
                " ",
                "Cat de des inlocuiti carnea rosie cu pui sau peste?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ6(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q6"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How often did you choose to put butter or margarine over cooked vegetables?",
                " ",
                " ",
                "Cat de des alegeti sa puneti unt sau margarina peste legumele gatite?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ7(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q7"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How often did you eat boiled or baked potatoes without adding butter or margarine?",
                " ",
                " ",
                "Cat de des mancati cartofi fierti sau copti fara a adauga unt sau margarina?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ8(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q8"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How often did you put sour cream, cheese or other sauces over cooked vegetables?",
                " ",
                " ",
                "Cat de des puneti smantana, branza sau alte sosuri peste legumele gatite?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ9(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q9"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How often did you eat bread, muffins without associating them with butter / margarine?",
                " ",
                " ",
                "Cat de des mancati paine, briose fara a le asocia cu unt/margarina?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ10(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q10"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How often did you use a tomato sauce without meat on pasta (spaghetti or noodles)?",
                " ",
                " ",
                "Cat de des folositi un sos de rosii fara carne pe paste (spaghetti sau noodles)?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ11(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q11"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How often did you have vegetarian meal?",
                " ",
                " ",
                "Cat de des aveti mese doar pe baza de produse vegetale?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ12(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q12"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How often did you use yogurt instead of sour cream?",
                " ",
                " ",
                "Cat de des folositi iaurt in loc de smantana?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ13(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q13"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How frequently did you use very low-fat milk or 100% skimmed milk?",
                " ",
                " ",
                "Cat de frecvent folositi lapte cu continut foarte scazut de grasimi sau lapte 100% degresat?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ14(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q14"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How frequently did you consume eatinghabitsary products (low-fat foods0 or eatinghabitsary cheese)?",
                " ",
                " ",
                "Cat de frecvent consumati produse eatinghabitsetice (alimente cu continut redus de grasimi sau branza eatinghabitsetica)?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ15(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q15"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How often did you eat ice milk, frozen yogurt or sherbet, instead of ice cream?",
                " ",
                " ",
                "Cat de des preferati in detrimentul inghetatei sherbet, iaurt sau lapte congelat?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ16(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q16"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How often did you use low-calorie instead of regular salad dressing?",
                " ",
                " ",
                "Cat de des folositi dressing pentru salate cu continut redus de calorii in locul celui normal?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ17(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q17"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How often did you use PAM or another non-stick spray when cooking?",
                " ",
                " ",
                "Cat de des folositi produse pe baza de uleiuri/grasimi concentrate (de exemplu sub forma de spray) cand gatiti?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ18(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q18"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How often did you have only fruit for dessert?",
                " ",
                " ",
                "Cat de des optati doar pentru fructe ca desert?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ19(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q19"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How often did you eat at least two vegetables (not green salad) for dinner?",
                " ",
                " ",
                "Cat de des mancati cel putin doua legume (altele decat salata verde) la cina?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskeatinghabitsQ20(Action):
    def name(self) -> Text:
        return "action_ask_eatinghabits_Q20"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How often did you prefer raw vegetables as a snack instead of potato chips or popcorn?",
                " ",
                " ",
                "Cat de des preferati legume crude ca snack in locul chips urilor din cartofi sau popcorn ului?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker, eatingHabits_buttons,
            [
                '/inform{"given_answer":"never"}', 
                '/inform{"given_answer":"rarely"}',
                '/inform{"given_answer":"sometimes"}',
                '/inform{"given_answer":"often"}',
                '/inform{"given_answer":"very often"}',
                '/inform{"given_answer":"always"}'
            ]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

####################################################################################################
# Muscle Tone Questionnaire                                                                        #
####################################################################################################

class ActionAskMuscleToneQ1(Action):
    def name(self) -> Text:
        return "action_ask_muscletone_Q1"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Have you ever had pain or aching in your low back, either at rest or when moving, on most days for at least a month?",
                " ",
                " ",
                "Ați avut vreodată dureri (de exemplu, dureri în zona lombară), în repaus sau in timpul mișcarii, în majoritatea zilelor timp de cel puțin o lună?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            muscletone_buttons,
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}', 
                '/inform{"given_answer":"Don\'t know/ refused"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskMuscleToneQ2(Action):
    def name(self) -> Text:
        return "action_ask_muscletone_Q2"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Have you ever had stiffness in your low back, when first getting out of bed in the morning, on most days for at least a month?",
                " ",
                " ",
                "Ați avut vreodată rigiditate în zona lombară, când vă ridicați din pat dimineața, în majoritatea zilelor, timp de cel puțin o lună?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            muscletone_buttons,
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}', 
                '/inform{"given_answer":"Don\'t know/ refused"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskMuscleToneQ3(Action):
    def name(self) -> Text:
        return "action_ask_muscletone_Q3"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Have you ever had pain or aching in your hips, either at rest or when moving, on most days for at least a month?",
                " ",
                " ",
                "Ați avut vreodată dureri (de exemplu dureri în șolduri), fie în repaus, fie in timpul miscarii în majoritatea zilelor, timp de cel puțin o lună?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            muscletone_buttons,
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}', 
                '/inform{"given_answer":"Don\'t know/ refused"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskMuscleToneQ4(Action):
    def name(self) -> Text:
        return "action_ask_muscletone_Q4"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Have you ever had stiffness in your hip joints or muscles, when first getting out of bed in the morning, on most days for at least a month?",
                " ",
                " ",
                "Ați avut vreodată rigiditate în articulațiile șoldului sau în mușchi, prima dată când vă ridicați din pat dimineața, în majoritatea zilelor, timp de cel puțin o lună?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            muscletone_buttons,
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}', 
                '/inform{"given_answer":"Don\'t know/ refused"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskMuscleToneQ5(Action):
    def name(self) -> Text:
        return "action_ask_muscletone_Q5"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Have you ever had pain, aching or stiffness in your knees, either at rest or when moving, on most days for at least a month?",
                " ",
                " ",
                "Ați avut vreodată dureri sau rigiditate la genunchi, fie în repaus, fie când vă mișcați, în majoritatea zilelor timp de cel puțin o lună?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            muscletone_buttons,
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}', 
                '/inform{"given_answer":"Don\'t know/ refused"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskMuscleToneQ6(Action):
    def name(self) -> Text:
        return "action_ask_muscletone_Q6"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "On most days, do you have pain, aching or stiffness in either of your feet?",
                " ",
                " ",
                "În majoritatea zilelor, aveți dureri sau rigiditate la oricare dintre picioare?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["No", "Yes, left foot", "Yes, right foot", "Yes, both feet", "Yes, not sure what side", "Not applicable (e.g. amputee)", "Don’t know"],
                [" ", " ", " ", " ", " ", " ", " "],                
                [" ", " ", " ", " ", " ", " ", " "],                
                ["Nu", "Da, la nivelul piciorului stang", "Da, la nivelul piciorului drept", "Da, la nivelul ambelor picioare", "Da, dar nu stiu exact pe care parte", "Nu se aplica (ex. membru amputat)", "Nu stiu"]
            ],
            [
                '/inform{"given_answer":"No"}', 
                '/inform{"given_answer":"Yes, left foot"}', 
                '/inform{"given_answer":"Yes, right foot"}',
                '/inform{"given_answer":"Yes, both feet"}', 
                '/inform{"given_answer":"Yes, not sure what side"}', 
                '/inform{"given_answer":"Not applicable (e.g. amputee)"}', 
                '/inform{"given_answer":"Don\'t know"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskMuscleToneQ7(Action):
    def name(self) -> Text:
        return "action_ask_muscletone_Q7"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Have you ever had pain or aching in your shoulder, either at rest or when moving, on most days for at least a month?",
                " ",
                " ",
                "Ați avut vreodată dureri la nivelul umărului, fie în repaus, fie când vă mișcați, în majoritatea zilelor timp de cel puțin o lună?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            muscletone_buttons,
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}', 
                '/inform{"given_answer":"Don\'t know/ refused"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskMuscleToneQ8(Action):
    def name(self) -> Text:
        return "action_ask_muscletone_Q8"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Have you ever had stiffness in your shoulder, when first getting out of bed in the morning, on most days for at least a month?",
                " ",
                " ",
                "Ați avut vreodată rigiditate la umăr, prima dată când vă ridicați din pat dimineața, în majoritatea zilelor, timp de cel puțin o lună?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            muscletone_buttons,
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}', 
                '/inform{"given_answer":"Don\'t know/ refused"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskMuscleToneQ9(Action):
    def name(self) -> Text:
        return "action_ask_muscletone_Q9"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Have you had pain, aching or stiffness in your hands, either at rest or when using them, on most days for at least a month?",
                " ",
                " ",
                "Ați avut dureri sau rigiditate în mâini, fie în repaus, fie in timpul miscarii, în majoritatea zilelor timp de cel puțin o lună?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            muscletone_buttons,
            [
                '/affirm{"given_answer":"Yes"}', 
                '/deny{"given_answer":"No"}', 
                '/inform{"given_answer":"Don\'t know/ refused"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskMuscleToneQ10(Action):
    def name(self) -> Text:
        return "action_ask_muscletone_Q10"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Have you ever been told by a doctor that you have arthritis?",
                " ",
                " ",
                "V-a spus vreodată un medic că ai artrită? Daca da, ce tip ?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Osteoarthritis", "Rheumatoid arthritis", "Yes, other (specify)", "Yes, don’t know type", "No, don’t have arthritis", "Don't know / refused"],
                [" ", " ", " ", " ", " ", " "],
                [" ", " ", " ", " ", " ", " "],
                ["Osteoartrita", "Poliartrita reumatoida", "Da, altele (specificati)", "Da, dar nu stiu exact ce tip", "Nu, nu am artrita", "Nu stiu/ refuz sa raspund"]
            ],
            [
                '/inform{"given_answer":"Osteoarthritis"}', 
                '/inform{"given_answer":"Rheumatoid arthritis"}', 
                '/inform{"given_answer":"Yes, other (specify)"}', 
                '/inform{"given_answer":"Yes, don’t know type"}', 
                '/inform{"given_answer":"No, don’t have arthritis"}', 
                '/inform{"given_answer":"Don\'t know / refused"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskMuscleToneQ10i(Action):
    def name(self) -> Text:
        return "action_ask_muscletone_Q10i"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Please specify...",
                " ",
                " ",
                "Vă rugăm să specificați..."
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []        

class ValidateMuscleToneForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_muscletone_form"

    async def required_slots(
        self, slots_mapped_in_domain, dispatcher, tracker, domain,
    ) -> List[Text]:

        if tracker.get_slot("muscletone_Q10") != "Yes, other (specify)":
            slots_mapped_in_domain.remove("muscletone_Q10i")

        return slots_mapped_in_domain

class ValidateMuscleToneForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_muscletone_form"

    def validate_muscletone_Q1(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        
        muscletone_score = 0

        if "Yes" in slot_value:
            return {"muscletone_score": muscletone_score + 1}
        else:
            return {"muscletone_score": muscletone_score}

    def validate_muscletone_Q2(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        
        muscletone_score = tracker.get_slot("muscletone_score")

        if "Yes" in slot_value:
            return {"muscletone_score": muscletone_score + 1}

    def validate_muscletone_Q3(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        
        muscletone_score = tracker.get_slot("muscletone_score")

        if "Yes" in slot_value:
            return {"muscletone_score": muscletone_score + 1}

    def validate_muscletone_Q4(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        
        muscletone_score = tracker.get_slot("muscletone_score")

        if "Yes" in slot_value:
            return {"muscletone_score": muscletone_score + 1}

    def validate_muscletone_Q5(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        
        muscletone_score = tracker.get_slot("muscletone_score")

        if "Yes" in slot_value:
            return {"muscletone_score": muscletone_score + 1}

    def validate_muscletone_Q6(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        
        muscletone_score = tracker.get_slot("muscletone_score")

        if "Yes" in slot_value:
            return {"muscletone_score": muscletone_score + 1}

    def validate_muscletone_Q7(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        
        muscletone_score = tracker.get_slot("muscletone_score")

        if "Yes" in slot_value:
            return {"muscletone_score": muscletone_score + 1}

    def validate_muscletone_Q8(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        
        muscletone_score = tracker.get_slot("muscletone_score")

        if "Yes" in slot_value:
            return {"muscletone_score": muscletone_score + 1}

    def validate_muscletone_Q9(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        
        muscletone_score = tracker.get_slot("muscletone_score")

        if "Yes" in slot_value:
            return {"muscletone_score": muscletone_score + 1}

    def validate_muscletone_Q10(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:
        
        muscletone_score = tracker.get_slot("muscletone_score")

        if "Yes" in slot_value:
            return {"muscletone_score": muscletone_score + 1}

####################################################################################################
# Coast Questionnaire                                                                              #
####################################################################################################

class ActionAskCoastQ0(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q0"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In the past week or so how well could you use the phone?",
                " ",
                " ",
                "În ultima săptămână sau cam asa ceva, cât de bine ai putut folosi telefonul?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_1,
            [
                '/inform{"given_answer":"Couldn\'t do it at all"}',
                '/inform{"given_answer":"With a lot of difficulty"}',
                '/inform{"given_answer":"With some difficulty"}',
                '/inform{"given_answer":"Quite well"}',
                '/inform{"given_answer":"Very well"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ1(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q1"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In the past week or so how well could you show that you mean YES or NO?",
                " ",
                " ",
                "In ultima saptamana, cat de usor v-a fost sa oferiti raspunsuri precum DA sau NU?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_1,
            [
                '/inform{"given_answer":"Couldn\'t do it at all"}',
                '/inform{"given_answer":"With a lot of difficulty"}',
                '/inform{"given_answer":"With some difficulty"}',
                '/inform{"given_answer":"Quite well"}',
                '/inform{"given_answer":"Very well"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ2(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q2"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Nowadays, how well can you use other ways to help you communicate? (eg pointing, writing etc)",
                " ",
                " ",
                "Cat de usor va este sa folositi alte mijloace care sa va ajute sa comunicati (ex. a scrie sau a indica folosind degetul)?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_2,
            [
                '/inform{"given_answer":"Can\'t do it at all"}',
                '/inform{"given_answer":"With a lot of difficulty"}',
                '/inform{"given_answer":"With some difficulty"}',
                '/inform{"given_answer":"Quite well"}',
                '/inform{"given_answer":"Very well"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ3(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q3"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In the past week or so how well could you have a chat with someone you know well ?",
                " ",
                " ",
                "In ultima saptamana, cat de usor v-a fost sa purtati o discutie cu o persoana cunoscuta?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_1,
            [
                '/inform{"given_answer":"Couldn\'t do it at all"}',
                '/inform{"given_answer":"With a lot of difficulty"}',
                '/inform{"given_answer":"With some difficulty"}',
                '/inform{"given_answer":"Quite well"}',
                '/inform{"given_answer":"Very well"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ4(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q4"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In the past week or so how well could you have a short conversation with an unfamiliar person?",
                " ",
                " ",
                "In ultima saptamana, cat de usor v-a fost sa purtati o scurta discutie cu o persoana necunoscuta?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_1,
            [
                '/inform{"given_answer":"Couldn\'t do it at all"}',
                '/inform{"given_answer":"With a lot of difficulty"}',
                '/inform{"given_answer":"With some difficulty"}',
                '/inform{"given_answer":"Quite well"}',
                '/inform{"given_answer":"Very well"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ5(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q5"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In the past week or so how well could you join in a conversation with a group of people?",
                " ",
                " ",
                "In ultima saptamana, cat de usor v-a fost sa va alaturati unei discutii cu un grup de persoane?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_1,
            [
                '/inform{"given_answer":"Couldn\'t do it at all"}',
                '/inform{"given_answer":"With a lot of difficulty"}',
                '/inform{"given_answer":"With some difficulty"}',
                '/inform{"given_answer":"Quite well"}',
                '/inform{"given_answer":"Very well"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ6(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q6"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Nowadays, how well can you make yourself understood in longer sentences?",
                " ",
                " ",
                "Cat de usor va este sa va faceti inteles folosind propozitii mai complexe ?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_2,
            [
                '/inform{"given_answer":"Can\'t do it at all"}',
                '/inform{"given_answer":"With a lot of difficulty"}',
                '/inform{"given_answer":"With some difficulty"}',
                '/inform{"given_answer":"Quite well"}',
                '/inform{"given_answer":"Very well"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ7(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q7"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In the past week or so how well could you understand simple spoken information ?",
                " ",
                " ",
                "In ultima saptamana cat de usor v-a fost sa intelegeti propozitii simple transmise verbal?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_1,
            [
                '/inform{"given_answer":"Couldn\'t do it at all"}',
                '/inform{"given_answer":"With a lot of difficulty"}',
                '/inform{"given_answer":"With some difficulty"}',
                '/inform{"given_answer":"Quite well"}',
                '/inform{"given_answer":"Very well"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ8(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q8"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Nowadays, how well can you show that you don’t understand ?",
                " ",
                " ",
                "Cat de usor va este sa aratati ca nu intelegeti ce vi se comunica?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_2,
            [
                '/inform{"given_answer":"Can\'t do it at all"}',
                '/inform{"given_answer":"With a lot of difficulty"}',
                '/inform{"given_answer":"With some difficulty"}',
                '/inform{"given_answer":"Quite well"}',
                '/inform{"given_answer":"Very well"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ9(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q9"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In the past week or so how well could you follow a change of subject in conversation?",
                " ",
                " ",
                "In ultima saptamana, cat de usor v-a fost sa urmariti o conversatie daca subiectul acesteia s-a schimbat? "
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_1,
            [
                '/inform{"given_answer":"Couldn\'t do it at all"}',
                '/inform{"given_answer":"With a lot of difficulty"}',
                '/inform{"given_answer":"With some difficulty"}',
                '/inform{"given_answer":"Quite well"}',
                '/inform{"given_answer":"Very well"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ10(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q10"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In the past week or so how well could you read?",
                " ",
                " ",
                "In ultima saptamana cat de usor v-a fost sa cititi?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_3,
            [
                '/inform{"given_answer":"Couldn\'t do it at all"}',
                '/inform{"given_answer":"With a lot of difficulty"}',
                '/inform{"given_answer":"With some difficulty"}',
                '/inform{"given_answer":"Quite well"}',
                '/inform{"given_answer":"As well as before my stroke"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ11(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q11"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In the past week or so how well could you write?",
                " ",
                " ",
                "In ultima saptamana cat de usor v-a fost sa scrieti?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_3,
            [
                '/inform{"given_answer":"Couldn\'t do it at all"}',
                '/inform{"given_answer":"With a lot of difficulty"}',
                '/inform{"given_answer":"With some difficulty"}',
                '/inform{"given_answer":"Quite well"}',
                '/inform{"given_answer":"As well as before my stroke"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ12(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q12"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Nowadays, how well can you deal with money?",
                " ",
                " ",
                "In prezent cat de usor va este sa va gestionati banii?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_1,
            [
                '/inform{"given_answer":"Can\'t do it at all"}',
                '/inform{"given_answer":"With a lot of difficulty"}',
                '/inform{"given_answer":"With some difficulty"}',
                '/inform{"given_answer":"Quite well"}',
                '/inform{"given_answer":"Very well"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ13(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q13"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How much has your communication changed since just after your stroke ?",
                " ",
                " ",
                "Cum s-a modificat modul in care comunicati fata de momentul de dupa ce ati avut accidentul vascular cerebral?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_4,
            [
                '/inform{"given_answer":"Not changed at all"}',
                '/inform{"given_answer":"A little bit better"}',
                '/inform{"given_answer":"Quite a bit better"}',
                '/inform{"given_answer":"A lot better"}',
                '/inform{"given_answer":"Completely better"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ14(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q14"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "What do you think about your communication now?",
                " ",
                " ",
                "Ce parere aveti despre capacitatea dumneavoastra de a comunica in prezent?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_5,
            [
                '/inform{"given_answer":"The worst possible"}',
                '/inform{"given_answer":"Quite poor"}',
                '/inform{"given_answer":"Fair"}',
                '/inform{"given_answer":"Quite good"}',
                '/inform{"given_answer":"As good as before my stroke"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ15(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q15"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How often does confidence about communicating affect what you do?",
                " ",
                " ",
                "Cat de des este afectata activitatea zilnică  in functie de capacitatea de comunicare?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_6,
            [
                '/inform{"given_answer":"All the time"}',
                '/inform{"given_answer":"Very often"}',
                '/inform{"given_answer":"Sometimes"}',
                '/inform{"given_answer":"Hardly ever"}',
                '/inform{"given_answer":"Never"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ16(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q16"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Nowadays, what effect do your speech or language problems have on your family life?",
                " ",
                " ",
                "In prezent, cat de mult va afecteaza viata de familie tulburarea de limbaj/vorbire?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_7,
            [
                '/inform{"given_answer":"The worst possible"}',
                '/inform{"given_answer":"Quite poor"}',
                '/inform{"given_answer":"Fair"}',
                '/inform{"given_answer":"Quite good"}',
                '/inform{"given_answer":"It\'s at least as good as before my stroke"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ17(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q17"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Nowadays, what effect do your speech or language problems have on your social life?",
                " ",
                " ",
                "In prezent, cat de mult va afecteaza viata de sociala tulburarea de limbaj/vorbire?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_7,
            [
                '/inform{"given_answer":"The worst possible"}',
                '/inform{"given_answer":"Quite poor"}',
                '/inform{"given_answer":"Fair"}',
                '/inform{"given_answer":"Quite good"}',
                '/inform{"given_answer":"It\'s at least as good as before my stroke"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ18(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q18"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Nowadays, what effect do your speech and language problems have on your interests or hobbies?",
                " ",
                " ",
                "In prezent, cat de mult va sunt afectate interesele si pasiunile de catre tulburarea de limbaj/vorbire?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_7,
            [
                '/inform{"given_answer":"The worst possible"}',
                '/inform{"given_answer":"Quite poor"}',
                '/inform{"given_answer":"Fair"}',
                '/inform{"given_answer":"Quite good"}',
                '/inform{"given_answer":"It\'s at least as good as before my stroke"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ19(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q19"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How often do difficulties communicating make you worried or unhappy?",
                " ",
                " ",
                "Cat de des dificultatea de a comunica va ingrijoreaza sau va intristeaza?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_6,
            [
                '/inform{"given_answer":"All the time"}',
                '/inform{"given_answer":"Very often"}',
                '/inform{"given_answer":"Sometimes"}',
                '/inform{"given_answer":"Hardly ever"}',
                '/inform{"given_answer":"Never"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskCoastQ20(Action):
    def name(self) -> Text:
        return "action_ask_coast_Q20"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How do you rate your overall quality of life?",
                " ",
                " ",
                "Cum apreciati calitatea vietii dumneavoastra in general?"
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            coast_buttons_5,
            [
                '/inform{"given_answer":"The worst possible"}',
                '/inform{"given_answer":"Quite poor"}',
                '/inform{"given_answer":"Fair"}',
                '/inform{"given_answer":"Quite good"}',
                '/inform{"given_answer":"It\'s at least as good as before my stroke"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

####################################################################################################
# Handle User's Deny                                                                               #
####################################################################################################

class ActionHandleUserDenyInformDoctors(Action):
    def name(self):
        return "action_utter_handle_user_deny_to_inform_doctors"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Are you sure? How you feel is also an important part of your physical progress.",
                "Είσαι σίγουρος? Το πως αισθάνεσαι είναι σημαντικό μέρος της προόδου σου.",
                "Sei sicuro? Anche il modo in cui ti senti è una parte importante del tuo andamento fisico.",
                "Ești sigur(ă)? Modul în care te simți este, de asemenea, o parte importantă a progresului tău fizic."
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []

####################################################################################################
# Set Questionnaire Slot Value                                                                     #
####################################################################################################

# class ActionUtterSetQuestionnaire(Action):
#     def name(self) -> Text:
#         return "action_utter_set_questionnaire"

#     def run(self, dispatcher, tracker, domain):
#         announce(self, tracker)

#         open_questionnaire = tracker.slots["questionnaire"].title()

#         return []

####################################################################################################
# STROKE Case Domain IV RQ1                                                                        #
####################################################################################################

class ActionAskStrokeDomainIVRQ1(Action):
    def name(self) -> Text:
        return "action_ask_STROKEdomainIV_RQ1"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How are you feeling today?",
                " ", 
                " ", 
                "Cum va simtiti astazi?"
            ]
        )

        if tracker.get_slot("language") == "Romanian":
            data = {
                "choices": [
                    "Furie", "Frica", "Tristete", "Bucurie",
                    "Multumire", "Incantare", "Rusine", "Anxietate",
                    "Dezamagire", "Iritare", "Liniste", "Gratitudine",
                    "Nemultumire", "Resemnare", "Speranta", "Nostalgie"
                ]
            }
        # this shouldn't happen but just in case
        elif tracker.get_slot("language") == "Italian":
            data = {
                "choices": ["", ""]
            }
        else:
            data = {
                    "choices": [
                        "Anger", "Fear", "Sadness", "Joy", "Contempt",
                        "Cheer", "Shame", "Anxiety", "Disappointment", "Irritation",
                        "Serenity", "Gratitude", "Grudge", "Resignation", "Hope",
                        "Nostalgia"
                    ]
                }


        print("\nBOT:", text + "\n" + str(data))
        dispatcher.utter_message(text=text, json_message=data)
        return []

####################################################################################################
# MS Case Domain I                                                                                 #
####################################################################################################

class ActionAskMSDomainIRQ1(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainI_RQ1"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In the last few days, have you noticed a sudden lack of strength in one or more limbs?",
                " ", 
                "Negli ultimi giorni hai notato un’improvvisa mancanza di forza a uno o più arti?",                
                " "
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                ["Sì", "No"],                 
                [" ", " "],
            ],
            [
                '/affirm',
                '/deny'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []     

class ActionAskMSDomainIRQ1a(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainI_RQ1a"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In which situation (e.g. carrying shopping, bags, or folders, picking up children or walking)?",
                " ",
                "In che situazione (ad es. portando spesa, borse, faldoni, prendendo in braccio bambini o camminando)?",                 
                " "
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []   

class ActionAskMSDomainIRQ1b(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainI_RQ1b"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Did these disorders occur in limbs that did not previously have deficits?",
                " ", 
                "Questi disturbi si sono verificati in arti che prima non presentavano deficit?",                
                " ", 
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                ["Sì", "No"],                 
                [" ", " "],
            ],
            [
                '/affirm{"given_answer":"yes"}',
                '/deny{"given_answer":"no"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []          

class ActionAskMSDomainIRQ1c(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainI_RQ1c"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How long did they last?",
                " ",
                "Per quanto tempo sono durati?",                 
                " "
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["A few hours or less", "About a day", "Two to four days", "Most of the week"],
                [" ", " "],
                ["Qualche ora o meno", "Circa un giorno", "Da due a quattro giorni", "Quasi tutti la settimana"],                
                [" ", " "] 
            ],
            [
                '/inform{"given_answer":"A few hours or less"}',
                '/inform{"given_answer":"About a day"}',
                '/inform{"given_answer":"Two to four days"}',
                '/inform{"given_answer":"Most of the week"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskMSDomainIRQ2(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainI_RQ2"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Have you felt more rigid or less fluid in your movements in the last few days?",
                " ", 
                "Negli ultimi giorni hai avvertito più rigidità (o meno fluidità) nei movimenti?",
                " "                
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                ["Sì", "No"],                
                [" ", " "], 
            ],
            [
                '/affirm',
                '/deny'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []   

class ActionAskMSDomainIRQ2a(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainI_RQ2a"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In which situation (e.g. carrying shopping, bags, or folders, picking up children or walking)?",
                " ",
                "In che situazione (ad es. portando spesa, borse, faldoni, prendendo in braccio bambini o camminando)?",                 
                " "
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []   

class ActionAskMSDomainIRQ2b(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainI_RQ2b"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Did these disorders occur in limbs that did not previously have deficits?",
                " ",
                "Questi disturbi si sono verificati in arti che prima non presentavano deficit?",                 
                " "
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                ["Sì", "No"],                
                [" ", " "], 
            ],
            [
                '/affirm{"given_answer":"yes"}',
                '/deny{"given_answer":"no"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []          

class ActionAskMSDomainIRQ2c(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainI_RQ2c"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How long did they last?",
                " ",
                "Per quanto tempo sono durati?",                 
                " "
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["A few hours or less", "About a day", "Two to four days", "Most of the week"],
                [" ", " "],
                ["Qualche ora o meno", "Circa un giorno", "Da due a quattro giorni", "Quasi tutti la settimana"],                
                [" ", " "] 
            ],
            [
                '/inform{"given_answer":"A few hours or less"}',
                '/inform{"given_answer":"About a day"}',
                '/inform{"given_answer":"Two to four days"}',
                '/inform{"given_answer":"Most of the week"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []    

class ActionAskMSDomainIRQ3(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainI_RQ3"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In the last few days, how have you felt when you move?",
                " ",
                "Negli ultimi giorni come ti sei sentito/a quando ti muovi?",                 
                " "
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Sure step", "I have to pay more attention or stop to do other things", "Unstable", "Real risk of falling"],
                [" ", " "],
                ["Passo sicuro", "Devo prestare più - attenzione o fermarmi per fare altre cose", "Instabile", "Rischio concreto di cadere"],                
                [" ", " "] 
            ],
            [
                '/inform{"given_answer":"Sure step"}',
                '/inform{"given_answer":"I have to pay more attention or stop to do other things"}',
                '/inform{"given_answer":"Unstable"}',
                '/inform{"given_answer":"Real risk of falling"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []    

class ActionAskMSDomainIRQ4(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainI_RQ4"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How many times have you stumbled over the last few days?\n(hint: Your answer must be 0 or a positive number)",
                " ",
                "Quante volte ti è capitato di inciampare negli ultimi giorni?\n(La tua risposta deve essere 0 o un numero positivo)",                 
                " ",
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []  

class ActionAskMSDomainIRQ5(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainI_RQ5"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How many times have you fallen in the last few days?\n(hint: Your answer must be 0 or a positive number)",
                " ",
                "Quante volte sei caduto/a negli ultimi giorni?\n(La tua risposta deve essere 0 o un numero positivo)",                 
                " "
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []  

class ActionAskMSDomainIRQ6(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainI_RQ6"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In the last few days, have you noticed an alteration in sensitivity (for example, arms or legs asleep, tingling, burning, unusual sensation to the touch, loss of sensitivity)?",
                " ",
                "Negli ultimi giorni hai notato un’alterazione della sensibilità (ad esempio braccia o gambe addormentate, formicolio, bruciore, sensazione insolita al tatto, perdita di sensibilità)?",                 
                " "
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                ["Sì", "No"],                
                [" ", " "], 
            ],
            [
                '/affirm{"given_answer":"yes"}',
                '/deny{"given_answer":"no"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []                                                             

class ValidateMSDomainIForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_MSdomainI_form"

    async def required_slots(
        self, slots_mapped_in_domain, dispatcher, tracker, domain,
    ) -> List[Text]:

        if not tracker.get_slot("MSdomainI_RQ1"):
            slots_mapped_in_domain.remove("MSdomainI_RQ1a")
            slots_mapped_in_domain.remove("MSdomainI_RQ1b")
            slots_mapped_in_domain.remove("MSdomainI_RQ1c")

        if not tracker.get_slot("MSdomainI_RQ2"):
            slots_mapped_in_domain.remove("MSdomainI_RQ2a")
            slots_mapped_in_domain.remove("MSdomainI_RQ2b")
            slots_mapped_in_domain.remove("MSdomainI_RQ2c")            

        return slots_mapped_in_domain

    def validate_MSdomainI_RQ4(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:

        # slot_value = next(tracker.get_latest_entity_values("number"), None)
        if isinstance(slot_value, str):
            slot_value = int(slot_value)
        
        if (slot_value is not None) & (slot_value >= 0):
            return {"MSdomainI_RQ4": slot_value}
        else:
            text = get_text_from_lang(
                tracker,
                ["Please type your answer as a positive number.",
                " ",
                "Si prega di digitare la risposta come numero.",
                " "]
            )

            dispatcher.utter_message(text=text)
            return {"MSdomainI_RQ4": None}

    def validate_MSdomainI_RQ5(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:

        # slot_value = next(tracker.get_latest_entity_values("number"), None)
        if isinstance(slot_value, str):
            slot_value = int(slot_value)
        
        if (slot_value is not None) & (slot_value >= 0):
            return {"MSdomainI_RQ5": slot_value}
        else:
            text = get_text_from_lang(
                tracker,
                ["Please give a valid answer",
                " ",
                "Si prega di dare una risposta valida",
                " "]
            )

            dispatcher.utter_message(text=text)
            return {"MSdomainI_RQ5": None}      

####################################################################################################
# MS Case Domain II                                                                                #
####################################################################################################                  
class ActionAskMSDomainII3MRQ3(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainII_3M_RQ3"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Have you ever been told, or suspected yourself, that you seem to act out your dreams while asleep (for example, punching, flailing your arms in the air, making running movements, etc.)?",
                " ",
                "Ti hanno detto che agisci i tuoi sogni mentre dormi o pensi di farlo (per esempio, dare dei pugni, muovere le braccia in aria, fare dei movimenti come se corressi ecc.)?",                 
                " "
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                ["Sì", "No"],                
                [" ", " "], 
            ],
            [
                '/affirm',
                '/deny'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return [] 

####################################################################################################
# MS Case Domain III                                                                               #
####################################################################################################        

class ActionAskMSDomainIII1WRQ2(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainIII_1W_RQ2"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "From 1 to 10 how hard are you struggling to stay focused on what you are doing (e.g. losing your train of thought, listening to what others are saying, reading a book or watching a movie)?\nPlease type an integer...",
                " ",
                "Da 1 a 10 quanto fai fatica a mantenere la concentrazione su quello che stai facendo (ad es. perdere il filo del discorso, ascoltare quello che dicono gli altri, leggendo un libro o guardando un film)?\nPer favore digita un numero intero...",                 
                " "
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return [] 

class ActionAskMSDomainIII1WRQ2a(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainIII_1W_RQ2a"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In which situation does it happen most frequently?",
                " ",
                "In quale situazione succede più frequentemente?",                 
                " "
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []    

class ActionAskMSDomainIII1WRQ5(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainIII_1W_RQ5"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "From 1 to 10 how difficult is to find the word in your head? How often do you get the terms wrong?\nPlease type an integer...",
                " ",
                "Da 1 a 10 quanto hai difficoltà a trovare la parola che hai in testa? Quanto ti capita di sbagliare i termini?\nPer favore digita un numero intero...",                 
                " "
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return [] 

class ActionAskMSDomainIII1WRQ5a(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainIII_1W_RQ5a"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In which situation does it happen most frequently?",
                " ",
                "In quale situazione succede più frequentemente?",                 
                " "
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []   

class ActionAskMSDomainIII2WRQ6(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainIII_2W_RQ6"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How many appointments or commitments have you forgotten in the last two weeks?",
                " ",
                "Quanti appuntamenti o impegni hai dimenticato nelle ultime due settimane?",                 
                " "
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []  

class ActionAskMSDomainIII2WRQ7(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainIII_2W_RQ7"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In the last two weeks, did you need to write down commitments more than usual to remember them (for example via extra notes or alarms in addition to the usual agenda)?",
                " ",
                "Nelle ultime due settimane, hai avuto particolarmente bisogno di annotare più del solito gli impegni per ricordarli (ad esempio tramite note, allarmi o sveglie in aggiunta alle abituale agenda)?",                 
                " "
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                ["Sì", "No"],                
                [" ", " "], 
            ],
            [
                '/affirm{"given_answer":"yes"}',
                '/deny{"given_answer":"no"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []                     

class ValidateMSDomainIII1WForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_MSdomainIII_1W_form"

    async def required_slots(
        self, slots_mapped_in_domain, dispatcher, tracker, domain,
    ) -> List[Text]:

        if (tracker.get_slot("MSdomainIII_1W_RQ2") is not None):
            if (tracker.get_slot("MSdomainIII_1W_RQ2") < 6):
                slots_mapped_in_domain.remove("MSdomainIII_1W_RQ2a")

        if tracker.get_slot("MSdomainIII_1W_RQ5") is not None:
            if tracker.get_slot("MSdomainIII_1W_RQ5") < 6:
                slots_mapped_in_domain.remove("MSdomainIII_1W_RQ5a")  

        # if not tracker.get_slot("MSdomainIII_both"):
        #     slots_mapped_in_domain.remove("MSdomainIII_2W_RQ6") 
        #     slots_mapped_in_domain.remove("MSdomainIII_2W_RQ7")                        

        return slots_mapped_in_domain

    def validate_MSdomainIII_1W_RQ2(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:

        # slot_value = next(tracker.get_latest_entity_values("number"), None)
        if isinstance(slot_value, str):
            slot_value = int(slot_value)
        
        if (slot_value is not None) and (slot_value in list(range(1, 11))):
            return {"MSdomainIII_1W_RQ2": slot_value}
        elif (slot_value is not None) and (slot_value not in list(range(1, 11))):
            text = get_text_from_lang(
                tracker,
                ["Your answer must be between 1 and 10.",
                " ",
                "La tua risposta deve essere compresa tra 1 e 10.",
                " "]
            )

            dispatcher.utter_message(text=text)
            return {"MSdomainIII_1W_RQ2": None}  
        else:
            text = get_text_from_lang(
                tracker,
                ["Please give a valid answer",
                " ",
                "Si prega di dare una risposta valida",
                " "]
            )

            dispatcher.utter_message(text=text)
            return {"MSdomainIII_1W_RQ2": None}     

    def validate_MSdomainIII_1W_RQ5(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:

        # slot_value = next(tracker.get_latest_entity_values("number"), None)
        if isinstance(slot_value, str):
            slot_value = int(slot_value)
        
        if (slot_value is not None) and (slot_value in list(range(1, 11))):
            return {"MSdomainIII_1W_RQ5": slot_value}
        elif (slot_value is not None) and (slot_value not in list(range(1, 11))):
            text = get_text_from_lang(
                tracker,
                ["Your answer must be between 1 and 10.",
                " ",
                "La tua risposta deve essere compresa tra 1 e 10.",
                " "]
            )

            dispatcher.utter_message(text=text)
            return {"MSdomainIII_1W_RQ5": None}  
        else:
            text = get_text_from_lang(
                tracker,
                ["Please give a valid answer",
                " ",
                "Si prega di dare una risposta valida",
                " "]
            )

            dispatcher.utter_message(text=text)
            return {"MSdomainIII_1W_RQ5": None}   

class ValidateMSDomainIII2WForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_MSdomainIII_2W_form"

    def validate_MSdomainIII_2W_RQ6(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain
    ) -> Dict[Text, Any]:

        # slot_value = next(tracker.get_latest_entity_values("number"), None)
        if isinstance(slot_value, str):
            slot_value = int(slot_value)
        
        if slot_value is not None:
            return {"MSdomainIII_2W_RQ6": slot_value}
        else:
            text = get_text_from_lang(
                tracker,
                ["Please give a valid answer",
                " ",
                "Si prega di dare una risposta valida",
                " "]
            )

            dispatcher.utter_message(text=text)
            return {"MSdomainIII_2W_RQ6": None}                               

####################################################################################################
# MS Case Domain IV                                                                                #
####################################################################################################   

class ActionAskMSDomainIVDailyRQ1(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainIV_Daily_RQ1"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How are you feeling today?",
                " ",
                "Cosa provi oggi? È possibile selezionare più di una parola",                 
                " "
            ]
        )

        if tracker.get_slot("language") == "Italian":
            data = {
                "choices": [
                    "Rabbia", "Paura", "Tristezza", "Gioia",
                    "Disprezzo", "Allegria", "Vergogna", "Ansia",
                    "Delusione", "Irritazione", "Serenità", "Gratitudine",
                    "Rancore", "Rassegnazione", "Speranza", "Nostalgia"
                ]
            }
        # this shouldn't happen but just in case
        elif tracker.get_slot("language") == "Romanian":
            data = {
                "choices": ["", ""]
            }
        else:
            data = {
                    "choices": [
                        "Anger", "Fear", "Sadness", "Joy", "Contempt",
                        "Cheer", "Shame", "Anxiety", "Disappointment", "Irritation",
                        "Serenity", "Gratitude", "Grudge", "Resignation", "Hope",
                        "Nostalgia"
                    ]
                }

        print("\nBOT:", text + "\n" + str(data))
        dispatcher.utter_message(text=text, json_message=data)
        return []  

# class ActionAskMSDomainIV1WRQ1(Action):
#     def name(self) -> Text:
#         return "action_ask_MSdomainIV_1W_RQ1"

#     def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
#         announce(self, tracker)

#         text = get_text_from_lang(
#             tracker,
#             [
#                 "How are you feeling today?",
#                 " ",
#                 "Cosa provi oggi? È possibile selezionare più di una parola",                 
#                 " "
#             ]
#         )

#         if tracker.get_slot("language") == "Italian":
#             data = {
#                 "choices": [
#                     "Rabbia", "Paura", "Tristezza", "Gioia",
#                     "Disprezzo", "Allegria", "Vergogna", "Ansia",
#                     "Delusione", "Irritazione", "Serenità", "Gratitudine",
#                     "Rancore", "Rassegnazione", "Speranza", "Nostalgia"
#                 ]
#             }
#         # this shouldn't happen but just in case
#         elif tracker.get_slot("language") == "Romanian":
#             data = {
#                 "choices": ["", ""]
#             }
#         else:
#             data = {
#                     "choices": [
#                         "Anger", "Fear", "Sadness", "Joy", "Contempt",
#                         "Cheer", "Shame", "Anxiety", "Disappointment", "Irritation",
#                         "Serenity", "Gratitude", "Grudge", "Resignation", "Hope",
#                         "Nostalgia"
#                     ]
#                 }

#         print("\nBOT:", text + "\n" + str(data))
#         dispatcher.utter_message(text=text, json_message=data)
#         return []   

class ActionAskMSDomainIV1WRQ2(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainIV_1W_RQ2"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Are you feeling stressed this week?",
                " ",
                "In questa settimana, ti senti stressato/a?",                 
                " "
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                ["Sì", "No"],                
                [" ", " "], 
            ],
            [
                '/affirm',
                '/deny'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []          

class ActionAskMSDomainIV1WRQ2a(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainIV_1W_RQ2a"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In which statement do you recognize yourself most?",
                " ",
                "In quale affermazione ti riconosci maggiormente?",                 
                " "
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Level 1: \"daily life\" stress (work, home, family management)", 
                 "Level 2: stress from overlapping commitments and difficulties in managing things to do with respect to my mental energies",
                 "Level 3: stress from the onset of worries or aggravation of existing ones (e.g. economic difficulties, conflicts at work or in the family, etc ...)",
                 "Level 4: stress from strong destabilizing events (e.g. a radical change of life, bereavement, etc ...)"],
                [" ", " "],
                ["Livello 1: stress da «vita quotidiana» (gestione lavoro, casa, famiglia)",
                 "Livello 2: stress da sovrapposizione di impegni e difficoltà di gestione delle cose da fare rispetto alle mie energie mentali",
                 "Livello 3: stress da insorgenza di preoccupazioni o aggravamento di quelle esistenti (es difficoltà economiche, conflitti sul lavoro o in famiglia, ecc…)",
                 "Livello 4: stress da forti eventi destabilizzanti (es. un cambiamento radicale di vita, un lutto, ecc …)"],                
                [" ", " "] 
            ],
            [
                '/inform{"given_answer":"Level 1: \"daily life\" stress (work, home, family management)"}',
                '/inform{"given_answer":"Level 2: stress from overlapping commitments and difficulties in managing things to do with respect to my mental energies"}',
                '/inform{"given_answer":"Level 3: stress from the onset of worries or aggravation of existing ones (e.g. economic difficulties, conflicts at work or in the family, etc ...)"}',
                '/inform{"given_answer":"Level 4: stress from strong destabilizing events (e.g. a radical change of life, bereavement, etc ...)"}',
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []      

class ActionAskMSDomainIV_1WRQ3(Action):
    def name(self) -> Text:
        return "action_ask_MSdomainIV_1W_RQ3"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "In the last week, have you experienced symptoms of previous relapses again?",
                " ",
                "Nell'ultima settimana ti è capitato di avvertire nuovamente sintomi di precedenti ricadute?",                 
                " "
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                ["Sì", "No"],                
                [" ", " "], 
            ],
            [
                '/affirm{"given_answer":"yes"}',
                '/deny{"given_answer":"no"}'
            ]
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []                    

class ValidateMSDomainIV_1WForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_MSdomainIV_1W_form"

    async def required_slots(
        self, slots_mapped_in_domain, dispatcher, tracker, domain,
    ) -> List[Text]:

        if not tracker.get_slot("MSdomainIV_1W_RQ2"):
            slots_mapped_in_domain.remove("MSdomainIV_1W_RQ2a")           

        return slots_mapped_in_domain