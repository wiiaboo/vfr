#!/usr/bin/env python
# chapparse.py
import sys, re, getopt, os
from string import Template

name = 'chapparse.py'
version = '0.4'
rat = re.compile('(\d+)(?:/|:)(\d+)')
chapre = re.compile("CHAPTER\d+=(\S+)",re.I)
x264 = 'x264-64'
ffmpeg = 'ffmpeg'
mkvmerge = 'mkvmerge'
avs2yuv = 'avs2yuv'
timeCodes = frameNumbers = merge = []

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "i:o:f:b:e:s:a:x:c:hmr",['help','avs=','test','x264opts='])
    except getopt.GetoptError as err:
        print(err)
        help()
        sys.exit()
    
    set = dict(input='video.mkv',output='',audio='',index='',
            fps='24000/1001',batch='',method='x264',resize='',avs='',mergeFiles=False,removeFiles=False,
            x264opts='--preset placebo --crf 16 --level 41 --rc-lookahead 250',test=False,
            x264=x264,ffmpeg=ffmpeg,mkvmerge=mkvmerge,avs2yuv=avs2yuv,chapters='chapters.txt',crop='0,0,0,0')
    
    for o, v in opts:
        if o == '-i':
            set['input'] = v
        elif o == '-o':
            set['output'] = v[:-4]
        elif o == '-f':
            set['fps'] = v
        elif o == '-b':
            set['batch'] = v
        elif o == '-e':
            set['method'] = v
        elif o == '-s':
            set['resize'] = v
        elif o == '-c':
            set['crop'] = v
        elif o in ('-x','--x264opts'):
            set['x264opts'] = v
        elif o == '-a':
            set['audio'] = v
        elif o in ('-h','--help'):
            help()
            sys.exit()
        elif o == '-m':
            set['mergeFiles'] = True
        elif o == '-r':
            set['removeFiles'] = True
        elif o == '--avs':
            set['avs'] = v
        elif o == '--test':
            set['test'] = True
        else:
            assert False, "unhandled option"
    
    set['chapters'] = set['chapters'] if len(args) != 1 else args[0]
    
    if set['output'] == '':
        set['output'] = set['input'][:-4]+'.encode'
    if set['avs'] == '' and set['method'] == 'avisynth':
        set['avs'] = set['output']+'.avs'
    if set['avs'] != '' and set['method'] == 'x264':
        set['method'] = 'avisynth'
    if set['batch'] == '':
        set['batch'] = set['output']+'.bat'
    if os.path.isfile(set['chapters']) != True:
        print("You must set a valid OGM chapters file.")
        sys.exit(2)
    
    if set['test'] == True:
        for key in sorted(set):
            print(key.ljust(8),'=',set[key])
        print()
    
    timeStrings = parseOgm(args[0])
    
    timeCodes = [time2ms(timeString) for timeString in timeStrings]
    
    frameNumbers = [ms2frame(timeCode,set['fps']) for timeCode in timeCodes]
    
    set['cmd'] = Template('${piper}"${x264}" ${x264opts} --demuxer y4m${end} - -o "${output}-part${part}.mkv"')
    
    if set['method'] == 'avisynth':
        set['avs'] = '"%s"' % set['avs']
        if set['test'] == False:
            set = writeAvisynth(set,frameNumbers)
        else:
            print('Writing avisynth script')
    elif set['method'] == 'ffmpeg':
        set['resize'] = ' -s '+set['resize'] if (set['method'] == 'ffmpeg' and set['resize'] != '') else ''
    elif set['method'] == 'x264':
        set['cmd'] = Template('"${x264}" ${x264opts}${seek}${end} $xinput -o "${output}-part${part}.mkv"')
        set['index'] = '"%s.x264.ffindex"' % set['input'] if set['input'][-3:] in ('mkv','mp4','wmv') else ''
        set['xinput'] = '"%s" --index %s' % (set['input'],set['index']) if set['index'] != '' else '"%s"' % set['input']
        x264crop = 'crop:'+set['crop'] if (set['method'] == 'x264' and set['crop'] != '0,0,0,0') else ''
        x264resize='resize:'+','.join(set['resize'].split('x')) if (set['method'] == 'x264' and set['resize'] != '') else ''
        sep = '/' if (x264crop != '' and x264resize != '') else ''
        set['x264opts'] = set['x264opts']+' --vf %s%s%s' % (x264crop,sep,x264resize) if (x264crop != '' or x264resize != '') else set['x264opts']
    
    writeBatch(set,frameNumbers,timeStrings)

def help():
    print("""
%s %s
Usage: chapparse.py [options] chapters.txt
chapters.txt is an OGM chapters file to get chapter points from whence to
separate the encodes

Options:
    -i video.mkv
        Video to be encoded
    -o encode.mkv
        Encoded video
    -f 24000/1001
        Frames per second
    -s 1280x720
        Resolution to resize to (no default)
    -e x264
        Method of resizing [avisynth,ffmpeg,x264]
    -a audio.m4a
        Audio to mux in the final file
    -b encode.bat
        Batch file with the instructions for chapter-separated encode
    -x "--preset placebo --crf 16 --level 41 --rc-lookahead 250", --x264opts
        x264 options (don't use --demuxer, --input, --output or --frames)
    --avs encode.avs
        If using avisynth method
    -m
        Merge parts
    -r
        Remove extra files
    -h, --help
        This help file""" % (name,version))

