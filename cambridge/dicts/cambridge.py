"""Parse and print cambridge dictionary."""

import requests
import threading
import sys
from ..console import console
from ..errors import ParsedNoneError, NoResultError, call_on_error
from ..settings import OP, DICTS
from ..log import logger
from ..utils import (
    make_a_soup,
    get_request_url,
    get_request_url_spellcheck,
    parse_response_url,
    replace_all,
)
from ..dicts import dict

CAMBRIDGE_URL = "https://dictionary.cambridge.org"
CAMBRIDGE_DICT_BASE_URL = CAMBRIDGE_URL + "/dictionary/english/"
CAMBRIDGE_SPELLCHECK_URL = CAMBRIDGE_URL + "/spellcheck/english/?q="

CAMBRIDGE_DICT_BASE_URL_CN = CAMBRIDGE_URL + "/dictionary/english-chinese-simplified/"
CAMBRIDGE_SPELLCHECK_URL_CN = CAMBRIDGE_URL + "/spellcheck/english-chinese-simplified/?q="
# CAMBRIDGE_DICT_BASE_URL_CN_TRADITIONAL = "https://dictionary.cambridge.org/dictionary/english-chinese-traditional/"
# CAMBRIDGE_SPELLCHECK_URL_CN_TRADITIONAL = CAMBRIDGE_URL + "/spellcheck/english-chinese-traditional/?q="


# ----------Request Web Resource----------
def search_cambridge(con, cur, input_word, is_fresh=False, is_ch=False, no_suggestions=False):
    if is_ch:
        req_url = get_request_url(CAMBRIDGE_DICT_BASE_URL_CN, input_word, DICTS.CAMBRIDGE.name)
    else:
        req_url = get_request_url(CAMBRIDGE_DICT_BASE_URL, input_word, DICTS.CAMBRIDGE.name)

    if not is_fresh:
        cached = dict.cache_run(con, cur, input_word, req_url, DICTS.CAMBRIDGE.name)
        if not cached:
            fresh_run(con, cur, req_url, input_word, is_ch, no_suggestions)
    else:
        fresh_run(con, cur, req_url, input_word, is_ch, no_suggestions)


def fetch_cambridge(req_url, input_word, is_ch):
    """Get response url and response text for later parsing."""

    with requests.Session() as session:
        session.trust_env = False   # not to use proxy
        res = dict.fetch(req_url, session)

        if res.url == CAMBRIDGE_DICT_BASE_URL or res.url == CAMBRIDGE_DICT_BASE_URL_CN:
            logger.debug(f'{OP.NOT_FOUND.name} "{input_word}" in {DICTS.CAMBRIDGE.name}')
            if is_ch:
                spell_req_url = get_request_url_spellcheck(CAMBRIDGE_SPELLCHECK_URL_CN, input_word)
            else:
                spell_req_url = get_request_url_spellcheck(CAMBRIDGE_SPELLCHECK_URL, input_word)

            spell_res = dict.fetch(spell_req_url, session)
            spell_res_url = spell_res.url
            spell_res_text = spell_res.text
            return False, (spell_res_url, spell_res_text)

        else:
            res_url = parse_response_url(res.url)
            res_text = res.text

            logger.debug(f'{OP.FOUND.name} "{input_word}" in {DICTS.CAMBRIDGE.name} at {res_url}')
            return True, (res_url, res_text)


def fresh_run(con, cur, req_url, input_word, is_ch, no_suggestions=False):
    """Print the result without cache."""

    result = fetch_cambridge(req_url, input_word, is_ch)
    found = result[0]

    if found:
        res_url, res_text = result[1]
        soup = make_a_soup(res_text)
        response_word = parse_response_word(soup)

        first_dict = parse_first_dict(res_url, soup)

        parse_thread = threading.Thread(target=parse_and_print, args=(first_dict, res_url))
        parse_thread.start()
        # parse_thread.join()

        dict.save(con, cur, input_word, response_word, res_url, str(first_dict))

    else:
        if no_suggestions:
            sys.exit(-1)
        else:
            spell_res_url, spell_res_text = result[1]

            logger.debug(f"{OP.PARSING.name} {spell_res_url}")
            soup = make_a_soup(spell_res_text)
            nodes = soup.find("div", "hfl-s lt2b lmt-10 lmb-25 lp-s_r-20")
            suggestions = []

            if not nodes:
                print(NoResultError(DICTS.CAMBRIDGE.name))
                sys.exit()

            for ul in nodes.find_all("ul", "hul-u"):
                if "We have these words with similar spellings or pronunciations:" in ul.find_previous_sibling().text:
                    for i in ul.find_all("li"):
                        sug = replace_all(i.text)
                        suggestions.append(sug)

            logger.debug(f"{OP.PRINTING.name} the parsed result of {spell_res_url}")
            dict.print_spellcheck(con, cur, input_word, suggestions, DICTS.CAMBRIDGE.name, is_ch)


