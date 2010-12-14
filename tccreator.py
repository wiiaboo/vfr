#!/usr/bin/env python3.1

import sys, os
from fractions import Fraction
try:
    from vfr import parseTc
    vfr = True
except ImportError:
    vfr = False

if len(sys.argv) == 4:
    with open(sys.argv[1],"w") as tc:
        frames=int(sys.argv[2])
        fps=sys.argv[3]
        # v1 timecodes parsing
        if os.path.exists(fps):
            tc.close()
            tc=sys.argv[1]
            if not vfr:
                sys.exit("vfr.py needs to be in the same directory for v1 timecodes parsing")
            parseTc(fps,tc,frames)
        # cfr frame generation
        else:
            fps=Fraction(fps).limit_denominator(1001)
            tc.write('# timecode format v2\n')
            for i in range(frames):
                ts=round(i*10**3*fps.denominator/fps.numerator,6)
                tc.write('%f\n' % ts)

else:
    print("tccreator.py <tcfile> <frames> <fps/v1>")
