"""
Cambridge is a terminal version of Cambridge Dictionary. 
The dictionary data comes from https://dictionary.cambridge.org.
"""

import sqlite3

# import sys
# import os
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .args import parse_args
from .cache import DB


def main():
    try:
        con = sqlite3.connect(
            DB, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        cur = con.cursor()

        args = parse_args()
        args.func(args, con, cur)

        cur.close()
        con.close()

    except KeyboardInterrupt:
        print("\nStopped by user")
