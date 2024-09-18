import sys
import re
from bs4 import BeautifulSoup
import asyncio

from .console import c_print
from .log import logger
from .utils import fetch, get_request_url, parse_response_url, replace_all, OP, DICT, has_tool, get_suggestion, get_suggestion_by_fzf, cancel_on_error, quit_on_no_result, cancel_on_error_without_retry
from .cache import check_cache, save_to_cache, get_cache
from . import webster


CAMBRIDGE_URL = "https://dictionary.cambridge.org"
CAMBRIDGE_EN_SEARCH_URL = CAMBRIDGE_URL + "/search/direct/?datasetsearch=english&q="
CAMBRIDGE_CN_SEARCH_URL = CAMBRIDGE_URL + "/search/direct/?datasetsearch=english-chinese-simplified&q="

CAMBRIDGE_SPELLCHECK_URL = CAMBRIDGE_URL + "/spellcheck/english/?q="
CAMBRIDGE_SPELLCHECK_URL_CN = CAMBRIDGE_URL + "/spellcheck/english-chinese-simplified/?q="


async def search_cambridge(session, input_word, is_fresh=False, is_ch=False, no_suggestions=False, req_url=None):
    if req_url is None:
        url = CAMBRIDGE_CN_SEARCH_URL if is_ch else CAMBRIDGE_EN_SEARCH_URL
        req_url = get_request_url(url, input_word, DICT.CAMBRIDGE.name)

    if is_fresh:
        await fresh_run(session, input_word, is_ch, no_suggestions, req_url)
    else:
        res_url = await check_cache(input_word, req_url)
        if res_url is None:
            logger.debug(f'{OP.NOT_FOUND.name} "{input_word}" in cache')
            await fresh_run(session, input_word, is_ch, no_suggestions, req_url)
        elif DICT.CAMBRIDGE.name.lower() not in res_url:
            await webster.cache_run(res_url)
        else:
            await cache_run(res_url)


async def cache_run(res_url_from_cache):
    res_word, res_text = await get_cache(res_url_from_cache)
    logger.debug(f'{OP.FOUND.name} "{res_word}" from {DICT.CAMBRIDGE.name} in cache')
    logger.debug(f"{OP.PARSING.name} {res_url_from_cache}")

    soup = BeautifulSoup(res_text, "lxml")
    first_dict = soup.find("div", "pr dictionary") or soup.find("div", "pr di superentry")

    logger.debug(f"{OP.PRINTING.name} the parsed result of {res_url_from_cache}")
    blocks = first_dict.find_all("div", ["pr entry-body__el", "entry-body__el clrd js-share-holder", "pr idiom-block"]) # type: ignore
    for block in blocks:
        parse_dict_head(block)
        parse_dict_body(block)
    c_print(f'\n#[#757575]{OP.FOUND.name} "{res_word}" from {DICT.CAMBRIDGE.name} in cache. You can add "-f -w" to fetch the {DICT.MERRIAM_WEBSTER.name} dictionary')


