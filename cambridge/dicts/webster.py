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
from ..colorschemes import webster_color

# TODO sub_num (1) (2) with parent meaning or not
# If not parent meaing, don't print.


# Test fzf preview under development env
# python main.py l | fzf --preview 'python main.py -w {}'


WEBSTER_BASE_URL = "https://www.merriam-webster.com"
WEBSTER_DICT_BASE_URL = WEBSTER_BASE_URL + "/dictionary/"

sub_text = ""
res_word = ""
word_entries = []


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


def fresh_run(con, cur, req_url, input_word):
    """Print the result without cache."""

    result = fetch_webster(req_url, input_word)
    found = result[0]
    res_url, res_text = result[1]
    nodes = parse_dict(res_text, found, res_url, True)

    if found:
        # res_word may not be returned when `save` is called by concurrency
        # word wiin res_url is still the input_word formatted
        global res_word
        if not res_word:
            res_word = input_word

        parse_thread = threading.Thread(
            target=parse_and_print, args=(nodes, res_url,)
        )
        parse_thread.start()

        dict.save(con, cur, input_word, res_word, res_url, sub_text)

    else:
        logger.debug(f"{OP[4]} the parsed result of {res_url}")

        suggestions = []
        for node in nodes:
            if node.tag != "h1":
                for word in node.itertext():
                    w = word.strip()
                    if w.startswith("The"):
                        continue
                    else:
                        sug = w.strip()
                        suggestions.append(sug)
        
        dict.print_spellcheck(con, cur, input_word, suggestions, DICTS[1])


def parse_dict(res_text, found, res_url, is_fresh):
    """Parse the dict section of the page for the word."""

    parser = etree.HTMLParser(remove_comments=True)
    tree = etree.HTML(res_text, parser)

    logger.debug(f"{OP[1]} {res_url}")

    if found:
        s = """
        //*[@id="left-content"]/div[contains(@id, "dictionary-entry")] |
        //*[@id="left-content"]/div[@id="phrases"] |
        //*[@id="left-content"]/div[@id="synonyms"] |
        //*[@id="left-content"]/div[@id="examples"]/div[@class="content-section-body"]/div[@class="on-web-container"]/div[@class="on-web read-more-content-hint-container"] |
        //*[@id="left-content"]/div[@id="related-phrases"] |
        //*[@id="left-content"]/div[@id="nearby-entries"]
        """

        nodes = tree.xpath(s)
        
        if is_fresh:
            global sub_text
            sub_tree = tree.xpath('//*[@id="left-content"]')
            sub_text = etree.tostring(sub_tree[0]).decode('utf-8')
        
        if len(nodes) < 2:
            logger.error("The fetched content is not intended for the word, due to your network or the website reasons, please try again.")
            sys.exit()

        ## [for debug]
        # for node in nodes:
        #     try:
        #         print("id:    ", node.attrib["id"])
        #     except KeyError:
        #         print("class: ", node.attrib["class"])
        
        # sys.exit()

    else:
        nodes = tree.xpath('//div[@class="widget spelling-suggestion"]')[0]

    return nodes
    

###########################################
# parse and print nearby entries
###########################################

def nearby_entries(node):
    """Print entries near value."""

    print("")

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
                console.print(f"[{webster_color.bold} {webster_color.nearby_title}]{elm.text}", end="")

            if has_em:
                console.print(f"[{webster_color.bold} {webster_color.italic} {webster_color.nearby_em}]{elm.text}", end="\n")

            if has_word:
                console.print(f"[{webster_color.nearby_word}]{elm.text}", end="\n")

            if has_nearby:
                console.print(f"[{webster_color.nearby_item}]{elm.text}", end="\n")


###########################################
# parse and print synonyms 
###########################################

def synonyms(node):
    """Print synonyms."""

    print()

    time = 0

    for elm in node.iterdescendants():
        try:
            has_title = (elm.tag == "h2") # "Synonyms"
            has_label = (elm.tag == "p") and (elm.attrib["class"] == "function-label") # "Noun"
            has_syn = (elm.tag == "ul") # synonym list
            has_em = (elm.tag == "em")
        except KeyError:
            continue
        else:
            if has_title:
                console.print(f"[{webster_color.bold} {webster_color.syn_title}]{elm.text}", end=" ")

            if has_em and time == 0:
                console.print(f"[{webster_color.bold} {webster_color.italic} {webster_color.syn_em}]{elm.text}", end="")
                time += 1

            if has_label:
                console.print(f"\n[{webster_color.syn_label} {webster_color.bold}]{elm.text}")

            if has_syn:
                for t in elm.itertext():
                    text = t.strip()
                    if text:
                        console.print(f"[{webster_color.syn_item}]{text}", end=" ")



