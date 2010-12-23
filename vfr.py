#!/usr/bin/env python3.1

import sys
import re
import linecache
import optparse
import os
import random
import math
try:
    from chapparse import writeAvisynth
    chapparseExists = True
except ImportError:
    chapparseExists = False
from subprocess import call
from fractions import Fraction

rat = re.compile('(\d+)(?:/|:)(\d+)')
v1re = re.compile('# timecode format v1')
v2re = re.compile('# timecode format v2')
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
                              version='VFR Chapter Creator 0.7.3',
                              usage='%prog [options] infile.avs{}'.format(" [outfile.avs]" if chapparseExists else ""))
    p.add_option('--label', '-l', action="store", help="Look for a trim() statement only on lines matching LABEL, interpreted as a regular expression. Default: case insensitive trim", dest="label")
    p.add_option('--input', '-i', action="store", help='Audio file to be cut', dest="input")
    p.add_option('--output', '-o', action="store", help='Cut audio from MKVMerge', dest="output")
    p.add_option('--fps', '-f', action="store", help='Frames per second (for cfr input)', dest="fps")
    p.add_option('--ofps', action="store", help='Output frames per second', dest="ofps")
    p.add_option('--timecodes', '-t', action="store", help='Timecodes file from the vfr video', dest="timecodes")
    p.add_option('--chapters', '-c', action="store", help='Chapters file [.%s/.txt]' % "/.".join(exts.keys()), dest="chapters")
    p.add_option('--chnames', '-n', action="store", help='Path to template file for chapter names', dest="chnames")
    p.add_option('--qpfile', '-q', action="store", help='QPFile for x264 (frame-accurate only if used with final framecount)', dest="qpfile")
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
        chapType = exts[cExt.group(1).lower()] if cExt else "OGM"
    else:
        chapType = ''

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
        status += "Chapters file:   %s%s\n" % (o.chapters," (%s)" % chapType if chapType else "") if o.chapters else ""
        status += "QP file:         %s\n" % o.qpfile if o.qpfile else ""
        status += "\n"
        status += "Merge/Rem files: %s/%s\n" % (o.merge,o.remove) if o.merge or o.remove else ""
        status += "Verbose:         %s\n" % o.verbose if o.verbose else ""
        status += "Test Mode:       %s\n" % o.test if o.test else ""

        print(status)
        print('In trims: %s' % ', '.join(['(%s,%s)' % (i[0],i[1]) for i in Trims]))

    # trims' offset calculation
    Trims2 = []
    Trims2ts = []
    tc = o.timecodes
    tcType = determineFormat(tc)
    if tcType == 2:
        if not os.path.isfile(tc[:-3]+"v2.txt"):
            tc2 = tc[:-3]+"v2.txt"
            tmp = tc2
            parseTc(tc,tmp,Trims[-1][1])
        else:
            tc2 = tc[:-3]+"v2.txt"
        tc = tc2
        tcType = 3

    for i in range(len(Trims)):
        fn1 = int(Trims[i][0])                     # first frame
        fn1tsaud = vTrunc(Ts(fn1,tc,tcType)[0])    # first frame timestamp for audio
        fn1ts = vTrunc(fn1tsaud)                   # first frame timestamp
        fn2 = int(Trims[i][1])                     # last frame
        fn2ts = vTrunc(Ts(fn2,tc,tcType)[0])       # last frame timestamp
        fn2tsaud = Ts(fn2+1,tc,tcType)             # last frame timestamp for audio
        adjacent = False

        # calculate offsets for non-continuous trims
        if i != 0:      # if it's not the first trim
            last = int(Trims[i-1][1])
            adjacent = True if fn1-(last+1) == 0 else False
            offset += fn1-(last+1)
            offsetts += 0 if adjacent else fn1ts-lastts
        elif fn1 > 0:   # if the first trim doesn't start at 0
            offset = fn1
            offsetts = fn1ts
        else:
            offset = 0
            offsetts = 0

        if o.input:
            # make list with timecodes to cut audio
            if adjacent:
                del audio[-1]
            else:
                audio.append(formatTime(fn1tsaud))

            if len(fn2tsaud) == 1:
                audio.append(formatTime(vTrunc(fn2tsaud[0])))

        # apply the offset to the trims
        lastts=vTrunc(fn2tsaud[0])
        fn1 -= offset
        fn2 -= offset
        fn1ts -= offsetts
        fn2ts -= offsetts

        # convert fps if --ofps
        if o.ofps and o.timecodes != o.ofps:
            fn1 = unTs(fn1,tc,o.ofps)
            fn2 = unTs(fn2,tc,o.ofps)

        # add trims and their timestamps to list
        Trims2.append([fn1,fn2])
        Trims2ts.append([fn1ts,fn2ts])

    if o.verbose: print('Out trims: %s\n' % ', '.join(['(%s,%s)' % (i[0],i[1]) for i in Trims2]))
    if o.verbose: print('Out timecodes: %s\n' % ', '.join(['(%s,%s)' % (formatTime(Trims2ts[i][0]), formatTime(Trims2ts[i][1])) for i in range(len(Trims2ts))]))
    if o.verbose and o.input: print('Audio cuts timecodes: %s\n' % ', '.join(['(%s,%s)' % (audio[i], audio[i+1]) for i in range(len(audio)//2)]))

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
            if tcType == 2: remove.append(tc)
            if o.verbose: print('\nDeleting: %s\n' % ', '.join(remove))
            if not o.test:
                [os.unlink(i) if os.path.exists(i) else True for i in remove]

    # make offseted avs
    if chapparseExists and len(a) > 1:
        fNum = [i[0] for i in Trims2]
        set = {'avs':'"'+a[1]+'"','input':'','resize':''}
        writeAvisynth(set,fNum)

    # write chapters
    if chapType:

        if chapType == 'MKV':
            EditionUID = random.randint(10**5,10**6)
            matroskaXmlHeader = '<?xml version="1.0" encoding="UTF-8"?>\n<!-- <!DOCTYPE Tags SYSTEM "matroskatags.dtd"> -->\n<Chapters>'
            matroskaXmlEditionHeader = """
	<EditionEntry>
		<EditionFlagHidden>{}</EditionFlagHidden>
		<EditionFlagDefault>{}</EditionFlagDefault>
		<EditionFlagOrdered>{}</EditionFlagOrdered>
		<EditionUID>{}</EditionUID>
""".format(0,1,1,EditionUID)
            matroskaXmlEditionFooter = '	</EditionEntry>'
            matroskaXmlFooter = '\n</Chapters>'

            matroskaXmlTagsHeader = '<?xml version="1.0" encoding="UTF-8"?>\n<!-- <!DOCTYPE Tags SYSTEM "matroskatags.dtd"> -->\n<Tags>'
            matroskaXmlTagsEdition = """
	<Tag>
		<Targets>
			<EditionUID>{}</EditionUID>
			<TargetTypeValue>50</TargetTypeValue>
		</Targets>

		<Simple>
			<Name>TITLE</Name>
			<String>{}</String>
			<TagLanguage>{}</TagLanguage>
			<DefaultLanguage>1</DefaultLanguage>
		</Simple>

	</Tag>""".format(EditionUID,"Default","eng")

        # Assign names to each chapter if --chnames
        chapNames = []

        if o.chnames:
            with open(o.chnames, "r") as f:
                [chapNames.append(line.strip()) for line in f.readlines()]

        if not o.chnames or len(chapNames) != len(Trims2ts):
            # The if statement is for clarity; it doesn't actually do anything useful
            for i in range(len(chapNames),len(Trims2ts)):
                chapNames.append("Chapter {:02d}".format(i+1))

        if not o.test:
            with open(o.chapters, "w") as output:
                if chapType == 'MKV':
                    output.write(matroskaXmlHeader)
                    output.write(matroskaXmlEditionHeader)
                    [output.write(generateChap(formatTime(Trims2ts[i][0]), formatTime(Trims2ts[i][1]),i+1,chapNames[i],chapType)) for i in range(len(Trims2ts))]
                    output.write(matroskaXmlEditionFooter)
                    output.write(matroskaXmlFooter)
                else:
                    [output.write(generateChap(formatTime(Trims2ts[i][0],1), formatTime(Trims2ts[i][1],1),i+1,chapNames[i],chapType)) for i in range(len(Trims2ts))]
        if o.verbose:
            print("Writing {} Chapters to {}".format(chapType,o.chapters))

def formatTime(ts,msp=None):
    """Converts ns timestamps to timecodes."""
    s = ts / 10**9
    m = s // 60
    s = s % 60
    h = m // 60
    m = m % 60
    if msp:
        return '{:02.0f}:{:02.0f}:{:06.3f}'.format(h, m, s)
    else:
        return '{:02.0f}:{:02.0f}:{:012.9f}'.format(h, m, s)

def determineFormat(timecodes):
    """Determines the format of the timecodes provided using regex."""
    if rat.match(timecodes) or re.match('^\d+$',timecodes): return 1
    elif v1re.match(linecache.getline(timecodes,1)): return 2
    elif v2re.match(linecache.getline(timecodes,1)): return 3
    else: return 0

def vTrunc(ts):
    """Truncates a ns timestamp to 0.1ms precision"""
    ts = ts / 10**6
    tts = round(ts,1) if round(ts,1) == math.floor(ts*10)/10 else math.ceil(ts*10)/10-0.05
    return int(round(tts*10**6))

def parseTc(tcfile,tmp,last):
    tc = open(tcfile)
    ts = 0
    ret = re.search('# timecode format (v\d)',tc.readline())
    version = ret.group(1) if ret else sys.exit('file is not in a supported format')
    tmp = open(tmp,'w')
    if version == 'v1':
        tclines = tc.readlines()
        tc.close()
        ret = re.search('Assume (\d+(?:\.\d+)?)(?i)',tclines[0])
        assume = Fraction(ret.group(1)).limit_denominator(1001) if ret else sys.exit('there is no assumed fps')
        overrides = [[range(int(i[0]),int(i[1])+1),Fraction(i[2]).limit_denominator(1001)] for i in re.findall('^(\d+),(\d+),(\d+(?:\.\d+)?)$(?m)',''.join(tclines[1:]))] if len(tclines) > 1 else None
        ret = re.search('^# TDecimate Mode 3:  Last Frame = (\d)$(?m)',''.join(tclines))
        last = int(ret) if ret else last
        tmp.write('# timecode format v2\n')
        for i in range(int(last)+1):
            fps = assume
            if overrides:
                for r in overrides:
                    if i in r[0]:
                        fps = r[1]
            ts += fps.denominator/fps.numerator if i > 0 else 0
            tmp.write('{}\n'.format(round(vTrunc(int(round(ts,7)*10**9))/10**6,6)))
        tmp.close()
    elif version == 'v2':
        tc.close()

def Ts(fn,tc,tcType=1,timecode_scale=1000):
    """Returns timestamps (in ns) from a frame number and timecodes file."""
    scale = 10**12 / timecode_scale
    # CFR
    if tcType == 1:
        fps = rat.search(tc).groups() if rat.search(tc) else [re.search('(\d+)',tc).group(0),'1']
        ts = int(round((scale * fn * float(fps[1])) / int(fps[0])))
        return [ts,]
    # VFR
    elif tcType >= 2:
        ts = linecache.getline(tc,fn+2)
        if ts == '':
            lines = 0
            with open(tc) as file:
                for line in file:
                    lines += 1
            nLines = math.ceil(lines / 100)
            average = 0
            for i in range(nLines):
                average += (int(float(linecache.getline(tc,lines-i))*10**6) - int(float(linecache.getline(tc,lines-i-1))*10**6))
            average = average / nLines
            lastTs = int(float(linecache.getline(tc,lines))*10**6)
            secdTs = int(float(linecache.getline(tc,lines-1))*10**6)
            ts = int(fn * average)
            if fn != lines-1:
                print("Warning: Trim {} goes beyond last frame. Audio cutting not recommended.".format(fn))
            return [ts,'out-of-bounds']
        return [int(float(ts)*10**6),]
    elif len(tc) != 2:
        sys.exit("Ts() needs a list with timecode file and format determined by determineFormat()")
    else:
        sys.exit("Couldn't get timestamps")

def unTs(fn,old,new):
    """Returns a frame number from fps and ofps (ConvertFPS)"""
    old=Ts(fn,old,1,10**9)[0]
    ofps = rat.search(new).groups() if rat.search(new) else [re.search('(\d+)',new).group(0),'1']
    new=old/10**3/(float(ofps[1])/int(ofps[0]))
    new=new if math.floor(new) == math.floor(abs(new-0.2)) else new-0.2
    return int(math.floor(new))

def generateChap(start, end, chapter, chaptername, type):
    """Generates chapters"""
    # Matroska
    if type == 'MKV':
        return """
		<ChapterAtom>
			<ChapterTimeStart>{}</ChapterTimeStart>
			<ChapterTimeEnd>{}</ChapterTimeEnd>
			<ChapterDisplay>
				<ChapterString>{}</ChapterString>
				<ChapterLanguage>{}</ChapterLanguage>
			</ChapterDisplay>
		</ChapterAtom>
"""[1:].format(start,end,chaptername,"eng")
    # OGM
    elif type == 'OGM':
        return 'CHAPTER{0:02d}={1}\nCHAPTER{0:02d}NAME={2}\n'.format(chapter,start,chaptername)
    # X264
    elif type == 'X264':
        return '{0} {1}\n'.format(start,chaptername)

if __name__ == '__main__':
    main()
