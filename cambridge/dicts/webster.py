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


        result = tree.xpath("//*[@id='dictionary-entry-1']/div[1]/div/div[1]/h1/text()")
        if not result:
            result = tree.xpath("//*[@id='dictionary-entry-1']/div[1]/div/div/h1/span/text()")

        global res_word
        res_word = result[0]

        ## NOTE: [only for debug]
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
                word = "".join(list(elm.itertext()))
                console.print(f"[{webster_color.bold} {webster_color.italic} {webster_color.nearby_em}]{word}", end="\n")

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

    for elm in node.iterdescendants():
        try:
            has_title = (elm.tag == "h2") # "Synonyms"
            has_label = (elm.tag == "p") and (elm.attrib["class"] == "function-label") # "Noun"
            has_syn = (elm.tag == "ul") # synonym list
        except KeyError:
            continue
        else:
            if has_title:
                console.print(f"[{webster_color.bold} {webster_color.syn_title}]{elm.text}", end=" ")

            if has_label:
                console.print(f"\n[{webster_color.syn_label} {webster_color.bold}]{elm.text}")

            if has_syn:
                children = elm.getchildren()
                total_num = len(children)
                
                for index, child in enumerate(children):
                    syn = "".join(list(child.itertext())).strip()
                    if index != (total_num - 1):
                        console.print(f"[{webster_color.syn_item}]{syn},", end=" ")
                    else:
                        console.print(f"[{webster_color.syn_item}]{syn}", end=" ")


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

    print()
    children = node.getchildren()[1]
    for child in children:
        try:
            if child.attrib["class"] == "drp":
                if child.getnext().tag == "span":
                    console.print(f"[{webster_color.ph_item} {webster_color.bold}]{child.text}", end = "")
                else:
                    console.print(f"[{webster_color.ph_item} {webster_color.bold}]{child.text}", end = "\n")

            if child.attrib["class"] == "vg":
                vg(child)

        except KeyError:
            for i in child.getchildren():
                if i.attrib["class"] == "vl":
                    print_or_badge(i.text)
                else:
                    console.print(f"[{webster_color.ph_item} {webster_color.bold}]{i.text}", end = "\n")


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


###########################################
# parse and print dictionary-entry-[number] 
###########################################

# --- parse class "vg" --- #
def dtText(node, ancestor_attr, count):
    texts = list(node.itertext())

    if count != 1:
        format_basedon_ancestor(ancestor_attr, prefix="\n")

    for text in texts:
        if text == " ":
            continue

        if text == ": ":
            text = text.strip()

        if text == " see also ":
            print_meaning_badge(text.strip())
            continue

        if text == " see ":
            print_meaning_badge("->" + text.strip())
            continue

        if "sense " in text:
            for t in text:
                if t.isnumeric():
                    text_new = " " + text
                    print_meaning_content(text_new, end="")
                    break
        else:
            print_meaning_content(text, end="")

    console.print("", end = " ")


def ex_sent(node, ancestor_attr):
    format_basedon_ancestor(ancestor_attr, prefix="\n")

    console.print(f"[{webster_color.accessory} {webster_color.bold}]|", end="")

    for text in node.itertext():
        if text.strip():
            console.print(f"[{webster_color.meaning_sentence}]{text}", end = "")
    
    
def sub_content_thread(node, ancestor_attr):
    children = node.getchildren()
    for child in children:
        attr = child.attrib["class"]

        if ("ex-sent" in attr) and ("aq has-aq" not in attr):
            ex_sent(child, ancestor_attr)

        if "vis" in attr:
            elm = child.getchildren()[0].getchildren()[0]
            elm_attr = elm.attrib["class"]
            if ("ex-sent" in elm_attr) and ("aq has-aq" not in elm_attr):
                ex_sent(elm, ancestor_attr)
            