###########################################
# parse and print examples 
###########################################

# NOTE: 
# Wester scrapes the web for examples in the way that it only finds the exact match of the word.
# If the word is a verb, only gets the word without tenses; if the word is a noun, only its single form.
def examples(node, words):
    """Print recent examples on the web."""

    print()
    time = 0

    for elm in node.iterdescendants():
        try:
            is_title = ("ex-header function-label" in elm.attrib["class"]) # Recent Examples on the Web
            has_aq = (elm.attrib["class"] == "t has-aq")
        except KeyError:
            continue
        else:
            if is_title:
                console.print(f"\n[{webster_color.eg_title} {webster_color.bold}]{elm.text}", end="")
            if has_aq:
                for index, t in enumerate(list(elm.itertext())):
                    if time in [0, 1, 8, 9, 16, 17, 24, 25]:
                        if index == 0:
                            console.print(f"\n[{webster_color.accessory} {webster_color.bold}]|", end="")
                            console.print(f"[{webster_color.eg_sentence}]{t}", end="")
                        else:
                            if t.strip().lower() in words:
                                console.print(f"[{webster_color.eg_word} {webster_color.italic}]{t}", end="")
                            else:
                                console.print(f"[{webster_color.eg_sentence}]{t}", end="")
                    else:
                        continue
                time = time + 1


###########################################
# parse and print phrases 
###########################################

def phrases(node):
    """Print phrases."""

    children = node.getchildren()[1]
    
    for child in children:
        if child.attrib["class"] == "drp":
            console.print(f"[{webster_color.ph_item} {webster_color.bold}]{child.text}")

        if child.attrib["class"] == "vg":
            vg(child)



###########################################
# parse and print related phrases 
###########################################

def related_phrases(node, words):
    """Print related phrases."""

    print("\n")

    children = node.getchildren()

    title = children[1]
    texts = list(title.itertext())
    for t in texts:
        if t.strip():
            if t.lower() in words:
                console.print(f"[{webster_color.rph_title} {webster_color.bold} {webster_color.italic}]{t}", end="\n")
            else:
                console.print(f"[{webster_color.rph_title} {webster_color.bold}]{t}", end="")

    pr_sec = children[2]
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
                console.print(f"[{webster_color.rph_item}]{t}", end="")
            else:
                if phrase != phrases[-1]:
                    console.print(f"[{webster_color.rph_item}]{t},", end=" ")
                else:
                    console.print(f"[{webster_color.rph_item}]{t}", end="\n")



########################################
# parse and print dictionary-entry-[num]
########################################

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
            if is_sdsense:
                print()
                console.print(f"{text}", style="italic bold", end=" ")
            else:
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
        if t == s_words[0] and t.strip() == "":
            continue
        else:
            console.print(f"[#3C8DAD]{t}", end="")


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
    print(text, subsense_index)
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
            if not before_subnum and subsense_index > 0:
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


###########################################
# parse and print dictionary-entry-[number] 
###########################################

def dtText(node):
    texts = list(node.itertext())

    # link_index = 0

    for index, text in enumerate(texts):
        if text == ": ":
            text = text.strip()
            # if index != 0:
            #     link_index = index + 1

        # if index == link_index and index != 0:
        #     text = text.upper()
        #     console.print(f"[{webster_color.meaning_link}]{text}", end = "")
        # else:
        console.print(f"[{webster_color.meaning_content}]{text}", end = "")

    # print()

def ex_sent(node, ancestor_attr):
    if ancestor_attr == "sense has-sn has-num-only":
        console.print(f"\n  [{webster_color.accessory} {webster_color.bold}]|", end="")
    if ancestor_attr == "sense has-sn has-num" or ancestor_attr == "sense has-sn":
        console.print(f"\n    [{webster_color.accessory} {webster_color.bold}]|", end="")
    if ancestor_attr == "sense  no-subnum":
        console.print(f"\n[{webster_color.accessory} {webster_color.bold}]|", end="")

    for text in node.itertext():
        console.print(f"[{webster_color.meaning_sentence}]{text}", end = "")
    
    
def sub_content_thread(node, ancestor_attr):
    children = node.getchildren()
    for child in children:
        attr = child.attrib["class"]
        if ("ex-sent" in attr) and ("aq has-aq" not in attr):
            ex_sent(child, ancestor_attr)

