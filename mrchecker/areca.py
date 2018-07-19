import logging
from subprocess import Popen, PIPE
from pprint import pprint
import re

from raid_check.controller import Controller
from raid_check.parser import row_hybrid_split, row_delimiter_split
from raid_check.condition import Condition

__version__ = '1.2'

# There is a single top level table for parsing the controller list, 
# and then a series of controller specific sub-tables.

# I changed the layout of the 'tables' dictionary so that one model of controller
# can re-use the settings from some other controller - a few of them are the same

tables = {
    'cntrs': { 'row_split': row_hybrid_split,
               'name_field': 'controller_num',
               'fields_list': [('controller_num', 4, 8),
                               ('model', 8, 19),
                               ('type', 19, 36),
                               ('interface', 36, 50)
                               ]
               },
    }

tables['ARC-1680'] = {
    'raids': { 'row_split': row_hybrid_split,
               'name_field': 'number',
               'fields_list': [('number', 0),
                               ('name', 4, 22),
                               ('disk count', -5),
                               ('total capacity', -4),
                               ('free capacity', -3),
                               ('mindiskcap', -2),
                               ('status', -1),
                               ]
               },
    'volumes': { 'row_split': row_hybrid_split,
                 'name_field': 'number',
                 'fields_list': [('number', 0),
                                 ('volume_name', 4, 21),
                                 ('raid_name', 21, 37),
                                 ('raid_level', -4),
                                 ('capacity', -3),
                                 ('ch/id/lun', -2),
                                 ('status', -1),
                                 ]
                 },
    'disks': { 'row_split': row_hybrid_split,
               'name_field': 'number',
               'fields_list': [('number', 0),
                               ('enclosure', 1),
                               ('slot', 9, 17),
                               ('modelname', 17, 50),
                               ('capacity', 50, 60),
                               ('raid_name', 60, -1),
                               ],
               },
    'sys': { 'row_split': row_delimiter_split,
             'delimiter': ':',
             'name_field': 0,
             'value_field': 1,
             'strip_list': [None],
             },
    'hw': { 'row_split': row_delimiter_split,
            'delimiter': ':',
            'name_field': 0,
            'value_field': 1,
            'strip_list': [None],
            },
    }

tables['ARC-1231'] = {
    'raids': { 'row_split': row_hybrid_split,
               'name_field': 'number',
               'fields_list': [('number', 0),
                               ('name', 4, 22),
                               ('disk count', -5),
                               ('total capacity', -4),
                               ('free capacity', -3),
                               ('disk channels', -2),
                               ('status', -1),
                               ]
               },
    'volumes': tables['ARC-1680']['volumes'],
    'disks': { 'row_split': row_hybrid_split,
               'name_field': 'number',
               'fields_list': [('number', 0),
                               ('channel', 1),
                               ('modelname', 8, 40),
                               ('capacity', 40, 50),
                               ('raid_name', 50, -1),
                               ],
               },
    'sys': tables['ARC-1680']['sys'],
    'hw': tables['ARC-1680']['hw'],
}

tables['ARC-1220'] = tables['ARC-1231']


program_list = ['cli64', 'cli32']

