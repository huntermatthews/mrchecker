
from subprocess import Popen, PIPE
import logging
from pprint import pprint

from raid_check.controller import Controller
from raid_check.condition import Condition
from raid_check.parser import row_hybrid_split, row_delimiter_split

__version__ = '1.0'


# FIXME: we mix the table, entry and row data in one dict here - very MESSY - seperate them
tables = {
    'cntrs': { 'row_split': row_delimiter_split,
               'delimiter': ':',
               'name_field': 0,
               'value_field': 1,
               'strip_list': [None, '.'],
               },
    
    'enclosures': { 'commandline': '%(program)s -encinfo -a%(controller)s',
                    'row_split': row_delimiter_split,
                    'delimiter': ':',
                    'name_field': 0,
                    'value_field': 1,
                    'entry_name': 'Device ID',
                    'strip_list': [None],
                    },
    
    'disks': { 'commandline': '%(program)s -pdlist -a%(controller)s',
               'row_split': row_delimiter_split,
               'delimiter': ':',
               'name_field': 0,
               'value_field': 1,
               'entry_name': 'Device Id',
               'strip_list': [None],
               },
    
    'volumes': { 'commandline': '%(program)s -ldinfo -lall -a%(controller)s',
                 'row_split': row_delimiter_split,
                 'delimiter': ':',
                 'name_field': 0,
                 'value_field': 1,
                 'entry_name': 'Name',
                 'strip_list': [None],
                 },
    }


program_list = ['MegaCli64', 'MegaCli']


class MegaRaid(Controller):
    
    def __init__(self, program_name):
        super(MegaRaid, self).__init__(program_name, program_list)
        self.log = logging.getLogger('Controller.MegaRaid')
        self.log.debug('__init__ starting')
        self.log.debug('__init__ ending')


    def setup(self):
        self.log.debug('setup() starting')

        self.ctrl_list = self._get_controller_list()
#        pprint(self.ctrl_list)
        
        if not self.ctrl_list:
            self.log.debug('setup() ending - didnt find any controllers - returning False')
            return False
        self.details = dict()
        for ctrl in self.ctrl_list.keys():
            self.details[ctrl] = self._get_controller_details(ctrl)
#            print 'inside setup() - printing results'
#            pprint(self.details[ctrl])
            if not self.details[ctrl]:
                self.log.debug('setup() ending - didnt find any details for a controller - returning False')
                return False

        self.log.debug('setup() ending - found controllers and details - returning True')
        return True


    def check_all(self):
        self.log.debug('check_all() starting')

        cond = Condition()
        for ctrl in self.ctrl_list.keys():
            rc = self._check_controller_details(ctrl)
#            self.log.info('_check_controller_details on %s said %s' % (ctrl, rc))
            cond.set(rc)

        self.log.debug('check_all() ending')
        return cond.state


    def _parse_table0(self, iter, table_spec):
        self.log.debug('parse_table0() starting')
        
        d = dict()

        for line in iter:
            line = line.strip()
            self.log.debug('  line is %s' % line)
            if line.count('Exit Code:'):
                self.log.debug('parse_table0() ending')
                return d 
            elif not line:
                continue
            else:
                self.log.debug('  table row - adding to dict')
                (name, value) = table_spec['row_split'](line, table_spec)
                d[name] = value



    def _parse_table1(self, iter, table_spec):
        self.log.debug('parse_table1() starting')

        d = dict()

        for line in iter:
            line = line.strip()
            if line.count('Exit Code:'):
                self.log.debug('parse_table1() ending = NONE')
                return None
            elif not line:
                self.log.debug('parse_table1() ending = DICT')
                return d
            else:
                self.log.debug('  table row - adding to dict')
                (name, value) = table_spec['row_split'](line, table_spec)
                d[name] = value


        
    def _get_controller_list(self):
        self.log.debug('_get_controller_list() starting')

        cmdline = '%s -adpcount' % self.program
        self.log.debug('attempting cmd "%s"' % cmdline)

        d = dict()
        try:
            proc = Popen(cmdline.split(), shell=False, stdout=PIPE)
        except OSError, ex:
            self.log.exception('Specified backend command not found')
            return False

        # Megacli only returns a count, which we then must convert to 0 based (subtract 1)
        # FIXME: next line does too much
        count = int(self._parse_table0(proc.stdout, tables['cntrs'])['Controller Count'])
        for num in range(count):
            d[num] = None        # we have no data as yet - just the "identifier" itself

        self.log.debug('_get_controller_list() ending')    
        return d
    

    def _get_controller_details(self, ctrl):
        self.log.debug('_get_controller_details() starting')

        d = dict() 
        for table in tables:
            if table == 'cntrs':
                continue         # we already did this - we want the details of each controller now,
                                 # not the controller itself.
            d[table] = self._get_controller_subdetail(ctrl, table)
