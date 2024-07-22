import sys
import sqlite3
from pathlib import Path

from .log import logger
from .utils import OP, has_tool, get_dict_name_by_url

dir = Path.home() / ".cache" / "cambridge"
dir.mkdir(parents=True, exist_ok=True)
DB = str(dir / "cambridge.db")

con = sqlite3.connect(DB, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)


# NOTE Python sqslite3 syntax suger is bitter.

# The following functions suffixed with _table are simply DB operations and not complicated by higher level business logics
# The following functions suffixed with _cache are wrappers of functions suffixed with _table


def create_table():
    con.execute(
        """CREATE TABLE IF NOT EXISTS words (
        "input_word" TEXT NOT NULL,
        "response_word" TEXT NOT NULL,
        "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        "response_url" TEXT UNIQUE NOT NULL,
        "response_text" TEXT NOT NULL,
        UNIQUE(response_url))"""
    )


def insert_entry_into_table(input_word, response_word, url, text):
    import datetime
    current_datetime = datetime.datetime.now()

    try:
        # 1. About sqlite3 context manager (from sqlite3 — DB-API 2.0 interface for SQLite databases):
        # "A Connection object can be used as a context manager that automatically commits or rolls back open transactions
        # when leaving the body of the context manager. If the body of the with statement finishes without exceptions, the transaction is committed."
        # "Connection object used as context manager **ONLY** commits or rollbacks transactions, so the connection object should be closed manually."
        # NOTE Assuming a context manager is designed in the first place for automatic close operation is wrong in the case of sqlite connection object.

        # 2. About how to use sqlite3 "RETURN" primitive in Python:
        # According to 1, Python autocommits if you use context manager and when the code leaves the with block, and you later fetchone(), RETURN won't work and you will get:
        # OperationalError: cannot commit transaction - SQL statements in progress
        # According to sqlite3 docs, only after SQLITE_DONE, the RETURN starts to work.
        # Then the code is dead with the context manager: COMMIT (when leaving with block) depends on RETURN, RETURN depends on SQLITE_DONE, SQLITE_DONE happens after COMMIT
        # NOTE Don't use a connection as context manager when RETURN is needed.

        # 4. After digging deep into cpython/modules/_sqlite/cursor.c, Python deals with sqlite3 step SQLITE_DONE within fetchone(),
        # fetchone() first, then manual COMMIT, and RETURN will work.

        # 5. ON CONFLICT only takes effect when there is PRIMARY KEY or UNIQUE constraint present in the table schema.
        # You can't enforce it with other column names, or it will throw:
        # OperationalError: ON CONFLICT clause does not match any PRIMARY KEY or UNIQUE constraint
        # Example code demonstrating UPSERT i.e. ON CONFLICT (column_name) DO UPDATE SET (The code in use chooses DO NOTHING conflict resolution instead):
        """
        con.execute(
            "INSERT INTO words (input_word, response_word, created_at, response_url, response_text)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (input_word) DO UPDATE SET
            response_word=excluded.response_word,
            created_at=excluded.created_at,
            response_url=excluded.response_url,
            response_text=excluded.response_text
            ",
            (input_word, response_word, current_datetime, url, text)
        )
        """
        res_word = con.execute(
            """INSERT INTO words (input_word, response_word, created_at, response_url, response_text)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            RETURNING response_word
            """,
            (input_word, response_word, current_datetime, url, text)
        ).fetchone()

    except sqlite3.OperationalError as error:
        if "no such table" in str(error):
            create_table()
        else:
            raise
    except sqlite3.Error:
        raise
    else:
        con.commit()
        return res_word


def check_word_in_table(word, request_url):
    try:
        cur = con.execute(
            "SELECT response_url FROM words WHERE response_url = ? OR response_word = ? OR input_word = ?",
            (request_url, word, word),
        )
    except sqlite3.OperationalError as error:
        if "no such table" in str(error):
            create_table()
        else:
            raise
    except sqlite3.Error:
        raise
    else:
        return cur.fetchone()


