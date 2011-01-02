#!/usr/bin/env python3.1

from subprocess import Popen
from sys import argv
from multiprocessing import cpu_count, Pool, Queue
from os import unlink
from math import ceil

#numprocs = cpu_count()

def mp(frange):
        f1,f2=frange
        args = ['python', '../tcconv.py', inf, 'multi2.txt', str(f2), str(f1)]
        p = Popen(args)
        return p

if __name__ == '__main__':
    inf = 'tc1-vfr.txt'
    outf = 'multi.txt'
    nf = 500000
    parts = 10
    cp = 0

    nfpp = nf//parts # frames per part
    franges = [[i*nfpp,(i+1)*nfpp] for i in range(parts)] # list with frame ranges
    if nf % parts: franges[-1][-1] = nf
    loops = ceil(parts/numprocs)

    #ps = [] # placeholder for the called processes

    def pc(cp):
        ps = []
        for i in range(numprocs):
            if franges:
                partf = outf+str(cp)
                ps.append(mp(partf,franges.pop(0)))
                cp += 1
            else:
                break
        for p in ps:
            p.wait()
        return cp

    while franges:
        for i in range(loops):
            cp = pc(cp)

    with open(outf,'wb') as final:
        for i in range(cp):
            with open(outf+str(i),'rb') as partcontent:
                final.writelines(partcontent.readlines())
            unlink(outf+str(i))