import random

from typing import Any, Dict, List, Text
from urllib import response

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet, FollowupAction
from rasa_sdk.executor import CollectingDispatcher

# Define this list as the values for the `language` slot. Arguments of the `get_..._lang` functions should respect this order.
lang_list = ["English", "Greek", "Italian", "Romanian"]  # Same as slot values

# PSQI Questionnaire
psqi_start_text = "During the past month,"

buttons_psqi = [
    {"title": "Not during the past month", "payload": " "},
    {"title": "Less than once a week", "payload": " "},
    {"title": "Once or twice a week", "payload": " "},
    {"title": "Three or more times a week", "payload": " "},
]

psqi_q5 = psqi_start_text + " how often have you had trouble sleeping because you "

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
# Questionnaire                                                                                    #
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


class ActionAskUsualBedTime(Action):
    def name(self) -> Text:
        return "action_ask_usualBedTime"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                " when have you usually go to bed at night?",
                " ",
                " ",
                " ",  # TODO to add romanian translation
            ],
        )

        text = psqi_start_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []


class ActionAskHoursPerSleepNight(Action):
    def name(self) -> Text:
        return "action_ask_hoursPerSleepNight"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                " how many hours of actual sleep did you get at night? (This may be different than the number of hours you spend in bed.)",
                " ",
                " ",
                " ",  # TODO to add romanian translation
            ],
        )

        text = psqi_start_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []


class ActionAskUsualGettingUpTime(Action):
    def name(self) -> Text:
        return "action_ask_usualGettingUpTime"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                " when have you usually gotten up in the morning?",
                " ",
                " ",
                " ",  # TODO to add romanian translation
            ],
        )

        text = psqi_start_text + text

        print("\nBOT:", text)
        dispatcher.utter_message(text=text)
        return []


class ActionAskNumberOfMinutes(Action):
    def name(self) -> Text:
        return "action_ask_numberOfMinutes"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        announce(self, tracker)

        text = get_text_from_lang(
            tracker,
            [
                " how long (in minutes) has it usually take you to fall asleep each night?",
                " ",
                " ",
                " ",  # TODO to add romanian translation
            ],
        )

        text = psqi_start_text + text

        print("\nBOT:", text)
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
