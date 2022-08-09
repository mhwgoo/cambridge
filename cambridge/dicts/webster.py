"""Fetch, parse, print, and save Webster dictionary."""

import requests
import threading
import sys
from urllib import parse
from lxml import etree

from cambridge.console import console
from cambridge.settings import OP, DICTS
from cambridge.utils import get_request_url
from cambridge.cache import get_cache
from cambridge.log import logger
from cambridge.dicts import dict


WEBSTER_DICT_BASE_URL = "https://www.merriam-webster.com/dictionary/"
WEBSTER_BASE_URL = "https://www.merriam-webster.com"


# ----------Request Web Resouce----------
def search_webster(con, cur, input_word):
    """
    Entry point for dealing with Mirriam Webster Dictionary.
    It first checks the cache, if the word has been cached,
    uses it and prints it; if not, go fetch the web.
    If the word is found, prints it to the terminal and caches it concurrently.
    if not found, prints word suggestions and exit.
    """

    req_url = get_request_url(WEBSTER_DICT_BASE_URL, input_word, DICTS[1])
    # data is a tuple (response_url, response_text) if any
    data = get_cache(con, cur, input_word, req_url)

    if data is not None:
        logger.debug(f'{OP[5]} "{input_word}" cached before. Use cache')
        res_url, res_text = data
        tree = parse_dict(res_text, True)
        parse_and_print(res_url, tree)

    else:
        result = fetch_webster(req_url, input_word)
        found = result[0]
        res_word, res_url, res_text = result[1]
        tree = parse_dict(res_text, found)

        parse_thread = threading.Thread(target=parse_and_print, args=(res_url, tree, found))
        parse_thread.start()

        if found:
            dict.save(con, cur, input_word, res_word, res_url, res_text)


def fetch_webster(request_url, input_word):
    """Get response url and response text for future parsing."""

    with requests.Session() as session:
        session.trust_env = False
        res = dict.fetch(request_url, session)

        res_url = res.url
        res_text = res.text
        res_word = parse.unquote(res_url.split("/")[-1])
        status = res.status_code

        if status == 200:
            logger.debug(f'{OP[5]} "{res_word}" at {res_url}')
            return True, (res_word, res_url, res_text)

        # By default Requests will perform location redirection for all verbs except HEAD.
        # https://requests.readthedocs.io/en/latest/user/quickstart/#redirection-and-history
        # You don't need to deal with redirection yourself.
        # if status == 301:
        #     loc = res.headers["location"]
        #     new_url = WEBSTER_BASE_URL + loc
        #     new_res = dict.fetch(new_url, session)

        if status == 404:
            logger.debug(f'{OP[6]} "{input_word}"')
            return False, (res_word, res_url, res_text)


def parse_and_print(response_url, tree, found):
    """The entry point for parsing and printing."""

    logger.debug(f"{OP[1]} the fetched result of {response_url}")

    if not found:
        logger.debug(f"{OP[4]} the parsed result of {response_url}")
        parse_spellcheck(tree)
        sys.exit()
    else:
        logger.debug(f"{OP[4]} the parsed result of {response_url}")
        parse_word(response_url, tree)


def parse_dict(res_text, found):
    """Parse the dict section of the page for the word."""

    tree = etree.HTML(res_text)

    if found:
        return tree.xpath('//*[@id="left-content"]')[0]
    else:
        return tree.xpath('//div[@class="widget spelling-suggestion"]')[0]


# TODO
def parse_word(res_url, tree):
    print("hello world")


def parse_spellcheck(tree):
    """Parse spellcheck info and print it to the terminal."""

    for i in tree:
        if i.tag == "h1":
            w = i.text.strip('”').strip('“')
            console.print("[bold #3C8DAD on #DDDDDD]" + w)
        else:
            for word in i.itertext():
                w = word.strip()
                if w.startswith("The"):
                    w = w.split(" or")[0].replace("Click on", "Check out")
                    console.print("[bold #3C8DAD]" + "\n" + w)
                else:
                    console.print("[#b2b2b2]" + "  • " + w.strip())
