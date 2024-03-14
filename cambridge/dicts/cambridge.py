import requests
import threading
import sys
import re
from ..console import c_print
from ..errors import ParsedNoneError, NoResultError, call_on_error
from ..log import logger
from ..utils import (
    make_a_soup,
    get_request_url,
    parse_response_url,
    replace_all,
    OP,
    DICT
)
from ..dicts import dict


CAMBRIDGE_URL = "https://dictionary.cambridge.org"
CAMBRIDGE_EN_SEARCH_URL = CAMBRIDGE_URL + "/search/direct/?datasetsearch=english&q="
CAMBRIDGE_CN_SEARCH_URL = CAMBRIDGE_URL + "/search/direct/?datasetsearch=english-chinese-simplified&q="

CAMBRIDGE_SPELLCHECK_URL = CAMBRIDGE_URL + "/spellcheck/english/?q="
CAMBRIDGE_SPELLCHECK_URL_CN = CAMBRIDGE_URL + "/spellcheck/english-chinese-simplified/?q="

# ----------Request Web Resource----------
def search_cambridge(con, cur, input_word, is_fresh=False, is_ch=False, no_suggestions=False):
    if is_ch:
        req_url = get_request_url(CAMBRIDGE_CN_SEARCH_URL, input_word, DICT.CAMBRIDGE.name)
    else:
        req_url = get_request_url(CAMBRIDGE_EN_SEARCH_URL, input_word, DICT.CAMBRIDGE.name)

    if not is_fresh:
        cached = dict.cache_run(con, cur, input_word, req_url, DICT.CAMBRIDGE.name)
        if not cached:
            fresh_run(con, cur, req_url, input_word, is_ch, no_suggestions)
    else:
        fresh_run(con, cur, req_url, input_word, is_ch, no_suggestions)


def fetch_cambridge(req_url, input_word, is_ch):
    """Get response url and response text for later parsing."""

    with requests.Session() as session:
        session.trust_env = False # not to use proxy
        res = dict.fetch(req_url, session)

        if "spellcheck" in res.url:
            logger.debug(f'{OP.NOT_FOUND.name} "{input_word}" in {DICT.CAMBRIDGE.name}')
            if is_ch:
                spell_req_url = get_request_url(CAMBRIDGE_SPELLCHECK_URL_CN, input_word, DICT.CAMBRIDGE.name)
            else:
                spell_req_url = get_request_url(CAMBRIDGE_SPELLCHECK_URL, input_word, DICT.CAMBRIDGE.name)

            spell_res = dict.fetch(spell_req_url, session)
            spell_res_url = spell_res.url
            spell_res_text = spell_res.text
            return False, (spell_res_url, spell_res_text)

        else:
            res_url = parse_response_url(res.url)
            res_text = res.text

            logger.debug(f'{OP.FOUND.name} "{input_word}" in {DICT.CAMBRIDGE.name} at {res_url}')
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

        parse_thread = threading.Thread(target=parse_and_print, args=(first_dict, res_url, True))
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
                print(NoResultError(DICT.CAMBRIDGE.name))
                sys.exit()

            for ul in nodes.find_all("ul", "hul-u"):
                if "We have these words with similar spellings or pronunciations:" in ul.find_previous_sibling().text:
                    for i in ul.find_all("li"):
                        sug = replace_all(i.text)
                        suggestions.append(sug)

            logger.debug(f"{OP.PRINTING.name} the parsed result of {spell_res_url}")
            dict.print_spellcheck(con, cur, input_word, suggestions, DICT.CAMBRIDGE.name, is_ch)


# ----------The Entry Point For Parse And Print----------

def parse_and_print(first_dict, res_url, new_line=False):
    """Parse and print different sections for the word."""

    logger.debug(f"{OP.PRINTING.name} the parsed result of {res_url}")

    attempt = 0
    while True:
        try:
            blocks = first_dict.find_all("div", ["pr entry-body__el", "entry-body__el clrd js-share-holder", "pr idiom-block"])
        except AttributeError as e:
            attempt = call_on_error(e, res_url, attempt, OP.RETRY_PARSING.name)
            continue
        else:
            if len(blocks) != 0:
                for block in blocks:
                    parse_dict_head(block)
                    parse_dict_body(block)
                # parse_dict_name(first_dict)
                if new_line:
                    print()
                return
            else:
                print(NoResultError(DICT.CAMBRIDGE.name))
                sys.exit()


