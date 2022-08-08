"""Fetch, parse, print, and save Webster dictionary."""

from cambridge.console import console
from cambridge.errors import ParsedNoneError, call_on_error
from cambridge.settings import OP

WEBSTER_DICT_BASE_URL = "https://www.merriam-webster.com/dictionary/"
WEBSTER_BASE_URL = "https://www.merriam-webster.com"



"""
def search_webster(con, cur, input_word):
    pass


def request_webster(response, session, input_word):
    if response.status_code == "302":
        response = fetch(response.headers["location"], session)

    response_url = parse_response_url(response.url)
    response_text = response.text

    logger.debug(f'{OP[5]} "{input_word}" in Merrian Webster at {response_url}')
    return True, (response_url, response_text)

"""


def search_webser(con, cur, input_word):
    pass


def parse_response_word(soup):
    "Parse the response word from html title tag."

    response_word = soup.find("title").text.split("Definition")[0].strip().lower()
    return response_word


def parse_dict(url, soup):
    """Parse the dict section of the page for the word."""

    attempt = 0

    while True:
        try:
            dict = soup.find("div", id ="left-content")
        except Exception as e:
            attempt = call_on_error(e, url, attempt, OP[1])
        else:
            if not dict:
                attempt = call_on_error(ParsedNoneError(), url, attempt, OP[1])

            return dict


# ----------Parse spellcheck----------
def parse_spellcheck(dict):
    """Parse spellcheck info and print it to the terminal."""

    input_word = dict.find("h1", "mispelled-word").text
    notice = dict.find("p", "spelling-suggestion-text").text.split("Click")[0].strip()
    suggestion = dict.find("p", "spelling-suggestions").text

    console.print("[bold #3C8DAD on #DDDDDD]" + input_word)
    console.print("[bold #3C8DAD]" + "\n" + notice)
    console.print("[#b2b2b2]" + "  • " + suggestion)



# ----------Parse Dict Head----------
def parse_dict_head():
    pass

