fastconv
========

**fastconv** quickly converts huge integers between different bases. It splits
up the integers into smaller chunks, processes the chunks individually, and
recombines the results. Even without parallelization, this results in a massive
speed improvement over iterated divisions of the original integer, but fastconv
also processes the chunks in parallel for even faster conversions.

Usage
-----

[number\_to\_digits.py][ntd] converts an integer (stored as a big-endian binary
integer or a Python `int`) to a sequence of base-*b* digits. Run
`./number_to_digits.py` for usage information.

[digits\_to\_number.py][dtn] converts a sequence of base-*b* digits to an
integer (stored as a big-endian binary integer or a Python `int`). Run
`./digits_to_number.py` for usage information.

[ntd]: number_to_digits.py
[dtn]: digits_to_number.py

Dependencies
------------

* Python ≥ 3.7

License
-------

fastconv is licensed under version 3 or later of the GNU Affero General Public
License. See [LICENSE](LICENSE).
