#!/usr/bin/env python3
from pathlib import Path

from yaml import dump


def deindent(text: str) -> str:
    """Remove any common leading whitespace from every line and any leading or trailing newlines.
    This can be used to make triple-quoted strings line up with the left edge of the display,
    while still presenting them in the source code in indented form.
    like textwrap.dedent but with these differences:
    1) strips leading newlines and all trailing whitespace
    2) only strips leading space characters from intermediate lines, not tabs etc
    3) uses only the first line's leading whitespace as the common leading whitespace
    4) does not strip leading whitespace from lines that do not have leading whitespace
    The differences make it more suitable for use in source code with prompts where the prompt may have
    been interpolated with values that contain newlines and different indentation.
    """
    text = text.lstrip("\n").rstrip()
    lines = text.splitlines()
    if lines:
        first = lines[0]
        index = first.find(first.lstrip(" "))
        if index > 0:
            prefix = first[:index]
            text = "\n".join(line.removeprefix(prefix) for line in lines)
    return text


def output(agents):
    for agent in agents:
        del agent["model"]
        with open(Path("agents") / (agent["name"] + ".yml"), "w") as stream:
            dump(agent, stream, sort_keys=False)
