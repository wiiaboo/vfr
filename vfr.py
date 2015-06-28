#!/usr/bin/env python3

from sys import exit, argv
from re import compile
from os.path import isfile, splitext
from math import floor, ceil
from fractions import Fraction

exts = {
    "xml": "MKV",
    "x264.txt": "X264"
}
default_fps = "30000/1001"

# Change the paths here if the programs aren't in your $PATH
mkvmerge = r'mkvmerge'

# Check to utilize mkvtoolnix for obtaining the uid and duration of the mkv
# files specified on templates, instead of letting this script parse them
# directly (faster).  Just in case the later fails.
parse_with_mkvinfo = False

def main(args):
    from optparse import OptionParser
    p = OptionParser(description='Grabs avisynth trims and outputs chapter '
                     'file, qpfile and/or cuts audio (works with cfr and '
                     'vfr input)',
                     version='VFR Chapter Creator 0.9.4',
                     usage='%prog [options] infile.avs [outfile.avs]')
    p.add_option('--label', '-l', action="store", dest="label",
                 help="Look for a trim() statement or succeeding comment only "
                 "on lines matching LABEL. Default: case insensitive trim")
    p.add_option('--line', '-g', action="store", type="int", dest="line",
                 help="Specify directly the line used")
    p.add_option('--input', '-i', action="store", help='Audio file to be cut',
                 dest="input")
    p.add_option('--output', '-o', action="store",
                 help='Cut audio from MKVMerge', dest="output")
    p.add_option('--fps', '-f', action="store",
                 help='Frames per second or Timecodes file', dest="fps")
    p.add_option('--ofps', action="store", help='Output frames per second',
                 dest="ofps")
    p.add_option('--timecodes', action="store", help='Output v2 timecodes',
                 dest="otc")
    p.add_option('--chapters', '-c', action="store",
                 help='Chapters file [.{0}/.txt]'.format("/.".join(
                 exts.keys())), dest="chapters")
    p.add_option('--chnames', '-n', action="store",
                 help='Path to template file for chapter names (utf8 w/o bom)',
                 dest="chnames")
    p.add_option('--template', '-t', action="store",
                 help="Template file for chapters", dest="template")
    p.add_option('--uid', action="store",
                 help="Base UID for --template or --chnames", dest="uid")
    p.add_option('--qpfile', '-q', action="store", help='QPFile for x264',
                 dest="qpfile")
    p.add_option('--verbose', '-v', action="store_true", help='Verbose',
                 dest="verbose")
    p.add_option('--merge', '-m', action="store_true", help='Merge cut files',
                 dest="merge")
    p.add_option('--remove', '-r', action="store_true",
                 help='Remove cut files', dest="remove")
    p.add_option('--delay', '-d', action="store",
                 help="Set delay of audio (can be negative)", dest="delay")
    p.add_option('--reverse', '-b', action="store_true",
                 help="Reverse parsing of .avs", dest="reverse")
    p.add_option('--test', action="store_true",
                 help="Test mode (do not create new files)", dest="test")
    p.add_option('--IDR', '--idr', action="store_true",
                 help="Set this to make qpfile with IDR frames instead of K frames",
                 dest="IDR")
    p.add_option('--sbr', action="store_true",
                 help="Set this if inputting an .aac and it's SBR/HE-AAC",
                 dest="sbr")
    (o, a) = p.parse_args(args)

    if len(a) < 1:
        p.error("No avisynth script specified.")
    if not o.fps:
        o.fps = default_fps
        ifps = False
    else:
        ifps = True

    #Determine chapter type
    if o.chapters:
        chre = compile("\.({0})$(?i)".format("|".join(exts.keys())))
        ret = chre.search(o.chapters)
        chapter_type = exts[ret.group(1).lower()] if ret else "OGM"
    else:
        chapter_type = ''

    if o.template and o.chnames:
        p.error("Choose either --chnames or --template, not both.")
    elif o.template and chapter_type != 'MKV':
        p.error("--template needs to output to .xml.")

    if not o.output and o.input:
        ret = splitext(o.input)
        o.output = '{0}.cut.mka'.format(ret[0])

    if o.verbose:
        status = "Avisynth file: \t{0}\n".format(a[0])
        status += "Label: \t\t{0}\n".format(o.label) if o.label else ""
        status += ("Parsing order: \t{0}\n".format("Bottom to top" if
                    o.reverse else "Top to bottom"))
        status += "Line: \t\t{0}\n".format(o.line) if o.line else ""
        status += ("Audio file: \t{0}{1}\n".format(o.input, "(SBR)" if o.sbr
                    else "") if o.input else "")
        status += "Cut Audio file: {0}\n".format(o.output) if o.output else ""
        status += "Timecodes/FPS: \t{0}{1}\n".format(o.fps, " to " + o.ofps if
                    o.ofps else "") if o.ofps != o.fps else ""
        status += "Output v2 Tc: \t{0}\n".format(o.otc) if o.otc else ""
        status += ("Chapters file: \t{0}{1}\n".format(o.chapters,
                    " ({0})".format(chapter_type) if chapter_type else "") if
                    o.chapters else "")
        status += ("Chapter Names: \t{0}\n".format(o.chnames) if o.chnames
                    else "")
        status += ("Template file: \t{0}\n".format(o.template) if o.template
                    else "")
        status += "QP file: \t\t\t{0}\n".format(o.qpfile) if o.qpfile else ""
        status += "\n"
        status += ("Merge/Rem files:{0}/{1}\n".format(o.merge, o.remove) if
                    o.merge or o.remove else "")
        status += ("Verbose: \t{0}\n".format(o.verbose) if o.verbose
                    else "")
        status += "Test Mode: \t{0}\n".format(o.test) if o.test else ""

        print(status)

    # Get frame numbers and corresponding timecodes from avs
    Trims, Trimsts, Trims2, Trims2ts, audio = parse_trims(a[0], o.fps, o.ofps,
                                           o.otc if not o.test else '', o.input,
                                           o.label, o.reverse, o.line)

    nt2 = len(Trims2ts)
    if o.verbose:
        print('In trims: {0}\n'.format(', '.join(['({0},{1})'.format(i[0],
                i[1]) for i in Trims])))
        print('In timecodes: {0}\n'.format(', '.join(['({0},{1})'.format(i[0],
                i[1]) for i in Trimsts])))
        print('Out trims: {0}\n'.format(', '.join(['({0},{1})'.format(i[0],
                i[1]) for i in Trims2])))
        print('Out timecodes: {0}\n'.format(', '.join(['({0},{1})'.format(
                fmt_time(i[0]), fmt_time(i[1])) for i in Trims2ts])))

    # make qpfile
    if o.qpfile and not o.template:
        if not o.test:
            write_qpfile(o.qpfile, Trims2, o.IDR)
        if o.verbose:
            print('Writing keyframes to {0}\n'.format(o.qpfile))

    # make audio cuts
    if o.input:
        from subprocess import call, check_output
        from sys import getfilesystemencoding

        if Trims[0][0] == '0':
            includefirst = True
            audio = audio[1:]
        else:
            includefirst = False
            cuttimes = []

        # get mkvmerge version
        get_mkvmerge_version = check_output([mkvmerge, "--version"]).decode()
        ver = [int(n) for n in get_mkvmerge_version.split()[1][1:].split('.')]
        parts_able = ver >= [5,6,0] # first version with --split parts

        if parts_able:
            if includefirst:
                cuttimes = ['-{}'.format(audio.pop(0))]
            if not includefirst and len(audio) == 1:
                cuttimes = '{}-'.format(audio[0])
            else:
                cuttimes = ',+'.join(cuttimes + ['{}-{}'.format(audio[i],
                           audio[i + 1]) for i in range(0,len(audio),2)])
        else:
            cuttimes = ','.join(audio)
        max_audio = len(audio) + 2

        # get info from mkvmerge
        ident = check_output([mkvmerge, "--identify-for-mmg", o.input])
        identre = compile("Track ID (\d+): audio( \(AAC\) "
                    "\[aac_is_sbr:true\])?")
        ret = (identre.search(ident.decode(getfilesystemencoding())) if ident
                else None)

        tid = ret.group(1) if ret else '0'
        sbr = ("0:1" if o.sbr or ret.group(2) else "0:0"
                if o.input.endswith("aac") else "")

        # determine delay
        delre = compile('DELAY ([-]?\d+)')
        ret = delre.search(o.input)
        delay = ('{0}:{1}'.format(tid, o.delay if o.delay else ret.group(1))
                if o.delay or ret else None)

        cutCmd = [mkvmerge, '-o', o.output]
        if not parts_able:
            cutCmd[-1] += '.split.mka'
        if delay:
            cutCmd.extend(['--sync', delay])
        if sbr:
            cutCmd.extend(['--aac-is-sbr', sbr])
        cutCmd.extend([o.input, '--split'])

        if parts_able:
            cutCmd.extend(['parts:' + cuttimes])
        else:
            cutCmd.extend(['timecodes:' + cuttimes])

        if o.verbose:
            print('Cutting: {0}\n'.format(
                        ' '.join(['"{0}"'.format(i) for i in cutCmd])))
        else:
            cutCmd.append('-q')

        if not o.test:
            cutExec = call(cutCmd)
            if cutExec == 1:
                print("Mkvmerge exited with warnings: {0:d}".format(cutExec))
            elif cutExec == 2:
                exit("Failed to execute mkvmerge: {0:d}".format(cutExec))
        if o.merge and not parts_able:
            merge = []
            for i in range(1, max_audio):
                if ((includefirst == True and i % 2 != 0) or
                (includefirst == False and i % 2 == 0)):
                    merge.append('{0}{1}.split-{2:03d}.mka'.format('+' if
                                    len(merge) > 0 else '', o.output, i))
            mergeCmd = [mkvmerge, '-o', o.output]
            mergeCmd.extend(merge)
            if o.verbose:
                print('\nMerging: {0}\n'.format(' '.join(['"{0}"'.format(i) for
                        i in mergeCmd])))
            else:
                mergeCmd.append('-q')

            if not o.test:
                mergeExec = call(mergeCmd)
                if mergeExec == 1:
                    print("Mkvmerge exited with warnings: {0:d}".format(
                            mergeExec))
                elif mergeExec == 2:
                    exit("Failed to execute mkvmerge: {0:d}".format(mergeExec))

        if o.remove and not parts_able:
            remove = ['{0}.split-{1:03d}.mka'.format(o.output, i) for
                        i in range(1, max_audio)]
            if o.verbose:
                print('\nDeleting: {0}\n'.format(', '.join(remove)))
            if not o.test:
                from os import unlink
                [unlink(i) if isfile(i) else True for i in remove]

    # make offseted avs
    if len(a) > 1:
        try:
            from chapparse import writeAvisynth
            fNum = [i[0] for i in Trims2]
            set = {'avs': '"' + a[1] + '"', 'input': '', 'resize': ''}
            writeAvisynth(set, fNum)
        except ImportError:
            print('Script chapparse.py needed for avisynth output to work.')

    # write chapters
    if chapter_type:

        if chapter_type == 'MKV':
            Trims2ts = [(fmt_time(i[0]), fmt_time(i[1]) if i[1] != 0 else None)
                        for i in Trims2ts]

        if o.template:
            from templates import AutoMKVChapters as amkvc
            output = o.chapters[:-4] if not o.test else None
            chaps = amkvc(o.template, output=output, avs=a[0], trims=Trims2ts,
                            kframes=Trims2, uid=o.uid, label=o.label,
                            ifps=ifps)

        else:
            # Assign names to each chapter if --chnames
            chapter_names = []

            if o.chnames:
                with open(o.chnames, encoding='utf-8') as f:
                    [chapter_names.append(line.strip()) for line in
                    f.readlines()]

            if not o.chnames or len(chapter_names) < len(Trims2ts):
                # The if statement is for clarity; it doesn't actually do
                # anything useful
                for i in range(len(chapter_names), len(Trims2ts)):
                    chapter_names.append("Chapter {:02d}".format(i + 1))

            if chapter_type == 'MKV':
                from templates import AutoMKVChapters as amkvc
                tmp = amkvc.Template()
                tmp.trims = Trims2ts
                tmp.kframes = Trims2
                if o.qpfile:
                    tmp.qpf = o.qpfile
                ed = tmp.Edition()
                ed.default = 1
                ed.num_chapters = len(chapter_names)
                ed.uid = int(o.uid) * 100 if o.uid else tmp.uid * 100
                cuid = ed.uid
                ed.chapters = []
                for i in range(len(chapter_names)):
                    ch = tmp.Chapter()
                    cuid += 1
                    ch.uid = cuid
                    ch.name = [chapter_names[i]]
                    ch.start, ch.end = (Trims2ts[i][0], Trims2ts[i][1])
                    ed.chapters.append(ch)
                tmp.editions = [ed]
                chaps = tmp

            if not o.test:
                if chapter_type == 'MKV':
                    chaps.toxml(o.chapters[:-4])
                else:
                    with open(o.chapters, "w", encoding='utf-8') as output:
                        if chapter_type == 'OGM':
                            chap = ('CHAPTER{1:02d}={0}\nCHAPTER{1:02d}'
                                    'NAME={2}\n')
                        elif chapter_type == 'X264':
                            chap = '{0} {2}\n'
                        Trims2ts = [fmt_time(i[0], 1) for i in Trims2ts]
                        [output.write(chap.format(Trims2ts[i], i + 1,
                        chapter_names[i])) for i in range(len(Trims2ts))]
        if o.verbose:
            print("Writing {} Chapters to {}". format(chapter_type,
                    o.chapters))


