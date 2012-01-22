#!/usr/bin/env python3

from sys import argv
try:
    from vfr import parse_tc
except ImportError:
    exit("tcconv requires vfr.py in order to work")

if len(argv) >= 4:
    fps = argv[1]
    tc = argv[2]
    frames = int(argv[3])
    first = int(argv[4]) if len(argv) == 5 else 0
    parse_tc(fps, frames, tc, first)
else:
    exit("tcconv.py <fps/v1 timecodes> <output v2 timecodes> <frames> [<first>]")
