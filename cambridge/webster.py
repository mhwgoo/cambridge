import sys
from lxml import etree # type: ignore

from .console import c_print
from .utils import fetch, get_request_url, decode_url, OP, DICT, has_tool, get_suggestion, get_suggestion_by_fzf, get_wod_selection, get_wod_selection_by_fzf
from .log import logger
from .cache import check_cache, save_to_cache, get_cache
from . import camb
from . import color as w_col

WEBSTER_BASE_URL = "https://www.merriam-webster.com"
WEBSTER_DICT_BASE_URL = WEBSTER_BASE_URL + "/dictionary/"
WEBSTER_WORD_OF_THE_DAY_URL = WEBSTER_BASE_URL + "/word-of-the-day"
WEBSTER_WORD_OF_THE_DAY_URL_CALENDAR = WEBSTER_BASE_URL + "/word-of-the-day/calendar"

search_pattern = """
//*[@id="left-content"]/div[contains(@id, "-entry")] |
//*[@id="left-content"]/div[@id="phrases"] |
//*[@id="left-content"]/div[@id="synonyms"] |
//*[@id="left-content"]/div[@id="examples"]/div[@class="content-section-body"]/div[contains(@class,"on-web-container")]/div[contains(@class,"on-web")] |
//*[@id="left-content"]/div[@id="related-phrases"] |
//*[@id="left-content"]/div[@id="nearby-entries"]
"""
parser = etree.HTMLParser(remove_comments=True)

word_entries = set() # A page may have multiple word entries, e.g. "give away", "giveaway"
word_forms = set()   # A word may have multiple word forms, e.g. "ran", "running", "run", "flies"
word_types = set()   # A word's word types, e.g. "preposition", "adjective"


def search_webster(input_word, is_fresh=False, no_suggestions=False, req_url=None, res_url_from_cache=None):
    if res_url_from_cache is not None:
        cache_run(res_url_from_cache)
        sys.exit()

    if req_url is None:
        req_url = get_request_url(WEBSTER_DICT_BASE_URL, input_word, DICT.MERRIAM_WEBSTER.name)

    if is_fresh:
        fresh_run(input_word, no_suggestions, req_url)
    else:
        res_url = check_cache(input_word, req_url)
        if res_url is None:
            logger.debug(f'{OP.NOT_FOUND.name} "{input_word}" in cache')
            fresh_run(input_word, no_suggestions, req_url)
        elif DICT.CAMBRIDGE.name.lower() in res_url:
            camb.search_cambridge(input_word, False, False, no_suggestions, None, res_url)
        else:
            cache_run(res_url)


def cache_run(res_url_from_cache):
    res_word, res_text = get_cache(res_url_from_cache)
    logger.debug(f'{OP.FOUND.name} "{res_word}" from {DICT.MERRIAM_WEBSTER.name} in cache')
    logger.debug(f"{OP.PARSING.name} {res_url_from_cache}")
    tree = etree.HTML(res_text, parser)
    nodes = tree.xpath(search_pattern)
    parse_and_print(nodes, res_url_from_cache, new_line=False)
    c_print(f'\n#[#757575]{OP.FOUND.name} "{res_word}" from {DICT.MERRIAM_WEBSTER.name} in cache. You can add "-f" to fetch the {DICT.CAMBRIDGE.name} dictionary')


