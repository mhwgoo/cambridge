import sys
import argparse
import asyncio

from .__init__ import __version__
from .cache import delete_from_cache, list_cache
from .webster import search_webster, get_webster_wod, get_webster_wod_list
from .camb import search_cambridge
from .utils import get_cache_selection, get_cache_selection_by_fzf

def parse_args(session):
    parser = argparse.ArgumentParser(
        description="Terminal Version of Cambridge Dictionary by default. Also supports Merriam-Webster Dictionary."
    )

    parser.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="print the current version of the program",
    )

    parser.set_defaults(session=session)

    parser.add_argument(
        "--debug",
        action="store_true",
        help="turn on debug mode",
    )

    # Add sub-command capability that can identify different sub-command name
    sub_parsers = parser.add_subparsers(dest="subparser_name")

    # Add sub-command l
    parser_lw = sub_parsers.add_parser(
        "l",
        help="list alphabetically ordered words/phrases you've found before",
    )

    # Make sub-command l run default funtion of "list_words"
    parser_lw.set_defaults(func=list_words)

    # Add an optional argument for l command
    parser_lw.add_argument(
        "-d",
        "--delete",
        nargs="+",
        help="delete a word/phrase or multiple words/phrases(separated by ', ') from cache",
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

    # Add an optional argument for s command
    parser_sw.add_argument(
        "-n",
        "--nosuggestions",
        action="store_true",
        help="look up a word/phrase without showing spelling suggestions if not found",
    )

    # Add sub-command wod
    parser_wod = sub_parsers.add_parser(
        "wod",
        help="list today's Word of the Day from Merriam-Webster Dictionary",
    )

    # Make sub-command wod run default funtion of "wod"
    parser_wod.set_defaults(func=wod)

    # Add an optional argument for wod command
    parser_wod.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="list all words of the day",
    )

    if len(sys.argv) == 1:
        print_help(parser, parser_lw, parser_sw, parser_wod)
        sys.exit()

    elif sys.argv[1] == "-h" or sys.argv[1] == "--help":
        print_help(parser, parser_lw, parser_sw, parser_wod)
        sys.exit()

    elif sys.argv[1] == "-v" or sys.argv[1] == "--version":
        print("cambridge " + __version__)
        sys.exit()

    elif "l" in sys.argv or "wod" in sys.argv:
        args = parser.parse_args()
        return args

    else:
        to_parse = []
        word = []
        for i in sys.argv[1 : ]:
            if i.startswith("-") and i[1] in ["-", "h", "d", "f", "w", "c", "n"]:
                to_parse.append(i)
            # NOTE
            # Python stdlib `parser.parse_args()` does not allow the value of an argument to start with "-", e.g. camb -w "-let"
            # Without the following workaround, Python interpreter will terminate the program  with the error:
            # `main.py s: error: the following arguments are required: word_or_phrase`
            # However, in terms of word lookup, you sometimes just want to know the meaning of a specific suffix like "-let"
            # Luckily, search without "-", the result of which can also contain the meaning of "-let" suffix
            elif i.startswith("-"):
                word.append(i[1 : ])
            else:
                word.append(i)

        to_search = " ".join(word)
        to_parse.append(to_search)
        parser_sw.set_defaults(session=session)
        args= parser_sw.parse_args(to_parse)
        return args


def print_help(parser, parser_lw, parser_sw, parser_wod):
    parser.print_help()
    print("\n\n\033[1mCOMMAND l\033[0m")
    parser_lw.print_help()

    print("\n\n\033[1mCOMMAND s (hidden)\033[0m")
    parser_sw.print_help()

    print("\n\n\033[1mCOMMAND wod\033[0m")
    parser_wod.print_help()

    sys.exit()


async def list_words(args):
    if args.delete:
        to_delete = args.delete
        words = " ".join(to_delete)
        tasks = []
        for w in words.split(","):
            i = w.strip()
            if i:
                tasks.append(delete_from_cache(i))
        await asyncio.gather(*tasks)
        sys.exit()

    if args.random:
        method = "random"
    elif args.time:
        method = "by_time"
    else:
        method = "by_alpha"

    has_fzf, data = list_cache(method)
    select_word = get_cache_selection_by_fzf(data) if has_fzf else get_cache_selection(data, method)

    if len(select_word) > 1 and not select_word.isnumeric():
        await search_webster(args.session, select_word)
    else:
        sys.exit()


async def search_word(args):
    if args.webster and args.chinese:
        print("Webster Dictionary doesn't support English to other language. Try again without -c(--chinese) option")
        sys.exit(3)

    input_word = args.word_or_phrase[0].strip(".").strip(",").strip()
    if not input_word:
        print("You didn't input any word or phrase.")
        sys.exit(3)

    if "," not in input_word:
        if args.webster:
            await search_webster(args.session, input_word, args.fresh, args.nosuggestions, None)
        else:
            await search_cambridge(args.session, input_word, args.fresh, args.chinese, args.nosuggestions, None)
    else:
        tasks = []
        for w in input_word.split(","):
            i = w.strip(".").strip()
            if i:
                if args.webster:
                    tasks.append(search_webster(args.session, i, args.fresh, args.nosuggestions, None))
                else:
                    tasks.append(search_cambridge(args.session, i, args.fresh, args.chinese, args.nosuggestions, None))
        await asyncio.gather(*tasks)


async def wod(args):
    if args.list:
        await get_webster_wod_list(args.session)
    else:
        await get_webster_wod(args.session)