def fmt_time(ts, msp=None):
    """Converts nanosecond timestamps to timecodes.
    
    msp = Set timecodes for millisecond precision if True
    
    """
    s = ts / 10 ** 9
    m = s // 60
    s = s % 60
    h = m // 60
    m = m % 60
    if msp:
        return '{:02.0f}:{:02.0f}:{:06.3f}'.format(h, m, s)
    else:
        return '{:02.0f}:{:02.0f}:{:012.9f}'.format(h, m, s)


def truncate(ts, scale=0):
    """Truncates a ns timestamp to 0.1*scale precision
    with an extra decimal place if it rounds up.
    
    Default: 0 (0.1 ms)
    
    Examples: 3 (0.1 µs); 6 (0.1 ns)
    
    """
    scale = abs(6 - scale)
    ots = ts / 10 ** scale
    tts = (floor(ots * 10) * 10 if round(ots, 1) == floor(ots * 10) / 10 else
            ceil(ots * 10) * 10 - 5)
    return int(tts * 10 ** (scale - 2))


def correct_to_ntsc(fps, ms=None):
    """Rounds framerate to NTSC values if close enough.
    
    Takes and returns a Rational number.
    
    Ported from FFmpegsource.
    
    """
    fps = Fraction(fps)
    TempFPS = Fraction(fps.denominator, fps.numerator)
    
    if TempFPS.numerator == 1:
        Num = TempFPS.denominator
        Den = TempFPS.numerator
    else:
        FTimebase = TempFPS.numerator / TempFPS.denominator
        NearestNTSC = floor(FTimebase * 1001 + 0.5) / 1001
        SmallInterval = 1 / 120

        if abs(FTimebase - NearestNTSC) < SmallInterval:
            Num = int((1001 / FTimebase) + 0.5)
            Den = 1001

    if not ms:
        return Fraction(Num, Den)
    else:
        return Den / (Num / 1000)


