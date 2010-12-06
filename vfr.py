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
fpsre = re.compile("AssumeFPS\((\d+)\s*,\s*(\d+)\)",re.I)
exts = {
    "xml":"MKV",
    "x264.txt":"X264"
}

# Change the paths here if the programs aren't in your $PATH
tcConv = r'tcConv'
mkvmerge = r'mkvmerge'

def main():

    p = optparse.OptionParser(description='Grabs avisynth trims and outputs chapter file, qpfile and/or cuts audio (works with cfr and vfr input)',
                              version='VFR Chapter Creator 0.7',
                              usage='%prog [options] infile.avs{}'.format(" [outfile.avs]" if chapparseExists else ""))
    p.add_option('--label', '-l', action="store", help="Look for a trim() statement only on lines matching LABEL, interpreted as a regular expression. Default: case insensitive trim", dest="label")
    p.add_option('--input', '-i', action="store", help='Audio file to be cut', dest="input")
    p.add_option('--output', '-o', action="store", help='Cut audio from MKVMerge', dest="output")
    p.add_option('--fps', '-f', action="store", help='Frames per second (for cfr input)', dest="fps")
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

    with open(a[0], "r") as avs:
        # use only the first non-commented line with trims
        if o.label:
            trimre = re.compile("(?<!#)%s\((\d+)\s*,\s*(\d+)\)" % o.label)
        else:
            trimre = re.compile("(?<!#)trim\((\d+)\s*,\s*(\d+)\)",re.I)
        for line in avs:
            if trimre.match(line):
                Trims = trimre.findall(line)
                break
        if len(Trims) < 1:
            sys.exit("Error: Avisynth script has no uncommented trims")

        # Look for AssumeFPS
        if not o.timecodes:
            avs.seek(0)
            for line in avs:
                if fpsre.search(line):
                    o.timecodes = '/'.join([i for i in fpsre.search(line).groups()])
                    if o.verbose:
                        print("\nFound AssumeFPS, setting CFR (%s)" % o.timecodes)
                    break
            if not o.timecodes: o.timecodes = '30000/1001'

        if o.verbose:
            status = """
Avisynth file:   {input}
Label:           {label}
Audio file:      {audio}
Cut Audio file:  {cutaudio}
Timecodes/FPS:   {timecodes}
Chapters file:   {chapters} ({cType})
QP file:         {qpfile}

Merge/Rem files: {merge}/{remove}
Verbose:         {verbose}
Test Mode:       {test}
""".format(input=a[0],
            audio=o.input,
            label=o.label,
            cutaudio=o.output,
            timecodes=o.timecodes,
            chapters=o.chapters,
            cType=chapType,
            qpfile=o.qpfile,
            merge=o.merge,
            remove=o.remove,
            verbose=o.verbose,
            test=o.test)
            print(status)
            print('In trims: %s' % ', '.join(['(%s,%s)' % (i[0],i[1]) for i in Trims]))

        # trims' offset calculation
        Trims2 = []
        Trims2ts = []
        o.timecodes = [o.timecodes, determineFormat(o.timecodes)]
        tc = o.timecodes
        if tc[1] == 2:
            nTrims = int(o.frames) if o.frames else int(Trims[-1][1])+2
            if os.path.isfile(tc[0]+"v2.txt") == False:
                tcConv = call('"%s" "%s" "%s" %d' % (tcConv, tc[0], tc[0]+"v2.txt", nTrims))
                if tcConv > 0:
                    sys.exit("Failed to execute tcConv: %d; Please put it in your path" % tcConv)
            o.timecodes[0] = tc[0]+"v2.txt"

        for i in range(len(Trims)):
            fn1 = int(Trims[i][0])  # first frame
            fn1ts = Ts(fn1,tc)[0]   # first frame timestamp
            fn2 = int(Trims[i][1])  # last frame
            fn2ts = Ts(fn2,tc)[0]   # last frame timestamp
            fn2tsaud = Ts(fn2+1,tc) # last frame timestamp for audio

            if i != 0:      # if it's not the first trim
                last = int(Trims[i-1][1])+1
                lastts = Ts(last,tc)[0]
                offset += fn1-last
                offsetts += fn1ts-lastts
            elif fn1 > 0:   # if the first trim doesn't start at 0
                offset = fn1
                offsetts = fn1ts
            else:
                offset = 0
                offsetts = 0

            # apply the offset to the trims
            Trims2.append([fn1-offset,fn2-offset])
            Trims2ts.append([fn1ts-offsetts,fn2ts-offsetts])

            # make list with timecodes to cut audio
            audio.append(formatTime(fn1ts,tc))
            if len(fn2tsaud) == 1:
                audio.append(formatTime(fn2tsaud[0],tc))

    if o.verbose: print('Out trims: %s\n' % ', '.join(['(%s,%s)' % (i[0],i[1]) for i in Trims2]))

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
        if audio[0] == "00:00:00.000":
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
            if o.verbose: print('\nMerging: %s\n' % ', '.join(merge))
            if not o.test:
                print(mergeCmd)
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
            EditionUID = random.randint(100000,1000000)
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
                    [output.write(generateChap(formatTime(Trims2ts[i][0],tc), formatTime(Trims2ts[i][1],tc),i+1,chapType)) for i in range(len(Trims2ts))]
                    output.write(matroskaXmlEditionFooter)
                    output.write(matroskaXmlFooter)
                else:
                    [output.write(generateChap(formatTime(Trims2ts[i][0],tc), formatTime(Trims2ts[i][1],tc),i+1,chapType)) for i in range(len(Trims2ts))]
        if o.verbose:
            print("Writing {} Chapters to {}".format(chapType,o.chapters))

