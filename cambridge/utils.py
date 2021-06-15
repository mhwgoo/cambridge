"""
This script contains utility functions.
"""
import cProfile, pstats, io


def replace_all(string):
    return (
        string.replace("\n            (", "(")
        .replace("(\n    \t                ", "(")
        .replace("\n", " ")
        .replace("      \t                ", " ")
        .replace("\\'", "'")
        .replace("  ", " ")
        .replace("\xa0 ", "")
        .replace("[ ", "[")
        .replace(" ]", "]")
        .replace("A1", "")
        .replace("A2", "")
        .replace("B1", "")
        .replace("B2", "")
        .replace("C1", "")
        .replace("C2", "")
        .strip()
    )


def profile(func):
    """A decorator that uses cProfile to profile a function"""

    def inner(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        retval = func(*args, **kwargs)
        pr.disable()
        s = io.StringIO()
        sortby = "cumulative"
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats()
        print(s.getvalue())
        return retval

    return inner
