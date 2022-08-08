"""Set, parse, and deal with terminal arguments."""

import sqlite3
import logging
import argparse
import sys

from cambridge.cache import (
    get_response_words,
    get_random_words,
    delete_word,
)
from cambridge.log import logger
from cambridge.settings import OP
from cambridge.dicts import webster, cambridge 


def parse_args():
    parser = argparse.ArgumentParser(
        description="Terminal Version of Cambridge Dictionary"
    )

    # Add sub-command capability that can identify different sub-command name
    sub_parsers = parser.add_subparsers(dest="subparser_name")

    # Add sub-command l
    parser_lw = sub_parsers.add_parser(
        "l",
        help="list all the words you've successfully searched in alphabetical order",
    )

    # Make sub-command l run default funtion of "list_words"
    parser_lw.set_defaults(func=list_words)

    # Add optional argument for deleting a word from word list
    parser_lw.add_argument(
        "-d",
        "--delete",
        nargs="+",
        help="delete a word or phrase from cache",
    )

    # Add optional argument for listing all words by time
    parser_lw.add_argument(
        "-t",
        "--time",
        action="store_true",
        help="list all the words you've successfully searched in reverse chronological order",
    )

    # Add optional argument for listing words randomly chosen
    parser_lw.add_argument(
        "-r",
        "--random",
        action="store_true",
        help="randomly list the words you've successfully searched",
    )

    # Add sub-command s
    parser_sw = sub_parsers.add_parser("s", help="search a word or phrase")

    # Make sub-command s run default function of "search_words"
    parser_sw.set_defaults(func=search_word)

    # Add positional arguments with n args
    parser_sw.add_argument(
        "words",
        nargs="+",
        help="A word or phrase you want to search",
    )
    # Add optional arguments
    parser_sw.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="search a word or phrase in verbose mode",
    )
    # Add optional arguments
    parser_sw.add_argument(
        "-w",
        "--webster",
        action="store_true",
        help="search a word or phrase in Merriam-Webster Dictionary",
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
        if delete_word(con, cur, word):
            print(f'{OP[9]} "{word}" from cache successfully')
        else:
            logger.error(f'{OP[6]} "{word}" in cache')
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
                print(i[0])


def search_word(args, con, cur):
    """
    The function triggered when a user searches a word or phrase on terminal.
    It checks the args, if "verbose" is in it, the debug mode will be turned on.
    Then it checks the cache, if the word has been cached, uses it and prints it; if not, go fetch the web.
    After fetching the data, prints it to the terminal and caches it.
    If no word found in the cambridge, display word suggestions and exit.
    """

    if args.verbose:
        logging.getLogger(__package__).setLevel(logging.DEBUG)

    input_word = args.words[0]
    is_webster = args.webster

    if is_webster:
        webster.search_webster(con, cur, input_word)
    else:
        cambridge.search_cambridge(con, cur, input_word)



