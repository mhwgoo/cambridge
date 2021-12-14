"""
This script sets up self-defined errors.
"""


class ParsedNoneError(Exception):
    """Used when bs4 returned None whereas there's content existing within the response body"""

    def __init__(self):
        self.message = "Parsed None wth content being good for parsing"