def fresh_run(input_word, no_suggestions, req_url):
        response = fetch(req_url)
        res_url = response.url

        # By default Requests will perform location redirection for all verbs except HEAD.
        # https://requests.readthedocs.io/en/latest/user/quickstart/#redirection-and-history
        # You don't need to deal with redirection yourself.
        # if status == 301:
        #     loc = res.headers["location"]
        #     new_url = WEBSTER_BASE_URL + loc
        #     new_res = fetch(new_url, session)

        status = response.status_code
        if status == 200:
            logger.debug(f'{OP.FOUND.name} "{input_word}" in {DICT.MERRIAM_WEBSTER.name} at {res_url}')

            logger.debug(f"{OP.PARSING.name} {res_url}")
            tree = etree.HTML(response.text, parser)

            partial_match = tree.xpath('//p[contains(@class,"partial")]')
            if partial_match:
                input_word = decode_url(res_url).split("/")[-1]
                suggestions = tree.xpath('//h2[@class="hword"]/text() | //h2[@class="hword"]/span/text()')

                logger.debug(f"{OP.PRINTING.name} out suggestions at {res_url}")
                select_word = get_suggestion_by_fzf(suggestions, DICT.MERRIAM_WEBSTER.name) if has_tool("fzf") else get_suggestion(suggestions, DICT.MERRIAM_WEBSTER.name)
                if select_word is None:
                    sys.exit()
                elif select_word == "":
                    logger.debug(f'{OP.SWITCHED.name} to {DICT.CAMBRIDGE.name}')
                    camb.search_cambridge(input_word, True, False, no_suggestions, None)
                else:
                    logger.debug(f'{OP.SELECTED.name} "{select_word}"')
                    search_webster(select_word, False, no_suggestions, None)
            else:
                sub_tree = tree.xpath('//*[@id="left-content"]')[0]
                nodes = sub_tree.xpath(search_pattern)
                if len(nodes) == 0:
                    logger.error(f"No result found in {DICT.MERRIAM_WEBSTER.name}")
                    sys.exit(1)

                # Response word within res_url is not same with what apppears on the web page. e.g. "set in stone"
                result = sub_tree.xpath('//*[@id="left-content"]/div[contains(@id, "-entry-1")]/div[1]/div/div[1]/h1/text()') \
                       or sub_tree.xpath('//*[@id="left-content"]/div[contains(@id, "-entry-1")]/div[1]/div/div/h1/span/text()')

                if len(result) == 0:
                    logger.error(f"No result found in {DICT.MERRIAM_WEBSTER.name}")
                    sys.exit(1)

                parse_and_print(nodes, res_url, new_line=True)

                sub_text = etree.tostring(sub_tree).decode('utf-8')
                # logger.debug(f'START CACHING: input_word is "{input_word}"; res_word is "{res_word}"; res_url is "{res_url}"')
                save_to_cache(input_word, result[0], res_url, sub_text)

        elif status == 404:
            logger.debug(f'{OP.NOT_FOUND.name} "{input_word}" at {res_url}')

            if no_suggestions:
                sys.exit(-1)

            logger.debug(f"{OP.PARSING.name} out suggestions at {res_url}")
            tree = etree.HTML(response.text, parser)
            result = tree.xpath('//div[@class="widget spelling-suggestion"]')
            if len(result) == 0:
                logger.error(f"No suggestions found in {DICT.MERRIAM_WEBSTER.name}")
                sys.exit(1)

            nodes = result[0]
            suggestions = []
            for node in nodes:
                if node.tag != "h1":
                    for word in node.itertext():
                        w = word.strip("\n").strip()
                        if w.startswith("The"):
                            continue
                        else:
                            suggestions.append(w)

            logger.debug(f"{OP.PRINTING.name} out suggestions at {res_url}")
            select_word = get_suggestion_by_fzf(suggestions, DICT.MERRIAM_WEBSTER.name) if has_tool("fzf") else get_suggestion(suggestions, DICT.MERRIAM_WEBSTER.name)
            if select_word is None:
                sys.exit()
            elif select_word == "":
                logger.debug(f'{OP.SWITCHED.name} to {DICT.CAMBRIDGE.name}')
                camb.search_cambridge(input_word, True, False, no_suggestions, None)
            else:
                logger.debug(f'{OP.SELECTED.name} "{select_word}"')
                search_webster(select_word, False, no_suggestions, None)

        else:
            logger.error(f'Something went wrong when fetching {req_url} with STATUS: {status}')
            sys.exit(2)


def nearby_entries(node):
    print()

    for elm in node.iterdescendants():
        try:
            has_title = (elm.tag == "h2")
            has_word = (elm.tag == "span") and (elm.attrib["class"] == "b-link hw-text fw-bold")
            has_nearby = (elm.tag == "a") and (elm.attrib["class"] == "b-link")
            has_em = (elm.tag == "em")
        except KeyError:
            continue
        else:
            if has_title:
                c_print(f"#[bold {w_col.nearby_title}]{elm.text}", end="")

            elif has_em:
                word = "".join(list(elm.itertext()))
                c_print(f"#[bold {w_col.nearby_em}]{word}", end="\n")

            elif has_word:
                c_print(f"#[{w_col.nearby_word}]{elm.text}", end="\n")

            elif has_nearby:
                c_print(f"#[{w_col.nearby_item}]{elm.text}", end="\n")


def synonyms(node):
    print()

    for elm in node.iterdescendants():
        try:
            has_title = (elm.tag == "h2") # "Synonyms"
            has_label = (elm.tag == "p") and (elm.attrib["class"] == "function-label") # "Noun"
            has_syn = (elm.tag == "ul") # synonym list
        except KeyError:
            continue
        else:
            if has_title:
                c_print(f"#[bold {w_col.syn_title}]{elm.text}", end=" ")

            elif has_label:
                c_print(f"\n#[{w_col.syn_label}]{elm.text}")

            elif has_syn:
                children = elm.getchildren()
                total_num = len(children)

                for index, child in enumerate(children):
                    syn = "".join(list(child.itertext())).strip()
                    if index != (total_num - 1):
                        c_print(f"#[{w_col.syn_item}]{syn},", end=" ")
                    else:
                        c_print(f"#[{w_col.syn_item}]{syn}", end=" ")


