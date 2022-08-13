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
        //*[@id="left-content"]/div[contains(@class, "row entry-header")] |
        //*[@id="left-content"]/div[@class="row entry-attr"] |
        //*[@id="left-content"]/div[@class="row headword-row"] |
        //*[@id="left-content"]/div[contains(@id, "dictionary-entry")] |
        //*[@id="left-content"]/div[@id="other-words-anchor"] |
        //*[@id="left-content"]/div[@id="synonyms-anchor"] |
        //*[@id="left-content"]/div[@id="examples-anchor"]/div[@class="on-web read-more-content-hint-container"] |
        //*[@id="left-content"]/div[@id="related-phrases-anchor"]
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


def print_other_words(node):
    """Print other word forms."""

    for elm in node.iterdescendants():
        try:
            has_title = (elm.tag == "h2")
            has_words = (elm.tag == "span") and (elm.attrib["class"] == "ure")
            has_type = (elm.tag == "span") and (elm.attrib["class"] == "fl")
            has_em = (elm.tag == "em")
        except KeyError:
            continue
        else:
            if has_title:
                print()
                console.print(f"[bold yellow]{elm.text}", end="")

            if has_em:
                console.print(f"[bold yellow italic]{elm.text}", end="\n")

            if has_words:
                console.print(f"[bold]{elm.text}", end=" ")

            if has_type:
                print(f"[{elm.text}]", end=" ")


def print_synonyms(node):
    """Print synonyms."""

    for elm in node.iterdescendants():
        try:
            has_title = (elm.tag == "h2")
            has_label = (elm.tag == "p") and (elm.attrib["class"] == "function-label")
            has_syn = (elm.tag == "ul")
            has_em = (elm.tag == "em")
        except KeyError:
            continue
        else:
            if has_title:
                console.print(f"\n[bold yellow]{elm.text}", end="")

            if has_em:
                console.print(f"[bold yellow italic]{elm.text}", end="")

            if has_syn:
                for t in elm.itertext():
                    if t.strip() == ",":
                        console.print(t.strip(), end=" ")
                    else:
                        console.print(t, end="")

            if has_label:
                console.print(f"\n{elm.text}", style="bold")


def print_examples(node, words):
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
                console.print(f"\n[bold yellow]{elm.text}", end="")
            if has_aq:
                for index, t in enumerate(list(elm.itertext())):
                    if time in [0, 1, 8, 9, 16, 17,  24, 25]:
                        if index == 0:
                            console.print("\n[#3C8DAD]//", end=" ")
                            console.print(f"[#3C8DAD]{t}", end="")
                        else:
                            if t.strip().lower() in words:
                                console.print(f"[#3C8DAD]{t}", end="", style="italic bold")
                            else:
                                console.print(f"[#3C8DAD]{t}", end="")
                    else:
                        continue
                time = time + 1


def print_phrases(node, words):
    """Print related phrases."""

    children = node.getchildren()
    title = children[0]

    print("\n")
    for t in title.itertext():
        if t.strip().lower() in words:
            console.print(f"[bold yellow italic]{t}", end="\n")
        else:
            console.print(f"[bold yellow]{t}", end="")

    pr_sec = children[1]
    sub_ps = pr_sec.getchildren()[1]  # divs: related-phrases-list-container-xs

    phrases = []    # li tags, each tag has one phrase
    for i in sub_ps.iterdescendants():
        if i.tag == "li":
            phrases.append(i)

    if len(phrases) > 20:
        phrases = phrases[:20]

    for phrase in phrases:
        ts = list(phrase.itertext())
        for t in ts:
            t = t.strip("\n").strip()
            if t != ts[-1]:
                console.print(f"{t}", end="")
            else:
                if phrase != phrases[-1]:
                    console.print(f"{t},", end=" ")
                else:
                    console.print(f"{t}", end="\n")

            # !!! print(repr(t))
            # '\n          '     # if the tag has no text
            # 'beta decay'
            # '\n          '
            # 'fall into decay'
            # '\n      '


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
                word = list(elm.itertext())[0]
                console.print(f"\n[bold #3C8DAD on #DDDDDD]{word}", end="")
            if has_type:
                console.print(f" [bold yellow] {elm.text}\n", end="")
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
    "Print one example sentence."

    console.print("[#3C8DAD]//", end=" ")
    s_words = list(node.itertext())
    for t in s_words:
        if t == s_words[-1]:
            console.print(f"[#3C8DAD]{t}", end="\n")
        else:
            console.print(f"[#3C8DAD]{t}", end="")


def print_def(node):
    "Print one definition."

    s_words = list(node.itertext())
    for t in s_words:
        if t == " " and t != s_words[-1]:
            continue
        if t == s_words[-1]:
            console.print(t, end="\n")
        else:
            console.print(t, end="")


