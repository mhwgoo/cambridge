import sys
import asyncio
from lxml import etree # type: ignore

from .console import c_print
from .utils import fetch, get_request_url, decode_url, OP, DICT, has_tool, get_suggestion, get_suggestion_by_fzf, get_wod_selection, get_wod_selection_by_fzf, quit_on_no_result, cancel_on_error, cancel_on_error_without_retry, remove_extra_spaces, is_last, get_clean_text_from_fat_node
from .log import logger
from .cache import check_cache, save_to_cache, get_cache, save_to_cache_examples_on_the_web, save_to_cache_metadata_mw, get_cache_metadata_mw
from . import camb
from . import color

WEBSTER_BASE_URL = "https://www.merriam-webster.com"
WEBSTER_DICT_BASE_URL = WEBSTER_BASE_URL + "/dictionary/"
# WEBSTER_SENT_BASE_URL = WEBSTER_BASE_URL + "/sentences/"
WEBSTER_WORD_OF_THE_DAY_URL = WEBSTER_BASE_URL + "/word-of-the-day"
WEBSTER_WORD_OF_THE_DAY_URL_CALENDAR = WEBSTER_BASE_URL + "/word-of-the-day/calendar"

parser = etree.HTMLParser(remove_blank_text=True, remove_comments=True, remove_pis=True)

async def search_webster(tg, session, input_word, is_fresh=False, no_suggestions=False, req_url=None):
    if req_url is None:
        req_url = get_request_url(WEBSTER_DICT_BASE_URL, input_word, DICT.MERRIAM_WEBSTER.name)

    if is_fresh:
        tg.create_task(fresh_run(tg, session, input_word, no_suggestions, req_url))
    else:
        response_url = await check_cache(input_word, req_url)
        if response_url is None:
            logger.debug(f'{OP.NOT_FOUND.name} "{input_word}" in cache')
            tg.create_task(fresh_run(tg, session, input_word, no_suggestions, req_url))
        else:
            if DICT.CAMBRIDGE.name.lower() in response_url:
                tg.create_task(camb.cache_run(response_url))
            else:
                tg.create_task(cache_run(tg, response_url))


#TODO examples
async def cache_run(tg, response_url_from_cache):
    response_word, response_text = await get_cache(response_url_from_cache)
    c_print(f'#[#757575]{OP.FOUND.name} "{response_word}" from {DICT.MERRIAM_WEBSTER.name} in cache. You can add "-f" to fetch the {DICT.CAMBRIDGE.name} dictionary')
    logger.debug(f'{OP.FOUND.name} "{response_word}" from {DICT.MERRIAM_WEBSTER.name} in cache')
    logger.debug(f"{OP.PARSING.name} text cached from {response_url_from_cache}")
    html_tree = etree.HTML(response_text, parser)
    entries = html_tree.xpath('//div[contains(@id, "dictionary-entry")]')
    for i, entry in enumerate(entries):
        dictionary_entry(i, entry)

    meta_data = await get_cache_metadata_mw(response_word)
    if meta_data is not None:
        tg.create_task(metadata(tg, meta_data, None))
    else:
        phrases = ""
        synonyms = ""
        antonyms = ""
        related_phrases = ""
        nearby_entries = ""
        meta_data = (response_word, phrases, synonyms, antonyms, related_phrases, nearby_entries)
        tg.create_task(metadata(tg, meta_data, html_tree))


