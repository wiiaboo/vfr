#!/usr/bin/env python3.1

from sys import exit,argv
from re import compile
from os.path import isfile, splitext
from math import floor, ceil
from fractions import Fraction

trimre = compile("(?<!#)trim\((\d+)\s*,\s*(\d+)\)(?i)")
exts = {
    "xml":"MKV",
    "x264.txt":"X264"
}
default_fps = "30000/1001"

# Change the paths here if the programs aren't in your $PATH
mkvmerge = r'mkvmerge'

def main(args):
    from optparse import OptionParser
    p = OptionParser(description='Grabs avisynth trims and outputs chapter file, qpfile and/or cuts audio (works with cfr and vfr input)',
                     version='VFR Chapter Creator 0.7.6',
                     usage='%prog [options] infile.avs [outfile.avs]')
    p.add_option('--label', '-l',action="store",dest="label",
                 help="Look for a trim() statement only on lines matching LABEL, interpreted as a regular expression. Default: case insensitive trim")
    p.add_option('--input', '-i', action="store", help='Audio file to be cut', dest="input")
    p.add_option('--output', '-o', action="store", help='Cut audio from MKVMerge', dest="output")
    p.add_option('--fps', '-f', action="store", help='Frames per second or Timecodes file', dest="fps")
    p.add_option('--ofps', action="store", help='Output frames per second', dest="ofps")
    p.add_option('--timecodes', action="store", help='Output v2 timecodes', dest="otc")
    p.add_option('--chapters', '-c', action="store", help='Chapters file [.%s/.txt]' % "/.".join(exts.keys()), dest="chapters")
    p.add_option('--chnames', '-n', action="store", help='Path to template file for chapter names (utf8 w/o bom)', dest="chnames")
    p.add_option('--qpfile', '-q', action="store", help='QPFile for x264', dest="qpfile")
    p.add_option('--verbose', '-v', action="store_true", help='Verbose', dest="verbose")
    p.add_option('--merge', '-m', action="store_true", help='Merge cut files', dest="merge")
    p.add_option('--remove', '-r', action="store_true", help='Remove cut files', dest="remove")
    p.add_option('--test', action="store_true", help="Test mode (do not create new files)", dest="test")
    (o, a) = p.parse_args(args)

    if len(a) < 1:
        p.error("No avisynth script specified.")
    elif not o.fps:
        o.fps = default_fps

    #Determine chapter type
    if o.chapters:
        chre = compile("\.(%s)$(?i)" % "|".join(exts.keys()))
        ret = chre.search(o.chapters)
        chapter_type = exts[ret.group(1).lower()] if ret else "OGM"
    else:
        chapter_type = ''

    if not o.output and o.input:
        ret = splitext(o.input)
        o.output = '%s.cut.mka' % ret[0]

    audio = []
    Trims = []

    with open(a[0], "r") as avsfile:
        # use only the first non-commented line with trims
        avs = avsfile.readlines()
        findTrims = compile("(?<!#)[^#]*\s*\.?\s*%s\((\d+)\s*,\s*(\d+)\)%s" % (o.label if o.label else "trim","" if o.label else "(?i)"))
        for line in avs:
            if findTrims.match(line):
                Trims = trimre.findall(line)
                break
        nt1 = len(Trims)
        if not Trims:
            exit("Error: Avisynth script has no uncommented trims")

    if o.verbose:
        status =  "Avisynth file:   %s\n" % a[0]
        status += "Label:           %s\n" % o.label if o.label else ""
        status += "Audio file:      %s\n" % o.input if o.input else ""
        status += "Cut Audio file:  %s\n" % o.output if o.output else ""
        status += "Timecodes/FPS:   %s%s\n" % (o.fps," to "+o.ofps if o.ofps else "") if o.ofps != o.fps else ""
        status += "Output v2 Tc:    %s\n" % o.otc if o.otc else ""
        status += "Chapters file:   %s%s\n" % (o.chapters," (%s)" % chapter_type if chapter_type else "") if o.chapters else ""
        status += "QP file:         %s\n" % o.qpfile if o.qpfile else ""
        status += "\n"
        status += "Merge/Rem files: %s/%s\n" % (o.merge,o.remove) if o.merge or o.remove else ""
        status += "Verbose:         %s\n" % o.verbose if o.verbose else ""
        status += "Test Mode:       %s\n" % o.test if o.test else ""

        print(status)

    # trims' offset calculation
    Trimsts = []
    Trims2 = []
    Trims2ts = []
    
    # Parse timecodes/fps
    tc, max = parse_tc(o.fps, int(Trims[-1][1])+2,o.otc)
    if tc[1] == 'vfr' and o.ofps:
        p.error("Can't use --ofps with timecodes file input")
    if o.ofps and o.fps != o.ofps:
        ofps = parse_tc(o.ofps)[0]
        if o.otc:
            max = convert_fps(int(Trims[-1][1]),tc,ofps)
            parse_tc(o.ofps,max+2,o.otc)

    for i in range(nt1):
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
                del audio[-1]
            elif fn1 <= max:
                audio.append(fmt_time(fn1tsaud))

            if fn2 <= max:
                audio.append(fmt_time(fn2tsaud))

        # apply the offset to the trims
        fn1 -= offset
        fn2 -= offset
        fn1ts -= offsetts
        fn2ts -= offsetts

        # convert fps if --ofps
        if o.ofps and o.fps != o.ofps:
            fn1 = convert_fps(fn1,tc,ofps) if fn1 != 0 else 0
            fn2 = convert_fps(fn2,tc,ofps)
            fn1ts = truncate(get_ts(fn1,ofps))
            fn2ts = truncate(get_ts(fn2,ofps))

        # add trims and their timestamps to list
        Trims2.append([fn1,fn2])
        Trims2ts.append([fn1ts,fn2ts])

    nt2 = len(Trims2ts)
    if o.verbose:
        print('In trims: %s\n' % ', '.join(['(%s,%s)' % (i[0],i[1]) for i in Trims]))
        print('In timecodes: %s\n' % ', '.join(['(%s,%s)' % (i[0],i[1]) for i in Trimsts]))
        print('Out trims: %s\n' % ', '.join(['(%s,%s)' % (i[0],i[1]) for i in Trims2]))
        print('Out timecodes: %s\n' % ', '.join(['(%s,%s)' % (fmt_time(i[0]),fmt_time(i[1])) for i in Trims2ts]))

    # make qpfile
    if o.qpfile:
        if not o.test:
            write_qpfile(o.qpfile,Trims2)
        if o.verbose: print('Writing keyframes to %s\n' % o.qpfile)

    # make audio cuts
    if o.input:
        from subprocess import call
        delre = compile('DELAY ([-]?\d+)')
        ret = delre.search(o.input)
        delay = ret.group(1) if ret else '0'
        if Trims[0][0] == 0:
            includefirst = True
            audio = audio[1:]
        else:
            includefirst = False
        cuttimes = ','.join(audio)
        quiet = '' if o.verbose else '-q'
        cutCmd = '"%s" -o "%s" --sync 0:%s "%s" --split timecodes:%s %s' % (mkvmerge, o.output + '.split.mka', delay, o.input, cuttimes, quiet)
        if o.verbose: print('Cutting: %s\n' % cutCmd)
        if not o.test:
            cutExec = call(cutCmd)
            if cutExec == 1:
                print("Mkvmerge exited with warnings: %d" % cutExec)
            elif cutExec == 2:
                exit("Failed to execute mkvmerge: %d" % cutExec)
        if o.merge:
            merge = []
            max_audio = len(audio)+2
            for i in range(1,max_audio):
                if (includefirst == True and i % 2 != 0) or (includefirst == False and i % 2 == 0):
                    merge.append('"%s.split-%03d.mka"' % (o.output, i))
            mergeCmd = '"%s" -o "%s" %s %s' % (mkvmerge,o.output, ' +'.join(merge), quiet)
            if o.verbose: print('\nMerging: %s\n' % mergeCmd)
            if not o.test:
                mergeExec = call(mergeCmd)
                if mergeExec == 1:
                    print("Mkvmerge exited with warnings: %d" % mergeExec)
                elif mergeExec == 2:
                    exit("Failed to execute mkvmerge: %d" % mergeExec)

        if o.remove:
            remove = ['%s.split-%03d.mka' % (o.output, i) for i in range(1,max_audio)]
            if o.verbose: print('\nDeleting: %s\n' % ', '.join(remove))
            if not o.test:
                from os import unlink
                [unlink(i) if isfile(i) else True for i in remove]

    # make offseted avs
    if len(a) > 1:
        try:
            from chapparse import writeAvisynth
            fNum = [i[0] for i in Trims2]
            set = {'avs':'"'+a[1]+'"','input':'','resize':''}
            writeAvisynth(set,fNum)
        except ImportError:
            print('Script chapparse.py needed for avisynth output to work.')

    # write chapters
    if chapter_type:
        from random import randint
        if chapter_type == 'MKV':
            EditionUID = randint(10**5,10**6)
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

        if not o.chnames or len(chapter_names) < len(Trims2ts):
            # The if statement is for clarity; it doesn't actually do anything useful
            for i in range(len(chapter_names),len(Trims2ts)):
                chapter_names.append("Chapter {:02d}".format(i+1))

        if not o.test:
            with open(o.chapters, "w",encoding='utf-8') as output:
                if chapter_type == 'MKV':
                    Trims2ts = [(fmt_time(i[0]),fmt_time(i[1])) for i in Trims2ts]
                    output.write(matroskaXmlHeader)
                    output.write(matroskaXmlEditionHeader)
                    [output.write(generate_chapters(Trims2ts[i][0], Trims2ts[i][1],i+1,chapter_names[i],chapter_type)) for i in range(len(Trims2ts))]
                    output.write(matroskaXmlEditionFooter)
                    output.write(matroskaXmlFooter)
                else:
                    Trims2ts = [(fmt_time(i[0],1),fmt_time(i[1],1)) for i in Trims2ts]
                    [output.write(generate_chapters(Trims2ts[i][0], Trims2ts[i][1],i+1,chapter_names[i],chapter_type)) for i in range(len(Trims2ts))]
        if o.verbose:
            print("Writing {} Chapters to {}".format(chapter_type,o.chapters))