# ----------The Entry Point For Parse And Print----------

def parse_and_print(first_dict, res_url):
    """Parse and print different sections for the word."""

    logger.debug(f"{OP.PRINTING.name} the parsed result of {res_url}")

    attempt = 0
    while True:
        try:
            blocks = first_dict.find_all(
                "div", ["pr entry-body__el", "entry-body__el clrd js-share-holder", "pr idiom-block"]
            )
        except AttributeError as e:
            attempt = call_on_error(e, res_url, attempt, OP.RETRY_PARSING.name)
            continue
        else:
            if blocks:
                for block in blocks:
                    parse_dict_head(block)
                    parse_dict_body(block)
                parse_dict_name(first_dict)
                return
            else:
                print(NoResultError(DICTS.CAMBRIDGE.name))
                sys.exit()

def parse_first_dict(res_url, soup):
    """Parse the dict section of the page for the word."""

    attempt = 0
    logger.debug(f"{OP.PARSING.name} {res_url}")

    while True:
        # first_dict = soup.find("div", "pr dictionary")
        first_dict = soup.find("div", "pr di superentry")
        if first_dict is None:
            attempt = call_on_error(ParsedNoneError(DICTS.CAMBRIDGE.name, res_url), res_url, attempt, OP.RETRY_PARSING.name)
            continue
        else:
            break

    return first_dict


# ----------Parse Response Word----------
def parse_response_word(soup):
    "Parse the response word from html head title tag."

    temp = soup.find("title").text.split("-")[0].strip()
    if "|" in temp:
        response_word = temp.split("|")[0].strip().lower()

    elif "in Simplified Chinese" in temp:
        response_word = temp.split("in Simplified Chinese")[0].strip().lower()
    else:
        response_word = temp.lower()

    return response_word


# ----------Parse Dict Head----------
# Compared to Webster, Cambridge is a bunch of deep layered html tags
# filled with unbearably messy class names.
# No clear pattern, somewhat irregular, sometimes you just need to
# tweak your codes for particular words and phrases for them to show.


def parse_head_title(block):
    word = block.find("div", "di-title").text
    return word


def parse_head_info(block):
    info = block.find_all("span", ["pos dpos", "lab dlab", "v dv lmr-0"])
    if info:
        temp = [i.text for i in info]
        type = temp[0]
        text = " ".join(temp[1:])
        return (type, text)
    return None


def parse_head_type(head):
    if head.find("span", "anc-info-head danc-info-head"):
        w_type = (
            head.find("span", "anc-info-head danc-info-head").text
            + head.find(
                "span",
                attrs={
                    "title": "A word that describes an action, condition or experience."
                },
            ).text
        )
        w_type = replace_all(w_type)
    elif head.find("div", "posgram dpos-g hdib lmr-5"):
        posgram = head.find("div", "posgram dpos-g hdib lmr-5")
        w_type = replace_all(posgram.text)
    else:
        w_type = ""
    return w_type


def parse_head_pron(head):
    w_pron_uk = head.find("span", "uk dpron-i").find("span", "pron dpron")
    if w_pron_uk:
        w_pron_uk = replace_all(w_pron_uk.text)
    # In bs4, not found element returns None, not raise error
    if head.find("span", "us dpron-i"):
        w_pron_us = head.find("span", "us dpron-i").find("span", "pron dpron")
        if w_pron_us:
            w_pron_us = replace_all(w_pron_us.text)
            console.print(
                "UK " + w_pron_uk + " US " + w_pron_us, end="  "
            )
        else:
            console.print("UK " + w_pron_uk, end="  ")


def parse_head_tense(head):
    w_tense = replace_all(head.find("span", "irreg-infls dinfls").text)
    console.print(w_tense, end="  ")


def parse_head_domain(head):
    domain = replace_all(head.find("span", "domain ddomain").text)
    console.print(domain, end="  ")