async def fresh_run(tg, session, input_word, no_suggestions, req_url):
    response = await fetch(session, req_url)
    status = response.status
    if status != 404 and status != 200:
        print(f"Got unexpected status {status} from {req_url}")
        sys.exit(2)

    response_url = str(response.real_url)
    response_text = None
    attempt = 0
    while True:
        try:
            response_text = await response.text()
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

    if response_text is None:
        print(f"UNABLE to get the document from {req_url}, perhaps due to unstable network. Please try again.")
        sys.exit(2)

    html_tree = etree.HTML(response_text, parser)

    if status == 404:
        if no_suggestions:
            sys.exit(-1)
        logger.debug(f'{OP.NOT_FOUND.name} "{input_word}" at {response_url}')
        logger.debug(f"{OP.PARSING.name} out suggestions at {response_url}")
        suggestions = html_tree.xpath('//div[@class="row m-0"][1]/p[@class="col-6 col-md-4 spelling-suggestion-col "]/a/text()')
        tg.create_task(parse_suggestions(tg, suggestions, session, input_word))

    elif status == 200:
        logger.debug(f'{OP.FOUND.name} "{input_word}" in {DICT.MERRIAM_WEBSTER.name} at {response_url}')
        entries = html_tree.xpath('//*[@id="left-content"]/div[contains(@id, "-entry") and (@class!= "entry-word-section-container-supplemental" or not(@class))]')
        if len(entries) == 0:
            quit_on_no_result(DICT.MERRIAM_WEBSTER.name, is_spellcheck=True)
        elif entries[0].get("class") is None:
            suggestions = []
            for e in entries:
                suggestion = "".join(list(e.getprevious().itertext())).replace("\n\n", " |").strip()
                meaning = "".join(list(e.itertext())).replace("\n", "").replace("See the full definition", "").strip()
                suggestion_and_meaning = "".join((suggestion + meaning).split("  "))
                suggestions.append(suggestion_and_meaning)
            tg.create_task(parse_suggestions(tg, suggestions, session, input_word))
        else:
            # NOTE:
            # Globals aren't safe with python asyncio, so the following variables have to be made local and passed around across functions and coroutines.
            # Asyncio runs tasks cooperatively on a single thread by default, so simultaneous CPU-level concurrent access to a global from multiple tasks won't occur, but logical race conditions can still happen when tasks interleave at await points.
            response_word = decode_url(response_url).split("/")[-1]
            word_entries = [] # A page may have multiple word entries, e.g. "runaway" as noun, "runaway" as adjective, "run away" as verb
            word_types = []
            word_variants_not_nested = []
            word_variants_nested = []
            word_forms_not_nested = []
            word_forms_nested = []
            entries_text = ""
            phrases = ""
            synonyms = ""
            antonyms = ""
            related_phrases = ""
            nearby_entries = ""
            meta_data = (response_word, phrases, synonyms, antonyms, related_phrases, nearby_entries)

            for i, entry in enumerate(entries):
                word_entry, word_type, word_variants, word_forms = dictionary_entry(i, entry)
                word_entries.append(word_entry)
                if word_type:
                    word_types.append(word_type)
                if word_variants:
                    word_variants_not_nested += word_variants
                word_variants_nested.append(word_variants)

                if word_forms:
                    word_forms_not_nested += word_forms
                word_forms_nested.append(word_forms)

                if "/" in word_entry:
                    va_1 = ""
                    va_2 = ""

                    words = word_entry.split(" ")
                    for word in words:
                        if "/" not in word:
                            va_1 += word + " "
                            va_2 += word + " "
                        else:
                            va_1 += word.split("/")[0] + " "
                            va_2 += word.split("/")[1] + " "
                    word_variants_not_nested.append(va_1.strip())
                    word_variants_not_nested.append(va_2.strip())


                text = etree.tostring(entry).decode('utf-8')
                cleaned_text = remove_extra_spaces(text)
                entries_text += cleaned_text

            word_types_and_forms = dict(zip(word_types, word_forms_nested))
            word_types_and_variants = dict(zip(word_types, word_variants_nested))

            for wt in word_types:
                if  "abbreviation" in wt:
                    del word_types_and_forms[wt]
                    del word_types_and_variants[wt]

            tg.create_task(metadata(tg, meta_data, html_tree))
            tg.create_task(examples(tg, html_tree, response_word, set(word_entries), word_variants_not_nested, word_forms_not_nested))
            tg.create_task(save_to_cache(input_word, response_word, response_url, entries_text))

            print("\n_______")
            print("response_word: ", response_word)
            print("word_entries: ", word_entries)
            print(f"word_variants_not_nested: {word_variants_not_nested} || word_variants_nested: {word_variants_nested}")
            print(f"word_forms_not_nested: {word_forms_not_nested} || word_forms_nested: {word_forms_nested}")
            print("word_types: ", word_types)
            print("word_types_and_variants: ", word_types_and_variants)
            print("word_types_and_forms: ", word_types_and_forms)
            # _______
            # response_word:  can
            # word_entries:  ['can', 'can', 'can', 'can', 'can']
            # word_variants_not_nested: ['canful', 'canner', 'Canad'] || word_variants_nested: [[], ['canful'], ['canner'], [], ['Canad']]
            # word_forms_not_nested: ['could', 'can', 'cans', 'canned', 'canning'] || word_forms_nested: [['could', 'can'], ['cans'], ['canned', 'canning'], [], []]
            # word_types:  ['verb (1)', 'noun', 'verb (2)', 'abbreviation (1)', 'abbreviation (2)']
            # word_types_and_variants:  {'verb (1)': [], 'noun': ['canful'], 'verb (2)': ['canner']}
            # word_types_and_forms:  {'verb (1)': ['could', 'can'], 'noun': ['cans'], 'verb (2)': ['canned', 'canning']}


