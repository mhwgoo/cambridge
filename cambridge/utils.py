import sys
import subprocess
import requests
from urllib import parse
from enum import Enum
from fake_user_agent import user_agent

from .log import logger
from .console import c_print

from typing import Optional, Literal
Initiator = Literal["wod_calendar", "spell_check", "cache_list", "redirect_list"]


class OP(Enum):
    FETCHING        = 1,
    PARSING         = 2,
    RETRY_FETCHING  = 3,
    RETRY_PARSING   = 4,
    PRINTING        = 5,
    FOUND           = 6,
    NOT_FOUND       = 7,
    CACHED          = 8,
    CANCELLED       = 9,
    DELETED         = 10,
    UPDATED         = 11,
    SWITCHED        = 12,
    SEARCHING       = 13
    SELECTED        = 14


class DICT(Enum):
    CAMBRIDGE       = 1,
    MERRIAM_WEBSTER = 2


def get_dict_name_by_url(url):
    return DICT.CAMBRIDGE.name if DICT.CAMBRIDGE.name.lower() in url else DICT.MERRIAM_WEBSTER.name


def call_on_error(error, url, attempt, op):
    attempt += 1
    logger.debug(f"{op} {url} {attempt} times")
    if attempt == 3:
        print(f"Maximum {op} reached: {error}")
        sys.exit(2)
    return attempt


def fetch(url):
    with requests.Session() as session:
        session.trust_env = False # not to use proxy
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


def replace_all(string):
    return (
        string.replace("\n            (", "(")
        .replace("(\n    \t                ", "(")
        .replace("\n", " ")
        .replace("      \t                ", " ")
        .replace("\\'", "'")
        .replace("  ", " ")
        .replace("\xa0 ", "")
        .replace("[ ", "")
        .replace(" ]", "")
        .replace("[", "")
        .replace("]", "")
        .replace("A1", "")
        .replace("A2", "")
        .replace("B1", "")
        .replace("B2", "")
        .replace("C1", "")
        .replace("C2", "")
        .strip()
    )


def parse_response_url(url):
    return url.split("?")[0]


def get_request_url(url, input_word, dict):
    if dict == DICT.CAMBRIDGE.name:
        if " " in input_word:
            query_word = input_word.replace(" ", "+").replace("/", "+")
            request_url = url + query_word
        else:
            request_url = url + input_word
        return request_url

    return url + parse.quote(input_word)


def decode_url(url):
    return parse.unquote(url)


def print_word_per_line(index, word, extra=""):
    import os
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


def has_tool(name):
    from shutil import which
    return which(name) is not None


def get_suggestion_notice(dict_name, has_fzf):
    is_cambridge = (dict_name == DICT.CAMBRIDGE.name)
    flip_dict = DICT.MERRIAM_WEBSTER.name if is_cambridge else DICT.CAMBRIDGE.name
    if has_fzf:
        return "Select to print the suggestion's meaning; [NUMBER] to switch to " + flip_dict + "; Input a new word; [ESC] to quit out."
    else:
        return "[NUMBER] to print the suggestion's meaning; [ENTER] to switch to " + flip_dict + "; Input a new word; [ANY OTHER KEY] to quit out: "


def get_suggestion(suggestions, dict_name):
    c_print(dict_name + (int(len(dict_name)/2))*" ", justify="center")
    list_items(suggestions, "spell_check")
    print(get_suggestion_notice(dict_name, has_fzf=False), end="")
    key = input("")

    if (key.isnumeric() and (1 <= int(key) <= len(suggestions))):
        return suggestions[int(key) - 1]
    elif len(key) > 1:
        return key
    elif key == "":
        return ""
    else:
        return None


def get_suggestion_by_fzf(suggestions, dict_name):
    notice = get_suggestion_notice(dict_name, has_fzf=True)
    choices = "\n".join(suggestions).strip("\n")
    p1 = subprocess.Popen(["echo", choices], stdout=subprocess.PIPE, text=True)
    p2 = subprocess.Popen(["fzf", "--layout=reverse", "--bind", "enter:accept-or-print-query", "--header", notice], stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
    select_word = p2.communicate()[0].strip("\n")

    if len(select_word) == 1 and select_word.isnumeric():
        return ""
    elif p2.returncode == 0 and select_word != "":
        return select_word
    else:
        return None


def get_wod_selection(data):
    title = DICT.MERRIAM_WEBSTER.name + " Calendar of Word of the Day"
    c_print(title + (int(len(title)/2))*" ", justify="center")
    list_items(data, "wod_calendar")
    notice =  "Type one word of day from above to print the meaning; Input a new word; [ANY OTHER KEY] to quit out: "
    print(notice, end="")
    return input("")


def get_wod_selection_by_fzf(data):
    notice = "Select to print the word-of-the-day meaning; [ESC] to quit out."
    choices = "\n".join(data.keys()).strip("\n")

    p1 = subprocess.Popen(["echo", choices], stdout=subprocess.PIPE, text=True)
    p2 = subprocess.Popen(["fzf", "--layout=reverse", "--bind", "enter:accept-or-print-query", "--header", notice], stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
    select_word = p2.communicate()[0].strip("\n")

    if p2.returncode == 0 and select_word != "":
        return select_word
    else:
        return None


def get_cache_selection(data, method):
    title = "List of Cache" + f" ({method})"
    c_print(title + (int(len(title)/2))*" ", justify="center")
    list_items(data, "cache_list")
    notice =  "Type one word from above to print the meaning; Input a new word; [ANY OTHER KEY] to quit out: "
    print(notice, end="")
    return input("")


def get_cache_selection_by_fzf(data):
    notice = "Select to print the word's meaning; [ESC] to quit out."
    choices = ""
    for i in data:
        choices = choices + i[0] + "\n"
    choices = choices.strip()

    p1 = subprocess.Popen(["echo", choices], stdout=subprocess.PIPE, text=True)
    p2 = subprocess.Popen(["fzf", "--layout=reverse", "--bind", "enter:accept-or-print-query", "--header", notice], stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
    select_word = p2.communicate()[0].strip("\n")

    if p2.returncode == 0 and select_word != "":
        return select_word
    else:
        return None


def profile(func):
    import io
    import cProfile
    import pstats

    def inner(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        retval = func(*args, **kwargs)
        pr.disable()
        s = io.StringIO()
        sortby = "cumulative"
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats()
        print(s.getvalue())
        return retval

    return inner


def timer(func):
    import time
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_at = time.time()
        f = func(*args, **kwargs)
        time_taken = round((time.time() - start_at), 2)
        print("\nTime taken: {} seconds".format(time_taken))
        return f

    return wrapper
