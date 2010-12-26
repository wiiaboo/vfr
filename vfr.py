#!/usr/bin/env python3.1

import sys
import re
import linecache
import optparse
import os
import random
import math
from subprocess import call
from fractions import Fraction
try:
    from chapparse import writeAvisynth
except ImportError:
    writeAvisynth = False

cfr_re = re.compile('(\d+(?:\.\d+)?)(?:/|:)?(\d+(?:\.\d+)?)?')
vfr_re = re.compile('# timecode format (v1|v2)')
fpsre = re.compile("(?<!#)AssumeFPS\((\d+)\s*,\s*(\d+)\)(?i)")
exts = {
    "xml":"MKV",
    "x264.txt":"X264"
}
defaultFps = "30000/1001"

# Change the paths here if the programs aren't in your $PATH
mkvmerge = r'mkvmerge'

def main():

    p = optparse.OptionParser(description='Grabs avisynth trims and outputs chapter file, qpfile and/or cuts audio (works with cfr and vfr input)',
                              version='VFR Chapter Creator 0.7.4',
                              usage='%prog [options] infile.avs{}'.format(" [outfile.avs]" if writeAvisynth else ""))
    p.add_option('--label', '-l', action="store", help="Look for a trim() statement only on lines matching LABEL, interpreted as a regular expression. Default: case insensitive trim", dest="label")
    p.add_option('--input', '-i', action="store", help='Audio file to be cut', dest="input")
    p.add_option('--output', '-o', action="store", help='Cut audio from MKVMerge', dest="output")
    p.add_option('--fps', '-f', action="store", help='Frames per second (for cfr input)', dest="fps")
    p.add_option('--ofps', action="store", help='Output frames per second', dest="ofps")
    p.add_option('--timecodes', '-t', action="store", help='Timecodes file from the vfr video', dest="timecodes")
    p.add_option('--chapters', '-c', action="store", help='Chapters file [.%s/.txt]' % "/.".join(exts.keys()), dest="chapters")
    p.add_option('--chnames', '-n', action="store", help='Path to template file for chapter names (utf8 w/o bom)', dest="chnames")
    p.add_option('--qpfile', '-q', action="store", help='QPFile for x264', dest="qpfile")
    p.add_option('--verbose', '-v', action="store_true", help='Verbose', dest="verbose")
    p.add_option('--merge', '-m', action="store_true", help='Merge cut files', dest="merge")
    p.add_option('--remove', '-r', action="store_true", help='Remove cut files', dest="remove")
    p.add_option('--test', action="store_true", help="Test mode (do not create new files)", dest="test")
    (o, a) = p.parse_args()

    if len(a) < 1:
        p.error("No avisynth script specified.")
    elif not o.timecodes and os.path.isfile(a[0] + ".tc.txt"):
        o.timecodes = a[0] + ".tc.txt"
    elif o.timecodes and o.fps:
        p.error("Can't use vfr input AND cfr input")
    elif o.timecodes and o.ofps:
        p.error("Can't use ofps with vfr input")
    elif o.timecodes and os.path.isfile(o.timecodes):
        o.timecodes = o.timecodes
    else:
        o.timecodes = o.fps

    #Determine chapter type
    if o.chapters:
        cExt = re.search("\.(%s)" % "|".join(exts.keys()),o.chapters,re.I)
        chapter_type = exts[cExt.group(1).lower()] if cExt else "OGM"
    else:
        chapter_type = ''

    if not o.output and o.input:
        ret = re.search("(.*)\.\w*$",o.input)
        o.output = '%s.cut.mka' % ret.group(1) if ret else o.input

    quiet = '' if o.verbose else '-q'
    audio = []
    Trims = []

    with open(a[0], "r") as avsfile:
        # use only the first non-commented line with trims
        avs = avsfile.readlines()
        findTrims = re.compile("(?<!#)[^#]*\s*\.?\s*%s\((\d+)\s*,\s*(\d+)\)%s" % (o.label if o.label else "trim","" if o.label else "(?i)"))
        trimre = re.compile("(?<!#)trim\((\d+)\s*,\s*(\d+)\)(?i)")
        for line in avs:
            if findTrims.match(line):
                Trims = trimre.findall(line)
                break
        if len(Trims) < 1:
            sys.exit("Error: Avisynth script has no uncommented trims")

        # Look for AssumeFPS
        if not o.timecodes:
            for line in avs:
                if fpsre.search(line):
                    o.timecodes = '/'.join([i for i in fpsre.search(line).groups()])
                    if o.verbose:
                        print("\nFound AssumeFPS, setting CFR (%s)" % o.timecodes)
                    break

    if not o.timecodes: o.timecodes = defaultFps

    if o.verbose:
        status =  "Avisynth file:   %s\n" % a[0]
        status += "Label:           %s\n" % o.label if o.label else ""
        status += "Audio file:      %s\n" % o.input if o.input else ""
        status += "Cut Audio file:  %s\n" % o.output if o.output else ""
        status += "Timecodes/FPS:   %s%s\n" % (o.timecodes," to "+o.ofps if o.ofps else "") if o.ofps != o.timecodes else ""
        status += "Chapters file:   %s%s\n" % (o.chapters," (%s)" % chapter_type if chapter_type else "") if o.chapters else ""
        status += "QP file:         %s\n" % o.qpfile if o.qpfile else ""
        status += "\n"
        status += "Merge/Rem files: %s/%s\n" % (o.merge,o.remove) if o.merge or o.remove else ""
        status += "Verbose:         %s\n" % o.verbose if o.verbose else ""
        status += "Test Mode:       %s\n" % o.test if o.test else ""

        print(status)
        print('In trims: %s' % ', '.join(['(%s,%s)' % (i[0],i[1]) for i in Trims]))

    # trims' offset calculation
    Trimsts = []
    Trims2 = []
    Trims2ts = []
    
    # Parse timecodes/fps
    tc, max = parse_tc(o.timecodes, int(Trims[-1][1]))
    if o.ofps and o.timecodes != o.ofps:
        ofps = parse_tc(o.ofps)[0]

    for i in range(len(Trims)):
        fn1 = int(Trims[i][0])
        fn1ts = truncate(get_ts(fn1,tc))
        fn1tsaud = get_ts(fn1,tc)
        fn2 = int(Trims[i][1])
        fn2ts = truncate(get_ts(fn2,tc))
        fn2tsaud = get_ts(fn2+1,tc)
        adjacent = False
        Trimsts.append((fmt_time(fn1ts),fmt_time(fn2ts)))

        # calculate offsets for non-continuous trims
        if i == 0:
            offset = 0
            offsetts = 0
            if fn1 > 0:
                # if the first trim doesn't start at 0
                offset = fn1
                offsetts = fn1ts
        else:
            # if it's not the first trim
            last = int(Trims[i-1][1])
            lastts = truncate(get_ts(last+1,tc))
            adjacent = True if not fn1-(last+1) else False
            offset += fn1-(last+1)
            offsetts += 0 if adjacent else fn1ts-lastts           

        if o.input:
            # make list with timecodes to cut audio
            if adjacent:
                #print("adjacent")
                del audio[-1]
            elif fn1 <= max:
                #print("fn1tsaud",fmt_time(fn1tsaud))
                audio.append(fmt_time(fn1tsaud))

            if fn2 <= max:
                #print("fn1tsaud",fmt_time(fn1tsaud))
                audio.append(fmt_time(fn2tsaud))

        # apply the offset to the trims
        fn1 -= offset
        fn2 -= offset
        fn1ts -= offsetts
        fn2ts -= offsetts

        # convert fps if --ofps
        if o.ofps and o.timecodes != o.ofps:
            fn1 = convert_fps(fn1,tc,ofps)
            fn2 = convert_fps(fn2,tc,ofps)

        # add trims and their timestamps to list
        Trims2.append([fn1,fn2])
        Trims2ts.append([fn1ts,fn2ts])

    #print(max,fmt_time(get_ts(max,tc)))
    if o.verbose: print('In timecodes: %s\n' % ', '.join(['(%s,%s)' % (i[0],i[1]) for i in Trimsts]))
    if o.verbose: print('Out trims: %s\n' % ', '.join(['(%s,%s)' % (i[0],i[1]) for i in Trims2]))
    if o.verbose: print('Out timecodes: %s\n' % ', '.join(['(%s,%s)' % (fmt_time(Trims2ts[i][0]), fmt_time(Trims2ts[i][1])) for i in range(len(Trims2ts))]))

    # make qpfile
    if o.qpfile:
        if not o.test:
            with open(o.qpfile, "w") as qpf:
                for trim in Trims2[1:]:
                    qpf.write('%s K\n' % trim[0])
        if o.verbose: print('Writing keyframes to %s\n' % o.qpfile)

    # make audio cuts
    if o.input:
        delayRe = re.search('DELAY ([-]?\d+)',o.input)
        delay = delayRe.group(1) if delayRe else '0'
        if Trims[0][0] == 0:
            includefirst = True
            audio = audio[1:]
        else:
            includefirst = False
        cuttimes = ','.join(audio)
        cutCmd = '"%s" -o "%s" --sync 0:%s "%s" --split timecodes:%s %s' % (mkvmerge, o.output + '.split.mka', delay, o.input, cuttimes, quiet)
        if o.verbose: print('Cutting: %s\n' % cutCmd)
        if not o.test:
            cutExec = call(cutCmd)
            if cutExec == 1:
                print("Mkvmerge exited with warnings: %d" % cutExec)
            elif cutExec == 2:
                sys.exit("Failed to execute mkvmerge: %d" % cutExec)
        if o.merge:
            merge = []
            for i in range(1,len(audio)+2):
                if (includefirst == True and i % 2 != 0) or (includefirst == False and i % 2 == 0):
                    merge.append('"%s.split-%03d.mka"' % (o.output, i))
            mergeCmd = '"%s" -o "%s" %s %s' % (mkvmerge,o.output, ' +'.join(merge), quiet)
            if o.verbose: print('\nMerging: %s\n' % mergeCmd)
            if not o.test:
                mergeExec = call(mergeCmd)
                if mergeExec == 1:
                    print("Mkvmerge exited with warnings: %d" % mergeExec)
                elif mergeExec == 2:
                    sys.exit("Failed to execute mkvmerge: %d" % mergeExec)

        if o.remove:
            remove = ['%s.split-%03d.mka' % (o.output, i) for i in range(1,len(audio)+2)]
            if o.verbose: print('\nDeleting: %s\n' % ', '.join(remove))
            if not o.test:
                [os.unlink(i) if os.path.exists(i) else True for i in remove]

    # make offseted avs
    if writeAvisynth and len(a) > 1:
        fNum = [i[0] for i in Trims2]
        set = {'avs':'"'+a[1]+'"','input':'','resize':''}
        writeAvisynth(set,fNum)

    # write chapters
    if chapter_type:

        if chapter_type == 'MKV':
            EditionUID = random.randint(10**5,10**6)
            matroskaXmlHeader = '<?xml version="1.0" encoding="UTF-8"?>\n<!-- <!DOCTYPE Tags SYSTEM "matroskatags.dtd"> -->\n<Chapters>'
            matroskaXmlEditionHeader = """
	<EditionEntry>
		<EditionFlagHidden>{}</EditionFlagHidden>
		<EditionFlagDefault>{}</EditionFlagDefault>
		<EditionFlagOrdered>{}</EditionFlagOrdered>
		<EditionUID>{}</EditionUID>""".format(0,1,0,EditionUID)
            matroskaXmlEditionFooter = '\n	</EditionEntry>'
            matroskaXmlFooter = '\n</Chapters>'

        # Assign names to each chapter if --chnames
        chapter_names = []

        if o.chnames:
            with open(o.chnames, "r", encoding='utf_8') as f:
                [chapter_names.append(line.strip()) for line in f.readlines()]

        if not o.chnames or len(chapter_names) != len(Trims2ts):
            # The if statement is for clarity; it doesn't actually do anything useful
            for i in range(len(chapter_names),len(Trims2ts)):
                chapter_names.append("Chapter {:02d}".format(i+1))

        if not o.test:
            with open(o.chapters, "w",encoding='utf_8') as output:
                if chapter_type == 'MKV':
                    output.write(matroskaXmlHeader)
                    output.write(matroskaXmlEditionHeader)
                    [output.write(generate_chapters(fmt_time(Trims2ts[i][0]), fmt_time(Trims2ts[i][1]),i+1,chapter_names[i],chapter_type)) for i in range(len(Trims2ts))]
                    output.write(matroskaXmlEditionFooter)
                    output.write(matroskaXmlFooter)
                else:
                    [output.write(generate_chapters(fmt_time(Trims2ts[i][0],1), fmt_time(Trims2ts[i][1],1),i+1,chapter_names[i],chapter_type)) for i in range(len(Trims2ts))]
        if o.verbose:
            print("Writing {} Chapters to {}".format(chapter_type,o.chapters))

