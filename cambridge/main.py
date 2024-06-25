def main():
    try:
        args = parse_args()
        if args is not None:
            args.func(args)

            # Connection object used as context manager only commits or rollbacks transactions,
            # so the connection object should be closed manually
            con.close()

    except KeyboardInterrupt:
        print("\nStopped by user")

if __name__ == "__main__":
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from cambridge.args import parse_args
    from cambridge.cache import con

    main()

else:
    from .args import parse_args
    from .cache import con
