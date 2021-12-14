"""
This script sets up self-defined errors.
"""


class ParsedNoneError(Exception):
    """Used when bs4 returned None whereas there's target content existing within the document"""

    def __init__(self):
        self.message = "Got None wth content in place"

    def __str__(self):
        return self.message
