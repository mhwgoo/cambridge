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
from .console import console


def parse_args():
    parser = argparse.ArgumentParser(
        description="Terminal Version of Cambridge Dictionary"
    )

    # Add sub-command capability that can identify different sub-command name
    sub_parsers = parser.add_subparsers(dest="subparser_name")

    # Add sub-command l
    parser_lw = sub_parsers.add_parser(
        "l",
        help="list all words you've found before in alphabetical order",
    )

    # Make sub-command l run default funtion of "list_words"
    parser_lw.set_defaults(func=list_words)

    # Add optional argument for deleting a word from word list
    parser_lw.add_argument(
        "-d",
        "--delete",
        nargs="+",
        help="delete a word/phrase from cache",
    )

    # Add optional argument for listing all words by time
    parser_lw.add_argument(
        "-t",
        "--time",
        action="store_true",
        help="list all words you've found before in reverse chronological order",
    )

    # Add optional argument for listing words randomly chosen
    parser_lw.add_argument(
        "-r",
        "--random",
        action="store_true",
        help="randomly list the words you've found before",
    )

    # Add sub-command s
    parser_sw = sub_parsers.add_parser("s", help="look up a word/phrase")

    # Make sub-command s run default function of "search_words"
    parser_sw.set_defaults(func=search_word)

    # Add positional arguments with n args
    parser_sw.add_argument(
        "words",
        nargs="+",
        help="look up a word/phrase in Cambridge Dictionary",
    )
    # Add optional arguments
    parser_sw.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="look up a word/phrase in verbose mode",
    )
    # Add optional arguments
    parser_sw.add_argument(
        "-w",
        "--webster",
        action="store_true",
        help="look up a word/phrase in Merriam-Webster Dictionary",
    )

    # Add optional arguments
    parser_sw.add_argument(
        "-f",
        "--fresh",
        action="store_true",
        help="look up a word/phrase afresh without using cache",
    )

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

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


def list_words(args, con, cur):
    # The subparser i.e. the sub-command isn't in the namespace of args
    if args.delete:
        word = " ".join(args.delete)
        deleted, data = delete_word(con, cur, word)
        if deleted:
            if "cambridge" in data[1]:
                print(f'{OP[9]} "{word}" from {DICTS[0]} in cache successfully')
            else:
                print(f'{OP[9]} "{word}" from {DICTS[1]} in cache successfully')
        else:
            print(f'{OP[6]} "{word}" in cache')
    elif args.random:
        try:
            # data is something like [('hello',), ('good',), ('world',)]
            data = get_random_words(cur)
        except sqlite3.OperationalError:
            logger.error("You may haven't searched any word yet")
        else:
            for i in data:
                print(i[0])
    else:
        try:
            # data is something like [('hello',), ('good',), ('world',)]
            data = get_response_words(cur)
        except sqlite3.OperationalError:
            logger.error("You may haven't searched any word yet")
        else:
            if args.time:
                data.sort(reverse=True, key=lambda tup: tup[1])
            else:
                data.sort()

            for i in data:
                console.print(i[0], justify="left")


def search_word(args, con, cur):
    """
    The function is triggered when a user searches a word or phrase on terminal.
    First checks the args having "verbose" in it or not, if so, the debug mode will be turned on.
    Then it checks which dictionary is intended, and then calls respective dictionary function.
    """

    if args.verbose:
        logging.getLogger(__package__).setLevel(logging.DEBUG)

    input_word = args.words[0]
    is_webster = args.webster
    is_fresh = args.fresh

    if is_webster:
        webster.search_webster(con, cur, input_word, is_fresh)
    else:
        cambridge.search_cambridge(con, cur, input_word, is_fresh)