def parse_head_usage(head):
    head_usage = head.find("span", "lab dlab")

    # NOTE: <span class = "var dvar"> </span>, attrs["class"] returns a list
    if head_usage is not None and head_usage.parent.attrs["class"] != ["var", "dvar"]:
        w_usage = replace_all(head_usage.text)
        return w_usage

    head_usage_next = head.find_next_sibling("span", "lab dlab")
    if head_usage_next is not None and head_usage_next.parent.attrs["class"] != ["var", "dvar"]:
        w_usage_next= replace_all(head_usage_next.text)
        return w_usage_next

    return ""


def parse_head_var(head):
    if head.find("span", "var dvar"):
        w_var = replace_all(head.find("span", "var dvar").text)
        console.print(w_var, end="  ")
    if head.find_next_sibling("span", "var dvar"):
        w_var = replace_all(head.find_next_sibling("span", "var dvar").text)
        console.print(w_var, end="  ")


def parse_head_spellvar(head):
    for i in head.find_all("span", "spellvar dspellvar"):
        spell_var = replace_all(i.text)
        console.print(spell_var, end="  ")


def parse_dict_head(block):
    head = block.find("div", "pos-header dpos-h")
    word = parse_head_title(block)
    info = parse_head_info(block)

    if head:
        head = block.find("div", "pos-header dpos-h")
        w_type = parse_head_type(head)
        usage = parse_head_usage(head)

        if not word:
            word = parse_head_title(head)
        if w_type:
            console.print(
                f"\n[bold #0A1B27 on #F4f4f4]{word}[/bold #0A1B27 on #F4f4f4]  {w_type} {usage}"
            )
        if head.find("span", "uk dpron-i"):
            if head.find("span", "uk dpron-i").find("span", "pron dpron"):
                parse_head_pron(head)

        if head.find("span", "irreg-infls dinfls"):
            parse_head_tense(head)

        if head.find("span", "domain ddomain"):
            parse_head_domain(head)

        parse_head_var(head)

        if head.find("span", "spellvar dspellvar"):
            parse_head_spellvar(head)

        print()
    else:
        console.print("[bold #0A1B27 on #F4F4F4]" + word)
        if info:
            console.print(f"{info[0]} {info[1]}")


# ----------Parse Dict Body----------
def parse_def_title(block):
    d_title = replace_all(block.find("h3", "dsense_h").text)
    console.print("[#ff8c00]" + "\n" + d_title)


def parse_ptitle(block):
    p_title = block.find("span", "phrase-title dphrase-title").text
    if block.find("span", "phrase-info dphrase-info"):
        phrase_info = replace_all(
            block.find("span", "phrase-info dphrase-info").text
        )
        print(f"\n\033[1m  {p_title}\33[0m {phrase_info}")
    else:
        print(f"\n\033[1m  {p_title}\033[0m")


def parse_def_info(def_block):
    def_info = replace_all(def_block.find("span", "def-info ddef-info").text)
    if def_info:
        if "phrase-body" in def_block.parent.attrs["class"]:
            print("  " + "\033[1m" + def_info + " " + "\033[0m", end="")
        else:
            print(def_info + " ", end="")


def parse_meaning(def_block):
    meaning_b = def_block.find("div", "def ddef_d db")
    if meaning_b.find("span", "lab dlab"):
        usage_b = meaning_b.find("span", "lab dlab")
        usage = replace_all(usage_b.text)
        meaning_words = replace_all(meaning_b.text).split(usage)[-1]
        print(usage + "\033[34m" + meaning_words + "\033[0m")
    else:
        meaning_words = replace_all(meaning_b.text)
        print("\033[34m" + meaning_words + "\033[0m")

    # Print the meaning's specific language translation if any
    meaning_lan = def_block.find("span", "trans dtrans dtrans-se break-cj")
    if meaning_lan:
        meaning_lan_words = meaning_lan.text
        print(meaning_lan_words)


def parse_pmeaning(def_block):
    meaning_b = def_block.find("div", "def ddef_d db")
    if meaning_b.find("span", "lab dlab"):
        usage_b = meaning_b.find("span", "lab dlab")
        usage = replace_all(usage_b.text)
        meaning_words = replace_all(meaning_b.text).split(usage)[-1]
        print("  " + usage + "\033[34m" + meaning_words + "\033[0m")
    else:
        meaning_words = replace_all(meaning_b.text)
        print("  " + "\033[34m" + meaning_words + "\033[0m")

    # Print the meaning's specific language translation if any
    meaning_lan = def_block.find("span", "trans dtrans dtrans-se break-cj")
    if meaning_lan:
        meaning_lan_words = meaning_lan.text
        print("  " + meaning_lan_words)