def examples(node):
    time = 0

    for elm in node.iterdescendants():
        try:
            is_title = ("ex-header function-label" in elm.attrib["class"]) # Recent Examples on the Web
            has_aq = (elm.attrib["class"] == "t has-aq")
        except KeyError:
            continue
        else:
            if is_title:
                c_print(f"\n#[{w_col.eg_title} bold]{elm.text}", end="")
            if has_aq:
                texts = list(elm.itertext())

                for index, t in enumerate(texts):
                    if time in [0, 1, 8, 9, 16, 17, 24, 25]:
                        if index == 0:
                            c_print(f"\n#[{w_col.accessory}]|", end="")
                            c_print(f"#[{w_col.eg_sentence}]{t}", end="")
                        else:
                            hit = False
                            text = t.strip().lower()
                            for w in word_entries:
                                if "preposition" in word_types or "adverb" in word_types or "conjuction" in word_types and ("noun" in word_types and text[-1] !="s"):
                                    if w == text:
                                        hit = True
                                        break
                                else:
                                    if w in text and len(text) < 20:
                                        hit = True
                                        break
                            for f in word_forms:
                                if f == text:
                                    hit = True
                                    break

                            if hit:
                                c_print(f"#[{w_col.eg_sentence} bold]{t}", end="")
                            else:
                                c_print(f"#[{w_col.eg_sentence}]{t}", end="")
                    else:
                        continue
                time = time + 1


def phrases(node):
    print()

    children = node.getchildren()[1]
    for child in children:
        try:
            if child.attrib["class"] == "drp":
                if child.getnext().tag == "span":
                    c_print(f"#[{w_col.ph_item} bold]{child.text}", end = "")
                else:
                    c_print(f"#[{w_col.ph_item} bold]{child.text}", end = "\n")

            elif child.attrib["class"] == "vg":
                vg(child)

        except KeyError:
            for i in child.getchildren():
                if i.attrib["class"] == "vl":
                    print_or_badge(i.text)
                else:
                    c_print(f"#[{w_col.ph_item} bold]{i.text}", end = "\n")


def related_phrases(node):
    print()

    children = node.getchildren()

    title = children[1]
    texts = list(title.itertext())

    for t in texts:
        if t.strip():
            if t.lower() in word_entries:
                c_print(f"#[{w_col.rph_em} bold]{t}", end="\n")
            else:
                c_print(f"#[{w_col.rph_title} bold]{t}", end="")

    pr_sec = children[2]
    phrases = [] # li tags, each tag has one phrase
    for i in pr_sec.iterdescendants():
        if i.tag == "li":
            phrases.append(i)

    for phrase in phrases:
        ts = list(phrase.itertext())
        ts = "". join(ts).strip("\n").strip()
        if phrase != phrases[-1]:
            c_print(f"#[{w_col.rph_item}]{ts},", end=" ")
        else:
            c_print(f"#[{w_col.rph_item}]{ts}", end="")


def get_word_cases(node):
    l_words = []
    u_words = []
    for i in node.iterdescendants():
        attr = i.get("class")
        if attr is not None:
            if "lowercase" in attr:
                l_words.append(i.text)
            elif "uppercase" in attr:
                u_words.append(i.text)
    return l_words, u_words


def dtText(node, ancestor_attr):
    texts = list(node.itertext())

    l_words = get_word_cases(node)[0]
    u_words = get_word_cases(node)[1]

    if node.getprevious() is not None and node.getprevious().get("class") == "sub-content-thread":
        format_basedon_ancestor(ancestor_attr, prefix="\n")

    for index, text in enumerate(texts):
        if text == " " and index == 0:
            continue
        if text == ": ":
            print_meaning_content(text, end="")
        elif text == " see also ":
            print_meaning_keyword(text.strip().upper())
        elif text == " see " or text == " compare ":
            print_meaning_keyword("-> " + text.strip().upper())
        elif u_words and text in u_words:
            text_new = text.upper()
            print_meaning_content(text_new, end="")
        elif l_words and text in l_words:
            text_new = (" " + text)
            print_meaning_content(text_new, end="")
        else:
            print_meaning_content(text, end="")

    print("", end = " ")


def print_mw(text, has_tail, tag):
    if tag == "hl":
        if has_tail is True:
            c_print(f"#[{w_col.meaning_sentence} bold]{text}", end = "")
        else:
            c_print(f"#[{w_col.meaning_sentence} bold]{text}", end = " ")
    if tag == "normal":
        if has_tail is True:
            c_print(f"#[{w_col.meaning_sentence}]{text}", end = "")
        else:
            c_print(f"#[{w_col.meaning_sentence}]{text}", end = " ")


def ex_sent(node, ancestor_attr, num_label_count=1):
    if ancestor_attr:
        format_basedon_ancestor(ancestor_attr, prefix="\n")
    else:
        print("")

    if num_label_count == 2:
        print(" ", end="")

    c_print(f"#[{w_col.accessory}]|", end="")

    hl_words = []
    ems = []
    for i in node.iterdescendants():
        attr = i.get("class")
        if attr is not None:
            if i.tag == "em" and "mw" in attr:
                ems.append(i.text)
            elif i.tag == "span" and "mw" in attr:
                hl_words.append(i.text)

    texts = list(node.itertext())
    count = len(texts)

    for index, t in enumerate(texts):
        text = t.strip("\n").strip()
        if text:
            if t in hl_words:
                hl_has_tail = ((index != (count - 1)) and (texts[index + 1].strip("\n").strip()) and (not texts[index + 1].strip("\n").strip()[0].isalnum()))
                print_mw(text, hl_has_tail, "hl")
            elif t in ems:
                if index != 0 and texts[index - 1].endswith(" "):
                    print("", end = " ")
                c_print(f"#[{w_col.meaning_sentence} bold]{text}", end = "")
                if index != (count - 1) and texts[index + 1].startswith(" "):
                    print("", end = " ")
            else:
                normal_has_tail = (index != (count - 1) and (texts[index + 1] in ems))
                print_mw(text, normal_has_tail, "normal")


