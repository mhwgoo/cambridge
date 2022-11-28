"""
Rich is a Python library for rich text and beautiful formatting in the terminal.
This script constructs rich console object.
"""

from rich.console import Console
from rich.table import Table

console = Console(color_system="truecolor", highlight=False)

table = Table()
table.add_column("No.", style = "white")
table.add_column("Input Word", style = "yellow")
table.add_column("Found Word", style = "blue")
table.add_column("Dictionary", style = "green")