def fmt_time(ts,msp=None):
    """Converts timestamps to timecodes.
    
    msp = Set timecodes for millisecond precision if True
    
    """
    s = ts / 10**9
    m = s // 60
    s = s % 60
    h = m // 60
    m = m % 60
    if msp:
        return '{:02.0f}:{:02.0f}:{:06.3f}'.format(h, m, s)
    else:
        return '{:02.0f}:{:02.0f}:{:012.9f}'.format(h, m, s)

def get_tc_type(timecodes):
    """Determines the format of the timecodes provided using regex."""
    if cfr_re.match(timecodes): return 1
    elif vfr_re.match(linecache.getline(timecodes,1)):
        type = vfr_re.match(linecache.getline(timecodes,1)).group(1)
        if type == 'v1': return 2
        elif type == 'v2': return 3
    else: sys.exit('Invalid timecodes/fps')

def truncate(ts,scale=0):
    """Truncates a ns timestamp to 0.1*scale precision
    with an extra decimal place if it rounds up.
    
    Default: 0 (0.1 ms)
    
    Examples: 3 (0.1 µs); 6 (0.1 ns)
    
    """
    scale = abs(6-scale)
    ots = ts / 10**scale
    tts = math.floor(ots*10)*10 if round(ots,1) == math.floor(ots*10)/10 else math.ceil(ots*10)*10-5
    return int(tts*10**(scale-2))