def sub_content_thread(node, ancestor_attr, num_label_count=1):
    children = node.getchildren()
    for child in children:
        attr = child.attrib["class"]

        if ("ex-sent" in attr) and ("aq has-aq" not in attr):
            ex_sent(child, ancestor_attr, num_label_count)

        elif "vis" in attr:
            elms = child.getchildren()
            for e in elms:
                elm = e.getchildren()[0]
                elm_attr = elm.attrib["class"]
                if ("ex-sent" in elm_attr) and ("aq has-aq" not in elm_attr):
                    ex_sent(elm, ancestor_attr, num_label_count)


def extra(node, ancestor_attr):
    texts = list(node.itertext())

    l_words = get_word_cases(node)[0]
    u_words = get_word_cases(node)[1]

    prev_attr = node.getprevious().get("class")
    if prev_attr is not None and prev_attr == "sub-content-thread":
        print()

    for text in texts:
        text_new = text.strip("\n").strip()
        if text_new:
            if text_new == "called also" or text_new == "compare":
                print_meaning_keyword("-> " + text_new.upper())
            elif u_words and text in u_words:
                text_new = text_new.upper()
                print_meaning_content(text_new, end="")
            elif l_words and text in l_words:
                text_new = (" " + text_new)
                print_meaning_content(text_new, end="")
            elif text_new == ",":
                print_meaning_content(text_new, end=" ")
            else:
                print_meaning_content(text_new, end="")

    print("", end = " ")


def unText_simple(node, ancestor_attr, num_label_count=1, has_badge=True):
    text = "".join(list(node.itertext())).strip()

    if not has_badge:
        print()
        if num_label_count == 2:
            print(" ", end="")
        format_basedon_ancestor(ancestor_attr, prefix="")

    node_pre = node.getprevious()
    node_pre_attr = node_pre.get("class")

    if "mdash" in node_pre_attr:
        print_meaning_arrow("-> " + text)
    else:
        print_meaning_badge(text)


def sense(node, attr, parent_attr, ancestor_attr, num_label_count=1):
    """e.g. sense(node, "sense has-sn", "sb-0 sb-entry, "sb has-num has-let ms-lg-4 ms-3 w-100", 1)"""

    children = node.getchildren()

    # meaning without any sign
    if attr == "sense  no-subnum":
        sense_content = children[0] # class "sense-content w-100"

    # meaning with "1" + "a"
    elif attr == "sense has-sn has-num":
        sn = children[0].getchildren()[0].text

        node_prev = node.getprevious()
        if "has-subnum" in ancestor_attr and node_prev is None and "sb-0" in parent_attr:
            c_print(f"#[bold {w_col.meaning_letter}]{sn}", end = " ")
        elif "has-subnum" in ancestor_attr and (node_prev is not None or parent_attr != "pseq no-subnum"):
            if num_label_count == 2:
                print(" ", end="")
            c_print(f"  #[bold {w_col.meaning_letter}]{sn}", end = " ")
        else:
            c_print(f"#[bold {w_col.meaning_letter}]{sn}", end = " ")

        sense_content = children[1] # class "sense-content w-100"

    # meaing with only "b" or "1" + "a" + "(1)", or "1" + "a"
    elif attr == "sense has-sn" or attr == "sen has-sn":
        sn = children[0].getchildren()[0].text

        if "has-subnum" in ancestor_attr and "sb-0" in parent_attr:
            c_print(f"#[bold {w_col.meaning_letter}]{sn}", end = " ")
        else:
            if num_label_count == 2:
                    print(" ", end="")

            if "letter-only" in ancestor_attr:
                if "sb-0" not in parent_attr:
                    print("  ", end="")
                c_print(f"#[bold {w_col.meaning_letter}]{sn}", end = " ")
            else:
                c_print(f"  #[bold {w_col.meaning_letter}]{sn}", end = " ")

        sense_content = children[1] # class "sense-content w-100"

    # meaning with only (2)
    elif attr == "sense has-num-only has-subnum-only":
        if num_label_count == 2:
            print(" ", end="")
        if "letter-only" in ancestor_attr:
            if children[0].attrib["class"] == "sn":
                print("    ", end = "")
            else:
                print("  ", end="")
        else:
            print("    ", end = "")
        sense_content = children[1] # class "sense-content w-100"

    # meaning with only number
    elif attr == "sense has-sn has-num-only":
        sense_content = children[1] # class "sense-content w-100"

    else:
        sense_content = children[1]

    # "sense-content w-100"
    tags(sense_content, attr, num_label_count)