def formatTime(ts,tc):
    """Converts timestamps to timecodes"""
    s = ts // 1000 if tc[1] == 1 else ts // 1000000000
    ms = ts % 1000 if tc[1] == 1 else ts % 1000000000
    m = s // 60
    s = s % 60
    h = m // 60
    m = m % 60
    return '{0:02d}:{1:02d}:{2:02d}.{3:03d}'.format(h, m, s, ms)

def determineFormat(timecodes):
    """Determines the format of the timecodes provided using regex."""
    if rat.match(timecodes) or re.match('^\d+$',timecodes): return 1
    elif v1re.match(linecache.getline(timecodes,1)): return 2
    elif v2re.match(linecache.getline(timecodes,1)): return 3
    else: return 0

def Ts(fn,tc):
    """Returns timestamps (in ms) from a frame number and timecodes file."""
    # CFR
    if tc[1] == 1:
        fps = rat.search(tc[0]).groups() if rat.search(tc[0]) else [re.search('(\d+)',tc[0]).group(0),'1']
        ts = int(round((1000 * fn * int(fps[1])) / int(fps[0])))
        return [ts,]
    # VFR
    elif tc[1] >= 2:
        ts = linecache.getline(tc[0],fn+2)
        if ts == '':
            lines = 0
            with open(tc[0],"r") as file:
                for line in file:
                    lines += 1
            nLines = math.ceil(lines / 100)
            average = 0
            for i in range(nLines):
                average += (int(float(linecache.getline(tc[0],lines-i))*1000000) - int(float(linecache.getline(tc[0],lines-i-1))*1000000))
            average = average / nLines
            lastTs = int(float(linecache.getline(tc[0],lines))*1000000)
            secdTs = int(float(linecache.getline(tc[0],lines-1))*1000000)
            ts = int(fn * average)
            if fn != lines-1:
                print("Warning: Trim {} goes beyond last frame. Audio cutting not recommended.".format(fn))
            return [ts,'out-of-bounds']
        return [int(float(ts)*1000000),]
    elif len(tc) != 2:
        print("tc needs a list with timecode file and format determined by determineFormat()")
    else:
        sys.exit("Couldn't get timestamps")

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