def convert_v1_to_v2(v1, max, asm, v2=None, first=0):
    """Converts a given v1 timecodes file to v2 timecodes.
    
    Original idea from tritical's tcConv.
    
    """
    ts = fn1 = fn2 = last = 0
    asm = correct_to_ntsc(asm, True)
    o = []
    ap = o.append
    en = str.encode
    for line in v1:
        ovr = line.split(',')
        if len(ovr) == 3:
            fn1, fn2, fps = ovr
            fn1 = int(fn1)
            fn2 = int(fn2)
            ovf = correct_to_ntsc(fps, True)
            while (last < fn1 and last < max):
                ap(ts)
                last, ts = last + 1, ts + asm
            while (last <= fn2 and last < max):
                ap(ts)
                last, ts = last + 1, ts + ovf
    while last < max:
        ap(ts)
        last, ts = last + 1, ts + asm
    if v2:
        with open(v2, 'wb') as v2f:
            from os import linesep as ls
            header = [en('# timecode format v2' + ls)] if first == 0 else [b'']
            v2f.writelines(header + [en(('{0:3.6f}'.format(s)) + ls) for s in
                            o[first:]])
    return o[first:]


def parse_tc(tcfile, max=0, otc=None, first=0):
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
        timecodes = Fraction(num, den)
        if otc:
            convert_v1_to_v2([], max + 2, timecodes, otc, first)

    else:
        type = 'vfr'
        with open(tcfile) as tc:
            v1 = tc.readlines()
        ret = vfr_re.search(v1.pop(0))
        version = ret.group(1) if ret else exit('File is not in a supported '
                                                'format.')

        if version == 'v1':
            ret = v1.pop(0).split(' ')
            asm = ret[1] if len(ret) == 2 else exit('there is no assumed fps')
            if v1:
                ret = convert_v1_to_v2(v1, max, asm, otc, first)
                timecodes = ['{0:3.6f}\n'.format(i) for i in ret]
            else:
                timecodes = correct_to_ntsc(asm)
                type = 'cfr'
                if otc:
                    convert_v1_to_v2([], max + 2, timecodes, otc, first)

        elif version == 'v2':
            if max > len(v1):
                temp_max = len(v1)
                sample = temp_max // 100
                average = 0
                for i in range(-sample, 0):
                    average += round(float(v1[i]) - float(v1[i - 1]), 6)
                fps = correct_to_ntsc(Fraction.from_float(sample / average *
                                        1000))
                ret = convert_v1_to_v2([], max - len(v1) + 1, fps, first=1)
                if v1[-1][-1] is not '\n':
                    v1[-1] += '\n'
                v1 += ['{0:3.6f}\n'.format(i + float(v1[-1])) for i in ret]
            timecodes = v1

    return (timecodes, type), max