def sb_entry(node, parent_attr, num_label_count=1):
    child = node.getchildren()[0]
    attr = node.attrib["class"]         # "sb-0 sb-entry"
    child_attr = child.attrib["class"]  # "sense has-sn" or "pseq no-subnum"
    if "pseq" in child_attr:
        elms = child.getchildren()[0].getchildren()
        for e in elms:
            e_attr = e.attrib["class"]  # "sense has-sn"
            sense(e, e_attr, attr, parent_attr, num_label_count)     # e.g. sense(child, "sense has-sn", "sb-0 sb-entry", "....", 1)
    elif "sense" in child_attr and child.tag != "span":
        sense(child, child_attr, attr, parent_attr, num_label_count) # e.g. sense(child, "sense has-sn", "sb-0 sb-entry, "sb has-num has-let ms-lg-4 ms-3 w-100", 1)


def tags(node, ancestor_attr, num_label_count):
    has_badge = True

    for elm in node.iterdescendants():
        elm_attr = elm.get("class")
        if elm_attr is not None:
            if "badge" in elm_attr and "pron" not in elm_attr:
                text = "".join(list(elm.itertext())).strip()
                print_meaning_badge(text)

            elif elm_attr == "et":
                et(elm)

            elif elm_attr == "il ":
                print_meaning_badge(elm.text.strip(), end=" ")

            elif elm_attr == "if":
                print_class_if(elm.text)

            elif elm_attr == "sgram":
                print_class_sgram(elm)

            elif elm_attr == "vl":
                print_meaning_badge(elm.text.strip())

            elif elm_attr == "va":
                print_class_va(elm.text.strip())

            elif elm_attr == "sd":
                parent = elm.getparent()
                parent_attr = parent.get("class")
                parent_prev = parent.getprevious()
                if parent_prev is not None and "hasSdSense" in parent_prev.get("class"):
                    print()
                if parent_attr is not None and parent_attr == "sdsense":
                    format_basedon_ancestor(ancestor_attr, prefix="")

                if num_label_count == 2:
                    print(" ", end="")

                print_meaning_badge(elm.text)

            elif elm_attr == "dtText":
                dtText(elm, ancestor_attr) # only meaning text

            elif elm_attr == "sub-content-thread":
                sub_content_thread(elm, ancestor_attr, num_label_count) # example under the meaning
                has_badge = False

            elif elm_attr == "ca":
                extra(elm, ancestor_attr)

            elif elm_attr == "unText":
                unText_simple(elm, ancestor_attr, num_label_count, has_badge)

            elif "prons-entries-list" in elm_attr:
                print_pron(elm)

    print()


def vg_sseq_entry_item(node):
    """Print one meaning of one entry(noun entry, adjective entry, or verb entry and so forth). e.g. 1: the monetary worth of something."""

    num_label_count = 0
    children = node.getchildren()
    for child in children:
        attr = child.attrib["class"]
        # print number label if any
        if attr == "vg-sseq-entry-item-label":
            c_print(f"#[bold {w_col.meaning_num}]{child.text}", end=" ")
            num_label_count = len(child.text)

        # print meaning content
        elif "ms-lg-4 ms-3 w-100" in attr:
            for c in child.iterchildren(): # c:  class="sb-0 sb-entry"
                cc = c.getchildren()[0]    # cc: class="sen has-num-only"
                cc_attr = cc.get("class")
                if cc_attr is not None and cc_attr == "sen has-num-only":
                    tags(cc, cc_attr, num_label_count)

                # print class "sb-0 sb-entry", "sb-1 sb-entry" ...
                sb_entry(c, attr, num_label_count)

def et(node):
    for t in node.itertext():
        print(t.strip("\n"), end= "")

    if node.getnext() is None:
        print()
    else:
        print("", end=" ")

def vg(node):
    """Print one entry(e.g. 1 of 3)'s all meanings. e.g. 1 :the monetary worth of something 2 :a fair return... 3 :..."""

    children = node.getchildren()
    for child in children:
        attr = child.get("class")
        # print one meaning of one entry
        if attr is not None and "vg-sseq-entry-item" in attr:
            vg_sseq_entry_item(child)

        # print transitive or intransitive
        elif attr is not None and (attr == "vd firstVd" or attr == "vd"):
            e = child.getchildren()[0]
            c_print(f"#[bold]{e.text}")

        # print tags like "informal" and the tags at the same livel with transitives
        elif attr is not None and "sls" in attr:
            e = child.getchildren()[0]
            e_attr = e.get("class")
            if e_attr is not None and "badge" in e_attr:
                print_meaning_badge(e.text)
            else:
                c_print(f"#[bold]{e.text}")

            if "vg-sseq-entry-item" in child.getnext().get("class"):
                print()


def print_word(text):
    c_print(f"#[{w_col.eh_h1_word} bold]{text}", end=" ")


def entry_header_content(node):
    """Print entry header content. e.g. value 1 of 3 noun"""

    for elm in node.iterchildren():
        if elm.tag == "h1" or elm.tag == "p":
            word = "".join(list(elm.itertext()))
            global word_entries
            word_entries.add(word.strip().lower())
            print_word(word)

        elif elm.tag == "span":
            num = " ".join(list(elm.itertext()))
            print(num, end=" ")

        elif elm.tag == "h2":
            type = " ".join(list(elm.itertext()))
            c_print(f"#[bold {w_col.eh_word_type}]{type}", end="")
            global word_types
            word_types.add(type.strip().lower())

    print()


