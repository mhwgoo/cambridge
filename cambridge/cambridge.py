import argparse
import time
import requests
from bs4 import BeautifulSoup


"""
Cambridge is a terminal version of Cambridge Dictionary. Its dictionary data comes from https://dictionary.cambridge.org.

Parsing takes less than 0.4 seconds.
Most of the time is spent on fetching webpage.
Total time is mostly between 0.5 to 3 seconds, occasionally 5 secs at most depending on network performance.
"""

DICT_BASE_URL = "https://dictionary.cambridge.org/dictionary/english/"
SPELLCHECK_BASE_URL = "https://dictionary.cambridge.org/spellcheck/english/?q="


def parse_args():
    parser = argparse.ArgumentParser(
        description="Terminal Version of Cambridge Dictionary"
    )
    parser.add_argument(
        "words",
        nargs="+",  # it makes -w input value in dict data structure even with only one word
        help="A word or a phrase you want to look up",
    )
    args = parser.parse_args()
    return args


def fetch(url, session):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/29.0.1547.62 Safari/537.36"
    }
    session.headers.update(headers)
    attempt = 0
    while True:
        if attempt == 3:
            logger.info("Maximum amount of retries reached")
        try:
            r = session.get(url)
            attempt += 1
        except requests.exceptions.ConnectTimeout:
            logger.error("Timed out during fetching %s. Retrying...", url)
            time.sleep(0.1)
        except requests.exceptions.ConnectionError:
            logger.error("%s terminated connection. Retrying...", url)
            time.sleep(0.1)
        except Exception:
            logger.exception("Error occured during fetching %s", url)
        else:
            return r


def parse_spellcheck(args, session):
    word = " ".join(args.words).upper()
    query_word = "+".join(args.words)
    url = SPELLCHECK_BASE_URL + query_word
    response = fetch(url, session)
    soup = BeautifulSoup(response.text, "lxml")
    content = soup.find("div", "hfl-s lt2b lmt-10 lmb-25 lp-s_r-20")
    print()
    console.print("[bold #3C8DAD on #DDDDDD]" + word)
    title = content.h1.text.upper().strip()
    console.print("[bold]" + "\n" + title)
    for ul in content.find_all("ul", "hul-u"):
        notice = ul.find_previous_sibling().text
        console.print("[bold #3C8DAD]" + "\n" + notice)
        for i in ul.find_all("li"):
            suggestion = replace_all(i.text)
            console.print("[#b2b2b2]" + "  • " + suggestion)


def parse_first_dict(response):
    soup = BeautifulSoup(response.text, "lxml")
    first_dict = soup.find("div", "pr dictionary")
    return first_dict


def parse_dict_blocks(response):
    first_dict = parse_first_dict(response)
    if first_dict.find(
        "div", ["pr entry-body__el", "entry-body__el clrd js-share-holder"]
    ):
        blocks = first_dict.find_all(
            "div", ["pr entry-body__el", "entry-body__el clrd js-share-holder"]
        )
    else:
        blocks = first_dict.find_all("div", "pr idiom-block")
    return blocks


# ----------parse dict head----------
def parse_head_title(title_block):
    if title_block.find("div", "di-title"):
        word = title_block.find("div", "di-title").text.upper()
        return word


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
        w_type = replace_all(w_type).upper()
    if head.find("div", "posgram dpos-g hdib lmr-5"):
        posgram = head.find("div", "posgram dpos-g hdib lmr-5")
        w_type = replace_all(posgram.text).upper()
    return w_type


def parse_head_pron(head):
    w_pron_uk = head.find("span", "uk dpron-i").find("span", "pron dpron")
    if w_pron_uk:
        w_pron_uk = replace_all(w_pron_uk.text)
    # In bs4, not found element returns None, not raise error, so try block is not right
    w_pron_us = head.find("span", "us dpron-i").find("span", "pron dpron")
    if w_pron_us:
        w_pron_us = replace_all(w_pron_us.text)
        console.print(
            "[bold]UK [/bold]" + w_pron_uk + "[bold] US [/bold]" + w_pron_us, end="  "
        )
    else:
        console.print("[bold]UK [/bold]" + w_pron_uk, end="  ")


def parse_head_tense(head):
    w_tense = replace_all(head.find("span", "irreg-infls dinfls").text)
    console.print("[bold]" + w_tense, end="  ")


def parse_head_domain(head):
    domain = replace_all(head.find("span", "domain ddomain").text.upper())
    console.print("[bold]" + domain, end="  ")


def parse_head_usage(head):
    if head.find("span", "lab dlab"):
        w_usage = replace_all(head.find("span", "lab dlab").text)
        console.print("[bold]" + w_usage, end="  ")
    if head.find_next_sibling("span", "lab dlab"):
        w_usage = replace_all(head.find_next_sibling("span", "lab dlab").text)
        console.print("[bold]" + w_usage, end="  ")


def parse_head_var(head):
    if head.find("span", "var dvar"):
        w_var = replace_all(head.find("span", "var dvar").text)
        console.print("[bold]" + w_var, end="  ")
    if head.find_next_sibling("span", "var dvar"):
        w_var = replace_all(head.find_next_sibling("span", "var dvar").text)
        console.print("[bold]" + w_var, end="  ")


