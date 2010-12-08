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
tcConv = r'tcConv'
mkvmerge = r'mkvmerge'

def main():

    p = optparse.OptionParser(description='Grabs avisynth trims and outputs chapter file, qpfile and/or cuts audio (works with cfr and vfr input)',
                              version='VFR Chapter Creator 0.7.1',
                              usage='%prog [options] infile.avs{}'.format(" [outfile.avs]" if chapparseExists else ""))
    p.add_option('--label', '-l', action="store", help="Look for a trim() statement only on lines matching LABEL, interpreted as a regular expression. Default: case insensitive trim", dest="label")
    p.add_option('--input', '-i', action="store", help='Audio file to be cut', dest="input")
    p.add_option('--output', '-o', action="store", help='Cut audio from MKVMerge', dest="output")
    p.add_option('--fps', '-f', action="store", help='Frames per second (for cfr input)', dest="fps")
    p.add_option('--ofps', action="store", help='Output frames per second', dest="ofps")
    p.add_option('--timecodes', '-t', action="store", help='Timecodes file from the vfr video (v1 needs tcConv)', dest="timecodes")
    p.add_option('--chapters', '-c', action="store", help='Chapters file [.%s/.txt]' % "/.".join(exts.keys()), dest="chapters")
    p.add_option('--qpfile', '-q', action="store", help='QPFile for x264 (frame-accurate only if used with final framecount)', dest="qpfile")
    p.add_option('--verbose', '-v', action="store_true", help='Verbose', dest="verbose")
    p.add_option('--merge', '-m', action="store_true", help='Merge cut files', dest="merge")
    p.add_option('--remove', '-r', action="store_true", help='Remove cut files', dest="remove")
    p.add_option('--frames', action="store", help='Number of frames for v1 conversion', dest="frames")
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
        o.output = '%s.cut.mka' % re.search("(.*)\.\w*$",o.input).group(1)

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
    tcType = determineFormat(o.timecodes)
    tc = o.timecodes
    if tcType == 2:
        nTrims = int(o.frames) if o.frames else int(Trims[-1][1])+2
        if os.path.isfile(tc+"v2.txt") == False:
            tcConv = call('"%s" "%s" "%s" %d' % (tcConv, tc, tc+"v2.txt", nTrims))
            if tcConv > 0:
                sys.exit("Failed to execute tcConv: %d; Please put it in your path" % tcConv)
        o.timecodes = tc+"v2.txt"

    for i in range(len(Trims)):
        fn1 = int(Trims[i][0])                     # first frame
        fn1ts = Ts(fn1,tc,tcType)[0]               # first frame timestamp
        fn2 = int(Trims[i][1])                     # last frame
        fn2ts = Ts(fn2,tc,tcType)[0]               # last frame timestamp
        if o.input: fn2tsaud = Ts(fn2+1,tc,tcType) # last frame timestamp for audio

        if i != 0:      # if it's not the first trim
            last = int(Trims[i-1][1])
            lastts = Trims2ts[i-1][1]
            offset += fn1-(last+1)
            offsetts += fn1ts-lastts if fn1-(last+1) != 0 else 0
        elif fn1 > 0:   # if the first trim doesn't start at 0
            offset = fn1
            offsetts = fn1ts
        else:
            offset = 0
            offsetts = 0

        if o.input:
            # make list with timecodes to cut audio
            audio.append(formatTime(fn1ts))
            if len(fn2tsaud) == 1:
                audio.append(formatTime(fn2tsaud[0]))

        # apply the offset to the trims
        fn1 -= offset
        fn2 -= offset
        fn1ts -= offsetts
        fn2ts -= offsetts

        # convert fps if --ofps
        if o.ofps and o.timecodes != o.ofps:
            fn1 = unTs(fn1ts,o.ofps)
            fn2 = unTs(fn2ts,o.ofps)

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

        if not o.test:
            with open(o.chapters, "w") as output:
                if chapType == 'MKV':
                    output.write(matroskaXmlHeader)
                    output.write(matroskaXmlEditionHeader)
                    [output.write(generateChap(formatTime(Trims2ts[i][0]), formatTime(Trims2ts[i][1]),i+1,chapType)) for i in range(len(Trims2ts))]
                    output.write(matroskaXmlEditionFooter)
                    output.write(matroskaXmlFooter)
                else:
                    [output.write(generateChap(formatTime(Trims2ts[i][0],1), formatTime(Trims2ts[i][1],1),i+1,chapType)) for i in range(len(Trims2ts))]
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

def Ts(fn,tc,tcType=1):
    """Returns timestamps (in ns) from a frame number and timecodes file."""
    # CFR
    if tcType == 1:
        fps = rat.search(tc).groups() if rat.search(tc) else [re.search('(\d+)',tc).group(0),'1']
        ts = int(round((10**5 * fn * float(fps[1])) / int(fps[0])))*10**4
        return [vTrunc(ts),]
    # VFR
    elif tcType >= 2:
        ts = linecache.getline(tc,fn+2)
        if ts == '':
            lines = 0
            with open(tc,"r") as file:
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
        print("tc needs a list with timecode file and format determined by determineFormat()")
    else:
        sys.exit("Couldn't get timestamps")

def unTs(ts,fps):
    """Returns a frame number from fps and ofps (ConvertFPS)"""
    ofps = rat.search(fps).groups() if rat.search(fps) else [re.search('(\d+)',fps).group(0),'1']
    return int(math.floor(ts / 1000.0 / (float(ofps[1]) / int(ofps[0]))))

def generateChap(start, end, chapter, type):
    """Generates chapters"""
    # Matroska
    if type == 'MKV':
        return """
		<ChapterAtom>
			<ChapterTimeStart>{}</ChapterTimeStart>
			<ChapterTimeEnd>{}</ChapterTimeEnd>
			<ChapterDisplay>
				<ChapterString>Chapter {:02d}</ChapterString>
				<ChapterLanguage>{}</ChapterLanguage>
			</ChapterDisplay>
		</ChapterAtom>
"""[1:].format(start,end,chapter,"eng")
    # OGM
    elif type == 'OGM':
        return 'CHAPTER{0:02d}={1}\nCHAPTER{0:02d}NAME=Chapter {0:02d}\n'.format(chapter,start)
    # X264
    elif type == 'X264':
        return '{0} Chapter {1:02d}\n'.format(start,chapter)

if __name__ == '__main__':
    main()
