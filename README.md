# Alameda-Conversational-Agent

## Zenon is a healthcare-oriented conversational agent.
Zenon conversational agent aims to help doctors caregivers, and patients. Doctors may employ Zenon to handle assessment tasks, extract results from questionnaires and give an overview of the sentiment of the patient. On the other hand, caregivers and patients may use Zenon for frequently asked questions, ask for quick help over an issue, and a report for their progress.

## Prerequisites
Make sure you have installed Python 3.8 to your system.

1. Create a new virtual environment (it is recommended to use pip based virtual environmnet instead of conda environments)
2. After you create your environment, activate it and run the following command. Make sure to use the specific versions of these packages to avoid dependencies issues.
        ```
        pip install rasa==2.8.3 rasa-sdk==2.8.1 sanic==20.12.3
        ```

2. To run Alameda chatbot on server:
    1. Open a terminal activate the conda environment then run the command `rasa run actions`
    2. Open a new terminal activate the conda environment and run `rasa run`
    4. Open a new terminal and run `ngrok http 5005` then copy the "https://" url and add it to the application.