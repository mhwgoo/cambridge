"""Print in a customized, prettified fashion."""

import os
import sys
import re
from rich.console import Console
from .log import logger
from .settings import COLOR_EFFECT

console = Console(color_system="truecolor", highlight=False, soft_wrap=True)

from typing import (
    Optional,
    Literal
)

JustifyMethod = Literal["left", "center", "right"]


def hex_to_rgb(hex):
    h = hex[1:]
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def get_color_escape(r, g, b, background=False):
    return '\033[{};2;{};{};{}m'.format(48 if background else 38, r, g, b)


def get_color_effect(code):
    if not isinstance(code, str):
        code = str(code)

    color_code = code.strip().upper()
    if color_code in COLOR_EFFECT.keys():
        return '\033[' + COLOR_EFFECT[color_code] + 'm'


def to_ansi_string(string):
    if not isinstance(string, str):
        logger.debug(f"'{string}' should be of 'str' type!")
        string = str(string)

    texts = re.split(r'[\[^[\]]', string)

    if len(texts) == 1:
        return texts[0]

    after_parse = ""

    for i, text in enumerate(texts):
        text_stripped = text.strip(" ")
        if text_stripped != "":
            if text_stripped[0] == "/":
                if text.replace(" ", "")[1:] != texts[i - 2].replace(" ", ""):
                    sys.exit(f"closing tag '{text}' doesn't match any open tag")
                else:
                    after_parse += get_color_effect("RESET")
            elif "#" in text:
                for i, t in enumerate(text):
                    if t == "#":
                        after_parse += get_color_escape(*hex_to_rgb(text[i : i + 7]))
                    if t == "b" and text[i : i + 4] == "bold":
                        after_parse += get_color_effect(text[i : i + 4])
                    if t == "i" and text[i : i + 6] == "italic":
                        after_parse += get_color_effect(text[i : i + 6])

            elif text_stripped == "bold":
                after_parse += get_color_effect(text)
            elif text_stripped == "italic":
                after_parse += get_color_effect(text)
            elif text_stripped == "italic bold" or text_stripped == "bold italic":
                after_parse += get_color_effect("bold") + get_color_effect("italic")
            else:
                after_parse += text

    return after_parse + get_color_effect("RESET")


class CONSOLE:
    def __init__(self):
        pass

    def print(self, *objects, sep=' ', end='\n', file=None, flush=False, justify: Optional[JustifyMethod] = None):
        if not objects:
            objects = ("\n",)

        text = to_ansi_string(objects[0])

        if justify is not None and isinstance(objects[0], str):
            cols = os.get_terminal_size().columns
            # https://docs.python.org/3/library/string.html#grammar-token-format-spec-align
            if justify == "right":
                print(f"{text:>{cols}}")
            elif justify == "left":
                print(f"{text:<{cols}}")
            elif justify == "center":
                print(f"{text:^{cols}}")
            else:
                justify = None
        else:
            print(text, end=end)

my_console = CONSOLE()