class Areca(Controller):

    def __init__(self, program_name):
        super(Areca, self).__init__(program_name, program_list)
        log = logging.getLogger('Controller.Areca.init')
        self.details = dict()

        log.debug('Controller.Areca.init ending')
        
    def setup(self):
        log = logging.getLogger('Controller.Areca.setup')

        # start the areca specific backend program
        log.debug('running cmd "%s"' % self.program)
        try:
            self.proc = Popen(self.program, shell=False, stdin=PIPE, stdout=PIPE, bufsize=0)
            log.debug('pid = %s' % self.proc.pid)
        except OSError, ex:
            log.exception('Specified backend command not found')
            return False

        summary = self._get_controller_list()
        for ctrl in summary.keys():
            self.details[ctrl] = self._get_controller_details(ctrl, summary[ctrl]['model'])
            self.details[ctrl]['summary'] = summary[ctrl]
        return True 


    def teardown(self):
        log = logging.getLogger('Controller.Areca.teardown')

        # We're done with our backend command line tool
        # finally we get to use subprocess.communicate()
        log.debug('shutting down backend program')
        self.proc.communicate('exit')

        # Fixme: we need to record the pid, and in here kill it if its somehow still alive.

        
    def check_all(self):
        cond = Condition()
        for ctrl in self.details.keys():
            cond.set(self._check_controller_details(ctrl))
        return cond.state


    def _get_controller_list(self):
        log = logging.getLogger('controller.getlist')
        log.debug('starting getlist')

        # We blindly set the current controller to 1, as any system should have at least one controller -
        # this forces cli64 to print out the GuiErrMsg we can stop parsing on.
        self.proc.stdin.write('set curctrl=1\n')
        info = self._parse_table(self.proc.stdout, tables['cntrs'])

        log.debug('end of getlist')
        return info


    def _parse_table(self, stdout, table_spec):
        log = logging.getLogger('_parse_table')
        
        d = dict()
        seperator = re.compile('=+')
        
        state = 'HEAD'        # state machine, states are "HEAD", "TABLE", "TAIL"
                              # start at HEAD, transition each time you see a line of '='s, only one way
        
        log.debug('starting parse loop:')
        while True:
            line = stdout.readline().rstrip()
        
            # FIXME: hard coded assumption from looking at cli64 - if we contain the esc char, delete the first 10 as thats
            # the code for clearing the screen and repositioning to the origin.
            # What we should do is find esc's, and then consume the string to the first char in range 64-126.
            if line.count(chr(27)):
                line = line[10:]
                
            log.debug('current line: "%s"' % line)
                
            # Do this before we enter the state machine proper, as we don't care about which state we're in -
            # if we see this, we're done, regardless.
            if line.count('GuiErrMsg<0x00>: Success.'):
                break

            if state == 'HEAD':
                #log.debug('state = HEAD')
                if seperator.match(line):
                    log.debug('  seperator line - changing state to TABLE')
                    state = 'TABLE'
                    continue
                else:
                    # ignore this line
                    log.debug('  trash line - ignoring it and looping')
                    continue
            elif state == 'TABLE':
                log.debug('state = TABLE')
                if seperator.match(line):
                    log.debug('  seperator line - changing state to TAIL')
                    state = 'TAIL'
                    continue
                else:
                    log.debug('  table row - adding to dict')
                    (name, value) = table_spec['row_split'](line, table_spec)
                    d[name] = value
            elif state == 'TAIL':
                log.debug('state = TAIL')
                log.debug('  trash line - ignoring it and looping')
            else:
                log.debug('parse error - invalid state reached -- raising exception')
                raise Exception('parse error - invalid state reached')

        return d


    def _get_controller_details(self, ctrl, ctrl_model):
        log = logging.getLogger('controller.getdetails')
        log.debug('starting getdetails')

        d = dict()

        log.debug('attempting write set ctrl to %s' % ctrl)
        self.proc.stdin.write('set curctrl=%s\n' % ctrl)
        # we need to consume the output up to the GuiErrMsg so that _parse_table() will work
        while True:
            line = self.proc.stdout.readline()
            if line.count('GuiErrMsg<0x00>: Success.'):
                break

        # FIXME: this could be a loop based on the table - one more field to contain the command.
        self.proc.stdin.write('rsf info\n')
        d['raids'] = self._parse_table(self.proc.stdout, tables[ctrl_model]['raids'])

        self.proc.stdin.write('vsf info\n')
        d['volumes'] = self._parse_table(self.proc.stdout, tables[ctrl_model]['volumes'])

        self.proc.stdin.write('disk info\n')
        d['disks'] = self._parse_table(self.proc.stdout, tables[ctrl_model]['disks'])

        self.proc.stdin.write('sys info\n')
        d['sys'] = self._parse_table(self.proc.stdout, tables[ctrl_model]['sys'])

        return d


    # FIXME: This is very spartan because I'm developing on a machine with all healthy raids.
    def _check_controller_details(self, ctrl):
        log = logging.getLogger('controller.checkdetails')
        cond = Condition(Condition.OK)

#        pprint(self.details)
        # check the raid units themselves
        for raid in self.details[ctrl]['raids'].keys():
            detail = self.details[ctrl]['raids'][raid]
            if detail['status'] != 'Normal':
                cond.error()
                log.error('controller %s raid unit %s is not ok with status %s' 
                          % (ctrl, raid, detail['status'])) 

    #    for disk in details['disks'].keys():
    #        detail = details['disks'][disk]
    #        # On areca, I don't see a per-disk status yet.        

        for volume in self.details[ctrl]['volumes'].keys():
            detail = self.details[ctrl]['volumes'][volume]
            if detail['status'] != 'Normal':
                cond.error()
                log.error('controller %s volume %s is not ok with status %s' 
                          % (ctrl, volume, detail['status'])) 

        return cond.state


## END OF LINE ##
