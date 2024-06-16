import os
import re

from .color import COLOR_EFFECT

from typing import (
    Optional,
    Literal
)

JustifyMethod = Literal["left", "center", "right"]

Symbol = {
    "L_BRACKET" : "[",
    "R_BRACKET" : "]",
    "SLASH"     : "/",
    "HASH"      : "#"
}


def hex_to_rgb(hex):
    h = hex[1:]
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def get_color_escape(r, g, b, background=False):
    return '\033[{};2;{};{};{}m'.format(48 if background else 38, r, g, b)


def get_color_effect(code):
    return '\033[' + COLOR_EFFECT[code] + 'm'


def parse_in_bracket(text):
    new_text = ""

    for i, t in enumerate(text):
        if t == Symbol["SLASH"]:
            new_text = get_color_effect("RESET")
            return new_text

        if t == Symbol["HASH"]:
            new_text += get_color_escape(*hex_to_rgb(text[i : i + 7]), background=False)

    for ce in COLOR_EFFECT.keys():
        if ce.lower() in text:
            new_text += get_color_effect(ce)

    return new_text


def parse(string):
    texts = re.split(r'[\[^[\]]', string)

    if len(texts) == 1:
        return texts[0]

    length = len(string)
    after_parse = ""

    i = 0
    while i < length:
        s = string[i]

        if s not in Symbol.values():
            after_parse += s
            i = i + 1
        elif s == Symbol["SLASH"] and string[i - 1] != Symbol["L_BRACKET"]:
            after_parse += s
            i = i + 1
        elif s == Symbol["HASH"] and string[i + 1] != Symbol["L_BRACKET"]:
            after_parse += s
            i = i + 1
        elif s == Symbol["HASH"] and string[i + 1] == Symbol["L_BRACKET"]:
            i = i + 1
        elif s == Symbol["L_BRACKET"] and string[i - 1] == Symbol["HASH"]:
                k = i
                for j, ss in enumerate(string[i + 1 : ]):
                    k += 1
                    if ss == Symbol["R_BRACKET"]:
                        text_in_bracket = string[i + 1 : i + 1 + j]
                        for word in text_in_bracket.split():
                            after_parse += parse_in_bracket(string[i + 1 : i + 1 + j])
                            i = k
                            break
                        break
                i = i + 1

        elif s == Symbol["L_BRACKET"] and string[i - 1] != Symbol["HASH"]:
            after_parse += s
            i = i + 1
        else:
            after_parse += s
            i = i + 1

    return after_parse + get_color_effect("RESET")


def c_print(*objects, sep=' ', end='\n', file=None, flush=False, justify: Optional[JustifyMethod] = None):
    if not objects:
        objects = ("\n",)

    if len(objects)  == 1:
        text = parse(objects[0])
    else:
        new_data = ""
        for i in objects:
            new_data = new_data + i
        text = parse(new_data)

    if justify is not None and isinstance(objects[0], str):
        cols = os.get_terminal_size().columns

        # https://docs.python.org/3/library/string.html#grammar-token-format-spec-align
        # FIXME to strip out color effect characters when justifying
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