def get_ts(fn, tc, scale=0):
    """Returns timestamps from a frame number and timecodes file or cfr fps
    
    fn = frame number
    tc = (timecodes list or Fraction(fps),tc_type)
    
    scale default: 0 (ns)
    examples: 3 (µs); 6 (ms); 9 (s)
    
    """
    scale = 9 - scale
    tc, tc_type = tc
    if tc_type == 'cfr':
        ts = round(10 ** scale * fn * Fraction(tc.denominator, tc.numerator))
        return ts
    elif tc_type == 'vfr':
        ts = round(float(tc[fn]) * 10 ** (scale - 3))
        return ts


def convert_fps(ofn, old, new, oldts=None):
    """Returns a frame number from fps and ofps (ConvertFPS)
    
    fn = frame number
    old = original fps ('30000/1001', '25')
    new = output fps ('24000/1001', etc.)
    
    """

    newts = 0
    nfn = 0
    thr = get_ts(1, old)  # milliseconds
    newframes = []
    newtimestamps = []
    temp = temp2 = []
    
    for i in ofn:
        for j in i:
            temp.append(j)
    
    ofn = temp
    
    if not oldts:
        oldtsi = []
        for fn in ofn:
            oldtsi.append(get_ts(fn, old))
    else:
        oldtsi = []
        for i in oldts:
            for j in i:
                oldtsi.append(j)

    for i in range(len(ofn)):

        fn = ofn[i]
        ots = oldtsi[i]
        nts = get_ts(nfn, new)
        if ots - nts >= thr:
            while (ots - nts > thr):
                nfn += 1
                nts = get_ts(nfn, new)
            if len(newframes) != 0 and nfn == newframes[-1]:
                newframes[-1] -= 1
                newtimestamps[-1] = get_ts(newframes[-1], new)
                newframes.append(nfn)
                newtimestamps.append(nts)
            else:
                newframes.append(nfn)
                newtimestamps.append(nts)
        elif ots - nts < thr:
            if len(newframes) != 0 and nfn == newframes[-1]:
                newframes[-1] -= 1
                newframes.append(nfn)
                newtimestamps.append(nts)
            else:
                newframes.append(nfn)
                newtimestamps.append(nts)
        else:
            nfn = 0
            while (ots - nts > thr):
                nfn += 1
                nts = get_ts(nfn, new)
            newframes.append(nfn)
            newtimestamps.append(nts)

    if len(newframes) % 2 == 0:
        temp = []
        temp2 = []
        for i in range(0, len(newframes), 2):
            temp.append([newframes[i], newframes[i + 1]])
            temp2.append([newtimestamps[i], newtimestamps[i + 1]])
        newframes, newtimestamps = temp, temp2

    if oldts:
        return newframes, newtimestamps
    else:
        return newframes