def dt(node, ancestor_attr, self_attr):
    children = node.getchildren()
    dtText_count = 1

    for child in children:
        child_attr = child.get("class")
        if child_attr is not None:
            if child_attr == "sd": # label before meaning content
                if self_attr == "sdsense":
                    format_basedon_ancestor(ancestor_attr, prefix="")
                    print_meaning_badge(child.text)
                else:
                    print_meaning_badge(child.text)
            if child_attr == "dtText":
                dtText(child, ancestor_attr, dtText_count)   # only meaning text
                dtText_count += 1
            if child_attr == "uns":
                if child.getprevious() is not None and child.getprevious().attrib["class"] == "sub-content-thread":
                    print()
                elms = child.getchildren()[0].getchildren()
                for elm in elms:
                    if elm.attrib["class"] == "unText":
                        text = "".join(list(elm.itertext())).strip()
                        if "mdash" in elm.getprevious().attrib["class"]:
                            print_meaning_badge(text)
                        else:
                            format_basedon_ancestor(ancestor_attr, prefix="")
                            print_meaning_badge(text)
                    if elm.attrib["class"] == "sub-content-thread":
                        sub_content_thread(elm, ancestor_attr)
            if child_attr == "sub-content-thread":
                sub_content_thread(child, ancestor_attr)  # example under the meaning

    print()
            

def sense(node, attr, parent_attr, ancestor_attr):
    children = node.getchildren()

    # meaning without any sign
    if attr == "sense  no-subnum":
        sense_content = children[0] # class "sense-content w-100"

    # meaning with "1" + "a"
    if attr == "sense has-sn has-num":
        sn = children[0].getchildren()[0].text
        if "has-subnum" in ancestor_attr and "sb-0" not in parent_attr:
            console.print(f"  [{webster_color.bold} {webster_color.meaning_letter}]{sn}", end = " ")
        else:
            console.print(f"[{webster_color.bold} {webster_color.meaning_letter}]{sn}", end = " ")

        sense_content = children[1]  # class "sense-content w-100"

    # meaing with only "b" or "1" + "a" + "(1)", or "1" + "a"
    if attr == "sense has-sn": 
        sn = children[0].getchildren()[0].text

        if ("has-subnum" in ancestor_attr and "sb-0" in parent_attr) or ("no-sn letter-only" in ancestor_attr):
            console.print(f"[{webster_color.bold} {webster_color.meaning_letter}]{sn}", end = " ")
        else:
            console.print(f"  [{webster_color.bold} {webster_color.meaning_letter}]{sn}", end = " ")

        sense_content = children[1]  # class "sense-content w-100"

    # meaning with only (2)   
    if attr == "sense has-num-only has-subnum-only":
        console.print(f"    ", end = "")
        sense_content = children[1]  # class "sense-content w-100"

    # meaning with only number
    if attr == "sense has-sn has-num-only":
        sense_content = children[1]  # class "sense-content w-100"

    elms = sense_content.getchildren()
    for elm in elms:
        elm_attr = elm.get("class")
        if elm_attr is not None:
            if "badge" in elm_attr:
                text = "".join(list(elm.itertext())).strip()
                print_meaning_badge(text)

            if elm_attr == "dt " or elm_attr == "dt hasSdSense" or elm_attr == "sdsense":
                dt(elm, attr, elm_attr)

            if elm_attr == "et":
                texts = list(elm.itertext())
                for index, text in enumerate(texts):
                    if index == 0:
                        text = text.replace("\n", "")
                        print(text, end="")  # print_meaning_content not work, not print anything
                    elif index == len(texts) - 1 and index != 0:
                        print_meaning_content(text, end=" ")
                    else:
                        print_meaning_content(text, end="")
        else:
            for i in elm.iterchildren():
                if i.get("class") == "vl":
                    print_meaning_badge(i.text.strip())                
                else:
                    print_meaning_content(i.text, end=" ")


def sb_entry(node, parent_attr):
    child = node.getchildren()[0]
    attr = node.attrib["class"]         # "sb-0 sb-entry"
    child_attr = child.attrib["class"]  # "sense has-sn" or "pseq no-subnum"
    if "pseq" in child_attr:
        elms = child.getchildren()[0].getchildren()
        for e in elms:
            e_attr = e.attrib["class"]  # "sense has-sn"
            sense(e, e_attr, attr, parent_attr)        # sense(child, "sense has-sn", "sb-0 sb-entry", "....")
    else:
        sense(child, child_attr, attr, parent_attr)    # sense(child, "sense has-sn", "sb-0 sb-entry, "sb has-num has-let ms-lg-4 ms-3 w-100")


