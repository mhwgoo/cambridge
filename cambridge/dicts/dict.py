"""Shared functionality of all dictionaries."""

import sqlite3
import requests
from fake_user_agent import user_agent

from ..cache import insert_into_table, get_cache
from ..log import logger
from ..settings import OP, DICTS
from ..errors import call_on_error
from ..dicts import cambridge, webster


def fetch(url, session):
    """Make a web request with retry mechanism."""

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


def cache_run(con, cur, input_word, req_url, dict):
    """Check the cache is from Cambridge or Merrian Webster."""

    # data is a tuple (response_url, response_text) if any
    data = get_cache(con, cur, input_word, req_url)

    if data is not None:
        res_url, res_text = data

        if DICTS[0].lower() in res_url:
            if dict != DICTS[0]:
                print(
                    f'{OP[5]} "{input_word}" from {DICTS[0]} in cache, used it. Not to use it, try with "-f" flag'
                )

            soup = cambridge.make_a_soup(res_text)
            cambridge.parse_and_print(res_url, soup)
        else:
            if dict != DICTS[1]:
                print(
                    f'{OP[5]} "{input_word}" from {DICTS[1]} in cache, used it. Not to use it, try with "-f" flag'
                )
            nodes = webster.parse_dict(res_text, True)
            webster.parse_and_print(res_url, nodes, True)
        return True

    return False


def save(con, cur, input_word, response_word, response_url, response_text):
    """Save a word info into local DB for cache."""

    try:
        insert_into_table(
            con, cur, input_word, response_word, response_url, response_text
        )
        logger.debug(f'{OP[7]} the search result of "{input_word}"')
    except sqlite3.IntegrityError as e:
        logger.debug(f'{OP[8]} caching "{input_word}" because of {str(e)}')
        pass