def entry_attr(node):
    """Print the pronounciation. e.g. val·ue |ˈval-(ˌ)yü|"""

    for elm in node.iterchildren():
        if "col word-syllables-prons-header-content" in elm.attrib["class"]:
            for i in elm.iterchildren():
                if i.tag == "span" and i.attrib["class"] == "word-syllables-entry":
                    syllables = i.text
                    print(f"{syllables}", end=" ")

                elif i.tag == "span" and "prons-entries-list-inline" in i.attrib["class"]:
                    print_pron(i, True)


def row_entry_header(node):
    """Print class row entry-header, the parent and caller of entry_header_content() and entry_attr()."""

    for elm in node.iterchildren():
        if elm.attrib["class"] == "col-12":
            for i in elm.iterchildren():
                if "entry-header-content" in i.attrib["class"]:
                    entry_header_content(i)
                elif "row entry-attr" in i.attrib["class"]:
                    entry_attr(i)


def entry_uros(node):
    """Print other word forms. e.g. valueless, valuelessness"""

    for elm in node.iterdescendants():
        attr = elm.get("class")
        if attr is not None:
            if elm.tag == "span" and "fw-bold ure" in attr:
                c_print(f"#[bold {w_col.wf}]{elm.text}", end = " ")

            elif elm.tag == "span" and "fw-bold fl" in attr:
                c_print(f"#[{w_col.eh_word_type}]{elm.text}", end = "")

            elif "ins" in attr:
                print("", end="")
                print_class_ins(elm)

            elif "sl badge" in attr:
                text = "".join(list(elm.itertext())).strip()
                print_meaning_badge(text)

            elif "utxt" in attr:
                for i in elm.iterchildren():
                    sub_attr = i.get("class")
                    if sub_attr is not None and sub_attr == "sub-content-thread":
                        sub_content_thread(i, "")
                print()

            elif "prons-entries-list" in attr:
                print_pron(elm)

            elif "vrs" in attr:
                # can't get css element ::before.content like "variants" in the word "duel"
                child = elm.getchildren()[0]
                for c in child.iterchildren():
                    attr_c = c.get("class")
                    if attr_c == "il " or attr_c == "vl":
                        print_or_badge(c.text)
                    elif attr_c == "va":
                        if c.text is None:
                            for i in child:
                                print_class_va(i.text)
                        else:
                            print_class_va(c.text)
                    elif "prons-entries-list" in attr_c:
                        continue


def row_headword_row_header_ins(node):
    """Print verb types. e.g. valued; valuing"""

    children = node.getchildren()[0].getchildren()[0]
    if "ins" in children.attrib["class"]:
        print_class_ins(children)
        print()


def print_vrs(node):
    for elm in node.iterchildren():
        elm_attr = elm.get("class")
        if elm_attr is not None and "badge mw-badge-gray-100 text-start text-wrap d-inline" in elm_attr:
            c_print(f"#[bold]{elm.text.strip()}", end="")
        else:
            for child in elm.iterdescendants():
                attr = child.get("class")
                if attr is not None:
                    if attr == "il " or attr == "vl":
                        print_or_badge(child.text)
                    elif attr == "va":
                        if child.text is None:
                            for i in child:
                                print_class_va(i.text)
                        else:
                            print_class_va(child.text)
                    elif "prons-entries-list" in attr:
                        print_pron(child)
                    else:
                        continue


def row_headword_row_header_vrs(node):
    """Print word variants. e.g. premise variants or less commonly premiss"""

    children = node.getchildren()[0].getchildren()[0] # class "entry-attr vrs"
    print_vrs(children)
    print()


def dxnls(node):
    """Print dxnls section, such as 'see also', 'compare' etc."""

    texts = list(node.itertext())
    for text in texts:
        text = text.strip()
        if not text:
            continue
        if text == "see also":
            c_print(f"\n#[bold {w_col.dxnls_content}]{text.upper()}", end = " ")
        elif text == "compare":
            c_print(f"\n#[bold {w_col.dxnls_content}]{text.upper()}", end = " ")
        elif text == ",":
            c_print(f"#[{w_col.dxnls_content}]{text}", end = " ")
        else:
            c_print(f"#[{w_col.dxnls_content}]{text}", end = "")

    print()


def dictionary_entry(node):
    """Print one entry of the word and its attributes like plural types, pronounciations, tenses, etc."""

    print()
    for elm in node.iterchildren():
        elm_attr = elm.get("class")
        if elm_attr is not None:
            if "row entry-header" in elm_attr:
                row_entry_header(elm)

            elif elm_attr == "row headword-row header-ins":
                row_headword_row_header_ins(elm)

            elif elm_attr == "row headword-row header-vrs":
                row_headword_row_header_vrs(elm)

            elif elm_attr == "vg":
                vg(elm)

            elif "entry-uros" in elm_attr:
                for i in elm.iterchildren():
                    entry_uros(i)
                    print()

            elif elm_attr == "dxnls":
                dxnls(elm)

            elif elm_attr == "mt-3":
                badge = elm.getchildren()[0] # class "lbs badge mw-badge-gray-100 text-start text-wrap d-inline"
                print_header_badge(badge.text, end="\n")

            elif elm_attr == "cxl-ref":
                text = list(elm.itertext())
                print_meaning_content(": ", end="")
                for t in text:
                    t = t.strip()
                    if t:
                        print_meaning_content(t, end=" ")
                print()


