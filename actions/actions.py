import random

from typing import Any, Dict, List, Text
from urllib import response
from matplotlib.pyplot import text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet, FollowupAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormValidationAction

# Define this list as the values for the `language` slot. Arguments of the `get_..._lang` functions should respect this order.
lang_list = ["English", "Greek", "Italian", "Romanian"]  # Same as slot values

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

muscletone_buttons = [
    ["Yes", "No", "Don't know/ refused"],
    [" ", " "],
    [" ", " "],
    ["Da", "Nu", "Nu stiu/ refuz sa raspund"]
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
            if "value" in msg["entities"][0].keys():
                output += (
                    "\n- Entities:   "
                    + str(msg["entities"][0]["entity"])
                    + ", Value: "
                    + str(msg["entities"][0]["value"])
                )
            else:
                output += "\n- Entities:   " + str(msg["entities"][0]["entity"])
            output += "\n- Slots:      "

            for slot_key, slot_value in slots.items():
                if slot_value is not None:
                    filled_slots[slot_key] = slot_value
            if len(filled_slots) > 0:
                for slot_key, slot_value in filled_slots.items():
                    output += str(slot_key) + ": " + str(slot_value) + ", "
                output = output[:-2]
        except Exception as e:
            print(f"\n> announce: [ERROR] {e}")
    print(output)

####################################################################################################
# SLOTS                                                                                            #
####################################################################################################

def reset_slots(tracker, slots, exceptions=[]):
    events = []
    none_slots = []

    for exception in exceptions:
        if exception in slots:
            slots.remove(exception)

    for slot in slots:
        if tracker.get_slot(slot) is not None:
            none_slots.append(slot)

    for slot in none_slots:
        events.append(SlotSet(slot, None))

    print("\n> reset_slots:", ", ".join(none_slots))
    return events

def list_slots(tracker, slots, exceptions=[]):
    filled_slots = ""

    for exception in exceptions:
        if exception in slots:
            slots.remove(exception)

    for slot in slots:
        value = tracker.get_slot(slot)

        if value is not None:
            filled_slots += f"\t- {slot}: {value}\n"

    # print(filled_slots[:-1])
    return filled_slots[:-1]

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
        text = "I only understand English, Greek, Italian and Romanian. The language is now English."

        if current_language == "English":
            text = "The language is now English."
        elif current_language == "Greek":
            text = "Η γλώσσα έχει τεθεί στα Ελληνικά"
        elif current_language == "Romanian":
            text = "Limba este acum Română."

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []

####################################################################################################
# SAVE CONVERSATION HISTORY                                                                        #
####################################################################################################

class ActionSaveConversation(Action):
    def name(self) -> Text:
        return "action_save_conversation"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        conversation = tracker.events
        print(conversation)
        import os

        if not os.path.isfile("chats.csv"):
            with open("chats.csv", "w") as file:
                file.write(
                    "intent,user_input,entity_name,entity_value,action,bot_reply\n"
                )
        chat_data = ""
        for i in conversation:
            if i["event"] == "user":
                chat_data += i["parse_data"]["intent"]["name"] + "," + i["text"] + ","
                print("user: {}".format(i["text"]))
                if len(i["parse_data"]["entities"]) > 0:
                    chat_data += (
                        i["parse_data"]["entities"][0]["entity"]
                        + ","
                        + i["parse_data"]["entities"][0]["value"]
                        + ","
                    )
                    print(
                        "extra data:",
                        i["parse_data"]["entities"][0]["entity"],
                        "=",
                        i["parse_data"]["entities"][0]["value"],
                    )
                else:
                    chat_data += ",,"
            elif i["event"] == "bot":
                print("Bot: {}".format(i["text"]))
                try:
                    chat_data += i["metadata"]["utter_action"] + "," + i["text"] + "\n"
                except KeyError:
                    chat_data += ",," + "\n"
        else:
            with open("chats.csv", "a") as file:
                file.write(chat_data)

        dispatcher.utter_message(text="All Chats saved.")

        return []

####################################################################################################
# Chit-Chat                                                                                        #
####################################################################################################

class ActionUtterGreet(Action):
    def name(self):
        return "action_utter_greet"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        if tracker.get_slot("questionnaire") == "ACTIVLIM":  # ACTIVLIM is only for Romanian use-case
            text = get_text_from_lang(
                tracker,
                [
                    "Hey there. Just to note that the ACTIVLim questionnaire is available to answer it.",
                    " ",
                    " ",
                    "Hei acolo. Doar să rețineți că chestionarul ACTIVLim este disponibil pentru a-i răspunde.",
                ],
            )
            print("\nBOT:", text)
            dispatcher.utter_message(text=text)
            return [FollowupAction("action_utter_ask_activlim_start")]

        elif tracker.get_slot("questionnaire") == "PSQI":
            text = get_text_from_lang(
                tracker,
                [
                    "Hey, just to note that the PSQI questionnaire is available to answer it.",
                    " ",
                    " ",
                    "Hei, doar să rețineți că chestionarul PSQI este disponibil pentru a-i răspunde.",
                ],
            )
            print("\nBOT:", text)
            dispatcher.utter_message(text=text)
            return [FollowupAction("action_utter_ask_psqi_start")]

        elif tracker.get_slot("questionnaire") == "DizzinessAndBalance":
            text = get_text_from_lang(
                tracker,
                [
                    "Hey, just to note that the Dizziness - Balance questionnaire is available to answer it.",
                    " ",
                    " ",
                    "Hei, doar să rețineți că chestionarul al evaluarii ametelii si echilibrului este disponibil pentru a-i răspunde.",
                ],
            )
            print("\nBOT:", text)
            dispatcher.utter_message(text=text)
            return [FollowupAction("action_utter_ask_dNb_start")]

        elif tracker.get_slot("questionnaire") == "EatingHabits":
            text = get_text_from_lang(
                tracker,
                [
                    "Hey, just to note that the Eating Habits questionnaire is available to answer it.",
                    " ",
                    " ",
                    "Hei, doar să rețineți că chestionarul obiceiuri alimentare este disponibil pentru a-i răspunde.",
                ],
            )
            print("\nBOT:", text)
            dispatcher.utter_message(text=text)
            return [FollowupAction("action_utter_ask_diet_start")]

        elif tracker.get_slot("questionnaire") == "MuscleTone":
            text = get_text_from_lang(
                tracker,
                [
                    "Hey, just to note that the Muscle Tone questionnaire is available to answer it.",
                    " ",
                    " ",
                    "Hei, doar să rețineți că chestionarul pentru tonusul muscular este disponibil pentru a răspunde.",
                ],
            )
            print("\nBOT:", text)
            dispatcher.utter_message(text=text)
            return [FollowupAction("action_utter_ask_muscle_start")]

        else:
            text = get_text_from_lang(
                tracker,
                [
                    "Hey there. How can I help you?",
                    "Χαίρεται. Πως μπορώ να σε βοηθήσω;",
                    "Ehilà. Come posso aiutarla?",
                    "Hei acolo. Cu ce ​​vă pot ajuta?",
                ],
            )
            print("\nBOT:", text)
            dispatcher.utter_message(text=text)
            return [FollowupAction("action_listen")]

####################################################################################################
# ACTIVLIM Questionnaire                                                                           #
####################################################################################################

class ActionUtterActivlimStart(Action):
    def name(self):
        return "action_utter_ask_activlim_start"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Would you like to fill it? It shouldn't take more than 7 minutes.",
                " ",
                " ",
                "Doriți să-l umpleți? Nu ar trebui să dureze mai mult de 7 minute.",
            ],
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Start ACTIVLim Questionnaire", "No"],
                [" ", " "],
                [" ", " "],
                ["Porniți chestionarul ACTIVLim", "Nu"],
            ],
            ['/activLim_start', '/deny']
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

