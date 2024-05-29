from pathlib import Path
import datetime
import sqlite3

dir = Path.home() / ".cache" / "cambridge"
dir.mkdir(parents=True, exist_ok=True)
DB = str(dir / "cambridge.db")

current_datetime = datetime.datetime.now()

con = sqlite3.connect(DB, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

def create_table():
    with con:
        con.execute(
            """CREATE TABLE words (
            "input_word" TEXT NOT NULL,
            "response_word" TEXT NOT NULL,
            "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            "response_url" TEXT UNIQUE NOT NULL,
            "response_text" TEXT NOT NULL,
            UNIQUE(response_url))"""
        )


def insert_into_table(input_word, response_word, url, text):
    response_word = response_word.lower()
    with con:
        try:
            con.execute(
                "INSERT INTO words (input_word, response_word, created_at, response_url, response_text) VALUES (?, ?, ?, ?, ?)",
                (input_word, response_word, current_datetime, url, text)
            )
        except sqlite3.IntegrityError as error:
            return (False, error)

        except sqlite3.InterfaceError as error:
            return (False, error)
        else:
            return (True, None)


def get_cache(word, request_url):
    try:
        with con:
            cur = con.execute(
                "SELECT response_url, response_word, response_text FROM words WHERE response_url = ? OR response_word = ? OR input_word = ?",
                (request_url, word, word)
            )
    except sqlite3.OperationalError:
        create_table()
    else:
        data = cur.fetchone()
        return data


def get_response_words(is_random=False):
    try:
        with con:
            if is_random:
                cur = con.execute("SELECT response_word, response_url FROM words ORDER BY RANDOM() LIMIT 20")
            else:
                cur = con.execute("SELECT response_word, response_url, created_at FROM words")
    except sqlite3.OperationalError:
        return (False, None)
    else:
        data = cur.fetchall()
        return (True, data)


def delete_word(word):
    with con:
        cur = con.execute("SELECT input_word, response_url FROM words WHERE input_word = ? OR response_word = ?", (word, word))
        data = cur.fetchall()

        if data == []:
            return (False, None)
        else:
            con.execute("DELETE FROM words WHERE input_word = ? OR response_word = ?", (word, word))
            return (True, data)