def parse_example(def_block):
    # NOTE:
    # suppose the first "if" has already run
    # and, the second is also "if", rather than "elif"
    # then, codes under "else" will also be run
    # meaning two cases took effect at the same time, which is not wanted
    # so, for exclusive cases, you can't write two "ifs" and one "else"
    # it should be one "if", one "elif", and one "else"
    # or three "ifs"
    for e in def_block.find_all("div", "examp dexamp"):
        if e is not None:
            example = replace_all(e.find("span", "eg deg").text)

            # Print the exmaple's specific language translation if any
            example_lan = e.find("span", "trans dtrans dtrans-se hdb break-cj")
            if example_lan is not None:
                example_lan_sent = example_lan.text
            else:
                example_lan_sent = ""

            if e.find("span", "lab dlab"):
                lab = replace_all(e.find("span", "lab dlab").text)
                console.print(
                    "[#757575]"
                    + "  • "
                    + "[/#757575]"
                    + lab
                    + " "
                    + "[#757575]"
                    + example
                    + " "
                    + example_lan_sent
                )
            elif e.find("span", "gram dgram"):
                gram = replace_all(e.find("span", "gram dgram").text)
                console.print(
                    "[#757575]"
                    + "  • "
                    + "[/#757575]"
                    + gram
                    + " "
                    + "[#757575]"
                    + example
                    + " "
                    + example_lan_sent
                )
            elif e.find("span", "lu dlu"):
                lu = replace_all(e.find("span", "lu dlu").text)
                console.print(
                    "[#757575]"
                    + "  • "
                    + "[/#757575]"
                    + lu
                    + " "
                    + "[#757575]"
                    + example
                    + " "
                    + example_lan_sent
                )
            else:
                console.print("[#757575]" + "  • " + example + " " + example_lan_sent)


def parse_synonym(def_block):
    if def_block.find("div", "xref synonym hax dxref-w lmt-25"):
        s_block = def_block.find("div", "xref synonym hax dxref-w lmt-25")
    else:
        s_block = def_block.find("div", "xref synonyms hax dxref-w lmt-25")

    if s_block is not None:
        s_title = s_block.strong.text.upper()
        console.print("[bold #757575]" + "\n  " + s_title)
        for s in s_block.find_all(
                "div", ["item lc lc1 lpb-10 lpr-10", "item lc lc1 lc-xs6-12 lpb-10 lpr-10"]
        ):
            s = s.text
            console.print("[#757575]" + "  • " + s)


def parse_see_also(def_block):
    if def_block.find("div", "xref see_also hax dxref-w"):
        see_also_block = def_block.find("div", "xref see_also hax dxref-w")
    elif def_block.find("div", "xref see_also hax dxref-w lmt-25"):
        see_also_block = def_block.find("div", "xref see_also hax dxref-w lmt-25")
    else:
        return
    see_also = see_also_block.strong.text.upper()
    console.print("[bold]" + "\n  " + see_also)
    items = see_also_block.find_all("span", ["x-h dx-h", "x-p dx-p"])
    for item in items:
        console.print("[#757575]  " + item.text, end = " ")
    modifiers = see_also_block.find_all("span", "x-pos dx-pos")
    for mod in modifiers:
        console.print(mod.text, end = " ")

    print()


def parse_compare(def_block):
    if def_block.find("div", "xref compare hax dxref-w lmt-25"):
        compare_block = def_block.find("div", "xref compare hax dxref-w lmt-25")
    else:
        compare_block = def_block.find("div", "xref compare hax dxref-w")

    if compare_block is not None:
        compare = compare_block.strong.text.upper()
        console.print("[bold #757575]" + "\n  " + compare)
        for word in compare_block.find_all(
            "div", ["item lc lc1 lpb-10 lpr-10", "item lc lc1 lc-xs6-12 lpb-10 lpr-10"]
        ):
            item = word.a.text
            usage = word.find("span", "x-lab dx-lab")
            if usage:
                usage = usage.text
                console.print("[#757575]" + "  • " + item + "[/#757575]" + usage)
            else:
                console.print("[#757575]" + "  • " + item)


def parse_usage_note(def_block):
    usage_block = def_block.find("div", "usagenote dusagenote daccord")
    usagenote = usage_block.h5.text
    console.print("[bold #757575]" + "\n  " + usagenote)
    for item in usage_block.find_all("li", "text"):
        item = item.text
        console.print("[#757575]" + "    " + item)


