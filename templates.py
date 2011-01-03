#!/usr/bin/env python3.1

def main(args):
    cfg = parse_amkvc(args[1])

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

    return cfg

if __name__ == '__main__':
    from sys import argv
    main(argv)