def parse_head_spellvar(head):
    for i in head.find_all("span", "spellvar dspellvar"):
        spell_var = replace_all(i.text)
        console.print("[bold]" + spell_var, end="  ")


def parse_dict_head(block):
    head = block.find("div", "pos-header dpos-h")
    word = parse_head_title(block)
    if head:
        head = block.find("div", "pos-header dpos-h")
        w_type = parse_head_type(head)
        if not word:
            word = parse_head_title(head)
        if w_type:
            print()
            console.print("[bold #3C8DAD on #DDDDDD]" + word + " " + w_type)
        else:
            print()
            console.print("[bold #3C8DAD on #DDDDDD]" + word)

        if head.find("span", "uk dpron-i"):
            if head.find("span", "uk dpron-i").find("span", "pron dpron"):
                parse_head_pron(head)

        if head.find("span", "irreg-infls dinfls"):
            parse_head_tense(head)

        if head.find("span", "domain ddomain"):
            parse_head_domain(head)

        parse_head_usage(head)
        parse_head_var(head)

        if head.find("span", "spellvar dspellvar"):
            parse_head_spellvar(head)

        print()
        print()
    else:
        console.print("[bold #3C8DAD on #DDDDDD]" + word)


# ----------parse dict body----------
def parse_def_title(block):
    d_title = replace_all(block.find("h3", "dsense_h").text).upper()
    console.print("[bold #3C8DAD]" + "\n" + d_title)


def parse_ptitle(block):
    p_title = block.find("span", "phrase-title dphrase-title").text
    if block.find("span", "phrase-info dphrase-info"):
        phrase_info = "  - " + replace_all(
            block.find("span", "phrase-info dphrase-info").text
        )
        print(f"\n\033[1m  {p_title} {phrase_info}\033[0m")
    else:
        print(f"\n\033[1m  {p_title}\033[0m")


def parse_def_info(def_block):
    def_info = replace_all(def_block.find("span", "def-info ddef-info").text)
    if def_info == " ":
        def_into = ""
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
        print(usage + "\033[33m" + meaning_words + "\033[0m")
    else:
        meaning_words = replace_all(meaning_b.text)
        print("\033[33m" + meaning_words + "\033[0m")


def parse_pmeaning(def_block):
    meaning_b = def_block.find("div", "def ddef_d db")
    if meaning_b.find("span", "lab dlab"):
        usage_b = meaning_b.find("span", "lab dlab")
        usage = replace_all(usage_b.text)
        meaning_words = replace_all(meaning_b.text).split(usage)[-1]
        print("  " + usage + "\033[33m" + meaning_words + "\033[0m")
    else:
        meaning_words = replace_all(meaning_b.text)
        print("  " + "\033[33m" + meaning_words + "\033[0m")


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
            if e.find("span", "lab dlab"):
                lab = replace_all(e.find("span", "lab dlab").text)
                console.print(
                    "[#b2b2b2]"
                    + "  • "
                    + "[/#b2b2b2]"
                    + lab
                    + " "
                    + "[#b2b2b2]"
                    + example
                )
            elif e.find("span", "gram dgram"):
                gram = replace_all(e.find("span", "gram dgram").text)
                console.print(
                    "[#b2b2b2]"
                    + "  • "
                    + "[/#b2b2b2]"
                    + gram
                    + " "
                    + "[#b2b2b2]"
                    + example
                )
            elif e.find("span", "lu dlu"):
                lu = replace_all(e.find("span", "lu dlu").text)
                console.print(
                    "[#b2b2b2]"
                    + "  • "
                    + "[/#b2b2b2]"
                    + lu
                    + " "
                    + "[#b2b2b2]"
                    + example
                )
            else:
                console.print("[#b2b2b2]" + "  • " + example)


def parse_synonym(def_block):
    if def_block.find("div", "xref synonym hax dxref-w lmt-25"):
        s_block = def_block.find("div", "xref synonym hax dxref-w lmt-25")
    if def_block.find("div", "xref synonyms hax dxref-w lmt-25"):
        s_block = def_block.find("div", "xref synonyms hax dxref-w lmt-25")
    s_title = s_block.strong.text.upper()
    console.print("[bold #b2b2b2]" + "\n  " + s_title)
    for s in s_block.find_all(
        "div", ["item lc lc1 lpb-10 lpr-10", "item lc lc1 lc-xs6-12 lpb-10 lpr-10"]
    ):
        s = s.text
        console.print("[#b2b2b2]" + "  • " + s)


def parse_see_also(def_block):
    if def_block.find("div", "xref see_also hax dxref-w"):
        see_also_block = def_block.find("div", "xref see_also hax dxref-w")
    if def_block.find("div", "xref see_also hax dxref-w lmt-25"):
        see_also_block = def_block.find("div", "xref see_also hax dxref-w lmt-25")
    see_also = see_also_block.strong.text.upper()
    console.print("[bold #b2b2b2]" + "\n  " + see_also)
    for word in see_also_block.find_all("div", "item lc lc1 lpb-10 lpr-10"):
        word = word.text
        console.print("[#b2b2b2]" + "  • " + word)


