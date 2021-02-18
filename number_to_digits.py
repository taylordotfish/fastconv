#!/usr/bin/env python3
# Copyright (C) 2020 taylor.fish <contact@taylor.fish>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from dataclasses import dataclass
from multiprocessing import JoinableQueue, Process, Queue
from typing import List
import math
import os
import sys

# numbers with more digits than this will be split into smaller numbers
LEAF_TASK_DIGIT_LIMIT = 1000

# If true, a message will be printed to stderr at the start of each task.
# Concurrent messages could appear interleaved, but this isn't a big deal
# and tends not to happen in practice.
DEBUG = bool(os.getenv("NUMBER_TO_DIGITS_DEBUG"))


def get_ndigits(n: int, base: int) -> int:
    # calculate (approx) ceil(n.bit_length() * math.log_{base}(2)), which is
    # the minimum number of base-`base` digits required to represent `n`
    ndigits = math.ceil(n.bit_length() / math.log2(base))

    # (exclusive) maximum number that can be represented by `ndigits` digits
    max = base**ndigits

    if max > n:
        # `ndigits` is enough, but maybe we don't need that many
        while max > n:
            max //= base
            ndigits -= 1
        # now `max` <= `n`, so we actually need one more digit
        ndigits += 1
    else:
        # we need more than `ndigits` -- find out how many more
        while max <= n:
            max *= base
            ndigits += 1
    return ndigits


def get_depth(ndigits: int) -> int:
    depth = 0
    while ndigits > LEAF_TASK_DIGIT_LIMIT:
        ndigits += 1
        ndigits //= 2
        depth += 1
    return depth


@dataclass
class Task:
    number: int
    ndigits: int
    index: int
    depth: int


@dataclass
class Result:
    index: int
    digits: List[int]


def process_internal(base: int, task: Task) -> List[Task]:
    depth = task.depth - 1
    lower_ndigits = task.ndigits // 2
    upper_ndigits = task.ndigits - lower_ndigits
    upper, lower = divmod(task.number, base**lower_ndigits)
    upper = Task(
        number=upper,
        ndigits=upper_ndigits,
        index=task.index,
        depth=depth,
    )
    lower = Task(
        number=lower,
        ndigits=lower_ndigits,
        index=(task.index + upper_ndigits),
        depth=depth,
    )
    return [upper, lower]


def process_leaf(base: int, task: Task) -> Result:
    n = task.number
    digits = [0] * task.ndigits
    for i in reversed(range(len(digits))):
        n, m = divmod(n, base)
        digits[i] = m
    return Result(index=task.index, digits=digits)


class Worker:
    def __init__(
        self, *,
        base: int,
        tasks: "JoinableQueue[Task]",
        return_values: "Queue[List[Result]]",
    ):
        self._base = base
        self._tasks = tasks
        self._return_values = return_values
        self._results = []

    def _process_task(self, task: Task):
        if DEBUG:
            print(
                f"working on {task.ndigits}-digit task (depth {task.depth})",
                file=sys.stderr,
            )
        if task.depth == 0:
            self._results.append(process_leaf(self._base, task))
            return
        for task in process_internal(self._base, task):
            self._tasks.put(task)

    def start(self):
        while True:
            task = self._tasks.get()
            try:
                if task is None:
                    break
                self._process_task(task)
            finally:
                self._tasks.task_done()
        self._return_values.put(self._results)


def apply_result(digits: List[int], result: Result):
    i = result.index
    for digit in result.digits:
        digits[i] = digit
        i += 1


def number_to_digits(n: int, base: int) -> List[int]:
    ndigits = get_ndigits(n, base)
    depth = get_depth(ndigits)

    tasks = JoinableQueue()
    tasks.put(Task(number=n, ndigits=ndigits, index=0, depth=depth))
    return_values: "Queue[List[Result]]" = Queue()

    # use 3/4 of cpus
    nworkers = os.cpu_count()
    nworkers -= nworkers // 4

    # spawn worker processes
    processes = []
    worker = Worker(base=base, tasks=tasks, return_values=return_values)
    for i in range(nworkers):
        # each process copies the worker; memory isn't shared
        p = Process(target=worker.start)
        p.start()
        processes.append(p)

    # block until all tasks have been completed
    tasks.join()

    # signal all worker processes to exit
    for p in processes:
        tasks.put(None)

    # retrieve results and construct the final list of digits
    digits = [0] * ndigits
    for p in processes:
        for result in return_values.get():
            apply_result(digits, result)

    # block until worker processes exit
    for p in processes:
        p.join()
    return digits


USAGE = """\
Usage: number_to_digits.py <base> <input-file> <output-file>

This script:
  1. Interprets the contents of <input-file> as a big-endian number.
  2. Converts the number to a sequence of base-<base> digits, starting
     with the most significant digit.
  3. Writes the base-10 representation of each digit to <output-file>.
     One digit is written per line.

If the environment variable NUMBER_TO_DIGITS_DEBUG is set to a non-empty
string, the program will print some debug messages to standard error about
the work it's doing.

For programmatic use, also see the number_to_digits() function.
"""


def main():
    try:
        base, infile, outfile = sys.argv[1:]
    except ValueError:
        print(USAGE, end="", file=sys.stderr)
        sys.exit(1)

    base = int(base)
    with open(infile, "rb") as f:
        n = int.from_bytes(f.read(), "big")
    digits = number_to_digits(n, base=base)
    with open(outfile, "w") as f:
        for digit in digits:
            print(digit, file=f)


if __name__ == "__main__":
    main()
