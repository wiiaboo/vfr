#!/usr/bin/env python3

from subprocess import check_output,CalledProcessError
from re import search
from os import rename, unlink
from os.path import isfile, join as pjoin

args = [
        r'-i audio.flac -vf 24000/1001 test.avs --test',
        r'-i audio.flac -vf 24/1.001 test.avs --test',
        r'-i audio.flac -v --ofps 24/1.001 test.avs --test',
        r'-i audio.flac -vf tc1-cfr.txt test.avs --test',
        r'-i audio.flac -vf tc1-vfr.txt test.avs --test',
        r'-i audio.flac -vf tc2-cfr.txt test.avs --test',
        r'-i audio.flac -vf tc2-vfr.txt test.avs --test',
        r'-f 24/1.001 -c chap-fps-{}.txt -n chnames.txt test.avs',
        r'-f tc1-cfr.txt -c chap-cfr-{}.txt -n chnames.txt test.avs',
        r'-f 24/1.001 -c chap-fps-{}.xml -n chnames.txt --uid 123456 test.avs',
        r'-f tc1-cfr.txt -c chap-cfr-{}.xml -t amkvc.mod.txt --uid 123456 test.avs'
        ]
stable = check_output('git tag',shell=True).decode()[:-1].split('\n')[-1]
current = search('^\* (\w+)(?m)',check_output("git branch",shell=True).decode()[:-1]).group(1)

check_output('git show {0}:vfr.py > vfr.py'.format(stable), shell=True)
check_output('git show {0}:templates.py > templates.py'.format(stable), shell=True)
try:
    old = [check_output(r'python vfr.py ' + command.format('old'), shell=True) for command in args]
    new = [check_output(r'python {0} {1}'.format(pjoin('..', 'vfr.py'), command.format('new')), shell=True) for command in args]
    fails = []
    for i in range(len(old)):
        if old[i] != new[i]:
            fails.append(args[i])
    chapters = [[f.format('old'),f.format('new')] for f in ['chap-fps-{}.txt','chap-cfr-{}.txt','chap-fps-{}.xml','chap-cfr-{}.xml','chap-cfr-{}tags.xml','chap-cfr-{}.qpfile']]
    for f in chapters:
        with open(f[0],'rb') as oldf:
            with open(f[1],'rb') as newf:
                old = oldf.readlines()
                new = newf.readlines()
                if old != new:
                    fails.append('{0} and {1} are not identical.'.format(f[0],f[1]))
    if len(fails) != 0:
        print('Failed:')
        [print(i) for i in fails]
    else:
        print('All tests passed.')
        f += ['vfr.py','templates.py']
        [[unlink(ff) for ff in f] for f in chapters]
except CalledProcessError:
    pass
