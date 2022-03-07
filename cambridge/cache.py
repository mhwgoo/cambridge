import sqlite3
from pathlib import Path

data = Path.home() / ".cache" / "cambridge"
data.mkdir(parents=True, exist_ok=True)

DB = str(data / "cambridge.db")

def create_table (con, cur):
    cur.execute('''CREATE TABLE words
       ("input_word" TEXT UNIQUE,
       "response_url" TEXT UNIQUE,
        "response_text" TEXT)''')
    con.commit()

def insert_into_table(con, cur, word, url, text):
    cur.execute("INSERT INTO words VALUES (?, ?, ?)", (word, url, text))
    con.commit()

def get_inputword(cur, word):
    cur.execute("SELECT input_word FROM words WHERE input_word = ?", (word,))
    data = cur.fetchone()
    return data


def get_response(cur, word):
    cur.execute("SELECT response_url, response_text FROM words WHERE input_word = ?", (word,))
    data = cur.fetchone()
    return data[0], data[1]
