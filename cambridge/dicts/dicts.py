import sys
import os
import sqlite3
import requests
import subprocess
from fake_user_agent import user_agent

from ..cache import insert_into_table, get_cache, delete_word
from ..log import logger
from ..errors import call_on_error
from ..dicts import cambridge, webster
from ..utils import make_a_soup, OP, DICT, is_tool
from ..console import c_print

from typing import (
    Optional,
    Literal
)

Initiator = Literal["wod_calendar", "spell_check", "cache_list"]

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


def cache_run(con, cur, input_word, req_url):
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

    if DICT.CAMBRIDGE.name.lower() in res_url:
        logger.debug(f"{OP.PARSING.name} {res_url}")
        soup = make_a_soup(res_text)
        cambridge.parse_and_print(soup, res_url)
        c_print(f'\n#[#757575]{OP.FOUND.name} "{res_word}" from {DICT.CAMBRIDGE.name} in cache. You can add "-f -w" to fetch the {DICT.MERRIAM_WEBSTER.name} dictionary', justify="left")
    else:
        nodes = webster.parse_dict(res_text, True, res_url, False)
        webster.parse_and_print(nodes, res_url)
        c_print(f'\n#[#757575]{OP.FOUND.name} "{res_word}" from {DICT.MERRIAM_WEBSTER.name} in cache. You can add "-f" to fetch the {DICT.CAMBRIDGE.name} dictionary', justify="left")
    return True


def save(con, cur, input_word, response_word, response_url, response_text):
    """Save a word info into local DB for cache."""

    try:
        insert_into_table(con, cur, input_word, response_word, response_url, response_text)
    except sqlite3.IntegrityError as error:
        error_str = str(error)
        if "UNIQUE constraint" in error_str:
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


def print_spellcheck(con, cur, input_word, suggestions, dict_name, is_ch=False):
    """Parse and print spellcheck info."""

    is_cambridge = (dict_name == DICT.CAMBRIDGE.name)
    flip_dict = DICT.MERRIAM_WEBSTER.name if is_cambridge else DICT.CAMBRIDGE.name

    if is_tool("fzf"):
        spellcheck_notice = "NOT FOUND. Select to print the suggestion's meaning; [NUMBER] to switch to " + flip_dict + "; Input a new word; [ESC] to quit out."
        list_items_fzf(con, cur, suggestions, "spell_check", spellcheck_notice, input_word, dict_name, is_ch)
    else:
        c_print(dict_name + (int(len(dict_name)/2))*" ", justify="center")
        list_items(suggestions, "spell_check")
        spellcheck_notice = "NOT FOUND. [NUMBER] to print the suggestion's meaning; [ENTER] to switch to " + flip_dict + "; Input a new word; [ANY OTHER KEY] to quit out: "
        c_print(spellcheck_notice, end="")
        key = input("")

        if (key.isnumeric() and (1 <= int(key) <= len(suggestions))):
            cambridge.search_cambridge(con, cur, suggestions[int(key) - 1], False, is_ch) if is_cambridge else webster.search_webster(con, cur, suggestions[int(key) - 1])
        elif len(key) > 1:
            cambridge.search_cambridge(con, cur, key, False, is_ch) if is_cambridge else webster.search_webster(con, cur, key)
        elif key == "":
            webster.search_webster(con, cur, input_word) if is_cambridge else cambridge.search_cambridge(con, cur, input_word, False, is_ch)
        else:
            sys.exit()


def print_word_per_line(index, word, extra=""):
    cols = os.get_terminal_size().columns
    word_len = len(word)

    if index % 2 == 0:
        print(f"\033[37;1;100m{index+1:6d}|{word}", end="")
        print(f"\033[37;1;100m{extra:>{cols-word_len-7}}\033[0m")
    else:
        c_print(f"#[bold #4A7D95]{index+1:6d}|{word}", end="")
        c_print(f"#[bold #4A7D95]{extra:>{cols-word_len-7}}")


def list_items(data, initiator: Optional[Initiator] = None):
    for index, entry in enumerate(data):
        if initiator == "cache_list":
            word = entry[0]
            dict_name = "CAMBRIDGE" if "cambridge" in entry[1] else "WEBSTER"
            print_word_per_line(index, word, dict_name)
        elif initiator == "wod_calendar":
            date_string = data[entry].split("/")[-1]
            date = ""
            for i, c in enumerate(date_string):
                if c.isnumeric():
                    date = date_string[i:]
                    break
            print_word_per_line(index, entry, date)
        else:
            print_word_per_line(index, entry, "")


def list_items_fzf(con, cur, data, initiator: Optional[Initiator] = None, notice="", input_word=None, dict_name=None, is_ch=False):
    choices = ""
    if initiator == "cache_list":
        for i in data:
            choices = choices + i[0] + "\n"
    elif initiator == "wod_calendar":
        choices = "\n".join(data.keys())
    else:
        choices = "\n".join(data)
    choices = choices.strip("\n")

    p1 = subprocess.Popen(["echo", choices], stdout=subprocess.PIPE, text=True)
    p2 = subprocess.Popen(["fzf", "--layout=reverse", "--bind", "enter:accept-or-print-query", "--header", notice], stdin=p1.stdout, stdout=subprocess.PIPE, text=True)

    select_word = p2.communicate()[0].strip("\n")

    logger.debug(f"select_word by fzf is: {repr(select_word)}; returncode by fzf is: {p2.returncode}")

    is_cambridge = (dict_name == DICT.CAMBRIDGE.name)

    if len(select_word) == 1 and not select_word.isalpha() and initiator == "spell_check":
        webster.search_webster(con, cur, input_word, req_url=None) if is_cambridge else cambridge.search_cambridge(con, cur, input_word, is_ch=is_ch, req_url=None)
    elif p2.returncode == 0 and select_word != "":
        if initiator == "wod_calendar" and select_word in data.keys():
            url = webster.WEBSTER_BASE_URL + data[select_word]
            webster.get_wod_past(url)
        else:
            cambridge.search_cambridge(con, cur, select_word, is_ch=is_ch, req_url=None) if is_cambridge else webster.search_webster(con, cur, select_word, req_url=None)
    else:
        sys.exit()