def parse_def(def_block):
    parse_def_info(def_block)
    if "phrase-body" in def_block.parent.attrs["class"]:
        parse_pmeaning(def_block)
    else:
        parse_meaning(def_block)
    parse_example(def_block)

    if def_block.find(
        "div", ["xref synonym hax dxref-w lmt-25", "xref synonyms hax dxref-w lmt-25"]
    ):
        parse_synonym(def_block)
    if def_block.find(
        "div", ["xref see_also hax dxref-w", "xref see_also hax dxref-w lmt-25"]
    ):
        parse_see_also(def_block)
    if def_block.find(
        "div", ["xref compare hax dxref-w lmt-25", "xref compare hax dxref-w"]
    ):
        parse_compare(def_block)
    if def_block.find("div", "usagenote dusagenote daccord"):
        parse_usage_note(def_block)


def parse_idiom(block):
    if block.find("div", "xref idiom hax dxref-w lmt-25 lmb-25"):
        idiom_block = block.find("div", "xref idiom hax dxref-w lmt-25 lmb-25")
    else:
        idiom_block = block.find("div", "xref idioms hax dxref-w lmt-25 lmb-25")

    if idiom_block is not None:
        idiom_title = idiom_block.h3.text.upper()
        console.print("[bold #757575]" + "\n" + idiom_title)
        for idiom in idiom_block.find_all(
            "div",
            [
                "item lc lc1 lpb-10 lpr-10",
                "item lc lc1 lc-xs6-12 lpb-10 lpr-10",
            ],
        ):
            idiom = idiom.text
            console.print("[#757575]" + "  • " + idiom)


def parse_sole_idiom(block):
    idiom_sole_meaning = block.find("div", "def ddef_d db")
    if idiom_sole_meaning is not None:
        print("\033[34m" + idiom_sole_meaning.text + "\033[0m")
    parse_example(block)
    parse_see_also(block)


def parse_phrasal_verb(block):
    if block.find("div", "xref phrasal_verbs hax dxref-w lmt-25 lmb-25"):
        pv_block = block.find("div", "xref phrasal_verbs hax dxref-w lmt-25 lmb-25")
    else:
        pv_block = block.find("div", "xref phrasal_verb hax dxref-w lmt-25 lmb-25")

    if pv_block is not None:
        pv_title = pv_block.h3.text.upper()
        console.print("[bold #757575]" + "\n" + pv_title)
        for pv in pv_block.find_all(
            "div",
            ["item lc lc1 lc-xs6-12 lpb-10 lpr-10", "item lc lc1 lpb-10 lpr-10"],
        ):
            pv = pv.text
            console.print("[#757575]" + "  • " + pv)


def parse_dict_body(block):
    subblocks = block.find_all("div", ["pr dsense", "pr dsense dsense-noh"])

    if subblocks:
        for subblock in subblocks:
            if subblock.find("h3", "dsense_h"):
                parse_def_title(subblock)

            for child in subblock.find("div", "sense-body dsense_b").children:
                try:
                    if child.attrs["class"] == ["def-block", "ddef_block"]:
                        parse_def(child)

                    if child.attrs["class"] == [
                        "pr",
                        "phrase-block",
                        "dphrase-block",
                        "lmb-25",
                    ] or child.attrs["class"] == ["pr", "phrase-block", "dphrase-block"]:
                        parse_ptitle(child)

                        for i in child.find_all("div", "def-block ddef_block"):
                            parse_def(i)
                except Exception:
                    pass

    else:
        if block.find("div", "idiom-block"):
            idiom_sole_block = block.find("div", "idiom-block")
            parse_sole_idiom(idiom_sole_block)

    if block.find(
        "div",
        [
            "xref idiom hax dxref-w lmt-25 lmb-25",
            "xref idioms hax dxref-w lmt-25 lmb-25",
        ],
    ):
        parse_idiom(block)

    if block.find(
        "div",
        [
            "xref phrasal_verbs hax dxref-w lmt-25 lmb-25",
            "xref phrasal_verb hax dxref-w lmt-25 lmb-25",
        ],
    ):
        parse_phrasal_verb(block)


# ----------Parse Dict Name----------
def parse_dict_name(first_dict):
    dict_info = replace_all(first_dict.small.text).strip("(").strip(")")
    dict_name = dict_info.split("©")[0]
    dict_name = dict_name.split("the")[-1]
    console.print(f"[#757575]{dict_name}", justify="right")
