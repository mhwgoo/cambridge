"""
This script sets up self-defined errors.
"""

import sys

from .log import logger


class ParsedNoneError(Exception):
    def __init__(self, dict_name, response_url):
        self.message = f"The word isn't in the {dict_name} Dictionary yet; OR the fetched html is not complete because of your temporary slow network. Try again. \nOr see {response_url}"

    def __str__(self):
        return self.message


class NoResultError(Exception):
    def __init__(self, dict_name):
        self.message = f"No result found in the {dict_name} Dictionary"

    def __str__(self):
        return self.message


def call_on_error(error, url, attempt, op):
    attempt += 1
    logger.debug(f"{op} {url} {attempt} times")
    if attempt == 3:
        print(f"Maximum {op} reached: {error}")
        sys.exit()
    return attempt
