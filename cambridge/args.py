"""Set, parse, and dispatch terminal arguments."""

import sqlite3
import logging
import argparse
import sys

from .cache import (
    get_response_words,
    get_random_words,
    delete_word,
)
from .log import logger
from .settings import OP, DICTS
from .dicts import webster, cambridge
from .console import console, table


def parse_args():
    parser = argparse.ArgumentParser(
        description="Terminal Version of Cambridge Dictionary by default. Also supports Merriam-Webster Dictionary."
    )

    # Add sub-command capability that can identify different sub-command name
    sub_parsers = parser.add_subparsers(dest="subparser_name")

    # Add sub-command l
    parser_lw = sub_parsers.add_parser(
        "l",
        help="list words/phrases you've found before in alphabetical order",
    )

    # Make sub-command l run default funtion of "list_words"
    parser_lw.set_defaults(func=list_words)

    # Add an optional argument for l command
    parser_lw.add_argument(
        "-d",
        "--delete",
        nargs="+",
        help="delete a word/phrase or multiple words/phrases(seperated by ',') from cache",
    )

    # Add an optional argument for l command
    parser_lw.add_argument(
        "-t",
        "--time",
        action="store_true",
        help="list words/phrases you've found before in reverse chronological order",
    )

    # Add an optional argument for l command
    parser_lw.add_argument(
        "-r",
        "--random",
        action="store_true",
        help="randomly list 20 words/phrases you've found before",
    )

    # Add sub-command s
    parser_sw = sub_parsers.add_parser("s", help="look up a word/phrase; hidden for convenience, no need to type")

    # Make sub-command s run default function of "search_words"
    parser_sw.set_defaults(func=search_word)

    # Add positional arguments with n args for s command
    parser_sw.add_argument(
        "word_or_phrase",
        nargs="+",
        help="look up a word/phrase in Cambridge Dictionary; e.g. camb <word/phrase>",
    )

    # Add an optional argument for s command
    parser_sw.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="look up a word/phrase in verbose mode",
    )

    # Add an optional argument for s command
    parser_sw.add_argument(
        "-w",
        "--webster",
        action="store_true",
        help="look up a word/phrase in Merriam-Webster Dictionary",
    )

    # Add an optional argument for s command
    parser_sw.add_argument(
        "-f",
        "--fresh",
        action="store_true",
        help="look up a word/phrase afresh without using cache",
    )

    # Add an optional argument for s command
    parser_sw.add_argument(
        "-c",
        "--chinese",
        action="store_true",
        help="look up a word/phrase in Cambridge Dictionary with Chinese translation",
    )

    if len(sys.argv) == 1:
        parser.print_help()
        console.print("[blue]\nCommand l")
        parser_lw.print_help()
        console.print("[blue]\nCommand s (hidden for convinience)")
        parser_sw.print_help()

        sys.exit()

    elif sys.argv[1] != "l" and len(sys.argv) > 1:
        to_parse = []
        word = []
        for i in sys.argv[1:]:
            if i.startswith("-"):
                to_parse.append(i)
            else:
                word.append(i)
        to_search = " ".join(word)
        to_parse.append(to_search)
        args = parser_sw.parse_args(to_parse)

    else:
        args = parser.parse_args()

    return args


def delete(word, con, cur):
    deleted, data = delete_word(con, cur, word)

    if deleted:
        if "cambridge" in data[1]:
            print(f'{OP[9]} "{word}" from {DICTS[0]} in cache successfully')
        else:
            print(f'{OP[9]} "{word}" from {DICTS[1]} in cache successfully')
    else:
        print(f'{OP[6]} "{word}" in cache')


def list_words(args, con, cur):
    # The subparser i.e. the sub-command isn't in the namespace of args
    if args.delete:
        to_delete = args.delete
    
        ids = []
        words = []
        
        for index, item in enumerate(to_delete):
            # multiple words/phrases are seperated by ","
            if "," in item or ("," not in item and index == len(to_delete) - 1):
                ids.append(index)

        # if there is only one word/phrase to delete
        if len(ids) == 1:
            word = " ".join(to_delete).strip().strip(",")
            delete(word, con, cur)

        # if there are multiple words/phrase to delete
        else:
            for i, id in enumerate(ids):
                if i == 0:
                    words.append(" ".join(to_delete[: (id + 1)]).strip(",").strip())
                if i > 0:
                    words.append(" ".join(to_delete[(ids[i-1] + 1): (id + 1)]).strip(",").strip())

            # If the last word in `to_delete` variable does not end with ",", it should be collected.
            # Else the last word ends with ",", it has been covered and handled above.
            if ids[-1] != len(to_delete) - 1:
                words.append(to_delete[-1])

            for word in words:
                delete(word, con, cur)
                

    else:
        if args.random:
            try:
                # data is something like [('hello',), ('good',), ('world',)]
                data = get_random_words(cur)
            except sqlite3.OperationalError:
                logger.error("You may haven't searched any word yet")
            else:
                print_table(data)

        else:
            try:
                # data is something like [('hello',), ('good',), ('world',)]
                data = get_response_words(cur)
            except sqlite3.OperationalError:
                logger.error("You may haven't searched any word yet")
            else:
                if args.time:
                    data.sort(reverse=False, key=lambda tup: tup[3])
                    print_table(data)
                else:
                    data.sort()
                    # Not using print_table() is for fzf preview
                    for entry in data:
                        print(entry[1])


def print_table(data):
    for index, entry in enumerate(data):
        num = str(index + 1)
        input_word, response_word = entry[0], entry[1]
        if "cambridge" in entry[2]:
            dict_name = DICTS[0]
        else:
            dict_name = DICTS[1]
        table.add_row(num, input_word, response_word, dict_name)
    console.print(table)


def search_word(args, con, cur):
    """
    The function is triggered when a user searches a word or phrase on terminal.
    First checks the args having "verbose" in it or not, if so, the debug mode will be turned on.
    Then it checks which dictionary is intended, and then calls respective dictionary function.
    """

    if args.verbose:
        logging.getLogger(__package__).setLevel(logging.DEBUG)

    
    input_word = args.word_or_phrase[0].strip(".").strip(",").strip()

    # boolean types
    is_webster = args.webster
    is_fresh = args.fresh
    is_ch = args.chinese

    if is_webster and is_ch:
        print("Webster Dictionary doesn't support English to other language. Try again without -c(--chinese) option")
        sys.exit()

    if is_webster:
        webster.search_webster(con, cur, input_word, is_fresh)
    else:
        cambridge.search_cambridge(con, cur, input_word, is_fresh, is_ch)
