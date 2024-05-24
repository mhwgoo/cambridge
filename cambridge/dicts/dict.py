import sys
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
def print_spellcheck(con, cur, input_word, suggestions, dict_name, is_ch=False):
    """Parse and print spellcheck info."""

    if is_tool("fzf"):
        fzf_spellcheck(con, cur, input_word, suggestions, dict_name, is_ch)
    else:
        for count, sug in enumerate(suggestions):
            c_print("#[bold]%2d" % (count+1), end="")
            if dict_name == DICT.MERRIAM_WEBSTER.name:
                c_print("#[#4A7D95] %s" % sug)
            else:
                print("\033[34m" + " " + sug + "\033[0m")

        c_print(f"Press [NUMBER] to look up the suggestion inferred from the unfound #[red]{input_word}#[/red], [ENTER] to toggle dictionary, or [ANY OTHER KEY] to exit: ", end="")
        key = input("")
        if key.isnumeric() and (1 <= int(key) <= len(suggestions)):
            if dict_name == DICT.MERRIAM_WEBSTER.name:
                webster.search_webster(con, cur, suggestions[int(key) - 1])
            if dict_name == DICT.CAMBRIDGE.name:
               cambridge.search_cambridge(con, cur, suggestions[int(key) - 1], False, is_ch)
        elif key == "":
            if dict_name == DICT.CAMBRIDGE.name:
                webster.search_webster(con, cur, input_word)
            if dict_name == DICT.MERRIAM_WEBSTER.name:
                cambridge.search_cambridge(con, cur, input_word, False, is_ch)
        else:
            sys.exit()


def print_entry(index, entry, extra):
    import os

    cols = os.get_terminal_size().columns
    entry_len = len(entry)

    if index % 2 == 0:
        print(f"\033[37;;40m{index+1:6d}|{entry}", end="")
        print(f"\033[37;;40m{extra:>{cols-entry_len-7}}\033[0m")

    else:
        c_print(f"#[#4A7D95]{index+1:6d}|{entry}", end="")
        c_print(f"#[#4A7D95]{extra:>{cols-entry_len-7}}")


def fzf(data, con, cur):
    choices = {}
    for entry in data:
        choices[entry[0]] = entry[1]

    c = "\n".join(choices.keys())
    p1 = subprocess.Popen(["echo", c], stdout=subprocess.PIPE, text=True)
    p2 = subprocess.Popen(["fzf", "--layout=reverse"], stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
    input_word = p2.communicate()[0].strip("\n")
    if p2.returncode == 130 and input_word == "": # press ESC, not word selected, quit out of fzf
        exit()
    if "merrian" in choices[input_word]:
        webster.search_webster(con, cur, input_word, req_url=choices[input_word])
    else:
        cambridge.search_cambridge(con, cur, input_word, req_url=choices[input_word])


def fzf_spellcheck(con, cur, input_word, data, dict_name, is_ch):
    choices = []
    for entry in data:
        choices.append(entry)

    choices.append("\nNOT FOUND. Select one suggestion above, or press [ESC] to exit.")

    c = "\n".join(choices)
    p1 = subprocess.Popen(["echo", c], stdout=subprocess.PIPE, text=True)
    p2 = subprocess.Popen(["fzf", "--layout=reverse"], stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
    select_word = p2.communicate()[0].strip("\n")
    if p2.returncode == 130 and select_word == "": # press ESC, not word selected, quit out of fzf
        exit()
    if "merrian" in dict_name.lower():
        webster.search_webster(con, cur, select_word, req_url=None)
    else:
        cambridge.search_cambridge(con, cur, select_word, is_ch=is_ch, req_url=None)


def fzf_wod(data):
    choices = []
    for entry in data:
        choices.append(entry)

    c = "\n".join(choices)
    p1 = subprocess.Popen(["echo", c], stdout=subprocess.PIPE, text=True)
    p2 = subprocess.Popen(["fzf", "--layout=reverse"], stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
    select_word = p2.communicate()[0].strip("\n")
    if p2.returncode == 130 and select_word == "": # press ESC, not word selected, quit out of fzf
        exit()