def dictionary_entry(num, node):
    logger.debug(f"STARTING to parse and print entry {num + 1}...")
    print()
    word_entry = ""
    word_type = ""
    word_variants = []
    word_forms = []

    for elm in node.iterchildren():
        elm_attr = elm.get("class")
        if elm_attr is None:
            continue

        elif "row entry-header" in elm_attr:
            for e in elm.iterchildren():
                if e.attrib["class"] == "col-12":
                    for i in e.iterchildren():
                        # Print entry header content. e.g. value 1 of 3 noun
                        if "entry-header-content" in i.attrib["class"]:
                            for j in i.iterchildren():
                                if j.tag == "h1" or j.tag == "p":
                                    word = get_clean_text_from_fat_node(j)
                                    word_entry = word.lower()
                                    end = "" if j.getnext() is None else " "
                                    c_print(f"#[{color.eh_h1_word} bold]{word}", end=end)
                                elif j.tag == "span":
                                    num = " ".join(list(j.itertext()))
                                    end = "" if j.getnext() is None else " "
                                    print(num, end=end)
                                elif j.tag == "h2":
                                    word_type = " ".join(list(j.itertext()))
                                    c_print(f"#[bold {color.eh_word_type}]{word_type}", end="")

                            print()
                        # Print the pronounciation. e.g. val·ue |ˈval-(ˌ)yü|"""
                        elif "row entry-attr" in i.attrib["class"]:
                            for j in i.iterchildren():
                                if "col word-syllables-prons-header-content" in j.attrib["class"]:
                                    for p in j.iterchildren():
                                        if p.tag == "span" and p.attrib["class"] == "word-syllables-entry":
                                            print(f"{p.text}", end=" ")
                                        elif p.tag == "span" and "prons-entries-list-inline" in p.attrib["class"]:
                                            for i, x in enumerate(p):
                                                end = "\n" if x.getnext() is None else " "
                                                if i == 0:
                                                    print_pron(x, True, end=end)
                                                else:
                                                    print_pron(x, False, end=end)

        # Print verb types. e.g. valued; valuing
        elif elm_attr == "row headword-row header-ins":
            children = elm.getchildren()[0].getchildren()[0]
            if "ins" in children.attrib["class"]:
                word_forms = print_class_ins(children)
                print()

        # Print word variants. e.g. premise variants or less commonly premiss
        elif elm_attr == "row headword-row header-vrs":
            node = elm.getchildren()[0].getchildren()[0] # class "entry-attr vrs"
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
                                end = " " if child.getnext() is not None else ""
                                if child.text is None:
                                    for i in child:
                                        print_class_va(i.text, end=end)
                                        word_variants.append(i.text)
                                else:
                                    print_class_va(child.text, end=end)
                                    word_variants.append(child.text)
                            elif child.tag == "a" and "play-pron-v2" in attr:
                                print_pron(child, False)
                            else:
                                continue

            print()

        elif elm_attr == "vg":
            vg(elm)

        # Print other word forms. e.g. valueless, valuelessness
        elif "entry-uros" in elm_attr:
            for child in elm.iterchildren():
                for e in child.iterdescendants():
                    attr = e.get("class")
                    if attr is not None:
                        if e.tag == "span" and "fw-bold ure" in attr:
                            word_variants.append(e.text)
                            c_print(f"#[bold {color.wf}]{e.text}", end = " ")

                        elif e.tag == "span" and "fw-bold fl" in attr:
                            e_next = e.getnext()
                            if e_next is not None and e_next.get("class") == "ins":
                                end = "\n"
                            elif e_next is not None and "badge" in e_next.get("class"):
                                end = " "
                            else:
                                end = ""
                            c_print(f"#[{color.eh_word_type}]{e.text}", end=end)

                        elif "ins" in attr:
                            print("", end="")
                            print_class_ins(e)

                        elif "sl badge" in attr:
                            text = "".join(list(e.itertext())).strip()
                            prev = e.getprevious()
                            if prev is not None and prev.get("class") == "vrs":
                                print_meaning_badge(" " + text)
                            else:
                                print_meaning_badge(text)

                        elif "utxt" in attr:
                            for i in e.iterchildren():
                                sub_attr = i.get("class")
                                if sub_attr is not None and "sub-content-thread" in sub_attr:
                                    sub_content_thread(i, "")

                        elif "prons-entries-list d-inline-flex" in attr:
                            for i, x in enumerate(e):
                                end = "\n" if e.getnext() is None else " "
                                if i == 0:
                                    print_pron(x, True, end=end)
                                else:
                                    print_pron(x, False, end=end)

                        elif "vrs" in attr:
                            # can't get css element ::before.content like "variants" in the word "duel"
                            child = e.getchildren()[0]
                            for c in child.iterchildren():
                                attr_c = c.get("class")
                                if attr_c == "il " or attr_c == "vl":
                                    print_or_badge(c.text)
                                elif attr_c == "va":
                                    if c.text is None:
                                        for i in child:
                                            print_class_va(i.text)
                                    else:
                                        end = " " if (c.getnext() is not None or e.getnext() is not None) else ""
                                        print_class_va(c.text, end=end)

                print()

        # Print dxnls section, such as 'see also', 'compare' etc.
        elif elm_attr == "dxnls":
            texts = list(elm.itertext())
            for text in texts:
                text = text.strip()
                if not text:
                    continue
                if text == "see also":
                    c_print(f"#[bold {color.dxnls_content}]{text.upper()}", end = " ")
                elif text == "compare":
                    c_print(f"#[bold {color.dxnls_content}]{text.upper()}", end = " ")
                elif text == ",":
                    print_meaning_content(text, end=" ")
                else:
                    print_meaning_content(text, end="")
            print()

        elif elm_attr == "mt-3":
            badge = elm.getchildren()[0] # class "lbs badge mw-badge-gray-100 text-start text-wrap d-inline"
            print_header_badge(badge.text, end="\n")

        elif elm_attr == "cxl-ref":
            for i in elm.iterdescendants():
                i_attr = i.get("class")
                if i.tag == "span" and i_attr == "cxl":
                    print_meaning_badge(i.text, end=" ")
                elif i.tag == "span" and i_attr == "text-uppercase":
                    print_meaning_content(i.text.upper(), end="")
            print()

    # print("\n_______from entry")
    # print("word_entry: ", word_entry)
    # print("word_type: ", word_type)
    # print("word_variants: ", word_variants)
    # print("word_forms: ", word_forms)

    return word_entry, word_type, word_variants, word_forms


async def parse_suggestions(tg, suggestions, session, input_word):
    select_word = get_suggestion_by_fzf(suggestions, DICT.MERRIAM_WEBSTER.name) if has_tool("fzf") else get_suggestion(suggestions, DICT.MERRIAM_WEBSTER.name)
    if "|" in select_word:
        select_word = select_word.split("|")[0].strip()

    if select_word == "":
        logger.debug(f'{OP.SWITCHED.name} to {DICT.CAMBRIDGE.name}')
        tg.create_task(camb.search_cambridge(tg, session, input_word, True, False, False, None))
    else:
        logger.debug(f'{OP.SELECTED.name} "{select_word}"')
        tg.create_task(search_webster(tg, session, select_word, False, False, None))


async def print_example(num, is_last, example, tags, word_entries):
    # logger.debug(f"STARTING to print #{num} example...")
    if num == 1:
        c_print(f"\n#[{color.eg_title} bold]Recent Examples on the Web", end="")
    c_print(f"\n#[{color.accessory}]|", end="")

    example = example.split()
    example_len = len(example)

    #FIXME
    for word_entry in word_entries: # e.g. "make a dent", "blue blood", "hotspot", "tone", "ghost", "tongue-in-cheek", "tongue in cheek"
        word_num = len(word_entry.split())
        i = 0
        while i < example_len:
            end = "" if i == example_len - 1 else " "
            example_range = " ".join(example[i : i + word_num])
            example_range_lowercase = example_range.lower()
            if word_entry in example_range_lowercase or example_range_lowercase in tags:
                if not example_range[-1].isalpha():
                    c_print(f"#[{color.eg_word} bold]{example_range[:-1]}#[{color.eg_sentence}]{example_range[-1]}", end=end)
                else:
                    c_print(f"#[{color.eg_word} bold]{example_range}", end=end)
                i = i + word_num
            else:
                c_print(f"#[{color.eg_sentence}]{example[i]}", end=end)
                i = i + 1

    if is_last:
        print()