def parse_avs(avs, label=None, reverse=None, line_number=None):
    """Parse an avisynth file. Scours it for the first uncommented trim line.
    
    By default it looks for case-insensitive 'trim'. Using label, you can make
    it parse only the line starting with a certain case of trim, ignoring the
    others. Ex: label = 'tRiM' looks for the line starting with tRiM, ignoring
    other cases.
    
    Returns a list with pairs of frames containing the first and last of each
    trim.
    
    """

    trimre = compile("(?<!#)trim\((\d+)\s*,\s*(-?\d+)\)(?i)")
    Trims = []

    trim_label = 'trim'
    comment = ''
    ignore_case = '(?i)'
    
    if line_number:
        label = None
    if label and label.lower() == 'trim':
        trim_label = label
        comment = ''
        ignore_case = ''
    elif label:
        comment = '#.*' + label

    with open(avs) as avsfile:
        avs = avsfile.readlines()
    findTrims = compile("(?<!#)[^#]*\s*\.?\s*{0}\((\d+)\s*,"
                        "\s*(-?\d+)\).*{1}{2}".format(trim_label, comment,
                        ignore_case))
    if line_number:
        avs = avs[line_number - 1:line_number]
    for line in avs if not reverse else reversed(avs):
        if findTrims.match(line):
            Trims = trimre.findall(line)
            break
    if not Trims:
        if label:
            exit("Error: Avisynth script has no uncommented trims with label "
                 "'{}'".format(label))
        if line_number:
            exit("Error: Avisynth script has no uncommented trims on line {}"
                 .format(line_number))
        exit("Error: Avisynth script has no uncommented trims")

    return Trims