async def fresh_run(session, input_word, is_ch, no_suggestions, req_url):
        response = await fetch(session, req_url)
        res_url = str(response.real_url)

        if "spellcheck" in res_url:
            logger.debug(f'{OP.NOT_FOUND.name} "{input_word}" at {req_url}')

            if no_suggestions:
                sys.exit(-1)

            spell_base_url = CAMBRIDGE_SPELLCHECK_URL_CN if is_ch else CAMBRIDGE_SPELLCHECK_URL
            spell_req_url = get_request_url(spell_base_url, input_word, DICT.CAMBRIDGE.name)

            spell_res = await fetch(session, spell_req_url)
            spell_res_text = None
            attempt = 0
            while True:
                try:
                    spell_res_text = await spell_res.text()
                except asyncio.TimeoutError as error:
                    attempt = cancel_on_error(spell_req_url, error, attempt, OP.FETCHING.name)
                    continue
                except Exception as error:
                    cancel_on_error_without_retry(spell_req_url, error, OP.FETCHING.name)
                    break
                else:
                    break

            if spell_res_text is not None:
                logger.debug(f"{OP.PARSING.name} out suggestions at {spell_res.url}")
                soup = BeautifulSoup(spell_res_text, "lxml")
                node = soup.find("div", "hfl-s lt2b lmt-10 lmb-25 lp-s_r-20")
                suggestions = []

                if not node:
                    quit_on_no_result(DICT.CAMBRIDGE.name, is_spellcheck=True)

                for ul in node.find_all("ul", "hul-u"): # type: ignore
                    if "We have these words with similar spellings or pronunciations:" in ul.find_previous_sibling().text:
                        for i in ul.find_all("li"):
                            sug = replace_all(i.text)
                            suggestions.append(sug)

                logger.debug(f"{OP.PRINTING.name} out suggestions at {spell_res.url}")
                select_word = get_suggestion_by_fzf(suggestions, DICT.CAMBRIDGE.name) if has_tool("fzf") else get_suggestion(suggestions, DICT.CAMBRIDGE.name)
                if select_word == "":
                    logger.debug(f'{OP.SWITCHED.name} to {DICT.MERRIAM_WEBSTER.name}')
                    await webster.search_webster(session, input_word, True, no_suggestions, None)
                else:
                    logger.debug(f'{OP.SELECTED.name} "{select_word}"')
                    await search_cambridge(session, select_word, False, False, no_suggestions, None)

        else:
            res_url = parse_response_url(res_url)
            res_text = None
            attempt = 0
            while True:
                try:
                    res_text = await response.text()
                except asyncio.TimeoutError as error:
                    attempt = cancel_on_error(req_url, error, attempt, OP.FETCHING.name)
                    continue
                # There is also a scenario that in the process of cancelling, while is still looping, leading to run coroutine with a closed session.
                # If session is closed, and you go on connecting, ClientConnectionError will be throwed.
                except Exception as error:
                    cancel_on_error_without_retry(req_url, error, OP.FETCHING.name)
                    break
                else:
                    break

            if res_text is not None:
                soup = BeautifulSoup(res_text, "lxml")
                first_dict = soup.find("div", "pr dictionary") or soup.find("div", "pr di superentry")
                if first_dict is None:
                    quit_on_no_result(DICT.CAMBRIDGE.name, is_spellcheck=False)

                logger.debug(f'{OP.FOUND.name} "{input_word}" in {DICT.CAMBRIDGE.name} at {req_url}')
                logger.debug(f"{OP.PARSING.name} {req_url}")
                blocks = first_dict.find_all("div", ["pr entry-body__el", "entry-body__el clrd js-share-holder", "pr idiom-block"]) # type: ignore
                if len(blocks) == 0:
                    quit_on_no_result(DICT.CAMBRIDGE.name, is_spellcheck=False)
                else:
                    logger.debug(f"{OP.PRINTING.name} the parsed result of {req_url}")
                    for block in blocks:
                        parse_dict_head(block)
                        parse_dict_body(block)

                    print()

                    hword = soup.find("b", "tb ttn").text
                    await save_to_cache(input_word, hword, res_url, str(first_dict))