async def examples(tg, html_tree, response_word, word_entries, word_variants, word_forms):
    logger.debug(f"STARTING to parse examples...")
    nodes = html_tree.xpath('//div[@id="examples"]/div[@class="content-section-body"]/div[contains(@class,"on-web-container")]/div[contains(@class,"on-web")]/span[contains(@class, "sub-content-thread ex-sent sents")]/span[contains(@class, "t has-aq")]')
    tags = set()
    for i in (word_entries, word_variants, word_forms):
        for j in i:
            if j != response_word:
                tags.add(j)

    examples = set()
    if len(nodes) != 0:
        for node in nodes:
            example = "".join(list(node.itertext()))
            examples.add(example)
    tags_to_cache = ",".join(tags)
    length = len(examples)
    for i, example in enumerate(examples):
        tg.create_task(print_example(i+1, is_last(i, length), example, tags, word_entries))
        tg.create_task(save_to_cache_examples_on_the_web(i+1, example, response_word, tags_to_cache))


async def print_metadata(title, text):
    logger.debug(f'STARTING to print metadata about "{title}"...')
    if title == "Phrases":
        phrases = text.split("#")
        for phrase in phrases:
            subphrases = phrase.split(":")
            # FIMEME "fish to fry"
            for i, subphrase in enumerate(subphrases):
                if i == 0:
                    names = subphrase.split("[")
                    c_print(f"\n#[{color.ph_item}bold]{names[0].replace("—used", " -> used")}", end="")
                    if len(names) > 1:
                        print_or_badge("[" + names[1])
                else:
                    if "|" not in subphrase:
                        c_print(f"\n#[{color.meaning_content}]:{subphrase}", end="")
                    else:
                        parts = subphrase.split("|")
                        for i, part in enumerate(parts):
                            if i == 0:
                                c_print(f"\n#[{color.meaning_content}]:{part}", end="")
                            else:
                                c_print(f"\n#[{color.meaning_sentence}]|{part}", end="")
        print("", end="\n")

    else:
        c_print(f"#[bold {color.syn_title}]{title}", end="\n")
        if title.lower() == "synonyms" and "[" == text[0]:
           subtexts = text.split(", [")
           for i, subtext in enumerate(subtexts):
               if i == 0:
                   c_print(f"#[{color.syn_item}]{subtext}", end="\n")
               else:
                   c_print(f"#[{color.syn_item}][{subtext}", end="\n")
        else:
            c_print(f"#[{color.syn_item}]{text}", end="\n")


async def metadata(tg, meta_data, html_tree=None):
    response_word, phrases, synonyms, antonyms, related_phrases, nearby_entries = meta_data
    if html_tree is not None:
        logger.debug(f"STARTING to parse metadata...")
        nodes = html_tree.xpath('//*[@id="left-content"]/div[@id="phrases" or @id="nearby-entries" or @id="synonyms" or @id="related-phrases"]')
        if len(nodes) == 0:
            return
        for node in nodes:
            id_name = node.get("id")
            if id_name == "phrases":
                children = node.getchildren()[1]
                for child in children:
                    phrase_name = ""
                    phrase_meaning = ""
                    attr = child.get("class")
                    if attr == "drp":
                        phrase_name += "".join(list(child.itertext())).strip()
                    elif child.tag == "span" and attr is None:
                        phrase_name += " [" + "".join(list(child.itertext())).strip() + "]"
                    elif child.tag == "div" and attr == "vg":
                        for elm in child.iterdescendants():
                            if elm.tag == "span" and elm.get("class") is not None and ("dtText" == elm.get("class") or "un" == elm.get("class")):
                                phrase_meaning += "".join(list(elm.itertext())).strip()
                                elm_next = elm.getnext()
                                if elm_next is not None and elm_next.get("class") is not None and elm_next.get("class") == "sub-content-thread mb-3":
                                    phrase_example = "|" + "".join(list(elm_next.itertext())).strip()
                                    phrase_meaning += phrase_example
                                if "  " in phrase_meaning:
                                    phrase_meaning = "".join(phrase_meaning.split("  "))
                        phrase_meaning += "#"
                    phrases += phrase_name + phrase_meaning
                phrases = phrases.strip("#")

            elif id_name == "synonyms":
                for child in node:
                    if child.get("class") is not None and child.get("class") == "content-section-body":
                        for elm in child:
                            if elm.tag == "ul":
                                elm_pre = elm.getprevious()
                                if elm_pre is not None and elm_pre.tag == "p":
                                    synonyms += "[" + elm_pre.text + "] "
                                for li in elm:
                                    text = "".join(list(li.itertext())).strip()
                                    if "  " in text:
                                        text = "".join(text.split("  "))
                                    synonyms += text + ", "
                synonyms = synonyms.strip(", ")

            elif id_name == "related-phrases":
                for elm in node.iterdescendants():
                    if elm.tag == "a" and elm.get("class") is not None and "pb-4 pr-4 d-block" == elm.get("class"):
                        related_phrases += "".join(list(elm.itertext())).strip() + ", "
                related_phrases = related_phrases.strip(", ")

            elif id_name == "nearby-entries":
                for elm in node.iterdescendants():
                    if elm.tag == "a" and elm.get("class") is not None and "b-link" == elm.get("class"):
                        nearby_entries += elm.text + ", "
                nearby_entries = nearby_entries.strip(", ")

        tg.create_task(save_to_cache_metadata_mw(response_word, phrases, synonyms, antonyms, related_phrases, nearby_entries))

    if phrases:
        phrase_title = "Phrases"
        tg.create_task(print_metadata(phrase_title, phrases))
    if synonyms:
        synonyms_title = "Synonyms"
        tg.create_task(print_metadata(synonyms_title, synonyms))
    if related_phrases:
        related_phrases_title = f"Phrases Containing {response_word}"
        tg.create_task(print_metadata(related_phrases_title, related_phrases))
    if nearby_entries:
        nearby_entries_title = "Browse Nearby Words"
        tg.create_task(print_metadata(nearby_entries_title, nearby_entries))


