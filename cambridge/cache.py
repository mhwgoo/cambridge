from pathlib import Path
import datetime
import sqlite3

dir = Path.home() / ".cache" / "cambridge"
dir.mkdir(parents=True, exist_ok=True)
DB = str(dir / "cambridge.db")

current_datetime = datetime.datetime.now()


def create_table(con, cur):
    cur.execute(
        """CREATE TABLE words (
        "input_word" TEXT NOT NULL,
        "response_word" TEXT UNIQUE NOT NULL,
        "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        "response_url" TEXT UNIQUE NOT NULL,
        "response_text" TEXT NOT NULL)"""
    )
    con.commit()


# def check_table(cur):
#     """Check a table exists or not"""
#
#     cur.execute("SELECT name FROM sqlite_schema WHERE type='table'")


def insert_into_table(con, cur, input_word, response_word, url, text):
    cur.execute(
        "INSERT INTO words (input_word, response_word, created_at, response_url, response_text) VALUES (?, ?, ?, ?, ?)",
        (input_word, response_word, current_datetime, url, text),
    )
    con.commit()


def get_cache(con, cur, word, resquest_url):
    try:
        cur.execute(
            "SELECT response_url, response_word, response_text FROM words WHERE response_url = ? OR response_word = ? OR input_word = ?",
            (resquest_url, word, word),
        )
    except sqlite3.OperationalError:
        create_table(con, cur)
    else:
        data = cur.fetchone()
        return data


def get_response_words(cur):
    """Get all response words for l command on terminal"""

    cur.execute("SELECT input_word, response_word, response_url, created_at FROM words")
    data = cur.fetchall()
    return data


def get_random_words(cur):
    """Get random response words for l -r command on terminal"""

    cur.execute("SELECT input_word, response_word, response_url FROM words ORDER BY RANDOM() LIMIT 20")
    data = cur.fetchall()
    return data


def delete_word(con, cur, word):
    cur.execute(
        "SELECT input_word, response_url FROM words WHERE input_word = ? OR response_word = ?",
        (word, word),
    )
    data = cur.fetchone()

    if data is None:
        return (False, None)
    else:
        cur.execute(
            "DELETE FROM words WHERE input_word = ? OR response_word = ?", (word, word)
        )
        con.commit()
        return (True, data)