def parse_dict_head(block):
    head = block.find("div", "pos-header dpos-h")
    word_block = block.find("div", "di-title") or head.find("div", "di-title")
    hword = word_block.text

    if head is None:
        c_print("#[bold blue]" + hword, end="")

        info = block.find_all("span", ["pos dpos", "lab dlab", "v dv lmr-0"])
        if len(info) != 0:
            temp = [i.text for i in info]
            type = temp[0]
            text = " ".join(temp[1:])
            print(f" {type} {text}")
        else:
            print()

    else:
        vars = head.find_all("span", "var dvar")
        spellvar = head.find("span", "spellvar dspellvar")
        irreg = head.find("span", "irreg-infls dinfls")
        domain = head.find("span", "domain ddomain")

        dlab = None
        lab = head.find("span", "lab dlab")
        if lab is not None:
            lab_parent = head.find("span", "lab dlab").find_parent()
            if lab_parent.has_attr('class') and lab_parent['class'][0] == "pos-header":
                dlab = lab

        w_type = ""
        if head.find("span", "anc-info-head danc-info-head") is not None:
            dpos = head.find("span", attrs={"title": "A word that describes an action, condition or experience."})
            if dpos is not None:
                w_type += dpos.text
                dgram = dpos.find_next_sibling("span", "gram dgram")
                if dgram is not None:
                    w_type += " " + dgram.text
            w_type = w_type.strip("\n").strip().replace(" or ", "/")
            end = " " if irreg is not None else "\n"
            c_print(f"\n#[bold blue]{hword}#[/bold blue] #[bold yellow]{w_type}#[/bold yellow]", end=end)

        elif head.find("div", "posgram dpos-g hdib lmr-5") is not None:
            posgram = head.find("div", "posgram dpos-g hdib lmr-5")
            w_type = posgram.text.strip("\n").strip().replace(" or ", "/")
            next_sibling = posgram.find_next_sibling()
            if next_sibling is None:
                end = ""
            elif next_sibling is not None and next_sibling.has_attr('class') and next_sibling['class'][0] == "lml--5":
                end = "  "
            elif len(vars) > 0 or spellvar is not None or domain is not None or dlab is not None or irreg is not None:
                end = "  "
            else:
                end = "\n"
            c_print(f"\n#[bold blue]{hword}#[/bold blue] #[bold yellow]{w_type}#[/bold yellow]", end=end)

        if domain is not None:
            print(domain.text.strip("\n").strip(), end="  ")

        if dlab is not None:
            next_sibling = dlab.find_next_sibling()
            end = "  " if ((next_sibling is not None and next_sibling.has_attr('class')) or len(vars) > 0 or irreg is not None) else "\n"
            print(dlab.text.strip("\n").strip(), end=end)

        if len(vars) > 0:
            for var in vars:
                next_sibling = var.find_next_sibling()
                end = "  " if ((next_sibling is not None and next_sibling.has_attr('class')) or irreg is not None) else "\n"
                print(var.text.replace("\n", "").replace("Your browser doesn't support HTML5 audio", " ").replace("/", "|").strip(), end=end)

        if spellvar is not None:
            next_sibling = spellvar.find_next_sibling()
            end = "  " if next_sibling is not None and next_sibling.has_attr('class') else "\n"
            print(spellvar.text.strip("\n").strip(), end=end)

        if irreg is not None:
            infgroups = irreg.find_all("span", "inf-group dinfg")
            if not infgroups:
                print(irreg.text.strip("\n").strip())
            else:
                # intentionally leave out pronunciations of the plural form:
                # e.g. cortex: uk  /ˈkɔː.tɪ.siːz/ us  /ˈkɔːr.tɪ.siːz/
                # e.g. vortex: uk  /-tɪ.siːz/ us  /-tə-/
                for index, infgroup in enumerate(infgroups):
                    infdlab = infgroup.find("span", "lab dlab")
                    if infdlab is not None:
                        previous_sibling = infdlab.find_previous_sibling()
                        if previous_sibling is not None:
                            c_print(f"#[bold] {previous_sibling.text}#[/bold]", end=" or ")

                        print(infdlab.text, end="")

                        next_sibling = infdlab.find_next_sibling()
                        if next_sibling is not None:
                            c_print(f"#[bold] {next_sibling.text}#[/bold]", end="")

                    else:
                        b = infgroup.find("b")
                        if b is not None:
                            next = b.find_next_sibling()
                            end = " or " if next is not None else ""
                            c_print(f"#[bold]{b.text}#[/bold]", end=end)
                            if next is not None and next.has_attr('class') and next['class'][0] == "inf":
                                c_print(f"#[bold]{next.text}#[/bold]", end="")

                    if index != len(infgroups) - 1:
                        print(" | ", end="")

                print()


        prons = head.find_all("span", "pron dpron")
        if len(prons) != 0:
            for pron in prons:
                parent = pron.find_parent()
                if parent.find_parent()['class'][0] == "pos-header":
                    pron_text = pron.text.strip("\n").strip().replace("/", "|")
                    area = parent.find("span", "region dreg")
                    area_text = area.text if area is not None else ""
                    end= "" if parent.find_next_sibling() is None else " "
                    c_print(f"#[bold]{area_text} #[/bold]" + pron_text, end=end)
        print()


def parse_def_title(block):
    d_title = replace_all(block.find("h3", "dsense_h").text)
    c_print("#[red]" + "\n" + d_title.upper())