def dtText(node, ancestor_attr, num_label_count):
    """Print the meaning text starting with `:`. E.g. one of the word replenish's meaning texts `: to fill or build up again`"""
    texts = list(node.itertext())

    l_words = get_word_cases(node)[0]
    u_words = get_word_cases(node)[1]

    node_pre = node.getprevious()
    node_pre_attr = None
    if node_pre is not None:
        node_pre_attr = node_pre.get("class")

    prefix = "\n " if num_label_count == 2 else "\n"

    is_format = False
    if node_pre_attr is not None and ("sub-content-thread" in node_pre_attr or node_pre_attr == "uns" or node_pre_attr == "dt "):
        format_basedon_ancestor(ancestor_attr, prefix=prefix)
        is_format = True

    for index, text in enumerate(texts):
        if text.strip("\n").strip():
            if text == ": ":
                print_meaning_content(text, end="")
            elif text in [" see also ", " see ", " compare "]: # e.g. "drag", "group"
                if is_format:
                    print_meaning_keyword(text.strip().upper())
                elif "has-sn" in ancestor_attr or "has-num" in ancestor_attr:
                    format_basedon_ancestor(ancestor_attr, prefix=prefix)
                    print_meaning_keyword(text.strip().upper())
                else:
                    print_meaning_keyword("\n" + text.strip().upper())
            elif u_words and text in u_words:
                text_new = text.upper()
                print_meaning_content(text_new, end="")
            elif l_words and text in l_words:
                text_new = (" " + text)
                print_meaning_content(text_new, end="")
            #elif index == len(texts) - 1:
            #    text = text[:-1] if text[-1] == " " else text
            #    print_meaning_content(text, end="") # e.g. creative
            else:
                print_meaning_content(text, end="")


def print_mw(text, nospace, tag):
    end = "" if nospace else " "
    bold = "" if tag == "normal" else "bold"
    c_print(f"#[{color.meaning_sentence}{bold}]{text}", end=end)


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


def get_word_faces(node):
    hl_words = []
    ems = []
    for i in node.iterdescendants():
        attr = i.get("class")
        if attr is not None:
            if i.tag == "em" and "mw" in attr:
                ems.append(i.text)
            elif i.tag == "span" and "mw" in attr and "mw_t_sp" != attr and "mw_t_gloss" != attr:
                hl_words.append(i.text)
    return hl_words, ems


def ex_sent(node, ancestor_attr, num_label_count):
    if ancestor_attr:
        format_basedon_ancestor(ancestor_attr, prefix="\n")
    else:
        print()

    if num_label_count == 2:
        print(" ", end="")

    c_print(f"#[{color.accessory}]|", end="")

    hl_words = get_word_faces(node)[0]
    ems = get_word_faces(node)[1]

    texts = list(node.itertext())
    count = len(texts)

    for index, t in enumerate(texts):
        text = t.strip("\n").strip()
        if text:
            if t in hl_words:
                if index == count - 1 or (index == count - 2 and (texts[count-1].strip("\n").strip() == "")):
                    print_mw(text, True, "hl")
                elif texts[index + 1][0].isalpha() or (texts[index + 1].strip("\n").strip() and texts[index + 1].strip("\n").strip()[0] in [",", ".", "?", "!", "-", "—"]):
                    print_mw(text, True, "hl")
                elif index != count - 2  and not texts[index + 1].strip("\n").strip() and texts[index + 2].strip("\n").strip() in ems:
                    print_mw(text, True, "hl")
                else:
                    print_mw(text, False, "hl")
            elif t in ems:
                if index != 0 and texts[index - 1].endswith(" "):
                    print("", end = " ")
                c_print(f"#[{color.meaning_sentence} bold]{text}", end = "")
                if index != (count - 1) and texts[index + 1] != " " and texts[index + 1].startswith(" ") :
                    print("", end = " ")
            else:
                if index == count - 1 or (index == count - 2 and texts[count-1].strip("\n").strip() == "") :
                    print_mw(text, True, "normal")
                elif texts[index + 1] in ems:
                    print_mw(text, True, "normal")
                elif texts[index + 1] in hl_words and (t[-1] == '"' or t[-1] == '-'):
                    print_mw(text, True, "normal")
                else:
                    print_mw(text, False, "normal")


def sub_content_thread(node, ancestor_attr, num_label_count=1):
    children = node.getchildren()
    for child in children:
        attr = child.get("class")

        if "ex-sent   t has-aq sents" == attr: # e.g. air 4a
            for i in child:
                if "d-block thread-anchor-content" in i.get("class"):
                    ex_sent(i, ancestor_attr, num_label_count)
        elif ("ex-sent" in attr) and ("aq has-aq" not in attr):
            ex_sent(child, ancestor_attr, num_label_count)
        elif "vis" in attr:
            elms = child.getchildren()
            for e in elms:
                elm = e.getchildren()[0]
                elm_attr = elm.get("class")
                if ("ex-sent" in elm_attr) and ("aq has-aq" not in elm_attr):
                    ex_sent(elm, ancestor_attr, num_label_count)


