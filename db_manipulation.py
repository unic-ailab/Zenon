import sqlite3
import time
import argparse

db_name = "demo.db"

def create_db():
    conn = sqlite3.connect(db_name) 
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS questionnaires_state (sender_id integer NOT NULL, 
    questionnaire_name text NOT NULL,
    available_at float NOT NULL,
    state text NOT NULL,
    timestamp_start float,
    timestamp_end float,
    answers text)''')


def insert_data(user_id, questionnaire, available_at, state, timestamp_start, timestamp_end, answers):
    conn = sqlite3.connect(db_name) 
    cursor = conn.cursor()

    # cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id integer NOT NULL, 
    # message text,
    # timestamp integer,
    # sentiment text)''')
 

    cursor.execute('''INSERT INTO questionnaires_state(sender_id, questionnaire_name, available_at, state, timestamp_start, timestamp_end, answers) VALUES (?,?,?,?,?,?,?)''', (user_id, questionnaire, available_at, state, timestamp_start, timestamp_end,  answers))
	
    print("Data added successfully...")

    # Commit your changes in the database
    conn.commit()


def delete_entry(user_id):
    conn = sqlite3.connect(db_name) 
    cursor = conn.cursor()
 

    cursor.execute('DELETE FROM userIDs WHERE sender_id=?', (user_id,))
    cursor.execute('DELETE FROM questionnaires_state WHERE sender_id=?', (user_id,))
	
    print("User deleted successfully.")

    # Commit your changes in the database
    conn.commit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='User id')
    parser.add_argument("--userid", default="stroke99")
    args = parser.parse_args()
    userid = args.userid

    insert_data(userid)
