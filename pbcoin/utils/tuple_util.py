from __future__ import annotations

import base64
from typing import Tuple

def tuple_to_string(t: Tuple[int, int], max_val: int, to_b64=True) -> bytes | str:
    val1, val2 = t
    length = len(hex(max_val))
    str1 = f"{val1:#0{length + 2}x}"
    str2 = f"{val2:#0{length + 2}x}"[2:]
    if to_b64:
        return base64.b64encode((str1 + str2).encode())
    return (str1 + str2)


def tuple_from_string(string: str, from_b64=True):
    if from_b64:
        string = base64.b64decode(string).decode()
    if string.startswith("0x"):
        string = string[2:]
    length = len(string) // 2
    val1 = int(string[:length], 16)
    val2 = int(string[length:], 16)
    return (val1, val2)