def dt(node, ancestor_attr, self_attr):
    children = node.getchildren()

    for child in children:
        child_attr = child.attrib["class"]
        
        if child_attr == "sd": # label before meaning content
            if self_attr == "sdsense":
                if "has-num-only" in ancestor_attr: 
                    console.print(f"  [{webster_color.italic} {webster_color.meaning_badge}]{child.text}", end=" ")
                elif "no-subnum" in ancestor_attr:
                    console.print(f"[{webster_color.italic} {webster_color.meaning_badge}]{child.text}", end=" ")
                else:
                     console.print(f"    [{webster_color.italic} {webster_color.meaning_badge}]{child.text}", end=" ")
            else:
                console.print(f"[{webster_color.italic} {webster_color.meaning_badged}]{child.text}", end=" ")
        
        if child_attr == "dtText":
            dtText(child)   # only meaning text

        if child_attr == "sub-content-thread":
            sub_content_thread(child, ancestor_attr)  # example under the meaning
    print()
            

def sense(node):
    attr = node.attrib["class"]
    children = node.getchildren()

    if attr == "sense  no-subnum":
        sense_content = children[0] # class "sense-content w-100"

    # meaning with "a", "b" letter,  with or without "1", "2" (having siblings before it)
    if attr == "sense has-sn has-num" or attr == "sense has-sn":
        sn = children[0].getchildren()[0].text
        if "has-num" in attr:
            console.print(f"[{webster_color.bold} {webster_color.meaning_letter}]{sn}", end = " ")
        else:
            console.print(f"  [{webster_color.bold} {webster_color.meaning_letter}]{sn}", end = " ")
        sense_content = children[1]  # class "sense-content w-100"

    # meaning with only number
    if attr == "sense has-sn has-num-only":
        sense_content = children[1]  # class "sense-content w-100"


    elms = sense_content.getchildren()
    
    for elm in elms:
        elm_attr = elm.attrib["class"]
        if "badge" in elm_attr:
            text = "".join(list(elm.itertext()))
            console.print(f"[{webster_color.italic} {webster_color.meaning_badge}]{text}", end="")

        if elm_attr == "dt " or elm_attr == "dt hasSdSense" or elm_attr == "sdsense":
            dt(elm, attr, elm_attr)
            

def sb_entry(node):
    child = node.getchildren()[0]
    sense(child)


# --- parse class "vg" --- #
def vg_sseq_entry_item(node):
    """Print one meaning of one entry(noun entry, adjective entry, or verb entry and so forth). e.g. 1: the monetary worth of something."""

    children = node.getchildren()
    for child in children:
        # print number label if any
        if child.attrib["class"] == "vg-sseq-entry-item-label":
            console.print(f"[{webster_color.bold} {webster_color.meaning_num}]{child.text}", end=" ")

        # print meaning content
        if "ms-lg-4 ms-3 w-100" in child.attrib["class"]:
            for i in child:
                # print class "sb-0 sb-entry", "sb-1 sb-entry" ...
                sb_entry(i) 


def vg(node):
    """Print one entry(e.g. 1 of 3)'s all meanings. e.g. 1 :the monetary worth of somethng 2 :a fair return... 3 :..."""

    children = node.getchildren()
    for child in children:
        # print one meaning of one entry
        if "vg-sseq-entry-item" in child.attrib["class"]:
            vg_sseq_entry_item(child)

        # print transitive or intransitive
        if child.attrib["class"] == "vd firstVd" or child.attrib["class"] == "vd":
            e = child.getchildren()[0]
            console.print(f"\n[{webster_color.tran}]{e.text}")


# --- parse class "row entry-header" --- #
def entry_header_content(node):
    """Print entry header content. e.g. value 1 of 3 noun"""

    for elm in node.iterchildren():
        if elm.tag == "h1" or elm.tag == "p":
            word = elm.text
            global word_entries
            word_entries.append(word)
            console.print(f"[{webster_color.eh_h1_word} {webster_color.bold}]{word}", end=" ")

        if elm.tag == "span":
            num = " ".join(list(elm.itertext()))
            console.print(f"[{webster_color.eh_entry_num}]{num}", end=" ")

        if elm.tag == "h2":
            type = " ".join(list(elm.itertext()))
            console.print(f"[{webster_color.eh_word_type}]{type}", end="\n")

