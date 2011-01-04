#!/usr/bin/env python3.1

class Info:
    editions = 1
    lang = 'eng'
    country = 'us'
    inputfps = [30000,1001]
    outputfps = [24000,1001]
    createqpfile = False

class Edition:
    default = False
    name = 'Edition'
    hidden = False
    ordered = False
    chapters = {}

class Chapter:
    name = 'Chapter'
    chapter = None
    start = None
    end = None
    suid = None
    hidden = False

def main(args):
    cfg, type = parse_amkvc(args[1])
    format_chapters(cfg, type)


def format_chapters(cfg,type):
    from random import randint
    from os import linesep as lsp

    uid = randint(10**5,10**6)

    mkv = ['<?xml version="1.0" encoding="UTF-8"?>\n',
           '<!-- <!DOCTYPE Tags SYSTEM "matroskatags.dtd"> -->\n']
    mkvchapters = mkv + ['<Chapters>\n']
    mkvtags = mkv + ['<Tags>\n']
    
    for edition_num in cfg['editions']:
        uid += 1
        edition = cfg['editions'][edition_num]
        mkvedition = ['\t<EditionEntry>\n',
                      '\t\t<EditionFlagHidden>0</EditionFlagHidden>\n',
                      '\t\t<EditionFlagDefault>%d</EditionFlagDefault>\n' % int(edition['default']),
                      '\t\t<EditionFlagOrdered>%d</EditionFlagOrdered>\n' % int(edition['ordered']),
                      '\t\t<EditionUID>%d</EditionUID>\n' % uid]
        
        mkvtags += ['\t<Tag>\n',
                    '\t\t<Targets>\n',
                    '\t\t\t<EditionUID>%d</EditionUID>\n' % uid,
                    '\t\t\t<TargetTypeValue>50</TargetTypeValue>\n',
                    '\t\t</Targets>\n',
                    '\t\t<Simple>\n',
                    '\t\t\t<Name>TITLE</Name>\n',
                    '\t\t\t<String>%s</String>\n' % edition['name'],
                    '\t\t\t<TagLanguage>%s</TagLanguage>\n' % cfg['lang'],
                    '\t\t\t<DefaultLanguage>1</DefaultLanguage>\n',
                    '\t\t</Simple>\n',
                    '\t</Tag>\n']

        for chapter_num in edition['chapters']:
            uid += 1
            chapter = edition['chapters'][chapter_num]
            mkvchapter = ['\t\t<ChapterAtom>\n',
                          '\t\t\t<ChapterDisplay>\n',
                          '\t\t\t\t<ChapterString>%s</ChapterString>\n' % chapter['name'],
                          '\t\t\t\t<ChapterLanguage>%s</ChapterLanguage>\n' % cfg['lang'],
                          '\t\t\t\t<ChapterCountry>%s</ChapterCountry>\n' % cfg['country'],
                          '\t\t\t</ChapterDisplay>\n',
                          '\t\t\t<ChapterUID>%d</ChapterUID>\n' % uid,
                          '\t\t\t<ChapterTimeStart>0</ChapterTimeStart>\n',
                          '\t\t\t<ChapterTimeEnd>0</ChapterTimeEnd>\n',
                          '\t\t\t<ChapterFlagHidden>0</ChapterFlagHidden>\n',# % chapter['hidden'],
                          '\t\t\t<ChapterFlagEnabled>1</ChapterFlagEnabled>\n',
                          '\t\t</ChapterAtom>\n']
            mkvedition += mkvchapter
            
        mkvedition += ['\t</EditionEntry>\n']
        mkvchapters += mkvedition
        
    mkvchapters += ['</Chapters>\n']
    
    outf = open('pilas.xml','w')
    outf.writelines(mkvchapters)
    
    outf2 = open('pilatags.xml','w')
    outf2.writelines(mkvtags)


def parse_amkvc(templatefile):
    from configparser import ConfigParser
    from re import compile

    # defaults
    Defaults = {
        'editions': '1',
        'lang': 'eng',
        'country': 'us',
        'inputfps': '30',
        'outputfps': '24',
        'createqpfile': '1',
        'hidden': '0',
        'ordered': '0',
        'default': '0',
        'chapters': '0'
    }

    cfg = {}
    
    chre = compile('(\d+)(\w+)')

    # init config
    config = ConfigParser(Defaults)

    # read template
    config.read(templatefile)

    # read info section
    editions         = config.getint('info','editions')
    cfg['lang']      = config.get('info','lang')
    cfg['country']   = config.get('info','country')
    cfg['inputfps']  = [config.getint('info','inputfps')*1000,1001]
    cfg['outputfps'] = [config.getint('info','outputfps')*1000,1001]
    cfg['qpfile']    = config.getboolean('info','createqpfile')
    cfg['editions']  = {}

    # read edition sections
    for ed_num in range(1,editions+1):

        cfg['editions'][ed_num] = {}

        # read edition info
        edition  = 'edition%d' % ed_num
        chapters = config.getint(edition, 'chapters')
        cfg['editions'][ed_num]['default']  = config.getboolean(edition, 'default')
        cfg['editions'][ed_num]['name']     = config.get(edition, 'name')
        cfg['editions'][ed_num]['ordered']  = config.getboolean(edition,'ordered')
        cfg['editions'][ed_num]['chapters'] = {}

        # join chapters in a single dict
        for cn in range(1,chapters+1):
            cfg['editions'][ed_num]['chapters'][cn] = {}
            
        for key in config.options(edition)[4:]:
            chaps = chre.match(key)
            if chaps:
                cfg['editions'][ed_num]['chapters'][int(chaps.group(1))][chaps.group(2)] = config.get(edition,key)

    return cfg, 'MKV'


if __name__ == '__main__':
    from sys import argv
    main(argv)