def parse_tc(tcfile,last=0):
    """Parses a timecodes file or cfr fps.
    
    tcfile = timecodes file or cfr fps to parse
    last = number of frames to be created in v1 parsing
    
    """
    
    ret = cfr_re.search(tcfile)
    if ret and not os.path.isfile(tcfile):
        type = 'cfr'
        num = Fraction(ret.group(1))
        den = Fraction(ret.group(2)) if ret.group(2) else 1
        timecodes = Fraction(num,den)
    
    else:
        type = 'vfr'
        with open(tcfile) as tc:
            tclines = tc.readlines()
        ret = vfr_re.search(tclines[0])
        version = ret.group(1) if ret else sys.exit('File is not in a supported format.')
        del tclines[0]
        
        if version == 'v1':
            ts = 0
            timecodes = []
            ret = re.search('^Assume (\d+(?:[.]\d+)?)(?i)',tclines[0])
            assume = Fraction(ret.group(1)).limit_denominator(1001) if ret else sys.exit('there is no assumed fps')
            overrides = {}
            ret = [[range(int(i[0])+1,int(i[1])+2),Fraction(i[2]).limit_denominator(1001)] for i in re.findall('^(\d+),(\d+),(\d+(?:\.\d+)?)$(?m)',''.join(tclines[1:]))] if len(tclines) > 1 else None
            if ret:
                for ov_fps in ret:
                    for frame in ov_fps[0]:
                        overrides[frame] = ov_fps[1]
            ret = re.search('^# TDecimate Mode 3:  Last Frame = (\d)$(?m)',''.join(tclines))
            last = int(ret) if ret else last
            for frame in range(int(last)+2):
                fps = assume
                if overrides and frame in overrides:
                    fps = overrides[frame]
                ts += fps.denominator/fps.numerator if frame > 0 else 0
                timecodes.append(round(ts*10**3,6))
        
        elif version == 'v2':
            if last > len(tclines):
                p_last = last+2
                last = len(tclines)
                sample = last//100
                average = 0
                for i in range(-sample,0):
                    average += round(float(tclines[-10])-float(tclines[-11]),6)
                fps = Fraction.from_float(average / sample / 1000).limit_denominator(60000)
                if tclines[-1][-1] is not '\n': tclines[-1] += '\n'
                for fn in range(last,p_last):
                    tclines.append(round(fn*fps,6))
            timecodes = [round(float(line),6) for line in tclines]

    return (timecodes, type), last