def time2ms(ts):
    
    t = ts.split(':')
    h = int(t[0]) * 3600000
    m = h + int(t[1]) * 60000
    ms = round(m + float(t[2]) * 1000)
    
    return ms

def ms2frame(ms,fps):
    
    s = ms / 1000
    fps = rat.search(fps).groups() if rat.search(fps) else \
        [re.search('(\d+)',fps).group(0),'1']
    frame = round((int(fps[0])/int(fps[1])) * s)
    
    return frame

def parseOgm(file):
    
    timeStrings = []
    
    with open(file) as chapFile:
        for line in chapFile:
            timeString = chapre.match(line)
            if timeString != None:
                timeStrings.append(timeString.group(1))
    
    return timeStrings

def writeAvisynth(set,frameNumbers):
    # needs dict with 'avs', 'input', 'resize' (if needed) and list with frameNumbers
    if os.path.isfile(set['avs'][1:-1]) != True:
        with open(set['avs'][1:-1],'w') as avs:
            if set['input'][:-4] in ('.mkv','.wmv','.mp4'):
                avs.write('FFVideoSource("%s")\n' % set['input'])
            elif set['input'][:-4] == '.avi':
                avs.write('AviSource("%s")\n' % set['input'])
            elif set['input'] != '':
                avs.write('DirectShowSource("%s")\n' % set['input'])
            if set['resize'] != '':
                avs.write('Spline36Resize(%s)\n' % ','.join(set['resize'].split('x')))
            avs.write('+'.join(['Trim(%d,%d)' % (frameNumbers[i],frameNumbers[i+1]-1) for i in range(len(frameNumbers)-1)]))
            avs.write('+Trim(%d,0)\n' % frameNumbers[-1])
    else:
        with open(set['avs'][1:-1],'a') as avs:
            avs.write('\n')
            avs.write('+'.join(['Trim(%d,%d)' % (frameNumbers[i],frameNumbers[i+1]-1) for i in range(len(frameNumbers)-1)]))
            avs.write('+Trim(%d,0)\n' % frameNumbers[-1])
    
    set['resize'] = ''
    if set['input'][:-3] in ('mkv','wmv','mp4'):
        set['index'] = '"%s.mkv.ffindex"' % set['output']
    
    return set

def cmdMake(set,frameNumbers,timeStrings,i):
    begin = frameNumbers[i]
    frames = frameNumbers[i+1]-begin if i != len(frameNumbers)-1 else 0
    
    if set['method'] == 'avisynth':
        set['seek'] = ' -seek %d' % begin
    elif set['method'] == 'ffmpeg':
        set['seek'] = ' -ss %s' % timeStrings[i]
    elif set['method'] == 'x264':
        set['seek'] = ' --seek %d' % begin
    if frames != 0:
        if set['method'] == 'avisynth':
            set['frames'] = ' -frames %d' % frames
        elif set['method'] == 'ffmpeg':
            set['frames'] = ' -vframes %d' % frames
        elif set['method'] == 'x264':
            set['frames'] = ''
        set['end'] = ' --frames %d' % frames
    else:
        set['end'] = set['frames'] = ''
    
    set['merge'] = '"%s-part%d.mkv"' % (set['output'],i+1)
    
    set['part'] = i+1
    
    if set['method'] == 'avisynth':
        set['piper'] = Template('"${avs2yuv}"${seek}${frames} $avs -o - | ')
    elif set['method'] == 'ffmpeg':
        set['piper'] = Template('"${ffmpeg}" -i "${input}"${resize}${seek}${frames} -f yuv4mpegpipe -sws_fags spline - | ')
    
    if set['method'] in ('avisynth','ffmpeg'):
        set['piper'] = set['piper'].substitute(set)
    
    return set

def writeBatch(set,frameNumbers,timeStrings):
    if set['test'] == False:
        with open(set['batch'],'w') as batch:
            merge = []
            if os.name == 'posix':
                batch.write('#!/bin/sh\n\n')
            for i in range(len(frameNumbers)):
                set2 = cmdMake(set,frameNumbers,timeStrings,i)
                batch.write(set['cmd'].substitute(set2)+'\n')
                merge.append(set2['merge'])
            
            if set['mergeFiles'] == True:
                batch.write('\n"%s" -o "%s" %s --default-duration "1:%sfps"' % (set['mkvmerge'],set['output']+'.mkv',' +'.join(merge),set['fps']))
                if set['audio'] != '':
                    batch.write(' -D --no-chapters "%s"' % set['audio'])
                batch.write(' --chapters "%s"' % set['chapters'])
                batch.write('\n')
            rem = ' '.join(merge)
            if set['removeFiles'] == True and os.name == 'nt':
                batch.write('del %s' % rem)
            elif set['removeFiles'] == True and os.name == 'posix':
                batch.write('rm %s' % rem)
    else:
        print('Writing batch file')
        #print('Example:',set['cmd'].format(cmdMake(set,frameNumbers,timeStrings,3)))

if __name__ == '__main__':
    if len(sys.argv) > 1:
        main()
    else:
        print('Usage: chapparse.py [options] chapters.txt')
        sys.exit()