def print_meaning_badge(text, end=" "):
    c_print(f"#[{w_col.meaning_badge}]{text}", end=end)


def print_header_badge(text, end=" "):
    c_print(f"#[{w_col.meaning_badge}]{text}", end=end)


def print_meaning_arrow(text, end=" "):
    c_print(f"#[{w_col.meaning_arrow}]{text}", end=end)


def print_meaning_keyword(text, end=" "):
    c_print(f"#[bold {w_col.meaning_keyword}]{text}", end=end)


def print_meaning_content(text, end=""):
    if text == ": ":
        c_print(f"#[{w_col.meaning_content} bold]{text}", end=end)
    else:
        c_print(f"#[{w_col.meaning_content}]{text}", end=end)


def format_basedon_ancestor(ancestor_attr, prefix="", suffix=""):
    print(prefix, end="")
    if ancestor_attr == "sense has-sn has-num-only":
        print("  ", end=suffix)
    elif ancestor_attr == "sense has-sn has-num":
        print("    ", end=suffix)
    elif ancestor_attr == "sense has-sn":
        #if "no-sn letter-only" in root_attr:
        #    print("  ", end=suffix)
        print("    ", end=suffix)
    elif ancestor_attr == "sense  no-subnum":
        print("", end=suffix)
    elif ancestor_attr == "sense has-num-only has-subnum-only":
        print("    ", end=suffix)


def print_pron(node, header=False):
    sibling = node.getnext()
    before_semicolon = ((sibling is not None) and (sibling.get("class") == "sep-semicolon"))
    before_or = ((sibling is not None) and (sibling.get("class") == "il "))

    prons = []
    for text in node.itertext():
        text = text.strip("\n").strip()
        if text:
            prons.append(text)

    count = len(prons)
    if count == 1:
        if sibling is None:
            if header:
                print(f"|{prons[0]}|", end="\n") # e.g. fortissimo 1 of 2
            else:
                print(f"|{prons[0]}|", end="")   # e.g. fortissimo 2 of 2
        else:
            if before_semicolon or before_or:
                print(f"|{prons[0]}|", end="")
            else:
                print(f"|{prons[0]}|", end=" ")
    if count > 1:
        for index, pron in enumerate(prons):
            if index == 0:
                if before_semicolon or before_or:
                    print(f"|{pron}|", end="")
                else:
                    print(f"|{pron}|", end="  ")
            elif index == count - 1:
                if sibling is not None:
                    c_print(f"#[{w_col.eh_word_syllables}]{pron}", end=" ")
                else:
                    if header:
                        c_print(f"#[{w_col.eh_word_syllables}]{pron}", end="\n")
                    else:
                        c_print(f"#[{w_col.eh_word_syllables}]{pron}", end="")
            elif pron == "," or pron == ";":
                continue
            else:
                text = pron + ", "
                c_print(f"#[{w_col.eh_word_syllables}]{text}", end="")


def print_or_badge(text):
    c_print(f"#[{w_col.or_badge}]{text}", end = "")


def print_class_if(text, before_semicolon=False, before_il=False):
    if before_semicolon or before_il:
        c_print(f"#[bold]{text}", end="")
    else:
        c_print(f"#[bold]{text}", end=" ")


def print_class_va(text):
    c_print(f"#[bold]{text}", end=" ")


def print_class_sgram(node):
    for t in node.itertext():
        text = t.strip("\n").strip()
        if text and text.isalpha():
            c_print(f"#[bold]{t}", end=" ")


def print_class_ins(node):
    """print node whose class name includes ins, such as 'ins', 'vg-ins'."""
    for child in node:
        attr = child.get("class")
        if attr is not None:
            if attr == "il  il-badge badge mw-badge-gray-100":
                if node.getprevious() is not None:
                    print_header_badge(child.text, end=" ")
                else:
                    print_header_badge(child.text.strip(), end=" ")
            elif attr == "prt-a":
                print_pron(child)
            elif attr == "il ":
                print_or_badge(child.text)
            elif attr == "sep-semicolon":
                print(f"{child.text}", end="")
            elif attr == "if":
                next_sibling = child.getnext()
                if next_sibling is None:
                    print_class_if(child.text, before_semicolon=False)
                else:
                    sub_attr = next_sibling.get("class")
                    if sub_attr == "sep-semicolon":
                        print_class_if(child.text, before_semicolon=True)
                    elif sub_attr == "il ":
                        print_class_if(child.text, before_il=True)
                    else:
                        print_class_if(child.text, before_semicolon=False)
                global word_forms
                word_forms.add(child.text.strip().lower())
            else:
                c_print(f"#[bold]{child.text}", end="")


def print_dict_name():
    dict_name = "The Merriam-Webster Dictionary"
    c_print(f"#[{w_col.dict_name}]{dict_name}", justify="right")


