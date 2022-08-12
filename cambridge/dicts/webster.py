"""Fetch, parse, print, and save Webster dictionary."""

import requests
import threading
import sys
from urllib import parse
from lxml import etree

from cambridge.console import console
from cambridge.settings import OP, DICTS
from cambridge.utils import get_request_url
from cambridge.log import logger
from cambridge.dicts import dict


WEBSTER_BASE_URL = "https://www.merriam-webster.com"
WEBSTER_DICT_BASE_URL = WEBSTER_BASE_URL + "/dictionary/"


# ----------Request Web Resouce----------
def search_webster(con, cur, input_word, is_fresh=False):
    """
    Entry point for dealing with Mirriam Webster Dictionary.
    It first checks the cache, if the word has been cached,
    uses it and prints it; if not, go fetch the web.
    If the word is found, prints it to the terminal and caches it concurrently.
    if not found, prints word suggestions and exit.
    """

    req_url = get_request_url(WEBSTER_DICT_BASE_URL, input_word, DICTS[1])

    if not is_fresh:
        cached = dict.cache_run(con, cur, input_word, req_url, DICTS[1])
        if not cached:
            fresh_run(con, cur, req_url, input_word)
    else:
        fresh_run(con, cur, req_url, input_word)


def fresh_run(con, cur, req_url, input_word):
    result = fetch_webster(req_url, input_word)
    found = result[0]
    res_word, res_url, res_text = result[1]
    nodes = parse_dict(res_text, found)

    parse_thread = threading.Thread(
        target=parse_and_print, args=(res_url, nodes, found)
    )
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
            logger.debug(f'{OP[5]} "{res_word}" in {DICTS[1]} at {res_url}')
            return True, (res_word, res_url, res_text)

        # By default Requests will perform location redirection for all verbs except HEAD.
        # https://requests.readthedocs.io/en/latest/user/quickstart/#redirection-and-history
        # You don't need to deal with redirection yourself.
        # if status == 301:
        #     loc = res.headers["location"]
        #     new_url = WEBSTER_BASE_URL + loc
        #     new_res = dict.fetch(new_url, session)

        if status == 404:
            logger.debug(f'{OP[6]} "{input_word}" in {DICTS[1]}')
            return False, (res_word, res_url, res_text)


def parse_and_print(response_url, nodes, found):
    """The entry point for parsing and printing."""

    logger.debug(f"{OP[1]} the fetched result of {response_url}")

    if not found:
        logger.debug(f"{OP[4]} the parsed result of {response_url}")
        parse_spellcheck(nodes)
        sys.exit()
    else:
        logger.debug(f"{OP[4]} the parsed result of {response_url}")
        parse_word(response_url, nodes)


def parse_dict(res_text, found):
    """Parse the dict section of the page for the word."""

    tree = etree.HTML(res_text)

    if found:
        s = """
        //*[@id="left-content"]/div[@class="row entry-header"] |
        //*[@id="left-content"]/div[@class="row entry-attr"] |
        //*[@id="left-content"]/div[@class="row headword-row"] |
        //*[@id="left-content"]/div[contains(@id, "dictionary-entry")] |
        //*[@id="left-content"]/div[@id="other-words-anchor"] |
        //*[@id="left-content"]/div[@id="synonyms-anchor"] |
        //*[@id="left-content"]/div[@id="examples-anchor"]/div[@class="on-web read-more-content-hint-container"]
        """

        # Discard ruling out strategy
        # *[@id="left-content"]/
        # div[following::div[@id="first-known-anchor"] and
        # not(attribute::class="ul-must-login-def") and
        # not(attribute::id="synonym-discussion-anchor") and
        # not(attribute::class="wgt-incentive-anchors")

        nodes = tree.xpath(s)

        # for node in nodes:
        #     try:
        #         print("id:    ", node.attrib["id"])
        #     except KeyError:
        #         print("class: ", node.attrib["class"])
        #
        # # class:  row entry-header
        # # class:  row entry-attr
        # # class:  row headword-row
        # # id:     dictionary-entry-1
        # # class:  row entry-header
        # # id:     dictionary-entry-2
        # # class:  row entry-header
        # # id:     dictionary-entry-3
        # # id:     other-words-anchor
        # # id:     synonyms-anchor
        # # class:  on-web read-more-content-hint-container

        return nodes

    else:
        nodes = tree.xpath('//div[@class="widget spelling-suggestion"]')[0]

        return nodes


# FIXME BIG based on word type
def print_synonyms(node):
    """Print synonyms."""

    time = 0
    for elm in node.iterdescendants():
        try:
            has_title = (elm.tag == "h2")
            has_syn = (elm.tag == "a") and (elm.attrib["href"].startswith("/dictionary"))
        except KeyError:
            continue
        else:
            if has_title:
                print("\n")
                for t in elm.itertext():
                    console.print(f"[bold]{t.upper()}", end="")
                print()

            if has_syn:
                if time == 10:
                    break
                console.print(f"{elm.text}", end="  ", style="italic")
                time = time + 1


def print_other_words(node):
    """Print other word forms."""

    for elm in node.iterdescendants():
        try:
            has_title = (elm.tag == "h2")
            has_words = (elm.tag == "span") and (elm.attrib["class"] == "ure")
            has_type = (elm.tag == "span") and (elm.attrib["class"] == "fl")
        except KeyError:
            continue
        else:
            if has_title:
                print("\n")
                for t in elm.itertext():
                    console.print(f"[bold]{t.upper()}", end="")
                print()

            if has_words:
                console.print(f"[bold]{elm.text}", end=" ")

            if has_type:
                print(f"[{elm.text}]", end=" ")


