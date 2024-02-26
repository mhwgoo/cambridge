"""Print in a customized, prettified fashion."""

import os
from rich.console import Console

console = Console(color_system="truecolor", highlight=False, soft_wrap=True)

from typing import (
    Optional,
    Literal
)

JustifyMethod = Literal["left", "center", "right"]


"""
my_console.print(f"[{w_col.dict_name}{w_col.bold}]{dict_name}", justify="right")
('[#757575bold]The Merriam-Webster Dictionary',)

my_console.print(f"[{w_col.dict_name} {w_col.bold}]{dict_name}", justify="right")
('[#757575 bold]The Merriam-Webster Dictionary',)

my_console.print(f"[{w_col.dict_name} {w_col.bold}] {dict_name}", justify="right")
('[#757575bold] The Merriam-Webster Dictionary',)

bold = "bold"
italic = "italic"
accessory = "#4A7D95"
console.print(f"[{w_col.eh_entry_num}]{num}", end=" ")
eh_entry_num = "{} on {}".format(eh_fg_entry_num, eh_bg_entry_num) # on 前后必须有空格
objects: ('[#0A1B27 on #F4F4F4]1 of 2',)
"""

class CONSOLE:
    def __init__(self):
        pass

    def print(self, *objects, sep=' ', end='\n', file=None, flush=False, justify: Optional[JustifyMethod] = None):
        if not objects:
            objects = ("\n",)

        text = objects[0]
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