def parse_trims(avs, fps, outfps=None, otc=None, input=None, label=None,
                reverse=None, line_number=None):
    """Parse trims from an avisynth file.

    Returns 5 lists containing:
    Trims = Trims as parsed from the avs without processing.
    Trimsts = Timecodes of each trim in Trims.
    Trims2 = Offset trims. If ofps is set, they will be using ofps's frame
             numbers.
    Trims2ts = Same as Trimsts only for Trims2.
    audio = Timecodes where each cut will be performed for audio.
            If the cuts are for adjacent frames they won't be appended to the
            list, so as to avoid unnecessary cuts.
            Ex: trim(0,10)+trim(11,20) will be output as trim(0,20)

    """

    Trims = parse_avs(avs, label, reverse, line_number)
    audio = []
    Trimsts = []
    Trims2 = []
    Trims2ts = []
    nt1 = len(Trims)
    adjacent = False

    # Parse timecodes/fps
    last_frame = int(Trims[-1][1])
    if last_frame < 0:
        last_frame = int(Trims[-1][0]) - int(Trims[-1][1]) - 1
    elif last_frame == 0:
        last_frame = int(Trims[-1][0])

    tc, max = parse_tc(fps, last_frame + 2, otc)
    if tc[1] == 'vfr' and outfps:
        exit("Can't use --ofps with timecodes file input")
    if outfps and fps != outfps:
        ofps = parse_tc(outfps, int(Trims[-1][1]) + 2)[0]
        if otc:
            max = convert_fps([[int(Trims[-1][1])]], tc, ofps)[0]
            parse_tc(outfps, max + 2, otc + '.ofps.txt')

    # Parse trims
    for i in range(nt1):
        fn1 = int(Trims[i][0])
        fn1ts = get_ts(fn1, tc)
        fn1tsaud = get_ts(fn1, tc)
        fn2 = int(Trims[i][1])
        if fn2 > 0:
            fn2ts = get_ts(fn2 + 1, tc)
            fn2tsaud = get_ts(fn2 + 1, tc)
            adjacent = False
            Trimsts.append((fmt_time(fn1ts), fmt_time(fn2ts)))
        elif fn2 < 0:
            fn2 = fn1 - fn2 - 1
            fn2ts = get_ts(fn2 + 1, tc)
            fn2tsaud = get_ts(fn2 + 1, tc)
            adjacent = False
            Trimsts.append((fmt_time(fn1ts), fmt_time(fn2ts)))
        else:
            fn2ts = 0
            fn2tsaud = 0
            Trimsts.append((fmt_time(fn1ts), 0))

        # Calculate offsets for non-continuous trims
        if i == 0:
            offset = 0
            offsetts = 0
            # If the first trim doesn't start at 0
            if fn1 > 0:
                offset = fn1
                offsetts = fn1ts
        else:
            # If it's not the first trim
            last = int(Trims[i - 1][1])
            lastts = get_ts(last + 1, tc)
            adjacent = True if not fn1 - (last + 1) else False
            offset += fn1 - (last + 1)
            offsetts += 0 if adjacent else fn1ts - lastts

        if input:
            # Make list with timecodes to cut audio
            if adjacent:
                del audio[-1]
            elif fn1 <= max:
                audio.append(fmt_time(fn1tsaud))

            if fn2 <= max and fn2 != 0:
                audio.append(fmt_time(fn2tsaud))

        # Apply the offset to the trims
        fn1 -= offset
        fn2 -= offset if fn2 else 0
        fn1ts -= offsetts
        fn2ts -= offsetts if fn2 else 0

        # Add trims and their timestamps to list
        Trims2.append([fn1, fn2])
        Trims2ts.append((fn1ts, fn2ts))

    # Convert fps if ofps is supplied
    if outfps and fps != outfps:
        Trims2, Trims2ts = convert_fps(Trims2, tc, ofps, Trims2ts)

    return Trims, Trimsts, Trims2, Trims2ts, audio


def write_qpfile(qpfile, trims, idr=None):
    """Writes keyframes for use in x264 from a list of Trims."""

    with open(qpfile, "w") as qpf:
        if trims[0][0] == 0:
            del trims[0]
        for trim in trims:
            qpf.write('{0} {1}\n'.format(trim[0], 'I' if idr else 'K'))

if __name__ == '__main__':
    main(argv[1:])