def print_examples(node, word):
    """Print recent examples on the web."""

    print()
    time = 0

    for elm in node.iterdescendants():
        try:
            is_label = (elm.attrib["class"] == "ex-header function-label")
            has_aq = (elm.attrib["class"] == "t has-aq")
        except KeyError:
            continue
        else:
            if is_label:
                console.print(f"\n[bold]{elm.text.upper()}", end="\n")

            if has_aq:
                for t in elm.itertext():
                    if time in [0, 1, 8, 9, 16, 17,  24, 25]:
                        if t.strip().lower() == word.lower():
                            console.print(f"[#3C8DAD]{t}", end="", style="italic bold")
                        else:
                            console.print(f"[#3C8DAD]{t}", end="")
                    else:
                        continue
                if time in [0, 1, 8, 9, 16, 17,  24, 25]:
                    print()
                time = time + 1


def print_word_and_wtype(node):
    """Print word and its type."""

    for elm in node.iterdescendants():
        try:
            has_word = (elm.attrib["class"] == "hword")
            has_type = (elm.attrib["class"] == "important-blue-link")
        except KeyError:
            continue
        else:
            if has_word:
                word = elm.text
                console.print(
                    f"\n[bold #3C8DAD on #DDDDDD]{word}[/bold #3C8DAD on #DDDDDD]", end=" "
                )
            if has_type:
                console.print(f"[bold] \033[33m{elm.text.upper()}\033[0m", end=" ")
                print()
    return word


# ---Print dictionary entry content---
def print_num(node):
    """Print number enumeration."""
    t = node.text
    if t != "1":
        console.print(f"\n[bold]{t}", end=" ")
    else:
        console.print(f"[bold]{t}", end=" ")


def print_letter(node):
    """Print letter enumeration."""

    t = node.text
    if t != "a":
        console.print(f"\n  [bold]{t}", end=" ")
    else:
        console.print(f"[bold]{t}", end=" ")


def print_sent(node):
    "Print example sentences under a definition."

    console.print("\n[#3C8DAD]//", end=" ")
    for t in node.itertext():
        console.print(f"[#3C8DAD]{t}", end="")


def print_def(node):
    "Print the definition."

    for t in node.itertext():
        if t == " ":
            continue
        if t.strip() == ":":
            console.print("\n", end="")
        else:
            console.print(f"{t}", end="")


# FIXME big
def print_dict_entry(node):
    """The dispatch function to dispatch parsing different sections of a dict entry."""

    for i in node.iterdescendants():
        try:
            # has_num = (i.tag == "span") and (i.attrib["class"] == "num")
            # has_letter = (i.tag == "span") and (i.attrib["class"] == "letter")
            has_def = (i.tag == "span") and (i.attrib["class"] == "dtText")
            has_sent = (i.tag == "span") and ("ex-sent" in i.attrib["class"] and ("ex-sent aq has-aq sents" != i.attrib["class"]))
            has_verb_form = (i.tag == "a") and (i.attrib["class"] ==  "important-blue-link")
            has_sl = (i.tag == "span") and (i.attrib["class"] == "sl")
            has_sd = (i.tag == "span") and (i.attrib["class"] == "sd")
            has_drp = (i.tag == "span") and (i.attrib["class"] == "drp")

        except KeyError:
            continue

        # Print the number enumeration of the definition
        # if has_num:
        #     print_num(i)

        # Print the letter enumeration of the definition
        # if has_letter:
        #     print_letter(i)

        # Print word definition
        if has_def:
            print_def(i)

        # Print sentences with author
        if has_sent:
            print_sent(i)

        # Print verb forms
        if has_verb_form:
            print(i.text)

        if has_sl or has_sd:
            console.print(f"\n({i.text.strip()})", style="italic", end="")

        if has_drp:
            console.print(f"\n\n{i.text.strip()}", style="bold", end=" ")


def parse_word(res_url, nodes):
    """The dispatch function to dispatch parsing different sections of a word."""

    for node in nodes:
        try:
            attr = node.attrib["id"]
        except KeyError:
            attr = node.attrib["class"]

        # Print word and its types like verb, noun, and adjetive etc.
        if attr == "row entry-header":
            word = print_word_and_wtype(node)

        # Print pronounciations
        if attr == "row entry-attr":
            attrs = list(node.itertext())
            for index, t in enumerate(attrs):
                if index == 2 or index == 5:
                    print(t.strip(), end=" ")
                else:
                    print(t.strip(), end="")
            print()

        # Print headword forms
        if attr == "row headword-row":
            for i in node.iterdescendants():
                if (i.tag == "span") and (i.attrib["class"] == "if"):
                    print(i.text, end=" ")
            print()

        # Print dictionary entry content
        if "dictionary-entry" in attr:
            print_dict_entry(node)

        # Print other word forms limiting 10
        if attr == "other-words-anchor":
            print_other_words(node)

        # Print synonyms
        if attr == "synonyms-anchor":
            print_synonyms(node)

        # Print web examples
        if attr == "on-web read-more-content-hint-container":
            print_examples(node, word)


def parse_spellcheck(nodes):
    """Parse spellcheck info and print it."""

    for node in nodes:
        if node.tag == "h1":
            w = node.text.strip("”").strip("“")
            console.print("[bold #3C8DAD on #DDDDDD]" + w)
        else:
            for word in node.itertext():
                w = word.strip()
                if w.startswith("The"):
                    w = w.split(" or")[0].replace("Click on", "Check out")
                    console.print("[bold #3C8DAD]" + "\n" + w)
                else:
                    console.print("[#b2b2b2]" + "  • " + w.strip())
