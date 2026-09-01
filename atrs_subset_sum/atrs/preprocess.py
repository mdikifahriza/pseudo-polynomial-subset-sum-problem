"""
ATRS - Input Parsing and Precomputations
"""
from math import gcd
from typing import List, Tuple

def parse_input(raw: str) -> List[int]:
    raw = raw.strip()
    if not raw:
        raise ValueError("Input tidak boleh kosong.")

    parts = [x.strip() for x in raw.split(",")]
    values = []

    for part in parts:
        if not part.isdigit():
            raise ValueError(f"'{part}' bukan bilangan bulat positif.")
        value = int(part)
        if value <= 0:
            raise ValueError(f"'{value}' harus lebih besar dari 0.")
        values.append(value)

    if not values:
        raise ValueError("Input himpunan kosong.")

    return sorted(values)

def build_suffix_gcd(values: List[int]) -> List[int]:
    n = len(values)
    suffix = [0] * n
    current = 0
    for i in range(n - 1, -1, -1):
        current = gcd(current, values[i])
        suffix[i] = current
    return suffix

def build_suffix_sum(values: List[int]) -> List[int]:
    n = len(values)
    suffix = [0] * n
    current = 0
    for i in range(n - 1, -1, -1):
        current += values[i]
        suffix[i] = current
    return suffix

def build_prefix_sum(values: List[int]) -> List[int]:
    n = len(values)
    prefix = [0] * (n + 1)
    for i in range(n):
        prefix[i + 1] = prefix[i] + values[i]
    return prefix
