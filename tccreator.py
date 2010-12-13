#!/usr/bin/env python3.1
import sys

if len(sys.argv) == 4:
    with open(sys.argv[1],"w") as tc:
        frames=range(int(sys.argv[2]))
        fps=sys.argv[3].split('/')
        tc.write('# timecode format v2\n')
        for i in frames:
            ts=round(i*10**3*int(fps[1])/int(fps[0]),6)
            tc.write('%f\n' % ts)

else:
    print("tccreator.py <tcfile> <frames> <fps>")