def fmt_time(ts,msp=None):
    """Converts nanosecond timestamps to timecodes.
    
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

def truncate(ts,scale=0):
    """Truncates a ns timestamp to 0.1*scale precision
    with an extra decimal place if it rounds up.
    
    Default: 0 (0.1 ms)
    
    Examples: 3 (0.1 µs); 6 (0.1 ns)
    
    """
    scale = abs(6-scale)
    ots = ts / 10**scale
    tts = floor(ots*10)*10 if round(ots,1) == floor(ots*10)/10 else ceil(ots*10)*10-5
    return int(tts*10**(scale-2))

def correct_to_ntsc(fps,ms=None):
    """Rounds framerate to NTSC values if close enough.
    
    Takes and returns a Rational number.
    
    Ported from FFmpegsource.
    
    """
    fps = Fraction(fps)
    TempFPS = Fraction(fps.denominator,fps.numerator)
    
    if TempFPS.numerator == 1:
        Num = TempFPS.denominator
        Den = TempFPS.numerator
    else:
        FTimebase = TempFPS.numerator/TempFPS.denominator
        NearestNTSC = floor(FTimebase * 1001 + 0.5) / 1001
        SmallInterval = 1/120

        if abs(FTimebase - NearestNTSC) < SmallInterval:
            Num = int((1001 / FTimebase) + 0.5)
            Den = 1001

    if not ms:
        return Fraction(Num, Den)
    else:
        return Den/(Num/1000)

def convert_v1_to_v2(v1,max,asm,v2=None,first=0):
    """Converts a given v1 timecodes file to v2 timecodes.
    
    Original idea from tritical's tcConv.
    
    """
    ts = fn1 = fn2 = last = 0
    asm = correct_to_ntsc(asm,True)
    o=[]
    ap=o.append
    en=str.encode
    for line in v1:
        ovr = line.split(',')
        if len(ovr) == 3:
            fn1,fn2,fps = ovr
            fn1 = int(fn1)
            fn2 = int(fn2)
            ovf = correct_to_ntsc(fps,True)
            while (last < fn1 and last < max):
                ap(ts)
                last,ts=last+1,ts+asm
            while (last <= fn2 and last < max):
                ap(ts)
                last,ts=last+1,ts+ovf
    while last < max:
        ap(ts)
        last,ts=last+1,ts+asm
    if v2:
        with open(v2,'wb') as v2f:
            from os import linesep as ls
            header = [en('# timecode format v2'+ls)] if first == 0 else [b'']
            v2f.writelines(header+[en(('%3.6f' % s)+ls ) for s in o[first:]])
    return o[first:]

def parse_tc(tcfile, max=0, otc=None,first=0):
    """Parses a timecodes file or cfr fps.
    
    tcfile = timecodes file or cfr fps to parse
    max = number of frames to be created in v1 parsing
    otc = output v2 timecodes filename
    
    """

    cfr_re = compile('(\d+(?:\.\d+)?)(?:/|:)?(\d+(?:\.\d+)?)?')
    vfr_re = compile('# timecode format (v1|v2)')

    ret = cfr_re.search(tcfile)
    if ret and not isfile(tcfile):
        type = 'cfr'
        num = Fraction(ret.group(1))
        den = Fraction(ret.group(2)) if ret.group(2) else 1
        timecodes = Fraction(num,den)
        if otc:
            convert_v1_to_v2([],max+2,timecodes,otc,first)
    
    else:
        type = 'vfr'
        with open(tcfile) as tc:
            v1 = tc.readlines()
        ret = vfr_re.search(v1.pop(0))
        version = ret.group(1) if ret else exit('File is not in a supported format.')

        if version == 'v1':
            ret = v1.pop(0).split(' ')
            asm = ret[1] if len(ret) == 2 else exit('there is no assumed fps')
            if v1:
                ret = convert_v1_to_v2(v1,max,asm,otc,first)
                timecodes = ['%3.6f\n' % i for i in ret]
            else:
                timecodes = correct_to_ntsc(asm)
                type = 'cfr'
                if otc:
                    convert_v1_to_v2([],max+2,timecodes,otc,first)

        elif version == 'v2':
            if max > len(v1):
                temp_max = len(v1)
                sample = temp_max//100
                average = 0
                for i in range(-sample,0):
                    average += round(float(v1[i])-float(v1[i-1]),6)
                fps = correct_to_ntsc(Fraction.from_float(average / sample))
                ret = convert_v1_to_v2([],max,fps,last=temp_max)
                if v1[-1][-1] is not '\n': v1[-1] += '\n'
                for fn in range(temp_max,max):
                    v1 += ['%3.6f\n' % i for i in ret]
            timecodes = v1

    return (timecodes, type), max

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
        ts = round(float(tc[fn])*10**(scale-3))
        return ts

def convert_fps(fn,old,new):
    """Returns a frame number from fps and ofps (ConvertFPS)
    
    fn = frame number
    old = original fps ('30000/1001', '25')
    new = output fps ('24000/1001', etc.)
    
    """
    oldts=get_ts(fn,old)
    ofps=new[0]
    new=oldts/10**9*ofps
    new=floor(new) if floor(new) == floor(abs(new-0.4)) else floor(new-0.4)
    return new

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
				<ChapterLanguage>eng</ChapterLanguage>
			</ChapterDisplay>
		</ChapterAtom>""".format(**locals())

    elif type == 'OGM':
        return 'CHAPTER{num:02d}={start}\nCHAPTER{num:02d}NAME={name}\n'.format(**locals())

    elif type == 'X264':
        return '{start} {name}\n'.format(**locals())

def write_qpfile(qpfile,trims):
    """Simply writes keyframes for use in x264 from a list of Trims."""
    
    with open(qpfile, "w") as qpf:
        if trims[0][0] == 0:
            del trims[0]
        for trim in trims:
            qpf.write('%s K\n' % trim[0])

if __name__ == '__main__':
    main(argv[1:])
