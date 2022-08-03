"""
This script sets up self-defined errors.
"""

import sys

from cambridge.log import logger


class ParsedNoneError(Exception):
    """Used when bs4 returned None whereas there's target content existing within the document"""

    def __init__(self):
        self.message = "Nothing parsed out"

    def __str__(self):
        return self.message


class NoResultError(Exception):
    """Used when bs4 returned None because Cambridge dict has no result"""

    def __init__(self):
        self.message = "No result found in Cambridge Dictionary"

    def __str__(self):
        return self.message


def call_on_error(error, url, attempt, op):
    attempt += 1
    logger.debug(
        "%s HTML from %s %d times",
        op,
        url,
        attempt,
    )
    if attempt == 3:
        logger.debug("Maximum %s retries reached. Exit", op)
        logger.error(str(error))
        sys.exit()
    return attempt
