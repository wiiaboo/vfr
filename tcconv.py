#!/usr/bin/env python3.1

from sys import argv, exit
from fractions import Fraction
try:
    from vfr import parse_tc, get_ts
except ImportError:
    parse_tc = False

if len(sys.argv) == 4:
    fps=sys.argv[1]
    frames=int(sys.argv[3])
    parse_tc(fps, frames, tc)

else:
    print("tccreator.py <fps/v1 timecodes> <output v2 timecodes> <frames>")