def extra(node, ancestor_attr):
    texts = list(node.itertext())

    l_words = get_word_cases(node)[0]
    u_words = get_word_cases(node)[1]

    prev = node.getprevious()
    prev_attr = ""
    if prev is not None:
        prev_attr = prev.get("class")

    for text in texts:
        text_new = text.strip("\n").strip()
        if text_new:
            if text_new == "called also" or text_new == "compare":
                prefix = "\n" if prev_attr == "sub-content-thread" else " "  # e.g. "flash-bang"
                print_meaning_keyword(prefix + text_new.upper())
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


def unText_simple(node, ancestor_attr, has_badge=True):
    if not has_badge:
        print()
        format_basedon_ancestor(ancestor_attr, prefix="")

    prefix = f"#[{color.meaning_arrow}]->"
    suffix = " "

    node_pre = node.getprevious()
    if node_pre is not None and node_pre.get("class") == "mdash mdash-silent":
        node_p_pre = node.getparent().getprevious()
        if node_p_pre is not None and node_p_pre.get("class") == "un":
            c_print(" " + prefix, end=suffix)
        else:
            c_print(prefix, end=suffix)

    bolds = get_word_faces(node)
    text_list = list(node.itertext())

    for bold in bolds:
        if bold:
            for index, t in enumerate(text_list):
                if t in bold:
                    # TODO "/" should only reset the current effect (bold), not including color.meaning_arrow
                    text_list[index] = f"#[bold]{t}#[/bold]#[{color.meaning_arrow}]"

    text = "".join(text_list).strip()
    c_print(f"#[{color.meaning_arrow}]{text}", end="")


def sense(node, attr, parent_attr, ancestor_attr, num_label_count):
    """e.g. sense(node, "sense has-sn", "sb-0 sb-entry, "sb has-num has-let ms-lg-4 ms-3 w-100", 1)"""

    sense_content = None
    children = node.getchildren()

    # meaning without any sign
    if "sense" in attr and "no-subnum" in attr:
        sense_content = children[0] # class "sense-content w-100"

    # meaning with "1" + "a"
    elif attr == "sense has-sn has-num":
        sn = children[0].getchildren()[0].text

        node_prev = node.getprevious()
        if "has-subnum" in ancestor_attr and node_prev is None and "sb-0" in parent_attr:
            c_print(f"#[bold {color.meaning_letter}]{sn}", end = " ")
        elif "has-subnum" in ancestor_attr and (node_prev is not None or parent_attr != "pseq no-subnum"):
            if num_label_count == 2:
                print(" ", end="")
            c_print(f"  #[bold {color.meaning_letter}]{sn}", end = " ")
        else:
            c_print(f"#[bold {color.meaning_letter}]{sn}", end = " ")

        sense_content = children[1] # class "sense-content w-100"

    # meaing with only "b" or "1" + "a" + "(1)", or "1" + "a"
    elif attr == "sense has-sn" or attr == "sen has-sn":
        sn = children[0].getchildren()[0].text

        if "has-subnum" in ancestor_attr and "sb-0" in parent_attr:
            c_print(f"#[bold {color.meaning_letter}]{sn}", end = " ")
        else:
            if "letter-only" in ancestor_attr:
                if "sb-0" not in parent_attr:
                    print("  ", end="")
                c_print(f"#[bold {color.meaning_letter}]{sn}", end = " ")
            else:
                if num_label_count == 2 and sn == "a":
                    if "sb-0 sb-entry" != ancestor_attr:
                        c_print(f"   #[bold {color.meaning_letter}]{sn}", end = " ")
                    else:
                        c_print(f"#[bold {color.meaning_letter}]{sn}", end = " ")
                elif num_label_count == 2:
                    c_print(f"   #[bold {color.meaning_letter}]{sn}", end = " ")
                else:
                    c_print(f"  #[bold {color.meaning_letter}]{sn}", end = " ")

        if node.tag == "span": # e.g. "knife and fork, track intransitive verb 2"
            # Intentionally take out this part from tags(), don't merge in later.
            # Because using tags() here conflicts with these same classes elsewhere with different new line or not requirements.
            # Adding extra checks as to where the node comes from in already complex tags() is not a good idea.
            for child in children[1 : ]:
                child_attr = child.get("class")
                if child_attr is not None:
                    if child_attr == "if":
                        end = "\n" if child.getnext() is None else ""
                        c_print(f"#[bold]{child.text.strip()}", end=end)
                    elif child_attr == "il ":
                        print_meaning_badge(child.text.strip(), end=" ")
                    elif "badge mw-badge-gray-100" in child_attr:
                        end = " " if child.getnext() is not None else "\n"
                        print_meaning_badge(child.text, end=end)
                else:
                    for c in child:
                        c_attr = c.get("class")
                        if c_attr == "vl":
                            print_meaning_badge(c.text.strip(), end=" ")
                        elif c_attr == "va":
                            print_class_va(c.text)
                        elif c.tag == "span" and "prons-entries-list-inline" in c_attr:
                            for x in c:
                                if x.tag == "a":
                                    print_pron(x, False)
                            print()
        else:
            sense_content = children[1]

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
    if sense_content is not None:
        tags(sense_content, attr, num_label_count)


