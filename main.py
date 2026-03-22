import sys
import os
import re
import subprocess
import logging
import argparse
import sqlite3
from pathlib import Path
from typing import Optional, Literal

VERSION = "4.0"

# =======
# Sqlite3
# =======
DIR = Path.home() / ".cache" / "cambridge"
DIR.mkdir(parents=True, exist_ok=True)
DB = str(DIR / "cambridge.db")
conn = sqlite3.connect(DB, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

def create_table():
    conn.execute(
        """CREATE TABLE IF NOT EXISTS words (
        "input_word" TEXT NOT NULL,
        "response_word" TEXT NOT NULL,
        "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        "response_url" TEXT UNIQUE NOT NULL,
        "response_text" TEXT NOT NULL)
        """
    )


def save_to_cache(input_word, response_word, response_url, response_text):
    import datetime
    current_datetime = datetime.datetime.now().replace(tzinfo=None).isoformat()

    for attempt in (1, 2):
        try:
            result = conn.execute(
                """
                INSERT INTO words (input_word, response_word, created_at, response_url, response_text)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                RETURNING response_word
                """,
                (input_word, response_word, current_datetime, response_url, response_text)).fetchone()
        except sqlite3.Error as error:
            if "no such table" in str(error):
                logger.debug("CREATING TABLE words...")
                create_table()
                continue
            logger.error(f'CANCELLED caching "{input_word}": [{error.__class__.__name__}] {error}')
            break
        else:
            conn.commit()
            if result is None: # hit ON CONFLICT
                logger.debug("CANCELLED caching, already cached before")
            else:
                logger.debug(f'CACHED "{result[0]}"')
            return


def list_cache(method):
    try:
        if method == "random":
            cur = conn.execute("SELECT response_word, response_url FROM words ORDER BY RANDOM() LIMIT 20")
        elif method == "by_time":
            cur = conn.execute("SELECT response_word, response_url FROM words ORDER BY created_at DESC")
        else:
            cur = conn.execute("SELECT response_word, response_url FROM words ORDER BY response_word ASC")
    except sqlite3.Error as error:
        if "no such table" in str(error):
            create_table()
        logger.error(f'CANCELLED listing cache: [{error.__class__.__name__}] {error}')
        return None
    else:
        result = cur.fetchall()
        if result is None:
            print("Cache is empty due to no prior word search or deliberately choosing not to use cache.")
        return result


def delete_from_cache(word):
    try:
        result = conn.execute("DELETE FROM words WHERE response_word = ? OR input_word = ? RETURNING response_url", (word, word)).fetchone()
    except sqlite3.Error as error:
        if "no such table" in str(error):
            create_table()
        logger.error(f'CANCELLED deleting "{word}" from cache: [{error.__class__.__name__}] {error}')
    else:
        conn.commit()
        if result is None:
            print(f'NOT_FOUND "{word}" in cache')
        else:
            dict_name = get_dict_name_from_url(result[0])
            print(f'DELETED "{word}" in {dict_name} from cache successfully')



# =====
# Utils
# =====
JustifyMethod = Literal["left", "center", "right"]
Initiator = Literal["wod_calendar", "spell_check", "cache_list", "redirect_list"]

Symbol = {
    "L_BRACKET" : "[",
    "R_BRACKET" : "]",
    "SLASH"     : "/",
    "HASH"      : "#"
}

COLOR_EFFECT = {
    "BLACK"         : "30",
    "RED"           : "31",
    "GREEN"         : "32",
    "YELLOW"        : "33",
    "BLUE"          : "34",
    "MAGENTA"       : "35",
    "CYAN"          : "36",
    "WHITE"         : "37",
    "RESET"         : "0",
    "BOLD"          : "1",
    "ITALIC"        : "3"
}

def hex_to_rgb(hex):
    h = hex[1:]
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def get_color_escape(r, g, b, background=False):
    return '\033[{};2;{};{};{}m'.format(48 if background else 38, r, g, b)


def get_color_effect(code):
    return '\033[' + COLOR_EFFECT[code] + 'm'


def parse_in_bracket(text):
    new_text = ""

    for i, t in enumerate(text):
        if t == Symbol["SLASH"]:
            new_text = get_color_effect("RESET")
            return new_text

        if t == Symbol["HASH"]:
            new_text += get_color_escape(*hex_to_rgb(text[i : i + 7]), background=False)

    for ce in COLOR_EFFECT.keys():
        if ce.lower() in text:
            new_text += get_color_effect(ce)

    return new_text


def parse_text(string):
    texts = re.split(r'[\[^[\]]', string)

    if len(texts) == 1:
        return texts[0]

    length = len(string)
    after_parse = ""

    i = 0
    while i < length:
        s = string[i]

        if s not in Symbol.values():
            after_parse += s
            i = i + 1
        elif s == Symbol["SLASH"] and string[i - 1] != Symbol["L_BRACKET"]:
            after_parse += s
            i = i + 1
        elif s == Symbol["HASH"] and string[i + 1] != Symbol["L_BRACKET"]:
            after_parse += s
            i = i + 1
        elif s == Symbol["HASH"] and string[i + 1] == Symbol["L_BRACKET"]:
            i = i + 1
        elif s == Symbol["L_BRACKET"] and string[i - 1] == Symbol["HASH"]:
                k = i
                for j, ss in enumerate(string[i + 1 : ]):
                    k += 1
                    if ss == Symbol["R_BRACKET"]:
                        text_in_bracket = string[i + 1 : i + 1 + j]
                        for word in text_in_bracket.split():
                            after_parse += parse_in_bracket(string[i + 1 : i + 1 + j])
                            i = k
                            break
                        break
                i = i + 1

        elif s == Symbol["L_BRACKET"] and string[i - 1] != Symbol["HASH"]:
            after_parse += s
            i = i + 1
        else:
            after_parse += s
            i = i + 1

    return after_parse + get_color_effect("RESET")


def pprint(*objects, sep=' ', end='\n', file=None, flush=False, justify: Optional[JustifyMethod] = None):
    if not objects:
        objects = ("\n",)

    if len(objects)  == 1:
        text = parse_text(objects[0])
    else:
        new_data = ""
        for i in objects:
            new_data = new_data + i
        text = parse_text(new_data)

    if justify is not None and isinstance(objects[0], str):
        cols = os.get_terminal_size().columns

        # https://docs.python.org/3/library/string.html#grammar-token-format-spec-align
        # FIXME to strip out color effect characters when justifying
        if justify == "right":
            print(f"{text:>{cols}}")
        elif justify == "left":
            print(f"{text:<{cols}}")
        elif justify == "center":
            print(f"{text:^{cols}}")
        else:
            justify = None
    else:
        print(text, end=end)


def print_word_per_line(index, word, extra=""):
    cols = os.get_terminal_size().columns
    word_len = len(word)

    if index % 2 == 0:
        print(f"\033[37;1;100m{index+1:6d}|{word}", end="")
        print(f"\033[37;1;100m{extra:>{cols-word_len-7}}\033[0m")
    else:
        pprint(f"#[bold #4A7D95]{index+1:6d}|{word}", end="")
        pprint(f"#[bold #4A7D95]{extra:>{cols-word_len-7}}")


def has_tool(name):
    from shutil import which
    return which(name) is not None


def get_dict_name_from_url(url):
    return "CAMBRIDGE" if "cambridge" in url else "MERRIAM_WEBSTER"


def list_items(data, initiator: Optional[Initiator] = None):
    for index, entry in enumerate(data):
        if initiator == "cache_list":
            word = entry[0]
            dict_name = get_dict_name_from_url(entry[1])
            print_word_per_line(index, word, dict_name)
        elif initiator == "wod_calendar":
            date_string = data[entry].split("/")[-1]
            date = ""
            for i, c in enumerate(date_string):
                if c.isnumeric():
                    date = date_string[i:]
                    break
            print_word_per_line(index, entry, date)
        else:
            print_word_per_line(index, entry, "")


def get_cache_selection(data):
    title = "List of Cache"
    pprint(title + (int(len(title)/2))*" ", justify="center")
    list_items(data, "cache_list")
    notice = "INPUT one word from above to print the meaning; TYPE a new word; [ANY OTHER KEY] to quit out: "
    print(notice, end="")
    return input("")


def get_cache_selection_by_fzf(data):
    notice = "Select to print the word's meaning; [ESC] to quit out."
    choices = ""
    for i in data:
        choices = choices + i[0] + "\n"
    choices = choices.strip()

    p1 = subprocess.Popen(["echo", choices], stdout=subprocess.PIPE, text=True)
    p2 = subprocess.Popen(["fzf", "--layout=reverse", "--bind", "enter:accept-or-print-query", "--header", notice], stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
    select_word = p2.communicate()[0].strip("\n")

    if p2.returncode == 0 and select_word != "":
        return select_word
    else:
        sys.exit()


def search_webster():
    pass


def wod():
    pass


def list_words(args):
    if args.delete:
        words = " ".join(args.delete).split(",")
        if len(words) == 1:
            delete_from_cache(words[0].strip())
        else:
            for w in words:
                i = w.strip()
                if i:
                    delete_from_cache(i)
        return


    method = "by_word"
    if args.random:
        method = "random"
    elif args.time:
        method = "by_time"

    result = list_cache(method)
    if result is None:
        sys.exit()

    select_word = get_cache_selection_by_fzf(result) if has_tool("fzf") else get_cache_selection(result)
    if len(select_word) > 1 and not select_word.isnumeric():
        pass
        # search_webster(select_word)
    else:
        sys.exit()


def main():
    # Global argparse code does not work.
    parser = argparse.ArgumentParser(description="Terminal version of Cambridge Dictionary by default. Also supports Merriam-Webster.")
    parser.add_argument("-v", "--version", action="store_true", help="print the current version of the program")

    sub_parsers = parser.add_subparsers(dest="subparser_name")

    parser_sw = sub_parsers.add_parser("s", help="look up terms; `s` is hidden for convenience, no need to type")
    parser_sw.set_defaults(func=search_webster)
    parser_sw.add_argument("-s", "--search", nargs="+", help="look up terms (separated by ',') in Cambridge")
    parser_sw.add_argument("-c", "--chinese", nargs="+", help="look up terms (separated by ',') in Cambridge with Chinese translation")
    parser_sw.add_argument("-w", "--webster", nargs="+", help="look up terms (separated by ',') in Merriam-Webster")
    parser_sw.add_argument("-f", "--fresh", action="store_true", help="look up terms without using cache")
    parser_sw.add_argument("-n", "--nosuggestions", action="store_true", help="look up terms without showing spelling suggestions if not found")
    parser_sw.add_argument("-d", "-debug", action="store_true", help="turn on debug mode")

    parser_wod = sub_parsers.add_parser("wod", help="list today's Word of the Day from Merriam-Webster")
    parser_wod.set_defaults(func=wod)
    parser_wod.add_argument("-a", "--all", action="store_true", help="list all Words of the Day")

    parser_lw = sub_parsers.add_parser("l", help="list the cached terms in alphabetical order")
    parser_lw.set_defaults(func=list_words)
    parser_lw.add_argument("-t", "--time", action="store_true", help="list the cached terms in reverse chronological order")
    parser_lw.add_argument("-r", "--random", action="store_true", help="randomly list 20 cached terms")
    parser_lw.add_argument("-d", "--delete", nargs="+", help="delete one or multiple terms (separated by ',') from the cache")


    if len(sys.argv) == 1:
        parser.print_help()
        return

    arg_list = [s.strip().lower() for s in sys.argv]

    if arg_list[1] == "-h" or arg_list[1] == "--help":
        parser.print_help()
        return

    elif arg_list[1] == "-v" or arg_list[1] == "--version":
        print("cambridge " + VERSION)
        return

    elif len(arg_list[1]) == 1 and arg_list[1] != "l" and arg_list[1] != "s":
        parser.print_help()
        pprint("\n#[bold]positional argument `s` (hidden)")
        parser_sw.print_help()
        pprint("\n#[bold]positional argument `l`")
        parser_lw.print_help()
        pprint("\n#[bold]positional argument `wod`")
        parser_wod.print_help()
        return

    try:
        # python3 main.py l -d " mmoodd "
        # Namespace(version=False, debug=False, subparser_name='l', time=False, random=False, delete=['mmoodd'], func=<function list_words at 0x106371940>)
        # {'version': False, 'debug': False, 'subparser_name': 'l', 'time': False, 'random': False, 'delete': ['mmoodd'], 'func': <function list_words at 0x10db31940>}

        args = parser.parse_args(arg_list[1 : ])

        if args.subparser_name == "l":
            list_words(args)
        elif args.subparser_name == "wod":
            wod(args)
        else:
            logging.basicConfig(
                format="%(asctime)s %(msecs)d msecs %(levelname)s %(name)s.%(filename)s[%(lineno)d] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                level=logging.INFO,
            )
            logger = logging.getLogger("CAMBRIDGE")
            pass
            # w_index = None
            # c_index = None
            # s_index = None
            # for index, word in enumerate(argv_list[1 : ]):
            #     if word == "--search" or word == "-s":
            #         s_index = index
            #     elif word == "--webster" or word == "-w":
            #         w_index = index
            #     elif word == "--chinese" or word == "-c":
            #         c_index = index
            #     elif word[0] != "-" and s_index is None and w_index is None and c_index is None:
            #         argv_list.insert(index, "-s")
            #         break
            #     else:
            #         continue

            # to_parse = []
            # for index, word in enumerate(argv_list[1 : ]):
            #     if word == "--debug":
            #         parser_sw.set_defaults(debug=True)
            #     elif word == "--fresh" or word == "-f":
            #         parser_sw.set_defaults(fresh=True)
            #     elif word == "--nosuggestions" or word == "-n":
            #         parser_sw.set_defaults(nosuggestions=True)
            #     elif (word == "--search" or word == "-s") and (index == len(argv_list) - 1):
            #         continue
            #     elif (word == "--webster" or word == "-w") and (index == len(argv_list) - 1):
            #         continue
            #     elif (word == "--chinese" or word == "-c") and (index == len(argv_list) - 1):
            #         continue
            #     else:
            #         to_parse.append(word)

            # args= parser_sw.parse_args(to_parse)
            # search_webster(args)

    except KeyboardInterrupt:
        print("Stopped by user.")
        return
    except SystemExit:
        print("Exit")
        pass
    except Exception as error:
        logger.error(f"{error}")
        return
    finally:
        conn.close()


if __name__ == "__main__":
    main()