def parse_ptitle(block):
    p_title = block.find("span", "phrase-title dphrase-title").text
    p_info = block.find("span", "phrase-info dphrase-info")

    if p_info is not None:
        phrase_info = replace_all(p_info.text)
        print(f"\033[34;1m  {p_title}\033[0m \033[33;1m{phrase_info}\033[0m")
    else:
        print(f"\033[34;1m  {p_title}\033[0m")


def parse_meaning(def_block, is_pmeaning=False):
    if is_pmeaning:
        print("  ", end="")

    meaning_b = def_block.find("div", "def ddef_d db")
    usage_b = meaning_b.find("span", "lab dlab")
    if usage_b is not None:
        usage = replace_all(usage_b.text)
        meaning_words = replace_all(meaning_b.text).split(usage)[-1]
        if meaning_words[-1] == ":":
            meaning_words = meaning_words[ : -1]
        print("\033[34;1m: \033[0m" + "[" + usage + "] " + "\033[34m" + meaning_words.strip() + "\033[0m", end="")
    else:
        meaning_words = replace_all(meaning_b.text)
        if meaning_words[-1] == ":":
            meaning_words = meaning_words[ : -1]

        print("\033[34;1m: \033[0m" + "\033[34m" + meaning_words.strip() + "\033[0m", end="")

    # e.g. def info tags like 'B1 [ C or U ]'
    def_info = replace_all(def_block.find("span", "def-info ddef-info").text).replace(" or ", "/")
    if def_info:
        if not def_info.startswith("("):
            print(" [" + def_info + "]", end="")
        else:
            print(" " + def_info, end="")

    # print the meaning's specific language translation if any
    meaning_lan = def_block.find("span", "trans dtrans dtrans-se break-cj")
    if meaning_lan is not None:
        meaning_lan_words = meaning_lan.text.replace(";", "；").replace(",", "，")
        if not meaning_lan_words.startswith("（"):
            print(" ", end="")
        print("\033[34m" + meaning_lan_words + "\033[0m")
    else:
        print()


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

        c_print("#[blue]" + "|" + "#[/blue]", end="")

        dlab = e.find("span", "lab dlab")
        print_example_tag(dlab)

        dgram = e.find("span", "gram dgram")
        print_example_tag(dgram)

        dlu = e.find("span", "lu dlu")
        print_example_tag(dlu)

        c_print(f"#[#757575]{example}{example_lan_sent}#[/#757575]")


def print_tag(node):
    for i in node.find_all("span"):
        has_class = i.has_attr("class")
        parent = i.find_parent()
        parent_has_class = parent.has_attr("class")

        if has_class and i.attrs["class"] == ['x-h', 'dx-h']:
            c_print("#[#757575]" + "  • " + i.text, end="")
        elif has_class and i.attrs["class"] ==  ['x-p', 'dx-p']:
            c_print("#[#757575]" + "  • " + i.text, end="")
        elif has_class and i.attrs["class"] == ['x-lab', 'dx-lab']:
            c_print("#[#757575]" + " [" + i.text + "]", end="")
        elif has_class and i.attrs["class"] == ['x-pos', 'dx-pos']:
            print(" " + i.text, end="")
        elif parent_has_class and parent.attrs["class"] == ['x-h', 'dx-h']:
            continue
        elif parent_has_class and parent.attrs["class"] == ['x-p', 'dx-p']:
            continue
        elif parent_has_class and parent.attrs["class"] == ['x-lab', 'dx-lab']:
            continue
        else:
            c_print("#[#757575]" + " " + i.text, end="")
    print()


def print_synonym(block):
    s_title = block.strong.text.upper()
    c_print("#[bold #757575]" + "\n" + s_title)

    for item in block.find_all("div", ["item lc lc1 lpb-10 lpr-10", "item lc lc1 lc-xs6-12 lpb-10 lpr-10"]):
        print_tag(item)


def parse_synonym(block):
    s_block = block.find("div", re.compile("xref synonyms? hax dxref-w( lmt-25)?"))
    if s_block is not None:
        print_synonym(s_block)
    elif "synonym" in block.attrs["class"]:
        print_synonym(block)


