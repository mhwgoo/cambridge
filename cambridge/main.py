async def main():
    try:
        async with aiohttp.ClientSession() as session:
            args = parse_args(session)
            args_dict = vars(args) # transfrom namespace object into a dict

            if args_dict.get("debug"):
                logger.setLevel(logging.DEBUG)

            if args_dict.get("word_or_phrase") is not None:
                await search_word(args)
            elif args_dict.get("subparser_name") is not None and args_dict.get("subparser_name") == "l":
                await list_words(args)
            elif args_dict.get("subparser_name") is not None and args_dict.get("subparser_name") == "wod":
                await wod(args)

    except asyncio.exceptions.CancelledError:
        print("Task cancelled.")

    except KeyboardInterrupt:
        print("\nStopped by user.")

    except SystemExit:
        pass

    con.close()

if __name__ == "__main__":
    import os
    import sys
    import asyncio
    import aiohttp
    import logging

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from cambridge.args import parse_args, search_word, list_words, wod
    from cambridge.cache import con
    from cambridge.log import logger

    asyncio.run(main())

else:
    import asyncio
    import aiohttp
    import logging

    from .args import parse_args, search_word, list_words, wod
    from .cache import con
    from .log import logger