def sb_entry(node, parent_attr, num_label_count):
    child = node.getchildren()[0]
    attr = node.attrib["class"]         # "sb-0 sb-entry"
    child_attr = child.attrib["class"]  # "sense has-sn" or "pseq no-subnum" or "sen has-sn"
    if "pseq" in child_attr:
        elms = child.getchildren()[0].getchildren()
        for e in elms:
            e_attr = e.attrib["class"]  # "sense has-sn"
            sense(e, e_attr, attr, parent_attr, num_label_count)
    elif "sense" in child_attr and child.tag != "span":
        sense(child, child_attr, attr, parent_attr, num_label_count) # e.g. sense(child, "sense has-sn", "sb-0 sb-entry, "sb has-num has-let ms-lg-4 ms-3 w-100", 1)
    elif "sen" in child_attr and child.tag == "span": # e.g. "knife and fork"
        sense(child, child_attr, attr, parent_attr, num_label_count)


def tags(node, ancestor_attr, num_label_count):
    has_badge = True
    has_et = False
    has_dtText = False
    no_print = False
    has_sense2 = False
    sense2_has_blank_span = False

    for elm in node.iterdescendants():
        elm_attr = elm.get("class")
        parent = elm.getparent()
        parent_attr = parent.get("class")

        if elm_attr is not None:
            if "sn sense-2" == elm_attr:
                has_sense2 = True
                if elm.getnext() is not None and elm.getnext().get("class") is None:
                    sense2_has_blank_span = True
            if "badge " in elm_attr and "pron" not in elm_attr:
                prev = elm.getprevious()
                if prev is not None and prev.get("class") is None:
                    print("", end=" ")
                text = "".join(list(elm.itertext())).strip()
                if elm.getnext() is not None:
                    print_meaning_badge(text, end=" ")
                elif "spl plural badge" in elm_attr or "lb badge" in elm_attr or "sl badge" in elm_attr:
                    end = "\n" if has_sense2 else ""
                    print_meaning_badge(text, end=end)
                else:
                    print_meaning_badge(text, end="")

            elif elm_attr == "et":
                et(elm)
                has_et = True

            elif elm_attr == "il ":
                print_meaning_badge(elm.text.strip(), end=" ")

            elif elm_attr == "if":
                print_class_if(elm.text)

            elif elm_attr == "sgram":
                print_class_sgram(elm)

            elif elm_attr == "vl":
                print_meaning_badge(elm.text[1 : ])

            elif elm_attr == "va":
                print_class_va(elm.text.strip())

            elif elm_attr == "sd":
                parent_prev = parent.getprevious()
                if parent_prev is not None and "hasSdSense" in parent_prev.get("class"):
                    print()
                if parent_attr is not None and parent_attr == "sdsense":
                    format_basedon_ancestor(ancestor_attr, prefix="")

                if num_label_count == 2:
                    print(" ", end="")

                print_meaning_badge(elm.text, end=" ")

            elif elm_attr == "dtText":
                dtText(elm, ancestor_attr, num_label_count) # only meaning text
                has_dtText = True

            elif "sub-content-thread" in elm_attr:
                sub_content_thread(elm, ancestor_attr, num_label_count) # example under the meaning
                has_badge = False

            elif elm_attr == "ca":
                extra(elm, ancestor_attr)

            elif elm_attr == "unText":
                unText_simple(elm, ancestor_attr, has_badge)

            elif elm.tag == "a" and "play-pron-v2" in elm_attr:
                print_pron(elm, False)

            elif elm_attr == "sn sense-2":
                no_print = True
    if (not has_et and not no_print) or (has_et and has_dtText) or (has_sense2 and sense2_has_blank_span):
        print()


def vg_sseq_entry_item(node):
    """Print one meaning of one entry(noun entry, adjective entry, or verb entry and so forth). e.g. 1: the monetary worth of something."""

    num_label_count = 1
    children = node.getchildren()
    for child in children:
        attr = child.attrib["class"]
        # print number label if any
        if attr == "vg-sseq-entry-item-label":
            c_print(f"#[bold {color.meaning_num}]{child.text}", end=" ")
            num_label_count = len(child.text) # important! making sure two-digit numbering and things under it can vertically align properly.

        # print meaning content
        elif "ms-lg-4 ms-3 w-100" in attr:
            for c in child.iterchildren(): # c:  class="sb-0 sb-entry"
                cc = c.getchildren()[0]    # cc: class="sen has-num-only"
                cc_attr = cc.get("class")
                if cc_attr is not None and cc_attr == "sen has-num-only":
                    tags(cc, cc_attr, num_label_count)
                    continue # !!! very important, or sb_entry() will run the node "sb-0 sb-entry" containing "sen has-num-only" once again

                # print class "sb-0 sb-entry", "sb-1 sb-entry" ...
                sb_entry(c, attr, num_label_count)


def et(node):
    text = "".join(node.itertext()).strip("\n")
    if node.getnext() is not None:
        print(text, end=" ")
    else:
        print(text, end="\n")


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
                print_meaning_badge(e.text, end="")
            else:
                c_print(f"#[bold]{e.text}")

            if "vg-sseq-entry-item" in child.getnext().get("class"):
                print()


def print_meaning_badge(text, end=""):
    c_print(f"#[{color.meaning_badge}]{text}", end=end)


def print_header_badge(text, end=" "):
    c_print(f"#[{color.meaning_badge}]{text}", end=end)


def print_meaning_keyword(text, end=" "):
    c_print(f"#[bold {color.meaning_keyword}]{text}", end=end)


def print_meaning_content(text, end=""):
    if text == ": ":
        c_print(f"#[{color.meaning_content} bold]{text}", end=end)
    else:
        c_print(f"#[{color.meaning_content}]{text}", end=end)


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
    elif "sense" in ancestor_attr and "no-subnum" in ancestor_attr:
        print("", end=suffix)
    elif ancestor_attr == "sense has-num-only has-subnum-only":
        print("    ", end=suffix)