def parse_see_also_lmb(def_block):
    see_also_block = def_block.find("div", "xref see_also hax dxref-w lmt-25 lmb-25")
    if see_also_block is not None:
        see_also = see_also_block.strong.text.upper()
        c_print("#[bold #757575]" + "\n" + see_also)
        for item in see_also_block.find_all("div", ["item lc lc1 lpb-10 lpr-10", "item lc lc1 lc-xs6-12 lpb-10 lpr-10"]):
            print_tag(item)


def parse_see_also(def_block):
    see_also_block = def_block.find("div", re.compile("xref see_also hax dxref-w( lmt-25)?"))
    if see_also_block is not None:
        see_also = see_also_block.strong.text.upper()
        c_print("#[bold #757575]" + "\n" + see_also)
        for item in see_also_block.find_all("div", ["item lc lc1 lpb-10 lpr-10", "item lc lc1 lc-xs6-12 lpb-10 lpr-10"]):
            print_tag(item)


def parse_compare(def_block):
    compare_block = def_block.find("div", re.compile("xref compare hax dxref-w( lmt-25)?"))

    if compare_block is not None:
        compare = compare_block.strong.text.upper()
        c_print("#[bold #757575]" + "\n" + compare)
        for item in compare_block.find_all("div", ["item lc lc1 lpb-10 lpr-10", "item lc lc1 lc-xs6-12 lpb-10 lpr-10"]):
            print_tag(item)


def parse_usage_note(def_block):
    usage_block = def_block.find("div", "usagenote dusagenote daccord")

    if usage_block is not None:
        usagenote = usage_block.h5.text
        c_print("#[bold #757575]" + "\n  " + usagenote)
        for item in usage_block.find_all("li", "text"):
            item = item.text
            c_print("#[#757575]" + "    " + item)


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
        c_print("#[bold #757575]" + "\n" + idiom_title)
        for item in idiom_block.find_all("div", ["item lc lc1 lpb-10 lpr-10", "item lc lc1 lc-xs6-12 lpb-10 lpr-10"]):
            print_tag(item)


def parse_sole_idiom(block):
    idiom_sole_meaning = block.find("div", "def ddef_d db")

    text = idiom_sole_meaning.text.strip()
    if text[-1] == ":":
        text = text[ : -1]

    if idiom_sole_meaning is not None:
        print("\033[34m" + text + "\033[0m")
    parse_example(block)
    parse_see_also(block)


def parse_phrasal_verb(block):
    pv_block = block.find("div", re.compile("xref phrasal_verbs? hax dxref-w lmt-25 lmb-25"))

    if pv_block is not None:
        pv_title = pv_block.h3.text.upper()
        c_print("#[bold #757575]" + "\n" + pv_title)
        for item in pv_block.find_all("div", ["item lc lc1 lc-xs6-12 lpb-10 lpr-10", "item lc lc1 lpb-10 lpr-10"]):
            print_tag(item)


def parse_dict_body(block):
    subblocks = block.find_all("div", ["pr dsense", "pr dsense dsense-noh"])

    if len(subblocks) != 0:
        for subblock in subblocks:
            sense = subblock.find("div", "sense-body dsense_b")
            if sense is not None:
                for child in sense.children:
                    try:
                        attr = child.attrs["class"]
                        if attr and attr == ["def-block", "ddef_block"]:
                            parse_def(child)

                        elif attr and "synonym" in attr:
                            parse_synonym(child)

                        elif attr and (attr == ["pr", "phrase-block", "dphrase-block", "lmb-25"] or attr == ["pr", "phrase-block", "dphrase-block"]):
                            parse_ptitle(child)

                            for i in child.find_all("div", "def-block ddef_block"):
                                parse_def(i)
                    except Exception:
                        pass

    else:
        idiom_sole_block = block.find("div", "idiom-block")
        if idiom_sole_block is not None:
            parse_sole_idiom(idiom_sole_block)

        parse_compare(block)

    parse_see_also_lmb(block)
    parse_idiom(block)
    parse_phrasal_verb(block)


def parse_dict_name(first_dict):
    if first_dict.small is not None:
        dict_info = replace_all(first_dict.small.text).strip("(").strip(")")
        dict_name = dict_info.split("©")[0]
        dict_name = dict_name.split("the")[-1]
    else:
        dict_name="Cambridge Dictionary"
    c_print(f"#[#757575]{dict_name}", justify="right")