def get_ts(fn,tc,scale=0):
    """Returns timestamps from a frame number and timecodes file or cfr fps
    
    fn = frame number
    tc = (timecodes list or Fraction(fps),tc_type)
    
    scale default: 0 (ns)
    examples: 3 (µs); 6 (ms); 9 (s)
    
    """
    scale = 9-scale
    tc, tc_type = tc
    if tc_type == 'cfr':
        ts = round(10**scale * fn * Fraction(tc.denominator,tc.numerator))
        return ts
    elif tc_type == 'vfr':
        ts = round(Fraction.from_float(tc[fn])*10**(scale-3))
        return ts

def convert_fps(fn,old,new):
    """Returns a frame number from fps and ofps (ConvertFPS)
    
    fn = frame number
    old = original fps ('30000/1001', '25')
    new = output fps ('24000/1001', etc.)
    
    """
    oldts=get_ts(fn,old)
    ofps=new[0]
    new=oldts/10**9/(ofps.denominator/ofps.numerator)
    new=new if math.floor(new) == math.floor(abs(new-0.2)) else new-0.2
    return int(math.floor(new))

def generate_chapters(start, end, num, name, type):
    """Generates chapters
    
    start = '00:00:00.000000000'
    end = same as start
    num = chapter number for OGM (int)
    name = chapter name
    type = 'MKV', 'OGM' or 'X264'
    
    """

    if type == 'MKV':
        return """
		<ChapterAtom>
			<ChapterTimeStart>{start}</ChapterTimeStart>
			<ChapterTimeEnd>{end}</ChapterTimeEnd>
			<ChapterDisplay>
				<ChapterString>{name}</ChapterString>
				<ChapterLanguage>"eng"</ChapterLanguage>
			</ChapterDisplay>
		</ChapterAtom>""".format(**locals())

    elif type == 'OGM':
        return 'CHAPTER{num:02d}={start}\nCHAPTER{num:02d}NAME={name}\n'.format(**locals())

    elif type == 'X264':
        return '{start} {name}\n'.format(**locals())

if __name__ == '__main__':
    main()