def parse_and_print(nodes, res_url, new_line=False):
    logger.debug(f"{OP.PRINTING.name} the parsed result of {res_url}")

    for node in nodes:
        try:
            attr = node.attrib["id"]
        except KeyError:
            attr = node.attrib["class"]

        if "-entry" in attr:
            dictionary_entry(node)

        elif attr == "phrases":
            phrases(node)

        elif attr == "nearby-entries":
            nearby_entries(node)

        elif attr == "synonyms":
            synonyms(node)

        elif "on-web" in attr:
            examples(node)

        elif attr == "related-phrases":
            related_phrases(node)

    if new_line:
        print()


# --- Word of the Day --- #
def print_wod_header(node):
    for elm in node.iterdescendants():
        attr = elm.get("class")
        if attr == "w-a-title":
            for c in elm.iterchildren():
                c_print(f"#[{w_col.wod_title} bold]{c.text}", end="")
            print()

        elif attr == "word-header-txt":
            c_print(f"#[bold]{elm.text}")

        elif attr == "main-attr":
            c_print(f"#[{w_col.wod_type}]{elm.text}", end="")
            print(" | ", end="")

        elif attr == "word-syllables":
            c_print(f"#[{w_col.wod_syllables}]{elm.text}")


def print_wod_p(node):
    text = node.text
    if text:
        print(text, end="")

    for child in node.iterchildren():
        if child is not None and child.tag == "em":
            t = "".join(list(child.itertext()))
            c_print(f"#[bold]{t}", end="")
            print(child.tail, end="")
        elif child is not None and child.tag == "a":
            child_text = child.text
            child_tail = child.tail
            if child_text == "See the entry >":
                continue
            else:
                if child_text is not None:
                    print(child_text, end="")
                for c in child.iterchildren():
                    if c is not None and c.tag == "em":
                        c_print(f"#[bold]{c.text}", end="")

            if child_tail is not None:
                print(child_tail, end="")
    print()


def print_wod_def(node):
    for elm in node.iterchildren():
        tag = elm.tag

        if tag == "h2":
            text = elm.text.strip("\n").strip()
            if text:
                c_print(f"\n#[{w_col.wod_subtitle} bold]{text}")
            children = list(elm.iterchildren())
            if children:
                child = children[0]
                tail = child.tail.strip("\n").strip()
                c_print(f"#[{w_col.wod_subtitle} bold]{child.text}", end=" ")
                c_print(f"#[{w_col.wod_subtitle} bold]{tail}", end="\n")

        elif tag == "p":
            print_wod_p(elm)

        elif tag == "div" and elm.attrib["class"] == "wotd-examples":
            child = elm.getchildren()[0].getchildren()[0]
            print_wod_p(child)


def print_wod_dyk(node):
    for elm in node.iterchildren():
        tag = elm.tag

        if tag == "h2":
            c_print(f"\n#[{w_col.wod_subtitle} bold]{elm.text}")

        elif tag == "p":
            print_wod_p(elm)


def parse_and_print_wod(res_url, res_text):
    logger.debug(f"{OP.PARSING.name} {res_url}")

    parser = etree.HTMLParser(remove_comments=True)
    tree = etree.HTML(res_text, parser)
    s = """
    //*[@class="article-header-container wod-article-header"] |
    //*[@class="wod-definition-container"] |
    //*[@class="did-you-know-wrapper"]
    """

    nodes = tree.xpath(s)

    logger.debug(f"{OP.PRINTING.name} the parsed result of {res_url}")

    print()
    for node in nodes:
        attr = node.attrib["class"]

        if "header" in attr:
            print_wod_header(node)

        elif "definition" in attr:
            print_wod_def(node)

        elif "did-you-know" in attr:
            print_wod_dyk(node)
    print()


def parse_and_print_wod_calendar(res_url, res_text):
    logger.debug(f"{OP.PARSING.name} {res_url}")

    parser = etree.HTMLParser(remove_comments=True)
    tree = etree.HTML(res_text, parser)
    nodes = tree.xpath("//li/h2/a")
    logger.debug(f"{OP.PRINTING.name} the parsed result of {res_url}")

    data = {}
    for node in nodes:
        data[node.text] = node.attrib["href"]

    select_word = get_wod_selection_by_fzf(data) if has_tool("fzf") else get_wod_selection(data)
    if select_word in data.keys():
        url = WEBSTER_BASE_URL + data[select_word]
        get_webster_wod_past(url)
    elif select_word is not None and len(select_word) > 1 and not select_word.isnumeric():
        search_webster(select_word)
    else:
        sys.exit()


def get_webster_wod():
    response = fetch(WEBSTER_WORD_OF_THE_DAY_URL)
    parse_and_print_wod(response.url, response.text)


def get_webster_wod_past(req_url):
    response = fetch(req_url)
    parse_and_print_wod(response.url, response.text)


def get_webster_wod_list():
    response = fetch(WEBSTER_WORD_OF_THE_DAY_URL_CALENDAR)
    parse_and_print_wod_calendar(response.url, response.text)
