"""Shared functionality of all dictionaries."""

import sys
import sqlite3
import requests
from fake_user_agent import user_agent

from ..cache import insert_into_table, get_cache
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

    logger.debug(f"{OP[0]} {url}")
    while True:
        try:
            r = session.get(url, timeout=9.05)
        except requests.exceptions.HTTPError as e:
            attempt = call_on_error(e, url, attempt, OP[2])
            continue
        except requests.exceptions.ConnectTimeout as e:
            attempt = call_on_error(e, url, attempt, OP[2])
            continue
        except requests.exceptions.ConnectionError as e:
            attempt = call_on_error(e, url, attempt, OP[2])
            continue
        except requests.exceptions.ReadTimeout as e:
            attempt = call_on_error(e, url, attempt, OP[2])
            continue
        except Exception as e:
            attempt = call_on_error(e, url, attempt, OP[2])
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

    if DICTS[0].lower() in res_url:
        logger.debug(f"{OP[1]} {res_url}")
        soup = make_a_soup(res_text)
        cambridge.parse_and_print(soup, res_url)
        if dict == DICTS[1]:
            console.print(f'{OP[5]} "{res_word}" from {DICTS[0]} in cache. You can add "-f -w" to fetch the {DICTS[1]} dictionary', justify="left", style="#757575")
    else:
        nodes = webster.parse_dict(res_text, True, res_url, False)
        webster.parse_and_print(nodes, res_url)
        if dict == DICTS[0]:
            console.print(f'{OP[5]} "{res_word}" from {DICTS[1]} in cache. You can add "-f" to fetch the {DICTS[0]} dictionary', justify="left", style="#757575")
    return True


def save(con, cur, input_word, response_word, response_url, response_text):
    """Save a word info into local DB for cache."""

    try:
        insert_into_table(con, cur, input_word, response_word, response_url, response_text)
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint" in str(error):
            logger.debug(f'{OP[8]} caching "{input_word}" - [ERROR] - already cached before\n')
        else:
            logger.debug(f'{OP[8]} caching "{input_word}" - [ERROR] - {error}\n')
    except sqlite3.InterfaceError as error:
        logger.debug(f'{OP[8]} caching "{input_word}" - [ERROR] - {error}\n')

    logger.debug(f'{OP[7]} the search result of "{input_word}"')


def print_spellcheck(con, cur, input_word, suggestions, dict, is_ch=False):
    """Parse and print spellcheck info."""

    if dict == DICTS[1]:
        console.print("[red bold]" + input_word.upper() + "[/red bold]" + " you've entered isn't in the " + "[blue]" + dict + "[/blue]" + " dictionary.\n")
    else:
        console.print("[red bold]" + input_word.upper() + "[/red bold]" + " you've entered isn't in the " + "[yellow]" + dict + "[/yellow]" + " dictionary.\n")

    for count, sug in enumerate(suggestions):
        console.print("[bold][%2d]" % (count+1), end="")
        if dict == DICTS[1]:
            console.print("[blue] %s" % sug)
        else:
            console.print("[yellow] %s" % sug)
   
    console.print("\nEnter the [bold]NUMBER[/bold] above to [u]look up[/u] the word suggestion || [bold]LOWER-CASE LETTER T[/bold] to [u]toggle[/u] dictionary || [bold]ANY OTHER KEY[/bold] to [u]exit[/u]:")

    key = input("You typed: ")
    print()

    if key.isnumeric() and (1 <= int(key) <= len(suggestions)):
        if dict == DICTS[1]:
            webster.search_webster(con, cur, suggestions[int(key) - 1])        
        if dict == DICTS[0]:
            cambridge.search_cambridge(con, cur, suggestions[int(key) - 1], False, is_ch)
    elif key == "t":
        if dict == DICTS[0]:
            webster.search_webster(con, cur, input_word)        
        if dict == DICTS[1]:
            cambridge.search_cambridge(con, cur, input_word, False, is_ch)
    else:
        sys.exit()