def parse_compare(def_block):
    if def_block.find("div", "xref compare hax dxref-w lmt-25"):
        compare_block = def_block.find("div", "xref compare hax dxref-w lmt-25")
    if def_block.find("div", "xref compare hax dxref-w"):
        compare_block = def_block.find("div", "xref compare hax dxref-w")
    compare = compare_block.strong.text.upper()
    console.print("[bold #b2b2b2]" + "\n  " + compare)
    for word in compare_block.find_all(
        "div", ["item lc lc1 lpb-10 lpr-10", "item lc lc1 lc-xs6-12 lpb-10 lpr-10"]
    ):
        item = word.a.text
        usage = word.find("span", "x-lab dx-lab")
        if usage:
            usage = usage.text
            console.print("[#b2b2b2]" + "  • " + item + "[/#b2b2b2]" + usage)
        else:
            console.print("[#b2b2b2]" + "  • " + item)


def parse_usage_note(def_block):
    usage_block = def_block.find("div", "usagenote dusagenote daccord")
    usagenote = usage_block.h5.text
    console.print("[bold #b2b2b2]" + "\n  " + usagenote)
    for item in usage_block.find_all("li", "text"):
        item = item.text
        console.print("[#b2b2b2]" + "    " + item)


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
    if block.find("div", "xref idioms hax dxref-w lmt-25 lmb-25"):
        idiom_block = block.find("div", "xref idioms hax dxref-w lmt-25 lmb-25")
    idiom_title = idiom_block.h3.text.upper()
    console.print("[bold #b2b2b2]" + "\n" + idiom_title)
    for idiom in idiom_block.find_all(
        "div",
        [
            "item lc lc1 lpb-10 lpr-10",
            "item lc lc1 lc-xs6-12 lpb-10 lpr-10",
        ],
    ):
        idiom = idiom.text
        console.print("[#b2b2b2]" + "  • " + idiom)


def parse_phrasal_verb(block):
    if block.find("div", "xref phrasal_verbs hax dxref-w lmt-25 lmb-25"):
        pv_block = block.find("div", "xref phrasal_verbs hax dxref-w lmt-25 lmb-25")
    if block.find("div", "xref phrasal_verb hax dxref-w lmt-25 lmb-25"):
        pv_block = block.find("div", "xref phrasal_verb hax dxref-w lmt-25 lmb-25")
    pv_title = pv_block.h3.text.upper()
    console.print("[bold #b2b2b2]" + "\n" + pv_title)
    for pv in pv_block.find_all(
        "div",
        ["item lc lc1 lc-xs6-12 lpb-10 lpr-10", "item lc lc1 lpb-10 lpr-10"],
    ):
        pv = pv.text
        console.print("[#b2b2b2]" + "  • " + pv)


def parse_dict_body(block):
    for subblock in block.find_all("div", ["pr dsense", "pr dsense dsense-noh"]):
        if subblock.find("h3", "dsense_h"):
            parse_def_title(subblock)

        for child in subblock.find("div", "sense-body dsense_b").children:
            try:
                if child.attrs["class"] == ["def-block", "ddef_block"]:
                    parse_def(child)

                if (
                    child.attrs["class"]
                    == [
                        "pr",
                        "phrase-block",
                        "dphrase-block",
                        "lmb-25",
                    ]
                    or child.attrs["class"] == ["pr", "phrase-block", "dphrase-block"]
                ):
                    parse_ptitle(child)

                    for i in child.find_all("div", "def-block ddef_block"):
                        parse_def(i)
            except:
                pass

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


def parse_dict_name(response):
    first_dict = parse_first_dict(response)
    dict_info = replace_all(first_dict.small.text).replace("(", "").replace(")", "")
    dict_name = dict_info.split("©")[0]
    dict_name = dict_name.split("the")[-1]
    console.print("[#125D98]" + "\n\n" + dict_name + "\n", justify="right")


# ----------main----------


def main():
    try:
        args = parse_args()
        query_word = "-".join(args.words)
        url = DICT_BASE_URL + query_word
        with requests.Session() as session:
            response = fetch(url, session)
            if response.url == DICT_BASE_URL:
                parse_spellcheck(args, session)
            elif response.url != url and response.url != DICT_BASE_URL:
                response = fetch(response.url, session)
                for block in parse_dict_blocks(response):
                    parse_dict_head(block)
                    parse_dict_body(block)
                parse_dict_name(response)
            else:
                for block in parse_dict_blocks(response):
                    parse_dict_head(block)
                    parse_dict_body(block)
                parse_dict_name(response)
    except KeyboardInterrupt:
        print("\nStopped by user")


if __name__ == "__main__":
    from log import logger
    from utils import replace_all
    from console import console

    t1 = time.time()
    main()
    t2 = time.time()
    print(f"\nTIME TAKEN: {t2 - t1}")


else:
    from .log import logger
    from .utils import replace_all
    from .console import console