def get_entry_from_table(response_url):
    try:

        # From https://docs.python.org/2/library/
        # "For the qmark style, parameters must be a sequence whose length must match the number of placeholders, or a ProgrammingError is raised."
        # sqlite3.ProgrammingError: Incorrect number of bindings supplied. The current statement uses 1, and there are 57 supplied.
        # "Note that it is actually the comma which makes a tuple, not the parentheses.
        # The parentheses are optional, except in the empty tuple case, or when they are needed to avoid syntactic ambiguity.
        # For example, f(a, b, c) is a function call with three arguments, while f((a, b, c)) is a function call with a 3-tuple as the sole argument."
        # NOTE (response_url) without comma won't be treated as sequence. (response_url,) should be used here.

        cur = con.execute(
            "SELECT response_word, response_text FROM words WHERE response_url = ?",
            (response_url,),
        )
    except sqlite3.Error:
        raise
    else:
        return cur.fetchone()


def get_entries_from_table(is_random=False):
    try:
        if is_random:
            cur = con.execute("SELECT response_word, response_url FROM words ORDER BY RANDOM() LIMIT 20")
        else:
            cur = con.execute("SELECT response_word, response_url, created_at FROM words")
    except sqlite3.OperationalError as error:
        if "no such table" in str(error):
            create_table()
        else:
            raise
    except sqlite3.Error:
        raise
    else:
        return cur.fetchall()


def delete_entry_from_table(word):
    try:
        res_url = con.execute("DELETE FROM words WHERE response_word = ? OR input_word = ? RETURNING response_url", (word, word)).fetchone()
    except sqlite3.OperationalError as error:
        if "no such table" in str(error):
            create_table()
        else:
            raise
    except sqlite3.Error:
        raise
    else:
        con.commit()
        return res_url


async def delete_from_cache(word):
    try:
        result = delete_entry_from_table(word)
    except sqlite3.Error as error:
        logger.error(f'{OP.CANCELLED.name} deleting "{word}" from cache: [{error.__class__.__name__}] {error}\n')
        sys.exit(4)
    else:
        if result is None:
            print(f'{OP.NOT_FOUND.name} "{word}" in cache')
        else:
            dict_name = get_dict_name_by_url(result[0])
            print(f'{OP.DELETED.name} "{word}" from {dict_name} in cache successfully')


def list_cache(method):
    is_random = True if method == "random" else False

    try:
        data = get_entries_from_table(is_random)
    except sqlite3.Error as error:
        logger.error(f'{OP.CANCELLED.name} listing cache: [{error.__class__.__name__}] {error}\n')
        sys.exit(4)
    else:
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


async def check_cache(input_word, req_url):
    logger.debug(f'{OP.SEARCHING.name} "{input_word}" in cache')

    try:
        data = check_word_in_table(input_word, req_url)
    except sqlite3.Error as error:
        logger.error(f'{OP.CANCELLED.name} searching "{input_word}" in cache: [{error.__class__.__name__}] {error}\n')
        sys.exit(4)
    else:
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
        return data[0]


async def get_cache(response_url):
    result = get_entry_from_table(response_url)
    if result is None:
        logger.error(f'The function argument "{response_url}" must actually come from the cache.')
        sys.exit(4)
    return result


async def save_to_cache(input_word, response_word, response_url, response_text):
    try:
        result = insert_entry_into_table(input_word, response_word, response_url, response_text)

        # a duplicate check way other than ON CONFLICT
        # sqllite3.IntegrityError: NOT NULL constraint failed
        # sqllite3.IntegrityError: UNIQUE constraint failed
        # Only with `as error`, can you get str(error) as error message; str(sqlite3.IntegrityError) gives you "<class 'sqlite3.IntegrityError'>".
        """
        except sqlite3.IntegrityError as error:
            if "UNIQUE constraint" in str(error): logger.debug(f'{OP.CANCELLED.name} caching "{input_word}": {error}\n')
        """

    except sqlite3.Error as error:
        logger.error(f'{OP.CANCELLED.name} caching "{input_word}": [{error.__class__.__name__}] {error}\n')
        sys.exit(4)

    else:
        if result is None:
            logger.debug(f'{OP.CANCELLED.name} caching, already cached before') # hit ON CONFLICT
        else:
            logger.debug(f'{OP.CACHED.name} "{result[0]}"')
