# Alameda-Conversational-Agent

1. Create a new virtual environment
    1. pip based virtual environment
    
        Please use the following commands if you want to build a virtual environment based on pip
        ```
        python3 -m venv env
        source env/bin/activate
        pip install -r requirements.txt
        ```
    2. conda based environment
    
        In case you want to create a conda environment you can install the packages by using the following command
        
        `conda env create -f alameda-chatbot.yml`

2. To run Alameda chatbot on server:
    1. Open a terminal activate the conda environment then run the command `rasa run actions`
    2. Open a new terminal activate the conda environment and run `rasa run`
    4. Open a new terminal and run `ngrok http 5005` then copy the "https://" url and add it to the application.