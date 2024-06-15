import sys
import datetime
import sqlite3
from pathlib import Path

from log import logger
from utils import OP, DICT, has_tool

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


def insert_entry_into_table(input_word, response_word, url, text):
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


def check_word_in_table(word, request_url):
    try:
        with con:
            cur = con.execute(
                "SELECT response_url FROM words WHERE response_url = ? OR response_word = ? OR input_word = ?",
                (request_url, word, word)
            )
    except sqlite3.OperationalError:
        create_table()
        return None
    else:
        return cur.fetchone()


def get_entry_from_table(response_url):
    try:
        with con:
            # NOTE if (response_url) without comma is passed, you will get:
            # sqlite3.ProgrammingError: Incorrect number of bindings supplied. The current statement uses 1, and there are 57 supplied.
            cur = con.execute("SELECT response_word, response_text FROM words WHERE response_url = ?", (response_url,))
    except sqlite3.OperationalError:
        create_table()
        return None
    else:
        return cur.fetchone()


def get_entries_from_table(is_random=False):
    try:
        with con:
            if is_random:
                cur = con.execute("SELECT response_word, response_url FROM words ORDER BY RANDOM() LIMIT 20")
            else:
                cur = con.execute("SELECT response_word, response_url, created_at FROM words")
    except sqlite3.OperationalError:
        create_table()
        return None
    else:
        return cur.fetchall()


def delete_entry_from_table(word):
    with con:
        cur = con.execute("SELECT input_word, response_url FROM words WHERE input_word = ? OR response_word = ?", (word, word))
        data = cur.fetchall()

        if data == []:
            return (False, None)
        else:
            con.execute("DELETE FROM words WHERE input_word = ? OR response_word = ?", (word, word))
            return (True, data)


def delete_from_cache(word):
    deleted, data = delete_entry_from_table(word)

    if deleted and data is not None:
        for i in data:
            dict_name = DICT.CAMBRIDGE.name if "cambridge" in i[1] else DICT.MERRIAM_WEBSTER.name
            print(f'{OP.DELETED.name} "{word}" from {dict_name} in cache successfully')
    else:
        print(f'{OP.NOT_FOUND.name} "{word}" in cache')


def list_cache(method):
    is_random = True if method == "random" else False
    data = get_entries_from_table(is_random)

    if data is None:
        print("You may haven't searched any word yet")
        sys.exit(3)

    has_fzf = has_tool("fzf")
    if method == "by_alpha":
        data.sort()
    elif method == "by_time":
        reverse = True if has_fzf else False
        data.sort(reverse=reverse, key=lambda tup: tup[2])

    return (has_fzf, data)


def check_cache(input_word, req_url):
    logger.debug(f'{OP.SEARCHING.name} "{input_word}" in cache')
    data = check_word_in_table(input_word, req_url)

    # considering user might input plural nouns, or verbs with tenses
    if data is None:
        if "s" != input_word[-1]:
            return None
        else:
            data = check_word_in_table(input_word[:-1], req_url)
            if data is None:
                if "es" != input_word[-2:]:
                    return None
                else:
                    data = check_word_in_table(input_word[:-2], req_url)
                    if data is None:
                        return None

    if data is not None:
        data = data[0]

    return data


def get_cache(response_url):
    result = get_entry_from_table(response_url)
    if result is None:
        logger.error(f'You might pass the wrong argument "{response_url}" to the function. It must be actually from the cache.')
        sys.exit(4)

    return result


def save_to_cache(input_word, response_word, response_url, response_text):
    result = insert_entry_into_table(input_word, response_word, response_url, response_text)
    if result[0]:
        logger.debug(f'{OP.CACHED.name} the search result of "{input_word}"')
    else:
        error_str = str(result[1])
        if "UNIQUE constraint" in error_str:
            if "response_word" in error_str:
                delete_entry_from_table(response_word)
                insert_entry_into_table(input_word, response_word, response_url, response_text)
                logger.debug(f'{OP.UPDATED.name} cache for "{input_word}" with the new search result\n')
            else:
                logger.debug(f'{OP.CANCELLED.name} caching "{input_word}", because it has been already cached before\n')
        else:
            logger.debug(f'{OP.CANCELLED.name} caching "{input_word}" - {error_str}\n')