#            pprint(d[table])

        self.log.debug('_get_controller_details() ending')
        return d

    def _parse_vertical_table(self, iter, table_spec):
        self.log.debug('_parse_vertical_table() starting')

        d = dict()
        while True:
            res = self._parse_table1(iter, table_spec)
            if res:
                d[res[table_spec['entry_name']]] = res
            else:
                return d
            
        
    def _get_controller_subdetail(self, ctrl, table):
        self.log.debug('_get_controller_subdetail() starting')
        

        args = dict(zip(['program', 'controller'], [self.program, ctrl]))
#        print 'args:'
#        pprint(args)
#        print 'table name:'
#        pprint(table)
#        print 'table spec:'
#        pprint(tables[table])
#        print 'command line string (before replacements):'
#        pprint(tables[table]['commandline'])
        cmdline = tables[table]['commandline'] % args
        self.log.debug('attempting cmd "%s"' % cmdline)

        d = dict()
        try:
            proc = Popen(cmdline.split(), shell=False, stdout=PIPE)
        except OSError, ex:
            self.log.exception('Specified backend command not found')
            return False

        # Skip over first 3 lines, and then parse the table.
        for lineno in range(3):
            if not proc.stdout.next():   # we explicitly don't care about the content of the lines, if any
                # FIXME
                raise Exception('parse error')

#        d[table] = self._parse_vertical_table(proc.stdout, tables[table])
#        return d
        return self._parse_vertical_table(proc.stdout, tables[table])


    # FIXME: This is very spartan because I'm developing on a machine with all healthy raids.
    def _check_controller_details(self, ctrl):
        log = logging.getLogger('controller.checkdetails')
        cond = Condition(Condition.OK)

        # check the disks (physical drives)
        for disk in self.details[ctrl]['disks'].keys():
            detail = self.details[ctrl]['disks'][disk]
            if detail['Firmware state'] != 'Online':
                cond.warning()
                log.warning('controller %s disk %s is not ok with Firmware State %s' 
                          % (ctrl, disk, detail['Firmware state'])) 
            if detail['Last Predictive Failure Event Seq Number'] != '0':
                cond.error()
                log.error('controller %s disk %s is not ok with Last Predictive Event Number %s' 
                          % (ctrl, disk, detail['Last Predictive Failure Event Seq Number'])) 
            if detail['Media Error Count'] != '0':
                cond.error()
                log.error('controller %s disk %s is not ok with Media Error Count %s' 
                          % (ctrl, disk, detail['Media Error Count'])) 
            if detail['Predictive Failure Count'] != '0':
                cond.warning()
                log.error('controller %s disk %s is not ok with Predictive Failure Count %s' 
                          % (ctrl, disk, detail['Predictive Failure Count'])) 
                

        for enclosure in self.details[ctrl]['enclosures'].keys():
            detail = self.details[ctrl]['enclosures'][enclosure]
            if detail['Status'] != 'Normal':
                cond.error()
                log.error('controller %s enclosure unit %s is not ok with status %s' 
                          % (ctrl, raid, detail['Status'])) 
            if detail['Number of Alarms'] != '0':
                cond.error()
                log.error('controller %s enclosure unit %s is not ok with Numer of Alarms %s' 
                          % (ctrl, raid, detail['Number of Alarms'])) 

        for volume in self.details[ctrl]['volumes'].keys():
            detail = self.details[ctrl]['volumes'][volume]
            if detail['State'] != 'Optimal':
                cond.error()
                log.error('controller %s volume %s is not ok with State %s' 
                          % (ctrl, volume, detail['State'])) 

        return cond.state


## END OF LINE ##

