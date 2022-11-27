"""
`cambridge` is a terminal version of Cambridge Dictionary.
The dictionary data comes from https://dictionary.cambridge.org
If you're not satisfied with the result, you can try with "-w" flag to look up the word in Merriam-Webster Dictionary.
"""

import sqlite3

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


if __name__ == "__main__":
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from cambridge.args import parse_args
    from cambridge.cache import DB

    main()

else:
    from .args import parse_args
    from .cache import DB

