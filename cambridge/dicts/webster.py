"""Fetch, parse, print, and save Webster dictionary."""

import requests
import threading
import sys
from lxml import etree

from ..console import console
from ..settings import OP, DICTS
from ..utils import get_request_url
from ..log import logger
from ..dicts import dict

# TODO sub_num (1) (2) with parent meaning or not
# If not parent meaing, don't print.


# Test fzf preview under development env
# python main.py l | fzf --preview 'python main.py -w {}'


WEBSTER_BASE_URL = "https://www.merriam-webster.com"
WEBSTER_DICT_BASE_URL = WEBSTER_BASE_URL + "/dictionary/"

res_word = ""


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
    res_url, res_text = result[1]
    nodes = parse_dict(res_text, found)

    parse_thread = threading.Thread(
        target=parse_and_print, args=(res_url, nodes, found)
    )
    parse_thread.start()

    if found:
        # res_word may not be returned when `save` is called by concurrency
        # word wiin res_url is still the input_word formatted
        global res_word
        if not res_word:
            res_word = input_word
        dict.save(con, cur, input_word, res_word, res_url, res_text)


def fetch_webster(request_url, input_word):
    """Get response url and response text for future parsing."""

    with requests.Session() as session:
        session.trust_env = False
        res = dict.fetch(request_url, session)

        res_url = res.url
        res_text = res.text
        status = res.status_code

        if status == 200:
            logger.debug(f'{OP[5]} "{input_word}" in {DICTS[1]} at {res_url}')
            return True, (res_url, res_text)

        # By default Requests will perform location redirection for all verbs except HEAD.
        # https://requests.readthedocs.io/en/latest/user/quickstart/#redirection-and-history
        # You don't need to deal with redirection yourself.
        # if status == 301:
        #     loc = res.headers["location"]
        #     new_url = WEBSTER_BASE_URL + loc
        #     new_res = dict.fetch(new_url, session)

        if status == 404:
            logger.debug(f'{OP[6]} "{input_word}" in {DICTS[1]}')
            return False, (res_url, res_text)


def parse_and_print(response_url, nodes, found):
    """The entry point for parsing and printing."""

    logger.debug(f"{OP[1]} the fetched result of {response_url}")

    if not found:
        logger.debug(f"{OP[4]} the parsed result of {response_url}")
        parse_spellcheck(nodes)
        sys.exit()
    else:
        logger.debug(f"{OP[4]} the parsed result of {response_url}")
        parse_word(nodes)


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

        # TODO
        # //*[@id="left-content"]/div[contains(@id, "art-anchor")] |

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


# --- Print other utility content ---
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
                print("\n")
                console.print(f"[bold yellow]{elm.text}", end="")

            if has_em:
                console.print(f"[bold yellow italic]{elm.text}", end="\n")

            if has_words:
                console.print(f"[#b2b2b2]{elm.text}", end=" ")

            if has_type:
                console.print(f"{elm.text}", end=" ", style="bold italic")


def print_synonyms(node):
    """Print synonyms."""

    print("\n")
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
                console.print(f"[bold yellow]{elm.text}", end="")

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
                    console.print(f"{t},", end=" ", style="#b2b2b2")
                else:
                    console.print(f"{t}", end="\n", style="#b2b2b2")

            # !!! print(repr(t))
            # '\n          '     # if the tag has no text
            # 'beta decay'
            # '\n          '
            # 'fall into decay'
            # '\n      '


# --- Print dictionary entry ---
def print_verb_types(node):
    """Print verb types, like transitive, intransitive."""

    print()

    ts = list(node.itertext())
    ts = [t for t in ts if len(t.strip("\n").strip()) > 0]
    for t in ts:
        console.print(f"{t}", style="bold italic", end="")

    print()


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


def print_num(num):
    """Print number enumeration."""

    if num != "1":
        console.print(f"\n[bold]{num}", end=" ")
    else:
        console.print(f"[bold]{num}", end=" ")


def print_label(node, inline, has_number, is_sdsense, tag_class, label_1_num=1):
    """Print the label before a definition text, like informal, especially."""

    if isinstance(node, str):
        text = node.strip()
    else:
        text = node.text.strip()

    if inline:
        console.print(f" {text}", style="italic bold", end=" ")

    else:
        if not has_number:
            console.print(f"{text}", style="italic bold", end=" ")
        else:
            if is_sdsense:
                print()
                console.print(f"   {text}", style="italic bold", end=" ")
            else:
                if tag_class == "sb-0":
                    if label_1_num == 1:
                        console.print(f" {text}", style="italic bold", end=" ")
                    else:
                        console.print(f"{text}", style="italic bold", end=" ")
                else:
                    if label_1_num == 1:
                        print()
                        console.print(f"   {text}", style="italic bold", end=" ")
                    else:
                        console.print(f"{text}", style="italic bold", end=" ")


def print_sent(node, has_number, tag_class):
    "Print one example sentence under the text of one definition item."

    print()
    if has_number or tag_class != "sb-0":
        console.print("[#3C8DAD]   //", end=" ")
    else:
        console.print("[#3C8DAD]//", end=" ")

    s_words = list(node.itertext())

    for t in s_words:
        console.print(f"[#3C8DAD]{t.strip()}", end="")


