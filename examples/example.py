# A small file with a few deliberate problems in it, used to demonstrate PyScan
# in the README and in the report.

import os


def calculateTotal(userName):
    unusedValue = 1
    total = 0
    for character in userName:
        total = total + 1
    return total
