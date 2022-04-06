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
    {"title": "Not during the past month", "payload": "/inform"},
    {"title": "Less than once a week", "payload": "/inform"},
    {"title": "Once or twice a week", "payload": "/inform"},
    {"title": "Three or more times a week", "payload": "/inform"},
]

psqi_q5 = [
    "During the past month, how often have you had trouble sleeping because you ",
    " ",
    " ",
    "In ultima luna cat de des ati avut probleme cu somnul deoarece nu "
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

    if lang_index >= len(payloads):  # No text defined for current language
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

        if (
            tracker.get_slot("questionnaire") == "ACTIVLIM"
        ):  # ACTIVLIM is only for Romanian use-case
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
            return []


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
            ["/activLim_start", "/deny"],
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
            ["/psqi_start", "/deny"],
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

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons_psqi)
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

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons_psqi)
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
                " a trebuit sa va treziti pentru a merge la baie ?",
            ],
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons_psqi)
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
                " nu ati putut respira confortabil?",
            ],
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons_psqi)
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
                " ati tusit sau sforait zgmotos?",
            ],
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons_psqi)
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
                " v-a fost frig?",
            ],
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons_psqi)
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
                " v-a fost cald?",
            ],
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons_psqi)
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
                " ati avut cosmaruri?",
            ],
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons_psqi)
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
                " ati avut dureri?",
            ],
        )

        text = entry_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons_psqi)
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
                " other reason? (please describe)",
                " ",
                " ",
                " alte motive?",
            ],
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
                "Cat de des in ultima luna ati avut probleme cu somnul din cauza lucrurilor mai sus mentionate?",
            ],
        )

        print("\nBOT:", text)
        dispatcher.utter_message(text=text, buttons=buttons_psqi)
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
            ["/inform", "/inform", "/inform", "/inform"],
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
            ["/inform", "/inform", "/inform", "/inform"],
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
            ["/inform", "/inform", "/inform", "/inform"],
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
            ["/inform", "/inform", "/inform", "/inform"],
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
                "Doriți să-l umpleți? Nu ar trebui să dureze mai mult de 7 minute.",
            ],
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Start Dizzines - Balance Questionnaire", "No"],
                [" ", " "],
                [" ", " "],
                ["Porniți chestionarul Dizzines - Balance", "Nu"],
            ],
            ["/dizzNbalance_start", "/deny"],
        )

        print("\nBOT:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []


class ActionAskDnBStartDate(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNb_startDate"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "When did your problem start (date)?",
                " ",
                " ",
                "Cand a inceput problema dumneavoastra (data)?",
            ],
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []


class ActionAskDnBRelatedEvent(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNb_relatedEvent"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                "Was it associated with a related event (e.g. head injury) ?",
                " ",
                " ",
                "A aparut in contextul unui alt eveniment (de exemplu, lovitura la cap) ?",
            ],
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Yes", "No"],
                [" ", " "],
                [" ", " "],
                ["Da", "Nu"]
            ],
            ["/affirm", "/deny"]
        )

        print("\nBot:", text, buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        return []


class ActionAskDnBRelatedEventNAME(Action):  # DnB Questionnaire
    def name(self) -> Text:
        return "action_ask_dNb_relatedEventNAME"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            ["If yes, please explain:", " ", " ", "DA/NU ; Daca da, explicati...",],
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
        return []


class ValidateDnBForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_dizznbalance_form"

    async def required_slots(
        self, slots_mapped_in_domain, dispatcher, tracker, domain,
    ) -> List[Text]:

        if not tracker.get_slot("dNb_relatedEvent"):
            slots_mapped_in_domain.remove("dNb_relatedEventNAME")

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
                "Doriți să-l umpleți? Nu ar trebui să dureze mai mult de 7 minute.",
            ],
        )

        buttons = get_buttons_from_lang(
            tracker,
            [
                ["Start Eating Habits Questionnaire", "No"],
                [" ", " "],
                [" ", " "],
                ["Porniți chestionarul obiceiuri alimentare", "Nu"],
            ],
            ["/diet_start", "/deny"],
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
                "Cand mancati carne de pui, cat de des o pregatiti la cuptor sau fiarta?",
            ],
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
                "Cand mancati carne de pui, cat de des renuntati la piele?",
            ],
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
                "Cand mancati carne rosie, cat de frecvent alegeti sa mancati doar portii mici?",
            ],
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
                "Cand mancati carne rosie, cat de frecvent separati carnea de portiunile vizibile de grasime?",
            ],
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
                "Cat de des inlocuiti carnea rosie cu pui sau peste?",
            ],
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
                "Cat de des alegeti sa puneti unt sau margarina peste legumele gatite?",
            ],
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
                "Cat de des mancati cartofi fierti sau copti fara a adauga unt sau margarina?",
            ],
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
                "Cat de des puneti smantana, branza sau alte sosuri peste legumele gatite?",
            ],
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
                "Cat de des mancati paine, briose fara a le asocia cu unt/margarina?",
            ],
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
                "Cat de des folositi un sos de rosii fara carne pe paste (spaghetti sau noodles)?",
            ],
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
                "Cat de des aveti mese doar pe baza de produse vegetale?",
            ],
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
                "Cat de des folositi iaurt in loc de smantana?",
            ],
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
                "Cat de frecvent folositi lapte cu continut foarte scazut de grasimi sau lapte 100% degresat?",
            ],
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
                "Cat de frecvent consumati produse dietetice (alimente cu continut redus de grasimi sau branza dietetica)?",
            ],
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
                "Cat de des preferati in detrimentul inghetatei sherbet, iaurt sau lapte congelat?",
            ],
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
                "Cat de des folositi dressing pentru salate cu continut redus de calorii in locul celui normal?",
            ],
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
                "Cat de des folositi produse pe baza de uleiuri/grasimi concentrate (de exemplu sub forma de spray) cand gatiti?",
            ],
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
                "Cat de des optati doar pentru fructe ca desert?",
            ],
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
                "Cat de des mancati cel putin doua legume (altele decat salata verde) la cina?",
            ],
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
                "Cat de des preferati legume crude ca snack in locul chips urilor din cartofi sau popcorn ului?",
            ],
        )

        print("\nBot:", text)
        dispatcher.utter_message(text=text)
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
            ],
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
