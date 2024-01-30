"""This script contains static data."""

from enum import Enum

VERSION = "3.8.2"

class OP(Enum):
    FETCHING = 1,
    PARSING = 2,
    RETRY_FETCHING = 3,
    RETRY_PARSING = 4,
    PRINTING = 5,
    FOUND = 6,
    NOT_FOUND = 7,
    CACHED= 8,
    CANCELLED = 9,
    DELETED = 10,
    UPDATED = 11

class DICTS(Enum):
    CAMBRIDGE = 1,
    MERRIAM_WEBSTER = 2
