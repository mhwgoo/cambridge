import sys
import subprocess
import asyncio
from urllib import parse
from enum import Enum
from fake_user_agent import aio_user_agent

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
    CANCELLING      = 10,
    DELETED         = 11,
    UPDATED         = 12,
    SWITCHED        = 13,
    SEARCHING       = 14,
    SELECTED        = 15


class DICT(Enum):
    CAMBRIDGE       = 1,
    MERRIAM_WEBSTER = 2


def get_dict_name_by_url(url):
    return DICT.CAMBRIDGE.name if DICT.CAMBRIDGE.name.lower() in url else DICT.MERRIAM_WEBSTER.name


def quit_on_error(path, error, op):
    print(f'{op} <{path}> failed: [{error.__class__.__name__}] {error}')
    sys.exit(2)


def quit_on_no_result(dict_name, is_spellcheck=False):
    w = "result" if not is_spellcheck else "suggestions"
    print(f"No {w} found in {dict_name}")
    sys.exit(1)


def cancel_on_error(path, error, attempt, op):
    attempt += 1
    logger.debug(f"{op} {path} {attempt} times")

    if attempt == 3:
        print(f'Maximum {op} reached.')
        cancel_on_error_without_retry(path, error, op)

    return attempt


def cancel_on_error_without_retry(path, error, op):
    print(f'{op} on {path} failed: [{error.__class__.__name__}]')

    logger.debug(f"{OP.CANCELLING.name} task...")
    task = asyncio.current_task()
    task.cancel() # Cancel won't exit the system, instead making it possible for fetch() to return None


async def fetch(session, url):
    attempt = 0
    ua = await aio_user_agent()
    logger.debug(f"Got User-Agent: {ua}")
    logger.debug(f"{OP.FETCHING.name} {url}")
    while True:
        try:
            resp = await session.get(url, headers={"User-Agent": ua}, timeout=5, ssl=False)
        except asyncio.TimeoutError as error:
            attempt = cancel_on_error(url, error, attempt, OP.FETCHING.name)
            continue
        except Exception as error:
            cancel_on_error_without_retry(url, error, OP.FETCHING.name) # NO break!
        else:
            return resp


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
            dict_name = get_dict_name_by_url(entry[1])
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
    flip_dict = DICT.MERRIAM_WEBSTER.name if (dict_name == DICT.CAMBRIDGE.name) else DICT.CAMBRIDGE.name
    if has_fzf:
        return f"[ENTER] to print the selected suggestion's meaning; Any [NUMBER] to switch to {flip_dict}, or a new word to search; [ESC] to quit out."
    else:
        return f"[ENTER] to switch to {flip_dict}; [NUMBER] to print the selected suggestion's meaning, or a new word to search; Any Other [KEY] to quit out: "


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
        sys.exit()


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
        sys.exit()


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
        sys.exit()


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
        sys.exit()