def print_pron(node, header=False, end=""):
    text = "".join(list(node.itertext())).strip()
    if header:
        if text[-1] == ",":
            print(f'|{text[:-1]}|', end=end)
        else:
            print(f'|{text}|', end=end)
    else:
            print(f'{text}', end=end)


def print_or_badge(text, end=""):
    c_print(f"#[{color.or_badge}]{text}", end = end)


def print_class_if(text, before_semicolon=False, before_il=False, has_next_sibling=True):
    if before_semicolon or before_il or not has_next_sibling:
        c_print(f"#[bold]{text}", end="")
    else:
        c_print(f"#[bold]{text}", end=" ")


def print_class_va(text, end= " "):
    c_print(f"#[bold]{text}", end=end)


def print_class_sgram(node):
    for t in node.itertext():
        text = t.strip("\n").strip()
        if text and text.isalpha():
            c_print(f"#[bold]{t}", end=" ")


def print_class_ins(node):
    word_forms = []
    for child in node:
        attr = child.get("class")
        if attr is not None:
            if "il-badge badge mw-badge-gray-100" in attr:
                print_header_badge(child.text.strip(), end=" ") # e.g. "natalism"
            elif attr == "prt-a":
                for c in child:
                    if c.tag == "a":
                        print_pron(c, False)
                    elif c.getnext() is None:
                        print("".join(list(c.itertext())).strip(), end="\n")
                    else:
                        print("".join(list(c.itertext())).strip(), end=" ")
            elif attr == "il ":
                if child.getprevious() is None and child.text[0] == " ":
                    print_or_badge(child.text[1:])
                else:
                    print_or_badge(child.text)
            elif attr == "sep-semicolon":
                print(child.text, end="")
            elif attr == "if":
                next_sibling = child.getnext()
                word_forms.append(child.text)
                # if child.getprevious() is not None and "il-badge badge mw-badge-gray-100" in child.getprevious().get("class"):
                #     word_forms.append(child.text)
                # else:
                #     word_forms.append(child.text)
                if next_sibling is None:
                    print_class_if(child.text, has_next_sibling=False)
                else:
                    sub_attr = next_sibling.get("class")
                    if sub_attr == "sep-semicolon":
                        print_class_if(child.text, before_semicolon=True)
                    elif sub_attr == "il ":
                        print_class_if(child.text, before_il=True)
                    else:
                        print_class_if(child.text, before_semicolon=False)
            else:
                c_print(f"#[bold]{child.text}", end="")

    return word_forms


# --- Word of the Day --- #
def print_wod_header(node):
    for elm in node.iterdescendants():
        attr = elm.get("class")
        if attr == "w-a-title":
            for c in elm.iterchildren():
                c_print(f"#[{color.wod_title} bold]{c.text}", end="")
            print()

        elif attr == "word-header-txt":
            c_print(f"#[bold]{elm.text}")

        elif attr == "main-attr":
            c_print(f"#[{color.wod_type}]{elm.text}", end="")
            print(" | ", end="")

        elif attr == "word-syllables":
            c_print(f"#[{color.wod_syllables}]{elm.text}")


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
                c_print(f"\n#[{color.wod_subtitle} bold]{text}")
            children = list(elm.iterchildren())
            if children:
                child = children[0]
                tail = child.tail.strip("\n").strip()
                c_print(f"#[{color.wod_subtitle} bold]{child.text}", end=" ")
                c_print(f"#[{color.wod_subtitle} bold]{tail}", end="\n")

        elif tag == "p":
            print_wod_p(elm)

        elif tag == "div" and elm.attrib["class"] == "wotd-examples":
            child = elm.getchildren()[0].getchildren()[0]
            print_wod_p(child)


def print_wod_dyk(node):
    for elm in node.iterchildren():
        tag = elm.tag

        if tag == "h2":
            c_print(f"\n#[{color.wod_subtitle} bold]{elm.text}")

        elif tag == "p":
            print_wod_p(elm)


def parse_and_print_wod(response_url, response_text):
    logger.debug(f"{OP.PARSING.name} {response_url}")

    s = """
    //*[@class="article-header-container wod-article-header"] |
    //*[@class="wod-definition-container"] |
    //*[@class="did-you-know-wrapper"]
    """

    nodes = etree.HTML(response_text, parser).xpath(s)
    logger.debug(f"{OP.PRINTING.name} the parsed result of {response_url}")

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


async def parse_and_print_wod_calendar(session, response_url, response_text):
    logger.debug(f"{OP.PARSING.name} {response_url}")

    nodes = etree.HTML(response_text, parser).xpath("//li/h2/a")
    logger.debug(f"{OP.PRINTING.name} the parsed result of {response_url}")

    data = {}
    for node in nodes:
        data[node.text] = node.attrib["href"]

    select_word = get_wod_selection_by_fzf(data) if has_tool("fzf") else get_wod_selection(data)
    if select_word in data.keys():
        url = WEBSTER_BASE_URL + data[select_word]
        await get_webster_wod_past(session, url)
    elif len(select_word) > 1 and not select_word.isnumeric():
        await search_webster(session, select_word)
    else:
        sys.exit()


async def get_webster_wod(session):
    resp = await fetch(session, WEBSTER_WORD_OF_THE_DAY_URL)
    result = await resp.text()
    parse_and_print_wod(resp.url, result)


async def get_webster_wod_past(session, req_url):
    resp = await fetch(session, req_url)
    result = await resp.text()
    parse_and_print_wod(resp.url, result)


async def get_webster_wod_list(session):
    resp = await fetch(session, WEBSTER_WORD_OF_THE_DAY_URL_CALENDAR)
    result = await resp.text()
    await parse_and_print_wod_calendar(session, resp.url, result)
