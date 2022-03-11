"""
This script sets up self-defined errors.
"""


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