####################################################################################################
# PSQI Questionnaire                                                                               #
####################################################################################################

class ActionUtterPSQIStart(Action):
    def name(self):
        return "action_utter_ask_psqi_start"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Would you like to fill it? It shouldn't take more than 7 minutes.",
                " ",
                " ",
                "Doriți să-l umpleți? Nu ar trebui să dureze mai mult de 7 minute.",
            ],
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Start PSQI Questionnaire", "No"],
                [" ", " "],
                [" ", " "],
                ["Porniți chestionarul PSQI", "Nu"],
            ],
            ['/psqi_start', '/deny']
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskPSQIQ1(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ1"

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

class ActionAskPSQIQ2(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ2"

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

class ActionAskPSQIQ3(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ3"

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

class ActionAskPSQIQ4(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ4"

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

class ActionAskPSQIQ5a(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ5a"

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

class ActionAskPSQIQ5b(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ5b"

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

class ActionAskPSQIQ5c(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ5c"

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

class ActionAskPSQIQ5d(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ5d"

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

class ActionAskPSQIQ5e(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ5e"

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

class ActionAskPSQIQ5f(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ5f"

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

class ActionAskPSQIQ5g(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ5g"

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

class ActionAskPSQIQ5h(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ5h"

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

class ActionAskPSQIQ5i(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ5i"

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

class ActionAskPSQIQ5j(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ5j"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        entry_text = get_text_from_lang(
            tracker, psqi_q5
        )

        text = get_text_from_lang(
            tracker,
            [
                " Other reason? (please describe)",
                " ",
                " ",
                " Alte motive?"
            ]
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskPSQIQ5k(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ5k"

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

class ActionAskPSQIQ6(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ6"

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
        
class ActionAskPSQIQ7(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ7"

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

class ActionAskPSQIQ8(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ8"

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

class ActionAskPSQIQ9(Action):  # PSQI Questionnaire
    def name(self) -> Text:
        return "action_ask_psqiQ9"

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

####################################################################################################
# Dizziness and Balance Questionnaire                                                              #
####################################################################################################

class ActionUtterDnBStart(Action):  # DnB Questionnaire
    def name(self):
        return "action_utter_ask_dNb_start"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Would you like to fill it? It shouldn't take more than 7 minutes.",
                " ",
                " ",
                "Doriți să-l umpleți? Nu ar trebui să dureze mai mult de 7 minute."
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Start Dizzines - Balance Questionnaire", "No"],
                [" ", " "],
                [" ", " "],
                ["Porniți chestionarul Dizzines - Balance", "Nu"],
            ],
            ['/dizzNbalance_start', '/deny']
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDnBQ1(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ1"

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

class ActionAskDnBQ2(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ2"

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

class ActionAskDnBQ2i(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ2i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            ["If yes, please explain:", " ", " ", "DA/NU ; Daca da, explicati...",],
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBQ3(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ3"

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

class ActionAskDnBQ3i(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ3i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            ["describe", " ", " ", "detaliati"]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBQ4(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ4"

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

class ActionAskDnBQ4a(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ4a"

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

class ActionAskDnBQ4b(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ4b"

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

class ActionAskDnBQ4c(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ4c"

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

class ActionAskDnBQ4ci(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ4ci"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "If yes, please describe:",
                " ",
                " ",
                "Daca da, descrieti."
            ]
        )
        
        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBQ4d(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ4d"

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
        return "action_ask_dNbSymptoms"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)
        
        text = get_text_from_lang(
            tracker, [
                "SYMPTOMS: Check all that apply:",
                " ",
                " ",
                "Simptome (bifati simptomele care se regasesc in cazul dumneavoastra) :"
            ]
        )

        if tracker.get_slot("language") == "English":
            data = {
                    "choices": [
                        "Dizziness", "Spinning/Vertigo", "Lightheadedness", "Rocking/tilting",
                        "Visual changes", "Headache", "Fatigue", "Unsteadiness", "Falling",
                        "Ringing/noise in ears", "Fullness in ears", "Motion sensitive",
                        "Hearing loss", "Double vision", "Brain fog", "Imbalance/Disequilibrium"
                    ]
                }

        elif tracker.get_slot("language") == "Romanian":
            data = {
                "choices": [
                    "Ameteala", "Senzatie de urechi infundate", "Tulburare de vedere", "Senzatie de ‘cap tulbure’",
                    "Caderi ", "Senzatia de rotire a lucrurilor din jur", "Pierdere a auzului", "Rau de miscare", "Durere de cap",
                    "Nesiguranta la mers", "Zgomote in urechi", "Oboseala", "Vedere dubla", "Tulburare de echilibru", "Brain fog",
                    "Imbalance/Disequilibrium"
                ]
            }

        print("\nBOT:", text + "\n" + str(data))
        dispatcher.utter_message(text=text, json_message=data)
        return []

class ActionAskDnBQ5(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ5"

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
        return "action_ask_dNbQ5i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)
        
        text = get_text_from_lang(
            tracker, [
                "If yes, check all that apply:",
                " ",
                " ",
                "Daca da, bifati ceea ce va caracterizeaza :"
            ]
        )

        if tracker.get_slot("language") == "English":
            data = {
                    "choices": [
                        "Rolling your body to the left", "Rolling your body to the right", 
                        "Moving from a lying to a sitting position", "Looking up with your head back",
                        "Turning head side to side while sitting/standing", "Bending over with your head down"
                    ]
                }

        elif tracker.get_slot("language") == "Romanian":
            data = {
                "choices": [
                    "Senzatia de rotire a corpului catre stanga", "Senzatia de rotire a corpului catre dreapta", 
                    "La trecerea din pozitia culcat in sezut", "La privirea in sus, cu capul pe spate",
                    "La intoarcerea capului", "La privirea in jos, cu capul in fata"
                ]
            }

        print("\nBOT:", text + "\n" + str(data))
        dispatcher.utter_message(text=text, json_message=data)
        return []

class ActionAskDnBQ6(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ6"

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
        return "action_ask_dNbQ6i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)
        
        text = get_text_from_lang(
            tracker, [
                "If yes, check all that apply:",
                " ",
                " ",
                "Daca da, bifati ce va caracterizeaza :"
            ]
        )

        if tracker.get_slot("language") == "English":
            data = {
                    "choices": [
                        "Moving my head", "Physical activity or exercise", "Riding or driving in the car", "Large crowds or a busy environment",
                        "Loud sounds", "Coughing, blowing the nose, or straining", "Standing up", "Eating certain foods", 
                        "Time of day", "Menstrual periods (if applicable)", "Other (please type your answer)"
                    ]
                }

        elif tracker.get_slot("language") == "Romanian":
            data = {
                "choices": [
                    "Miscarea capului", "Activitatea fizica", "Condus masina", "Zone aglomerate",
                    "Zgomote puternice", "Tusea, suflatul nasului", "Stat in picioare", "Mancatul anumitor alimente", 
                    "Perioada din zi", "Perioada menstruala", "Altele (vă rugăm să introduceți răspunsul dvs.)"
                ]
            }

        print("\nBOT:", text + "\n" + str(data))
        dispatcher.utter_message(text=text, json_message=data)
        return []

class ActionAskDnBQ7(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ7"

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

class ActionAskDnBQ7i(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ7i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            ["If yes, please explain:", " ", " ", "Daca da, detaliati."]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBQ8(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ8"

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

class ActionAskDnBQ9(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ9"

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

class ActionAskDnBQ9i(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ9i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "If yes, how do you support yourself?",
                " ", 
                " ", 
                "Dacă da, cum vă întrețineți?"
            ]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBQ10(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ10"

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

class ActionAskDnBQ11(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ11"

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

class ActionAskDnBQ11i(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ11i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            ["If yes, # of falls in the last 6 months...",
             " ", 
             " ", 
             "Daca da, cate caderi au fost pe parcursul a 6 luni ?"]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBQ12(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ12"

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

class ActionAskDnBQ12i(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbQ12i"

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
        return "action_ask_dNbPastMedicalHistory"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)
        
        text = get_text_from_lang(
            tracker, [
                "Past medical history - Please circle all that apply:",
                " ",
                " ",
                "Antecedente personale patologice - Incercuiti ce va caracterizeaza :"
            ]
        )

        if tracker.get_slot("language") == "English":
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

        elif tracker.get_slot("language") == "Romanian":
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

        print("\nBOT:", text + "\n" + str(data))
        dispatcher.utter_message(text=text, json_message=data)
        return []

class ActionAskDnBPastMedicalHistoryOther(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbPastMedicalHistoryOther"

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
        return "action_ask_dNbMedicalTests"

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

        if tracker.get_slot("language") == "English":
            data = {
                    "choices": [
                        "MRI", "MRA", "CT", "X-Ray", "Blood"
                    ]
                }

        elif tracker.get_slot("language") == "Romanian":
            data = {
                "choices": [
                    "MRI", "MRA", "CT", "X-Ray", "Blood"    # TODO To be changed to romanian version
                ]
            }

        print("\nBOT:", text + "\n" + str(data))
        dispatcher.utter_message(text=text, json_message=data)
        return []

class ActionAskDnBMedicalTestsOther(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbMedicalTestsOther"

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

class ActionAskDnBOnSetType(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbOnSetType"

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

        if tracker.get_slot("language") == "English":
            data = {
                    "choices": [
                        "SURGICAL", "INJURY", "INSIDIOUS"
                    ]
                }

        elif tracker.get_slot("language") == "Romanian":
            data = {
                "choices": [
                    "dupa interventie chirurgicala", "dupa un traumatism", "fara sa poata fi asociate cu un anumit eveniment"
                ]
            }

        print("\nBOT:", text + "\n" + str(data))
        dispatcher.utter_message(text=text, json_message=data)
        return []

class ActionAskDnBEarSymptomI(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomI"

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

class ActionAskDnBEarSymptomIa(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomIa"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "If yes, which ear(s):",
                " ",
                " ",
                "Dacă da, care ureche(e):"
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

class ActionAskDnBEarSymptomIb(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomIb"

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

class ActionAskDnBEarSymptomII(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomII"

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

class ActionAskDnBEarSymptomIIa(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomIIa"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "If yes, which ear(s):",
                " ",
                " ",
                "Dacă da, care ureche(e):"
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

class ActionAskDnBEarSymptomIII(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomIII"

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

class ActionAskDnBEarSymptomIIIa(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomIIIa"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "If yes, which ear(s):",
                " ",
                " ",
                "Dacă da, care ureche(e):"
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

class ActionAskDnBEarSymptomIIIa1(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomIIIa1"

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

class ActionAskDnBEarSymptomIIIa2(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomIIIa2"

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

class ActionAskDnBEarSymptomIIIa3(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomIIIa3"

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

class ActionAskDnBEarSymptomIIIa3i(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomIIIa3i"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "If yes, explain:",
                " ",
                " ",
                "Dacă da, explicați."
            ]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDnBEarSymptomIV(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomIV"

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

class ActionAskDnBEarSymptomV(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomV"

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

class ActionAskDnBEarSymptomVI(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomVI"

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

class ActionAskDnBEarSymptomVII(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomVII"

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

class ActionAskDnBEarSymptomVIII(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomVIII"

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

class ActionAskDnBEarSymptomIX(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomIX"

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

class ActionAskDnBEarSymptomX(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomX"

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

class ActionAskDnBEarSymptomXI(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNbEarSymptomXI"

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

class ValidateDnBForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_dizznbalance_form"

    async def required_slots(
        self, slots_mapped_in_domain, dispatcher, tracker, domain,
    ) -> List[Text]:

        if not tracker.get_slot("dNbQ2"):
            slots_mapped_in_domain.remove("dNbQ2i")
        
        if tracker.get_slot("dNbQ3"):
            slots_mapped_in_domain.remove("dNbQ3i")
        
        if not tracker.get_slot("dNbQ4"):
            slots_mapped_in_domain.remove("dNbQ4a")
            slots_mapped_in_domain.remove("dNbQ4b")
            slots_mapped_in_domain.remove("dNbQ4c")
            slots_mapped_in_domain.remove("dNbQ4ci")
            slots_mapped_in_domain.remove("dNbQ4d")
        elif not tracker.get_slot("dNbQ4c"):
            slots_mapped_in_domain.remove("dNbQ4ci")

        if not tracker.get_slot("dNbQ5"):
            slots_mapped_in_domain.remove("dNbQ5i")

        if not tracker.get_slot("dNbQ6"):
            slots_mapped_in_domain.remove("dNbQ6i")

        if not tracker.get_slot("dNbQ7"):
            slots_mapped_in_domain.remove("dNbQ7i")

        if not tracker.get_slot("dNbQ9"):
            slots_mapped_in_domain.remove("dNbQ9i")

        if not tracker.get_slot("dNbQ11"):
            slots_mapped_in_domain.remove("dNbQ11i")

        if not tracker.get_slot("dNbQ12"):
            slots_mapped_in_domain.remove("dNbQ12i")

        if not tracker.get_slot("dNbEarSymptomI"):
            slots_mapped_in_domain.remove("dNbEarSymptomIa")
            slots_mapped_in_domain.remove("dNbEarSymptomIb")

        if not tracker.get_slot("dNbEarSymptomII"):
            slots_mapped_in_domain.remove("dNbEarSymptomIIa")

        if not tracker.get_slot("dNbEarSymptomIII"):
            slots_mapped_in_domain.remove("dNbEarSymptomIIIa")
            slots_mapped_in_domain.remove("dNbEarSymptomIIIa1")
            slots_mapped_in_domain.remove("dNbEarSymptomIIIa2")
            slots_mapped_in_domain.remove("dNbEarSymptomIIIa3")
            slots_mapped_in_domain.remove("dNbEarSymptomIIIa3i")
        elif not tracker.get_slot("dNbEarSymptomIIIa3"):
            slots_mapped_in_domain.remove("dNbEarSymptomIIIa3i")

        return slots_mapped_in_domain

####################################################################################################
# Eating Habits Questionnaire                                                                      #
####################################################################################################

class ActionUtterDietStart(Action):
    def name(self):
        return "action_utter_ask_diet_start"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Would you like to fill it? It shouldn't take more than 7 minutes.",
                " ",
                " ",
                "Doriți să-l umpleți? Nu ar trebui să dureze mai mult de 7 minute."
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Start Eating Habits Questionnaire", "No"],
                [" ", " "],
                [" ", " "],
                ["Porniți chestionarul obiceiuri alimentare", "Nu"]
            ],
            ['/diet_start', '/deny']
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskDietQ1(Action):
    def name(self) -> Text:
        return "action_ask_dietQ1"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ2(Action):
    def name(self) -> Text:
        return "action_ask_dietQ2"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ3(Action):
    def name(self) -> Text:
        return "action_ask_dietQ3"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ4(Action):
    def name(self) -> Text:
        return "action_ask_dietQ4"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ5(Action):
    def name(self) -> Text:
        return "action_ask_dietQ5"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ6(Action):
    def name(self) -> Text:
        return "action_ask_dietQ6"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ7(Action):
    def name(self) -> Text:
        return "action_ask_dietQ7"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ8(Action):
    def name(self) -> Text:
        return "action_ask_dietQ8"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ9(Action):
    def name(self) -> Text:
        return "action_ask_dietQ9"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ10(Action):
    def name(self) -> Text:
        return "action_ask_dietQ10"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ11(Action):
    def name(self) -> Text:
        return "action_ask_dietQ11"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ12(Action):
    def name(self) -> Text:
        return "action_ask_dietQ12"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ13(Action):
    def name(self) -> Text:
        return "action_ask_dietQ13"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ14(Action):
    def name(self) -> Text:
        return "action_ask_dietQ14"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "How frequently did you consume dietary products (low-fat foods0 or dietary cheese)?",
                " ",
                " ",
                "Cat de frecvent consumati produse dietetice (alimente cu continut redus de grasimi sau branza dietetica)?"
            ]
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ15(Action):
    def name(self) -> Text:
        return "action_ask_dietQ15"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ16(Action):
    def name(self) -> Text:
        return "action_ask_dietQ16"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ17(Action):
    def name(self) -> Text:
        return "action_ask_dietQ17"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ18(Action):
    def name(self) -> Text:
        return "action_ask_dietQ18"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ19(Action):
    def name(self) -> Text:
        return "action_ask_dietQ19"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

class ActionAskDietQ20(Action):
    def name(self) -> Text:
        return "action_ask_dietQ20"

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

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []

####################################################################################################
# Muscle Tone Questionnaire                                                                        #
####################################################################################################

class ActionUtterMuscleToneStart(Action):
    def name(self):
        return "action_utter_ask_muscle_start"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Would you like to fill it? It shouldn't take more than 7 minutes.",
                " ",
                " ",
                "Doriți să-l umpleți? Nu ar trebui să dureze mai mult de 7 minute."
            ]
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Start Muscle Tone Questionnaire", "No"],
                [" ", " "],
                [" ", " "],
                ["Începeți chestionarul pentru tonusul muscular", "Nu"]
            ],
            ['/muscletone_start', '/deny']
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []

class ActionAskMTQ1(Action):
    def name(self) -> Text:
        return "action_ask_mtQ1"
    
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

class ActionAskMTQ2(Action):
    def name(self) -> Text:
        return "action_ask_mtQ2"
    
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
class ActionAskMTQ3(Action):
    def name(self) -> Text:
        return "action_ask_mtQ3"
    
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

class ActionAskMTQ4(Action):
    def name(self) -> Text:
        return "action_ask_mtQ4"
    
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

class ActionAskMTQ5(Action):
    def name(self) -> Text:
        return "action_ask_mtQ5"
    
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

class ActionAskMTQ6(Action):
    def name(self) -> Text:
        return "action_ask_mtQ6"
    
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

class ActionAskMTQ7(Action):
    def name(self) -> Text:
        return "action_ask_mtQ7"
    
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

class ActionAskMTQ8(Action):
    def name(self) -> Text:
        return "action_ask_mtQ8"
    
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

class ActionAskMTQ9(Action):
    def name(self) -> Text:
        return "action_ask_mtQ9"
    
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

class ActionAskMTQ10(Action):
    def name(self) -> Text:
        return "action_ask_mtQ10"
    
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
                "Esti sigur? Modul în care te simți este, de asemenea, o parte importantă a progresului tău fizic.",
                "Sei sicuro? Anche il modo in cui ti senti è una parte importante del tuo progresso fisico.",
            ]
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []

####################################################################################################
# Set Questionnaire Slot Value                                                                     #
####################################################################################################

class ActionUtterSetQuestionnaire(Action):
    def name(self) -> Text:
        return "action_utter_set_questionnaire"

    def run(self, dispatcher, tracker, domain):
        announce(self, tracker)

        open_questionnaire = tracker.slots["questionnaire"].title()

        return []
