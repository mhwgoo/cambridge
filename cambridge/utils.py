import time
import cProfile
import pstats
import io
from urllib import parse
from functools import wraps
from bs4 import BeautifulSoup
from enum import Enum


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
    UPDATED         = 11


class DICT(Enum):
    CAMBRIDGE       = 1,
    MERRIAM_WEBSTER = 2


def make_a_soup(text):
    soup = BeautifulSoup(text, "lxml")
    return soup


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
    """Return the unquoted Cambridge url for displaying and saving."""

    response_base_url = url.split("?")[0]
    return response_base_url


def get_request_url(url, input_word, dict):
    """Return the url formatted to request the web page."""

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


def profile(func):
    """A decorator that uses cProfile to profile a function"""

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
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_at = time.time()
        f = func(*args, **kwargs)
        time_taken = round((time.time() - start_at), 2)
        print("\nTime taken: {} seconds".format(time_taken))
        return f

    return wrapper
