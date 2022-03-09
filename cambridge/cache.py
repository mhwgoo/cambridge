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
        "created_at" TEXT NOT NULL,
       "response_url" TEXT UNIQUE NOT NULL,
        "response_text" TEXT NOT NULL)''')
    con.commit()

def insert_into_table(con, cur, word, url, text):
    cur.execute("INSERT INTO words VALUES (?, ?, ?, ?)", (word, current_datetime, url, text))
    con.commit()

def get_inputword(cur, word):
    cur.execute("SELECT input_word FROM words WHERE input_word = ?", (word,))
    data = cur.fetchone()
    return data

def get_response(cur, word):
    cur.execute("SELECT response_url, response_text FROM words WHERE input_word = ?", (word,))
    data = cur.fetchone()
    return data[0], data[1]

def get_inputwords(cur):
    cur.execute("SELECT input_word FROM words")
    data = cur.fetchall()
    return data

def check_table(cur):
    cur.execute("SELECT name FROM sqlite_schema WHERE type='table'")
    data = cur.fetchall()
    return data
