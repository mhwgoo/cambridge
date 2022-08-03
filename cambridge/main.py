"""
Cambridge is a terminal version of Cambridge Dictionary. 
The dictionary data comes from https://dictionary.cambridge.org.
"""

import sqlite3

# @timer
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
    from args import parse_args
    from cache import DB

    main()

else:
    from .args import parse_args
    from .cache import DB

    print("Welcome to cambridge!")