def print_seealso(node):
    """Print seealso section."""

    console.print("\nSee Also", end="\n", style="bold yellow")
    children = list(node.iterchildren())

    for i in children:
        for t in i.itertext():
            print(t, end="")

        if i != children[-1]:
            print(",", end=" ")
    print()


def print_dict_entry(node):
    """Dispatch the parsing of different sections of a dict entry."""

    for i in node.iterdescendants():
        try:
            has_num = (i.tag == "span") and (i.attrib["class"] == "num")
            # has_letter = (i.tag == "span") and (i.attrib["class"] == "letter")
            has_def = (i.tag == "span") and (i.attrib["class"] == "dtText")
            has_sent = (i.tag == "span") and ("ex-sent" in i.attrib["class"] and ("ex-sent aq has-aq sents" != i.attrib["class"]))
            has_verb_form = (i.tag == "a") and (i.attrib["class"] == "important-blue-link")
            has_sl = (i.tag == "span") and (i.attrib["class"] == "sl")
            has_sd = (i.tag == "span") and (i.attrib["class"] == "sd")
            has_vl = (i.tag == "span") and (i.attrib["class"] == "vl")
            has_drp = (i.tag == "span") and (i.attrib["class"] == "drp")
            has_va = (i.tag == "span") and (i.attrib["class"] == "va")
            has_unText = (i.tag == "span") and (i.attrib["class"] == "unText")
            has_dxnls = (i.tag == "p") and (i.attrib["class"] == "dxnls")

        except KeyError:
            continue

        # Print the number enumeration of the definition
        if has_num:
            print_num(i)

        # Print the letter enumeration of the definition
        # if has_letter:
        #     print_letter(i)

        # Print word definition
        if has_def:
            print_def(i)

        # Print sentences with author
        if has_sent:
            print_sent(i)

        # Print verb forms, like intransitive verb, transitive verb
        if has_verb_form:
            console.print(f"\n{i.text}", style="bold italic")

        if has_sl or has_sd or has_vl:
            console.print(f"({i.text.strip()})", style="italic", end=" ")

        if has_unText:
            console.print(f"({i.text.strip()})", style="italic", end="\n")

        if has_drp:
            console.print(f"\n{i.text.strip()}", style="bold yellow", end="\n")

        if has_va:
            console.print(f"{i.text.strip()}", style="bold yellow", end="")

        if has_dxnls:
            print_seealso(i)


def print_pron(node):
    """Print the pronounciation."""

    attrs = list(node.itertext())
    for index, t in enumerate(attrs):
        t = t.strip("\n").strip()
        if t == "|":
            continue
        if index == 2 and t != "":
            console.print(t, end="   ", style="bold")
        else:
            console.print(t, end="", style="bold")
    print()


def print_tenses(node):
    """Print headwords"""

    for i in node.iterdescendants():
        if (i.tag == "span") and (i.attrib["class"] == "if"):
            console.print(f"|{i.text}", end=" ", style="bold")
        if (i.tag == "span") and (i.attrib["class"] == "entry-attr vrs"):
            for t in i.itertext():
                t = t.strip("\n").strip()
                console.print(t, end=" ", style="bold")
        if (i.tag == "span") and (i.attrib["class"] == "il plural"):
            console.print(i.text.strip(), end=" ", style="italic")
    print()


def parse_word(res_url, nodes):
    """Dispatch the parsing of different sections of a word."""

    # A page may have multiple word forms, e.g. "give away", "giveaway"
    words = []

    for node in nodes:
        try:
            attr = node.attrib["id"]
        except KeyError:
            attr = node.attrib["class"]

        # Print one entry header: one word and its types like verb, noun, adj
        # One page has multiple entry headers
        # Also print a phrase entry's name and its types
        if "row entry-header" in attr:
            word = print_word_and_wtype(node)
            words.append(word)

        # Print pronounciations
        if attr == "row entry-attr":
            print_pron(node)

        # Print headword forms like verb tenses
        if attr == "row headword-row":
            print_tenses(node)

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
            print_examples(node, words)

        # Print related phrases
        if attr == "related-phrases-anchor":
            print_phrases(node, words)


def parse_spellcheck(nodes):
    """Parse spellcheck info and print it."""

    for node in nodes:
        if node.tag == "h1":
            w = node.text.strip("”").strip("“")
            console.print("[bold yellow]" + w)
        else:
            for word in node.itertext():
                w = word.strip()
                if w.startswith("The"):
                    w = w.split(" or")[0].replace("Click on", "Check out")
                    console.print("[bold #3C8DAD]" + "\n" + w)
                else:
                    console.print("  • " + w.strip())