def parse_first_dict(res_url, soup):
    """Parse the dict section of the page for the word."""

    attempt = 0
    logger.debug(f"{OP.PARSING.name} {res_url}")

    while True:
        first_dict = soup.find("div", "pr dictionary") or soup.find("div", "pr di superentry")
        if first_dict is None:
            attempt = call_on_error(ParsedNoneError(DICT.CAMBRIDGE.name, res_url), res_url, attempt, OP.RETRY_PARSING.name)
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

    if len(info) != 0:
        temp = [i.text for i in info]
        type = temp[0]
        text = " ".join(temp[1:])
        return (type, text)
    return None


def parse_head_type(head):
    anc = head.find("span", "anc-info-head danc-info-head")
    posgram = head.find("div", "posgram dpos-g hdib lmr-5")
    dpos = head.find("span", attrs={"title": "A word that describes an action, condition or experience."})

    w_type = ""
    if anc is not None:
        # e.g. "phrasal verb with sneak" superfluous
        # w_type = anc.text
        if dpos is not None:
            w_type += dpos.text
            dgram = dpos.find_next_sibling("span", "gram dgram")
            if dgram is not None:
                w_type += " " + dgram.text
        w_type = replace_all(w_type)
    elif posgram is not None:
        w_type = replace_all(posgram.text)
    return w_type


def print_pron(block, area):
    w_pron = block.find("span", "pron dpron")
    if w_pron is not None:
        w_pron_text = replace_all(w_pron.text).replace("/", "|")
        c_print(f"[bold]{area} [/bold]" + w_pron_text, end=" ")


def parse_head_pron(head):
    uk_dpron = head.find("span", "uk dpron-i")
    if uk_dpron is not None:
        print_pron(uk_dpron, "UK")

    us_dpron = head.find("span", "us dpron-i")
    if us_dpron is not None:
        print_pron(us_dpron, "US")


def parse_head_tense(block):
    sub_blocks = block.find_all("span", "inf-group dinfg")
    if len(sub_blocks) != 0:
        for index, sub in enumerate(sub_blocks):
            tenses = sub.find_all("b", "inf dinf")
            if len(tenses) != 0:
                for tense in tenses:
                    c_print("[bold]" + tense.text + "[/bold]", end=" ")
            if index == 0 and len(sub_blocks) > 1:
                print("|", end=" ")


def parse_head_domain(block):
    domain = replace_all(block.text)
    print(domain, end="  ")


def parse_head_var(head):
    var_dvar = head.find("span", "var dvar")
    if var_dvar is not None:
        w_var = replace_all(var_dvar.text)
        print(w_var, end="  ")

    var_dvar_sib = head.find_next_sibling("span", "var dvar")
    if var_dvar_sib is not None:
        w_var = replace_all(var_dvar_sib.text)
        print(w_var, end="  ")


def parse_head_spellvar(block):
    for i in block:
        spell_var = replace_all(i.text)
        print(spell_var, end="  ")


def parse_dict_head(block):
    head = block.find("div", "pos-header dpos-h")
    word = parse_head_title(block)
    info = parse_head_info(block)

    if head is not None:
        w_type = parse_head_type(head)

        if not word:
            word = parse_head_title(head)
        if w_type:
            w_type = w_type.replace(" or ", "/")
            c_print(f"\n[bold blue]{word}[/bold blue] [bold yellow]{w_type}[/bold yellow]")

        parse_head_pron(head)

        irreg = head.find("span", "irreg-infls dinfls")
        if irreg is not None:
            parse_head_tense(irreg)

        domain = head.find("span", "domain ddomain")
        if domain is not None:
            parse_head_domain(domain)

        parse_head_var(head)

        spellvar = head.find_all("span", "spellvar dspellvar")
        if len(spellvar) != 0:
            parse_head_spellvar(spellvar)

        print()

    else:
        c_print("[bold blue]" + word)
        if info:
            print(f"{info[0]} {info[1]}")


# ----------Parse Dict Body----------
def parse_def_title(block):
    d_title = replace_all(block.find("h3", "dsense_h").text)
    c_print("[red]" + "\n" + d_title.upper())