def vg_sseq_entry_item(node):
    """Print one meaning of one entry(noun entry, adjective entry, or verb entry and so forth). e.g. 1: the monetary worth of something."""

    children = node.getchildren()
    for child in children:
        attr = child.attrib["class"]
        # print number label if any
        if attr == "vg-sseq-entry-item-label":
            console.print(f"[{webster_color.bold} {webster_color.meaning_num}]{child.text}", end=" ")

        # print meaning content
        if "ms-lg-4 ms-3 w-100" in attr:
            for c in child.iterchildren():
                if c.getchildren()[0].attrib["class"] == "sen has-num-only":
                    print_meaning_badge(c.getchildren()[0][1].text)
                    print()
                    continue
                    
                # print class "sb-0 sb-entry", "sb-1 sb-entry" ...
                sb_entry(c, attr) 


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
            console.print(f"[{webster_color.tran}]{e.text}")


# --- parse class "row entry-header" --- #
def entry_header_content(node):
    """Print entry header content. e.g. value 1 of 3 noun"""

    for elm in node.iterchildren():
        if elm.tag == "h1" or elm.tag == "p":
            word = "".join(list(elm.itertext()))
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
                    print_pron(i, end="\n")


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

    children = node.getchildren()[0].getchildren()[0]
    for child in children:
        attr = child.attrib["class"]
        if attr == "il  il-badge badge mw-badge-gray-100":
            console.print(f"[{webster_color.bold} {webster_color.italic} {webster_color.wt}]{child.text.strip()}", end=" ")
        elif attr == "prt-a":
            print_pron(child, end="")
        elif attr == "il ":
            print_or_badge(child.text)
        else:
            console.print(f"[{webster_color.wt}]{child.text}", end="")

    print()


# --- parse class "dxnls" --- #
def see_also(node):
    """Print seealso section."""

    texts = list(node.itertext())
    for text in texts:
        text = text.strip()
        if not text:
            continue
        if text == "see also":
            console.print(f"[{webster_color.bold} {webster_color.sa_title}]{text}", end = " ")
        else:
            console.print(f"[{webster_color.sa_content}]{text}")


# --- parse class "dictionary-entry-[number]" --- #
def dictionary_entry(node):
    """Print one entry of the word and its attributes like plural types, pronounciations, tenses, etc."""

    print()

    for elm in node.iterchildren():
        try: 
            if elm.attrib["class"]:
                if "row entry-header" in elm.attrib["class"]:
                    row_entry_header(elm)

                if elm.attrib["class"] == "row headword-row header-ins":
                    row_headword_row_header_ins(elm) 

                if elm.attrib["class"] == "vg":
                    vg(elm)

                if elm.attrib["class"] == "entry-uros ":
                    entry_uros(elm)

                if elm.attrib["class"] == "dxnls":
                    see_also(elm)
                
                if elm.attrib["class"] == "mt-3":
                    badge = elm.getchildren()[0]  # class with "badge mw-badge"
                    print_meaning_badge(badge.text)
                    print()

        except:
            continue


##############################
# --- print abstractions --- #
##############################

def print_meaning_badge(text, end=" "):
    console.print(f"[{webster_color.italic} {webster_color.meaning_badge}]{text}", end=end)


def print_meaning_content(text, end=""):
    console.print(f"[{webster_color.meaning_content}]{text}", end=end)


def format_basedon_ancestor(ancestor_attr, prefix="", suffix=""):
    console.print(prefix, end="")
    if ancestor_attr == "sense has-sn has-num-only":
        console.print(f"  ", end=suffix)
    if ancestor_attr == "sense has-sn has-num" or ancestor_attr == "sense has-sn":
        console.print(f"    ", end=suffix)
    if ancestor_attr == "sense  no-subnum":
        console.print(f"", end=suffix)
    if ancestor_attr == "sense has-num-only has-subnum-only":
        console.print(f"    ", end=suffix)

def print_pron(node, end=""):
    pron = list(node.itertext())[1].strip()
    console.print(f"[{webster_color.eh_pron}]|{pron}|", end=end)

def print_or_badge(text):
    console.print(f"[{webster_color.badge}]{text}", end = "")


#####################################################
# --- Entry point of all prints of a word found --- #
#####################################################

def parse_and_print(nodes, res_url):
    """Parse and print different sections for the word."""

    logger.debug(f"{OP[4]} the parsed result of {res_url}")

    # A page may have multiple word forms, e.g. "give away", "giveaway"
    global word_entries

    for node in nodes:
        try:
            attr = node.attrib["id"]
        except KeyError:
            attr = node.attrib["class"]

        if "dictionary-entry" in attr:
            dictionary_entry(node)

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
    console.print(f"[{webster_color.dict_name}]{dict_name}", justify="right")
