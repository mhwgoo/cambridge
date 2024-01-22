"""Shared functionality of all dictionaries."""

import sys
import sqlite3
import requests
from fake_user_agent import user_agent

from ..cache import insert_into_table, get_cache, delete_word
from ..log import logger
from ..settings import OP, DICTS
from ..errors import call_on_error
from ..dicts import cambridge, webster
from ..utils import make_a_soup
from ..console import console


def fetch(url, session):
    """Make a web request with retry mechanism."""

    ua = user_agent()
    headers = {"User-Agent": ua}
    session.headers.update(headers)
    attempt = 0

    logger.debug(f"{OP.FETCHING.name} {url}")
    while True:
        try:
            r = session.get(url, timeout=9.05)
            # Only when calling raise_for_status, will requests raise HTTPError if any.
            # See: https://blog.csdn.net/Odaokai/article/details/100133503
            # for webster, only when status code is 404, can we know to redirect to spellcheck page, so you can't exit on 404
            if r.status_code >= 500:
                r.raise_for_status()

        except requests.exceptions.HTTPError as e:
            attempt = call_on_error(e, url, attempt, OP.RETRY_FETCHING.name)
            continue
        except requests.exceptions.ConnectTimeout as e:
            attempt = call_on_error(e, url, attempt, OP.RETRY_FETCHING.name)
            continue
        except requests.exceptions.ConnectionError as e:
            attempt = call_on_error(e, url, attempt, OP.RETRY_FETCHING.name)
            continue
        except requests.exceptions.ReadTimeout as e:
            attempt = call_on_error(e, url, attempt, OP.RETRY_FETCHING.name)
            continue
        except Exception as e:
            attempt = call_on_error(e, url, attempt, OP.RETRY_FETCHING.name)
            continue
        else:
            return r


def cache_run(con, cur, input_word, req_url, dict):
    """Check the cache is from Cambridge or Merrian Webster."""

    # data is a tuple (response_url, response_text) if any
    data = get_cache(con, cur, input_word, req_url)

    if data is None:
        if "s" != input_word[-1]:
            return False
        else:
            data = get_cache(con, cur, input_word[:-1], req_url)
            if data is None:
                if "es" != input_word[-2:]:
                    return False
                else:
                    data = get_cache(con, cur, input_word[:-2], req_url)
                    if data is None:
                        return False

    res_url, res_word, res_text = data

    if DICTS.CAMBRIDGE.name.lower() in res_url:
        logger.debug(f"{OP.PARSING.name} {res_url}")
        soup = make_a_soup(res_text)
        cambridge.parse_and_print(soup, res_url)
        console.print(f'{OP.FOUND.name} "{res_word}" from {dict} in cache. You can add "-f -w" to fetch the {DICTS.MERRIAM_WEBSTER.name} dictionary', justify="left", style="#757575")
    else:
        nodes = webster.parse_dict(res_text, True, res_url, False)
        webster.parse_and_print(nodes, res_url)
        console.print(f'{OP.FOUND.name} "{res_word}" from {dict} in cache. You can add "-f" to fetch the {DICTS.CAMBRIDGE.name} dictionary', justify="left", style="#757575")
    return True


def save(con, cur, input_word, response_word, response_url, response_text):
    """Save a word info into local DB for cache."""

    try:
        insert_into_table(con, cur, input_word, response_word, response_url, response_text)
    except sqlite3.IntegrityError as error:
        error_str = str(error)
        if "UNIQUE constraint" in error_str:
            # For version v3.6.3 and prior, whose cache db has `response_word` column being UNIQUE
            # in this case, update the record with the new search result
            if "response_word" in error_str:
                delete_word(con, cur, response_word)
                insert_into_table(con, cur, input_word, response_word, response_url, response_text)
                logger.debug(f'{OP.UPDATED.name} cache for "{input_word}" with the new search result\n')
            else:
                logger.debug(f'{OP.CANCELLED.name} caching "{input_word}", because it has been already cached before\n')
        else:
            logger.debug(f'{OP.CANCELLED.name} caching "{input_word}" - {error}\n')
    except sqlite3.InterfaceError as error:
        logger.debug(f'{OP.CANCELLED.name} caching "{input_word}" - {error}\n')

    else:
        logger.debug(f'{OP.CACHED.name} the search result of "{input_word}"')

#TODO add an option for inputing a new word
def print_spellcheck(con, cur, input_word, suggestions, dict, is_ch=False):
    """Parse and print spellcheck info."""

    if dict == DICTS.MERRIAM_WEBSTER.name:
        console.print("[red bold]" + input_word.upper() + "[/red bold]" + " you've entered isn't in the " + "[#4A7D95]" + dict + "[/#4A7D95]" + " dictionary.\n")
    else:
        console.print("[red bold]" + input_word.upper() + "[/red bold]" + " you've entered isn't in the " + "\033[34m" + dict + "\033[0m" + " dictionary.\n")

    for count, sug in enumerate(suggestions):
        console.print("[bold]%2d" % (count+1), end="")
        if dict == DICTS.MERRIAM_WEBSTER.name:
            console.print("[#4A7D95] %s" % sug)
        else:
            console.print("\033[34m" + " " + sug + "\033[0m")


    console.print("\nEnter [bold][NUMBER][/bold] above to look up the word suggestion, press [bold][ENTER][/bold] to toggle dictionary, or [bold][ANY OTHER KEY][/bold] to exit:")

    key = input("You typed: ")
    print()

    if key.isnumeric() and (1 <= int(key) <= len(suggestions)):
        if dict == DICTS.MERRIAM_WEBSTER.name:
            webster.search_webster(con, cur, suggestions[int(key) - 1])
        if dict == DICTS.CAMBRIDGE.name:
           cambridge.search_cambridge(con, cur, suggestions[int(key) - 1], False, is_ch)
    elif key == "":
        if dict == DICTS.CAMBRIDGE.name:
            webster.search_webster(con, cur, input_word)
        if dict == DICTS.MERRIAM_WEBSTER.name:
            cambridge.search_cambridge(con, cur, input_word, False, is_ch)
    else:
        sys.exit()