def print_subsense_text(text, subsense_index):
    """
    Print one definition text only in the case that it has the form of (1) text or (2) text ... 
    and must have a general meaning above it without (1) or (2). For example:

    : this is the general meaning
    (1) text
    (2) text

    The '(1) text part' or 'the (2) text' part is what this function prints.

    Without the general meaing, it will be treated as a normal definition in `print_def_text`.
    And '(1)' sign won't get printed.
    """

    if subsense_index == 0:
        print()
        console.print(f"  {text}", end="", style="#b2b2b2")
    if subsense_index > 0:
        console.print(text, end="", style="#b2b2b2")


def print_bare_def(text):
    """Print a definition text without labels or subsense signs in itself."""

    print()
    console.print(f"  {text}", end="", style="#b2b2b2")


def print_def_text(node, dtText_index, tag_class, has_label_1, has_label_2, subsense_index, before_subnum, has_number):
    """Print one definition text."""

    ts = list(node.itertext())
    if ts[0] == " ":
        ts = ts[1:]

    new_ts = []
    after = False

    for idx, text in enumerate(ts):
        if text == ": ":
            if idx == 0:
                if has_label_1 or has_label_2 or before_subnum:
                    continue
                elif tag_class == "sb-0" and not has_number:
                    continue
                else:
                    text = ":"
                    new_ts.append(text)
            else:
                text = "- "
                after = True
                new_ts.append(text)
        else:
            if after:
                text = text.upper()
                new_ts.append(text)
            else:
                new_ts.append(text)

    t = "".join(new_ts)

    if dtText_index == 0:
        if has_label_1 or has_label_2:
            console.print(t, end="", style="#b2b2b2")
        elif tag_class == "sb-0":
            if subsense_index > 0:
                print_bare_def(t)
            else:
                console.print(t, end="", style="#b2b2b2")
        else:
            if subsense_index == -1:
                print_bare_def(t)
            else:
                if before_subnum:
                    print_subsense_text(t, subsense_index)
                else:
                    print_bare_def(t)

    # If it's not the first dtText, it has to indent
    # except that it has label
    else:
        if has_label_2:
            console.print(t, end="", style="#b2b2b2")
        if has_label_1:
            print()
            console.print(f"   {t}", end="", style="#b2b2b2")
        else:
            if subsense_index == -1:
                print_bare_def(t)
            else:
                if before_subnum:
                    print_subsense_text(t, subsense_index)
                else:
                    print_bare_def(t)


def print_def_content(node, has_number, tag_class, has_label_1, is_sdsense, subsense_index, before_subnum):
    """Print definition content including definition text and its examples."""

    dtText_index = 0    # number of dtText under span "dt " tag
    children = node.getchildren()
    has_label_2 = False

    # span "dt " has definite child span "dtText"
    # and/or children span class starting with "ex-sent"
    for i in children:
        attr = i.attrib["class"]

        if attr == "sd":
            print_label(i, False, has_number, is_sdsense, tag_class)
            has_label_2 = True

        if attr == "dtText":
            print_def_text(i, dtText_index, tag_class, has_label_1, has_label_2, subsense_index, before_subnum, has_number)
            dtText_index += 1

        if attr == "uns":
            un = i.getchildren()[0]
            for c in un.iterchildren():
                cattr = c.attrib["class"]
                if cattr == "unText":
                    t = "". join(list(c.itertext()))
                    if len(children) == 1:
                        print_label(t, False, False, is_sdsense, tag_class)
                    else:
                        print_label(t, True, False, is_sdsense, tag_class)
                if cattr == "vis":
                    print_sent(c, has_number, tag_class)

        if "ex-sent " in attr and (attr != "ex-sent aq has-aq sents"):
            print_sent(i, has_number, tag_class)


def print_sense(node, tag_class, subsense_index, before_subnum):
    """
    Like print a meaning, b meaning and so forth.
    """

    has_number = False
    has_label_1 = False
    is_sdsense = False
    label_1_num = 1

    # sense has one child span "dt " or two children: "sn sense- ..." or "dt "
    for i in node.iterchildren():
        attr = i.attrib["class"]

        # number and letter enunciation section
        if "sn sense-" in attr:
            # no matter is_number or not, has_number is True
            has_number = True
            for c in i.iterchildren():
                if (c.tag == "span") and (c.attrib["class"] == "num"):
                    print_num(c.text)

                if (c.tag == "span") and (c.attrib["class"] == "sub-num") and before_subnum:
                    print()
                    console.print(f"  [bold]{c.text}", end=" ")

        # span "sl" is a label
        if (attr == "sl") or ("if" in attr) or ("plural" in attr) or ("il" in attr):
            has_label_1 = True
            print_label(i, False, has_number, is_sdsense, tag_class, label_1_num)
            label_1_num += 1

        # definition content section including definition and sentences
        if "dt " in attr:
            print_def_content(i, has_number, tag_class, has_label_1, is_sdsense, subsense_index, before_subnum)

        # span section under span section "dt hasSdSense"
        if attr == "sdsense":
            is_sdsense = True
            print_def_content(i, has_number, tag_class, has_label_1, is_sdsense, subsense_index, before_subnum)