def parse_ptitle(block):
    p_title = block.find("span", "phrase-title dphrase-title").text
    p_info = block.find("span", "phrase-info dphrase-info")

    if p_info is not None:
        phrase_info = replace_all(p_info.text)
        print(f"\033[34;1m  {p_title}\033[0m \033[33;1m{phrase_info}\033[0m")
    else:
        print(f"\033[34;1m  {p_title}\033[0m")


def parse_def_info(def_block):
    """ def info tags like 'B1 [ C or U ]' """

    def_info = replace_all(def_block.find("span", "def-info ddef-info").text).replace(" or ", "/")
    return def_info


def print_meaning_lan(meaning_lan):
    if meaning_lan is not None:
        meaning_lan_words = meaning_lan.text.replace(";", "；").replace(",", "，")
        if not meaning_lan_words.startswith("（"):
            print(" ", end="")
        print("\033[34m" + meaning_lan_words + "\033[0m")
    else:
        print()


def print_meaning(meaning_b, usage_b, is_pmeaning):
    if is_pmeaning:
        print("  ", end="")

    if usage_b is not None:
        usage = replace_all(usage_b.text)
        meaning_words = replace_all(meaning_b.text).split(usage)[-1].replace(":", "")
        print("\033[34;1m: \033[0m" + "[" + usage + "]" + "\033[34m" + meaning_words + "\033[0m", end="")
    else:
        meaning_words = replace_all(meaning_b.text).replace(":", "")
        print("\033[34;1m: \033[0m" + "\033[34m" + meaning_words + "\033[0m", end="")


def parse_meaning(def_block, is_pmeaning=False):
    meaning_b = def_block.find("div", "def ddef_d db")
    usage_b = meaning_b.find("span", "lab dlab")

    print_meaning(meaning_b, usage_b, is_pmeaning)

    def_info = parse_def_info(def_block)
    if def_info:
        if not def_info.startswith("("):
            print(" [" + def_info + "]", end="")
        else:
            print(" " + def_info, end="")

    # Print the meaning's specific language translation if any
    meaning_lan = def_block.find("span", "trans dtrans dtrans-se break-cj")
    print_meaning_lan(meaning_lan)


def print_example_tag(tag_block):
    if tag_block is None:
        return

    tag = tag_block.text
    tag = replace_all(tag)
    print("[" + tag + "]", end= " ")


def parse_example(def_block, is_pexample=False):
    es = def_block.find_all("div", "examp dexamp")
    if len(es) == 0:
        return

    for e in es:
        result = e.find("span", "eg deg")
        if result is not None:
            example = replace_all(result.text)
        else:
            continue

        if is_pexample:
            print("  ", end="")

        example_lan = e.find("span", "trans dtrans dtrans-se hdb break-cj")
        if example_lan is not None:
            example_lan_sent = " " + example_lan.text.replace("。", "")
        else:
            example_lan_sent = ""

        c_print("[blue]" + "|" + "[/blue]", end="")

        dlab = e.find("span", "lab dlab")
        print_example_tag(dlab)

        dgram = e.find("span", "gram dgram")
        print_example_tag(dgram)

        dlu = e.find("span", "lu dlu")
        print_example_tag(dlu)

        c_print(f"[#757575]{example}{example_lan_sent}[/#757575]")


def print_synonym(block):
    s_title = block.strong.text.upper()
    c_print("[bold #757575]" + "\n  " + s_title)

    for s in block.find_all("div", ["item lc lc1 lpb-10 lpr-10", "item lc lc1 lc-xs6-12 lpb-10 lpr-10"]):
        s = s.text
        c_print("[#757575]" + "  • " + s)

    print()


def parse_synonym(block):
    s_block = block.find("div", re.compile("xref synonyms? hax dxref-w( lmt-25)?"))
    if s_block is not None:
        print_synonym(s_block)
    elif "synonym" in block.attrs["class"]:
        print_synonym(block)


def parse_see_also(def_block):
    see_also_block = def_block.find("div", re.compile("xref see_also hax dxref-w( lmt-25)?"))

    if see_also_block is not None:
        see_also = see_also_block.strong.text.upper()
        c_print("[bold #757575]" + "\n  " + see_also)

        for item in see_also_block.find_all("span", ["x-h dx-h", "x-p dx-p"]):
            c_print("[#757575]" + "  • " + item.text, end=" ")
            next_sibling = item.find_next_sibling("span")
            if next_sibling is not None:
                print(next_sibling.text)
            else:
                print()


