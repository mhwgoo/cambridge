"""
This script sets up self-defined errors.
"""

import sys

from .log import logger


class ParsedNoneError(Exception):
    """Used when bs4 parsing returned None, when there's document fetched, which may not be the right document for the word."""

    def __init__(self, response_url):
        self.message = "The word isn't in the Cambridge Dictionary yet; or the html document returned isn't about the word because of your temporary slow network. See " + response_url 

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
    logger.debug(f"{op} {url} {attempt} times")
    if attempt == 3:
        print(f"Maximum {op} reached: {error}")
        sys.exit()
    return attempt