def entry_attr(node):
    """Print the pronounciation. e.g. val·​ue |ˈval-(ˌ)yü|"""

    for elm in node.iterchildren():
        if "col word-syllables-prons-header-content" in elm.attrib["class"]:
            for i in elm.iterchildren():
                if i.tag == "span" and i.attrib["class"] == "word-syllables-entry":
                    syllables = i.text
                    console.print(f"[{webster_color.eh_word_syllables}]{syllables}", end=" ")

                if i.tag == "span" and "prons-entries-list-inline" in i.attrib["class"]:
                    pron = list(i.itertext())[1].strip()
                    console.print(f"[{webster_color.eh_pron}]|{pron}|", end="\n")

def row_entry_header(node):
    """Print class row entry-header, the parent and caller of entry_header_content() and entry_attr()."""

    for elm in node.iterchildren():
        if elm.attrib["class"] == "col-12":
            for i in elm.iterchildren():
                if "entry-header-content" in i.attrib["class"]:
                    entry_header_content(i)
                if "row entry-attr" in i.attrib["class"]:
                    entry_attr(i)
    

# --- parse class "entry-uros" --- #
def entry_uros(node):
    """Print other word forms. e.g. valueless, valuelessness"""

    for elm in node.iterdescendants():
        if elm.tag == "span" and elm.attrib["class"] == "fw-bold ure":
            console.print(f"[{webster_color.bold} {webster_color.wf}]{elm.text}", end = " ")

        if elm.tag == "span" and elm.attrib["class"] == "fw-bold fl":
            console.print(f"[{webster_color.bold} {webster_color.wf_type}]{elm.text}", end = "\n")


# --- parse class "row headword-row header-ins" --- #
def row_headword_row_header_ins(node):
    """Print verb types. e.g. valued; valuing"""

    children = node.getchildren()[0][0]
    for child in children:
        if child.attrib["class"] == "il  il-badge badge mw-badge-gray-100":
            console.print(f"[{webster_color.bold} {webster_color.italic} {webster_color.wt}]{child.text}", end="")
        else:
            console.print(f"[{webster_color.wt}]{child.text}", end="")

    print()


# --- parse class "dictionary-entry-[number]" --- #
def dictionary_entry(node, head):
    """Print one entry of the word and its attributes like plural types, pronounciations, tenses, etc."""

    # if head == 1:
    #     print()
    # else:
    #     print("\n")
    print()

    for elm in node.iterchildren():
        try: 
            if elm.attrib["class"]:
                if elm.attrib["class"] == "row entry-header":
                    row_entry_header(elm)

                if elm.attrib["class"] == "row headword-row header-ins":
                    row_headword_row_header_ins(elm) 

                if elm.attrib["class"] == "vg":
                    vg(elm)

                if elm.attrib["class"] == "entry-uros ":
                    entry_uros(elm)
        except:
            continue


    # for elm in node.iterdescendants():
    #     try:
    #         has_word = ( "hword")
    #         has_type = (elm.attrib["class"] == "important-blue-link")
    #         has_lb = (elm.attrib["class"] == "lb")
    #     except KeyError:
    #         continue
    #     else:
    #         if has_word:
    #             word = list(elm.itertext())[0]
    #             console.print(f"[bold #3C8DAD on #DDDDDD]{word}", end="")
    #         if has_type:
    #             console.print(f" [red] {elm.text}", end="")
    #         if has_lb:
    #             console.print(f"[red] {elm.text}", end="")


# --- Entry point of all prints of a word found ---
def parse_and_print(nodes, res_url):
    """Parse and print different sections for the word."""

    logger.debug(f"{OP[4]} the parsed result of {res_url}")

    # A page may have multiple word forms, e.g. "give away", "giveaway"
    global word_entries
    head = 1

    for node in nodes:
        try:
            attr = node.attrib["id"]
        except KeyError:
            attr = node.attrib["class"]

        if "dictionary-entry" in attr:
            dictionary_entry(node, head)
            head += 1

        if attr == "phrases":
            phrases(node)

        if attr == "nearby-entries":
            nearby_entries(node)

        if attr == "synonyms":
            synonyms(node)

        if attr == "on-web read-more-content-hint-container":
            examples(node, word_entries)

        if attr == "related-phrases":
            related_phrases(node, word_entries)

    dict_name = "The Merriam-Webster Dictionary"
    console.print(f"\n[{webster_color.dict_name}]{dict_name}", justify="right")

    # global res_word
    # if words:
    #     res_word = words[0]


#[test]
# value
# big
# run way
# give away
# take on
