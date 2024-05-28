def main():
    try:
        args = parse_args()
        if args is not None:
            args.func(args)

        if con:
            con.close()

    except KeyboardInterrupt:
        print("\nStopped by user")


if __name__ == "__main__":
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from cambridge.args import parse_args
    from cambridge.cache import con

else:
    from .args import parse_args
    from .cache import con

main()
