#!/usr/bin/env python

import ConfigParser
import sys

def main():
    # init config
    config = ConfigParser.ConfigParser()
    
    # read template
    config.read("%s" % sys.argv[1])
    
    # read info section
    Lang      = config.get('info','lang')
    Country   = config.get('info','country')
    QPFile    = config.getboolean('info','createqpfile')
    InputFPS  = [config.getint('info','inputfps')*1000,1001]
    OutputFPS = [config.getint('info','outputfps')*1000,1001]
    nEditions = config.getint('info','editions')
    Editions  = {}
    
    # read edition sections
    for edition in range(1,nEditions+1):
        
        Editions.update({edition:{}})
        
        # read edition info
        edName    = 'edition%d' % edition
        nChapters = config.getint(edName, 'chapters')
        default   = config.getboolean(edName, 'default')
        name      = config.get(edName, 'name')
        ordered   = config.get(edName,'ordered')
        
        # join chapters in a single dict
        Editions[edition]['chapters'] = {}
        for i in [{i:{}} for i in range(1,nChapters+1)]:
            Editions[edition]['chapters'].update(i)
        for key in config.options(edName):
            chaps = re.match(r'(\d+)(\w+)',key)
            if chaps != None:
                Editions[edition]['chapters'][int(chaps.group(1))].update(dict([[chaps.group(2),config.get(edName,key)]]))


if __name__ == '__main__':
    main()