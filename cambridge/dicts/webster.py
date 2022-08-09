"""Fetch, parse, print, and save Webster dictionary."""

import requests
import threading
import sys
from urllib import parse
from lxml import etree

from cambridge.console import console
from cambridge.settings import OP, DICTS
from cambridge.utils import construct_request_url, parse_response_url
from cambridge.cache import get_cache
from cambridge.log import logger
from cambridge.dicts import dict


WEBSTER_DICT_BASE_URL = "https://www.merriam-webster.com/dictionary/"
WEBSTER_BASE_URL = "https://www.merriam-webster.com"


# ----------Request Web Resouce----------
def search_webser(con, cur, input_word):
    request_url = construct_request_url(WEBSTER_DICT_BASE_URL, input_word, DICTS[1])
    data = get_cache(con, cur, input_word, request_url)  # data is a tuple (response_url, response_text) if any

    if data is not None:    
        logger.debug(f'{OP[5]} "{input_word}" cached before. Use cache')
        response_url = data[0]
        tree = parse_dict(data[1], True) 

        parse_and_print(response_url, tree)

    else:
        result = fetch_webster(request_url, input_word)
        found = result[0]

        if found:
            response_url, response_text = result[1]
            tree = parse_dict(response_text, found) 
            response_word = parse_response_word(response_text)

            parse_thread = threading.Thread(
                target=parse_and_print, args=(response_url, tree)
            )
            parse_thread.start()

            dict.save(con, cur, input_word, response_word, response_url, response_text)

        else:
            spell_res_url, spell_res_text = result[1]
            tree = parse_dict(spell_res_text, False) 
            parse_and_print(spell_res_url, tree)


def fetch_webster(request_url, input_word):
    """Get response url and response text for future parsing."""

    with requests.Session() as session:
        session.trust_env = False
        res = dict.fetch(request_url, session)

        res_url = parse_response_url(res.url, DICTS[1])
        res_text = res.text
        status = res.status_code

        if status == "200":
            logger.debug(f'{OP[5]} "{input_word}" in Cambridge at {res_url}')
            return True, (res_url, res_text)
        if status == "301":
            logger.debug(f'{OP[5]} "{parse.unquote(input_word)}" instead in Cambridge at {res_url}')
            loc = res.headers["location"]
            new_url = WEBSTER_BASE_URL + loc
            new_res = dict.fetch(new_url, session)
            return True, (parse_response_url(new_res.url), new_res.text)
        if status == "404":
            logger.debug(f'{OP[6]} "{input_word}" in Cambridge')
            return False, (res_url, res_text) 


# ----------The Entry Point For Parse And Print----------
def parse_and_print(response_url, tree, found):
    logger.debug(f"{OP[1]} the fetched result of {response_url}")

    if not found:
        logger.debug(f"{OP[4]} the parsed result of {response_url}")
        parse_spellcheck(tree)
        sys.exit()
    else:
        logger.debug(f"{OP[4]} the parsed result of {response_url}")
        parse_word(response_url, tree)


def parse_dict(response_text, found):
    """Parse the dict section of the page for the word."""

    tree = etree.HTML(response_text)
    if found:
        return tree.xpath('//*[@id="left-content"]')
    else:
        return tree.xpath('//*[@class="left-content col-lg-7 col-xl-8 mb-5"]')


# TODO
def parse_word(response_url, tree):
    pass


def parse_spellcheck(tree):
    """Parse spellcheck info and print it to the terminal."""

    input_word = dict.find("h1", "mispelled-word").text
    notice = dict.find("p", "spelling-suggestion-text").text.split("Click")[0].strip()
    suggestion = dict.find("p", "spelling-suggestions").text

    console.print("[bold #3C8DAD on #DDDDDD]" + input_word)
    console.print("[bold #3C8DAD]" + "\n" + notice)
    console.print("[#b2b2b2]" + "  • " + suggestion)



# ----------Parse Response Word----------
def parse_response_word(text):
    "Parse the response word from html head title tag."

    resp_word = etree.HTML(text).xpath("/html/head/title/text()")[0].split("Definition")[0].strip().lower()
    return resp_word