def parse_compare(def_block):
    compare_block = def_block.find("div", re.compile("xref compare hax dxref-w( lmt-25)?"))

    if compare_block is not None:
        compare = compare_block.strong.text.upper()
        c_print("[bold #757575]" + "\n  " + compare)
        for word in compare_block.find_all("div", ["item lc lc1 lpb-10 lpr-10", "item lc lc1 lc-xs6-12 lpb-10 lpr-10"]):
            item = word.a.text
            c_print("[#757575]" + "  • " + item + "[/#757575]", end="")

            usage = word.find("span", "x-lab dx-lab")
            if usage:
                usage = usage.text
                print(usage, end="")

            print()


def parse_usage_note(def_block):
    usage_block = def_block.find("div", "usagenote dusagenote daccord")

    if usage_block is not None:
        usagenote = usage_block.h5.text
        c_print("[bold #757575]" + "\n  " + usagenote)
        for item in usage_block.find_all("li", "text"):
            item = item.text
            c_print("[#757575]" + "    " + item)


def parse_def(def_block):
    if "phrase-body" in def_block.parent.attrs["class"]:
        parse_meaning(def_block, True)
        parse_example(def_block, True)
    else:
        parse_meaning(def_block)
        parse_example(def_block)

    parse_synonym(def_block)
    parse_see_also(def_block)
    parse_compare(def_block)
    parse_usage_note(def_block)

def parse_idiom(block):
    idiom_block = block.find("div", re.compile("xref idioms? hax dxref-w lmt-25 lmb-25"))

    if idiom_block is not None:
        idiom_title = idiom_block.h3.text.upper()
        c_print("[bold #757575]" + "\n" + idiom_title)
        for idiom in idiom_block.find_all("div", ["item lc lc1 lpb-10 lpr-10", "item lc lc1 lc-xs6-12 lpb-10 lpr-10"]):
            idiom = idiom.text
            c_print("[#757575]" + "  • " + idiom)


def parse_sole_idiom(block):
    idiom_sole_meaning = block.find("div", "def ddef_d db")

    if idiom_sole_meaning is not None:
        print("\033[34m" + idiom_sole_meaning.text + "\033[0m")
    parse_example(block)
    parse_see_also(block)


def parse_phrasal_verb(block):
    pv_block = block.find("div", re.compile("xref phrasal_verbs? hax dxref-w lmt-25 lmb-25"))

    if pv_block is not None:
        pv_title = pv_block.h3.text.upper()
        c_print("[bold #757575]" + "\n" + pv_title)
        for pv in pv_block.find_all("div", ["item lc lc1 lc-xs6-12 lpb-10 lpr-10", "item lc lc1 lpb-10 lpr-10"]):
            pv = pv.text
            c_print("[#757575]" + "  • " + pv)


def parse_dict_body(block):
    subblocks = block.find_all("div", ["pr dsense", "pr dsense dsense-noh"])

    if len(subblocks) != 0:
        for subblock in subblocks:
            # Comment out because h3 block seems superfluous.
            # if subblock.find("h3", "dsense_h"):
            #     parse_def_title(subblock)

            sense = subblock.find("div", "sense-body dsense_b")
            if sense is not None:
                for child in sense.children:
                    try:
                        attr = child.attrs["class"]
                        if attr and attr == ["def-block", "ddef_block"]:
                            parse_def(child)

                        if attr and "synonym" in attr:
                            parse_synonym(child)

                        if attr and (attr == ["pr", "phrase-block", "dphrase-block", "lmb-25"] or attr == ["pr", "phrase-block", "dphrase-block"]):
                            parse_ptitle(child)

                            for i in child.find_all("div", "def-block ddef_block"):
                                parse_def(i)
                    except Exception:
                        pass

    else:
        idiom_sole_block = block.find("div", "idiom-block")
        if idiom_sole_block is not None:
            parse_sole_idiom(idiom_sole_block)

    parse_idiom(block)
    parse_phrasal_verb(block)


# ----------Parse Dict Name----------
def parse_dict_name(first_dict):
    if first_dict.small is not None:
        dict_info = replace_all(first_dict.small.text).strip("(").strip(")")
        dict_name = dict_info.split("©")[0]
        dict_name = dict_name.split("the")[-1]
    else:
        dict_name="Cambridge Dictionary"
    c_print(f"[#757575]{dict_name}", justify="right")
