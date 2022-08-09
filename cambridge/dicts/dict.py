"""Shared functionality of all dictionaries."""

import sqlite3
import requests
from fake_user_agent import user_agent

from cambridge.cache import insert_into_table
from cambridge.log import logger
from cambridge.settings import OP
from cambridge.errors import call_on_error


# ----------Fetch Web Resource----------
def fetch(url, session):
    ua = user_agent()
    headers = {"User-Agent": ua}
    session.headers.update(headers)
    attempt = 0

    while True:
        try:
            logger.debug(f"{OP[0]} {url}")
            r = session.get(url, timeout=9.05)
        except requests.exceptions.HTTPError as e:
            attempt = call_on_error(e, url, attempt, OP[2])
        except requests.exceptions.ConnectTimeout as e:
            attempt = call_on_error(e, url, attempt, OP[2])
        except requests.exceptions.ConnectionError as e:
            attempt = call_on_error(e, url, attempt, OP[2])
        except requests.exceptions.ReadTimeout as e:
            attempt = call_on_error(e, url, attempt, OP[2])
        except Exception as e:
            attempt = call_on_error(e, url, attempt, OP[2])
        else:
            return r


# ----------Cache Web Resource----------
def save(con, cur, input_word, response_word, response_url, response_text):
    try:
        insert_into_table(
            con, cur, input_word, response_word, response_url, response_text
        )
        logger.debug(f'{OP[7]} the search result of "{input_word}"')
    except sqlite3.IntegrityError as e:
        logger.debug(f'{OP[8]} caching "{input_word}" because of {str(e)}')
        pass


