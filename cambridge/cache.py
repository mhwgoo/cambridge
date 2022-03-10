import sqlite3
import datetime
from pathlib import Path

dir = Path.home() / ".cache" / "cambridge"
dir.mkdir(parents=True, exist_ok=True)
DB = str(dir / "cambridge.db")

current_datetime = datetime.datetime.now()

def create_table (con, cur):
    cur.execute('''CREATE TABLE words
        ("input_word" TEXT UNIQUE NOT NULL,
        "response_word" TEXT UNIQUE NOT NULL,
        "created_at" TEXT NOT NULL,
       "response_url" TEXT UNIQUE NOT NULL,
        "response_text" TEXT NOT NULL)''')
    con.commit()

def check_table(cur):
    cur.execute("SELECT name FROM sqlite_schema WHERE type='table'")
    data = cur.fetchall()
    return data

def insert_into_table(con, cur, input_word, response_word, url, text):
    cur.execute("INSERT INTO words VALUES (?, ?, ?, ?, ?)", (input_word, response_word, current_datetime, url, text))
    con.commit()

def get_cache(cur, word, resquest_url):
    cur.execute("SELECT response_url, response_text FROM words WHERE input_word = ? OR response_word = ? OR response_url = ?", (word, word, resquest_url))
    data = cur.fetchone()
    return data

# Get all response words for l command
def get_response_words(cur):
    cur.execute("SELECT response_word FROM words")
    data = cur.fetchall()
    return data

def delete_word(con, cur, word):
    cur.execute("SELECT input_word FROM words WHERE input_word = ? OR response_word = ? ", (word, word))
    data = cur.fetchone()
    if data is None:
        return False
    else:
        cur.execute("DELETE FROM words WHERE input_word = ? OR response_word = ? ", (word, word))
        con.commit()
        return True
