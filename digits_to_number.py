#!/usr/bin/env python3
# Copyright (C) 2020 taylor.fish <contact@taylor.fish>
# Licensed under version 3 of the GNU Affero General Public License,
# or (at your option) any later version.

from dataclasses import dataclass
from multiprocessing import Process, Queue
from typing import List
import os
import sys

# sequences of digits longer than this will be split into smaller sequences
LEAF_TASK_DIGIT_LIMIT = 1000


@dataclass
class Result:
    worker_id: int
    number: int
    base: int


def convert(base: int, digits: List[int], indices: range):
    n = 0
    for i in indices:
        n *= base
        n += digits[i]
    return n


# returns (number, base)
def combine(nums: List[int], base: int, last_base: int) -> (int, int):
    while len(nums) > 1:
        new = []
        for i in range(0, len(nums), 2):
            remaining = len(nums) - i
            if remaining > 2:
                new.append(nums[i] * base + nums[i + 1])
            elif remaining == 2:
                new.append(nums[i] * last_base + nums[i + 1])
                last_base *= base
            else:
                new.append(nums[i])
        nums = new
        base **= 2
    return (nums[0], last_base)


class Worker:
    def __init__(self, *, base: int, results: "Queue[Result]"):
        self._base = base
        self._large_base = base**LEAF_TASK_DIGIT_LIMIT
        self._results = results

    def start(self, worker_id: int, digits: List[int]):
        base = self._base
        nums = []

        for i in range(0, len(digits), LEAF_TASK_DIGIT_LIMIT):
            ndigits = min(len(digits) - i, LEAF_TASK_DIGIT_LIMIT)
            nums.append(convert(base, digits, range(i, i + ndigits)))

        num, base = combine(
            nums,
            base=self._large_base,
            last_base=base**ndigits,
        )
        self._results.put(Result(worker_id=worker_id, number=num, base=base))


def combine_result_pair(
    inputs: [Result, Result],
    results: "Queue[Result]",
):
    num = inputs[0].number * inputs[1].base + inputs[1].number
    base = inputs[0].base * inputs[1].base
    worker_id = inputs[0].worker_id // 2
    results.put(Result(worker_id=worker_id, number=num, base=base))


def combine_results(results: List[Result]) -> int:
    while len(results) > 1:
        results_queue: "Queue[List[Result]]" = Queue()
        new_results = [None] * ((len(results) + 1) // 2)
        processes = []

        for i in range(0, len(results), 2):
            if len(results) - i < 2:
                new_results[-1] = results[i]
                continue
            p = Process(
                target=combine_result_pair,
                args=(results[i:i+2], results_queue),
            )
            p.start()
            processes.append(p)

        # collect results
        for p in processes:
            result = results_queue.get()
            new_results[result.worker_id] = result

        # block until worker processes exit
        for p in processes:
            p.join()
        results = new_results
    return results[0].number


def digits_to_number(digits: List[int], base: int) -> int:
    # use 3/4 of cpus
    nworkers = os.cpu_count()
    nworkers -= nworkers // 4

    ndigits = len(digits)
    nworkers = min(nworkers, ndigits)
    digits_per_worker = (ndigits + nworkers - 1) // nworkers
    results_queue: "Queue[List[Result]]" = Queue()

    # spawn worker processes
    processes = []
    worker = Worker(base=base, results=results_queue)
    for i in range(nworkers):
        start = i * digits_per_worker
        end = start + digits_per_worker
        # each process copies the worker; memory isn't shared
        p = Process(target=worker.start, args=(i, digits[start:end],))
        p.start()
        processes.append(p)

    # collect results
    results = [None] * nworkers
    for p in processes:
        result = results_queue.get()
        results[result.worker_id] = result

    # block until worker processes exit
    for p in processes:
        p.join()
    return combine_results(results)


USAGE = """\
Usage: digits_to_number.py <base> <digits-file> <output-file>

This script:
  1. Reads digits from <digit-file>. Each line should contain the base-10
     representation of exactly one digit.
  2. Interprets the sequence of digits as base-<base> digits, starting
     with the most significant digit, and converts them to a number.
  3. Writes the big-endian representation of the number to <output-file>.

For programmatic use, also see the digits_to_number() function.
"""


def main():
    try:
        base, infile, outfile = sys.argv[1:]
    except ValueError:
        print(USAGE, end="", file=sys.stderr)
        sys.exit(1)

    base = int(base)
    with open(infile) as f:
        digits = list(map(int, f))
    n = digits_to_number(digits, base=base)
    with open(outfile, "wb") as f:
        f.write(n.to_bytes((n.bit_length() + 7) // 8, "big"))


if __name__ == "__main__":
    main()