def print_sub_def(node, tag_class):
    """
    Print sub definition within one defition bundle.
    Peel down to the core of a meaning, b meaning, etc.
    """

    sense = node.getchildren()[0]
    index = -1
    before_subnum = False  # if there is a general definition above (1) and (2)

    if sense.attrib["class"] == "pseq no-subnum":
        sub_senses = sense.getchildren()
        for idx, sub in enumerate(sub_senses):
            if (idx == 0) and (sub.attrib["class"] != "sense has-sn has-subnum"):
                before_subnum = True

            print_sense(sub, tag_class, idx, before_subnum)
    else:
        # Under a span "sb + number", get a child div with a class name being:
        # "sense no-subnum" or "sense has-number-only" or "sense-has-sn" ...
        # sense is the only one child of the node
        print_sense(sense, tag_class, index, before_subnum)


def print_def_bundle(node):
    """
    Print one bundle of similar definitions and sentences within one entry.
    Like print definition 1, definition 2 and so forth.
    """

    children = node.getchildren()   # get spans with class "sb-0", "sb-1" ...

    for c in children:
        tag_class = c.attrib["class"]
        print_sub_def(c, tag_class)  # print a span class "sb-0" or "sb-1"


def print_main_entry(node):
    """Print the main entry aside from the phrase part."""

    sections = node.getchildren()  # get class "vd", "sb has-num" ...
    for s in sections:
        if s.tag == "p" and ("vd" in s.attrib["class"]):
            print_verb_types(s)

        if s.tag == "div" and ("sb" in s.attrib["class"]):
            print_def_bundle(s)     # print class "sb has-num", "sb no-sn" ...


def print_phrase_part(node):
    """Print the phrase part in the main entry."""

    for i in node.iterchildren():
        if (i.tag == "span") and (i.attrib["class"] == "drp"):
            print("\n")
            console.print(f"{i.text}", end="\n", style="bold yellow")
        if (i.tag == "div") and (i.attrib["class"] == "vg"):
            print_main_entry(i)


def print_dict_entry(node):
    """Dispatch the parsing of different sections of a dict entry."""

    for i in node.iterchildren():
        try:
            attr = i.attrib["class"]
        except KeyError:
            continue

        # div "vg" is the main dictionary section
        if attr == "vg":
            print_main_entry(i)

        # div "dro" is the phrase section with its own name and definitions
        if attr == "dro":
            print_phrase_part(i)

        # p "dxnlx" is the seealso section
        if attr == "dxnls":
            print_seealso(node)


# --- Print head info of a word ---
def print_forms(node):
    """Print word forms including tenses, plurals, etc."""

    for i in node.iterdescendants():
        if (i.tag == "span") and ("if" in i.attrib["class"]):
            console.print(f"{i.text}", end="  ", style="bold")

        if (i.tag == "span") and (i.attrib["class"] == "entry-attr vrs"):
            for t in i.itertext():
                t = t.strip("\n").strip()
                console.print(t, end=" ", style="bold")

        if (i.tag == "span") and ("il" in i.attrib["class"]):
            console.print(i.text.strip(), end=" ", style="italic")
    print()


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


def print_word_and_wtype(node, head):
    """Print word and its type."""

    if head == 1:
        print()
    else:
        print("\n")

    for elm in node.iterdescendants():
        try:
            has_word = (elm.attrib["class"] == "hword")
            has_type = (elm.attrib["class"] == "important-blue-link")
            has_lb = (elm.attrib["class"] == "lb")
        except KeyError:
            continue
        else:
            if has_word:
                word = list(elm.itertext())[0]
                console.print(f"[bold #3C8DAD on #DDDDDD]{word}", end="")
            if has_type:
                console.print(f" [bold yellow] {elm.text}", end="")
            if has_lb:
                console.print(f"[bold yellow] {elm.text}", end="")
    print()
    return word


# --- Entry point of all prints of a word found ---
def parse_word(nodes):
    """Dispatch the parsing of different sections of a word."""

    # A page may have multiple word forms, e.g. "give away", "giveaway"
    words = []
    head = 1

    for node in nodes:
        try:
            attr = node.attrib["id"]
        except KeyError:
            attr = node.attrib["class"]

        # Print one entry header: one word and its types like verb, noun, adj
        # One page has multiple entry headers
        # Also print a phrase entry's name and its types
        if "row entry-header" in attr:
            word = print_word_and_wtype(node, head)
            words.append(word)
            head += 1

        # Print pronounciations
        if attr == "row entry-attr":
            print_pron(node)

        # Print headword forms like verb tenses, noun plurals
        if attr == "row headword-row":
            print_forms(node)

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

    dict_name = "The Merriam-Webster Dictionary"
    console.print(f"\n{dict_name}", justify="right", style="bold")

    global res_word
    if words:
        res_word = words[0]


# --- Print spell check ---
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
                    console.print("[bold #3C8DAD]" + "\n" + w + ":")
                else:
                    console.print("  • " + w.strip())
