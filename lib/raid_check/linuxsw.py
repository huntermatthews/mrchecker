
from subprocess import Popen, PIPE
import logging
from pprint import pprint

from raid_check.controller import Controller
from raid_check.condition import Condition
from raid_check.parser import row_hybrid_split, row_delimiter_split

__version__ = '1.0'


# FIXME: we mix the table, entry and row data in one dict here - very MESSY - seperate them
tables = {
    'arrays': { 'commandline': '%(program)s --examine --brief --scan --config=partition',
                'row_split': row_hybrid_split,
                'name_field': 'array_name',
                'fields_list': [('array_name', 1),
                                ('level', 2),
                                ('device_count', 3),
                                ('uuid', 4)],
                # 'strip_list': [None, '.'],
                },
    
    'array_details': { 'commandline': '%(program)s --detail %(array)s',
               'row_split': row_delimiter_split,
               'delimiter': ':',
               'name_field': 0,
               'value_field': 1,
               'strip_list': [None],
               },
    
    'disks': { 'commandline': None,    # we got the data from the array_details command...
               'row_split': row_hybrid_split,
               'name_field': 'number',
               'fields_list': [('number', 0),
                               ('major_devid', 1),
                               ('minor_devid', 2),
                               ('raid_device', 3),
                               ('state', 4),
                               ('device', -1)],
               'strip_list': [None],
               },
    }


program_list = ['mdadm']


class LinuxSW(Controller):
    
    def __init__(self, program_name):
        super(LinuxSW, self).__init__(program_name, program_list)
        self.log = logging.getLogger('Controller.LinuxSW')
        self.log.debug('__init__ starting')
        self.log.debug('__init__ ending')


    def setup(self):
        # Usually we do this by controller - in linux software raid, the OS _IS_ the controller,
        # so there can only be one. (VM's are their own OS, so thats irrelevant here I hope).
        self.log.debug('setup() starting')

        self.details = dict()
        array_list = self._get_array_list()
#        pprint(array_list)

        if not array_list:
            self.log.debug('setup() ending - didnt find any arrays - returning False')
            return False

        for array in array_list.keys():
            self.details[array] = self._get_array_details(array)
#            self.details[array]['summary'] = array_list[array]
#            silly for linux sw raid - repeats everything we already know.
            if not self.details[array]:
                self.log.debug('setup() ending - didnt find any details for a controller - returning False')
                return False

        self.log.debug('setup() ending - found array and details - returning True')
        return True


    def check_all(self):
        self.log.debug('check_all() starting')

        cond = Condition()
        for array in self.details.keys():
            rc = self._check_array_details(array)
#            self.log.info('_check_array_details on %s said %s' % (array, rc))
            cond.set(rc)

        self.log.debug('check_all() ending')
        return cond.state


    def _parse_array_table(self, iter, table_spec):
        self.log.debug('parse_array_table() starting')
        
        d = dict()

        for line in iter:
            line = line.strip()
            self.log.debug('  line is %s' % line)
            self.log.debug('  table row - adding to dict')
            (name, value) = table_spec['row_split'](line, table_spec)
            for key in value.keys():
                if value[key].count('='):
                    value[key] = value[key].split('=')[1]
            d[name] = value

        return d


    def _get_array_list(self):
        self.log.debug('_get_array_list() starting')

        args = dict(zip(['program'], [self.program]))
        cmdline = tables['arrays']['commandline'] % args
        self.log.debug('attempting cmd "%s"' % cmdline)

        d = dict()
        try:
            proc = Popen(cmdline.split(), shell=False, stdout=PIPE)
        except OSError, ex:
            self.log.exception('Specified backend command not found')
            return False

        d = self._parse_array_table(proc.stdout, tables['arrays'])
        self.log.debug('_get_array_list() ending')
        return d
    

    def _parse_table0(self, iter, table_spec):
        self.log.debug('parse_table0() starting')
        
        d = dict()

        for line in iter:
            line = line.strip()
            self.log.debug('  line is %s' % line)
            if line.count('Number   Major   Minor'):
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
            self.log.debug('  line is %s' % line)
            self.log.debug('  table row - adding to dict')
            (name, value) = table_spec['row_split'](line, table_spec)
            d[name] = value

        return d
    

    def _get_array_details(self, array):
        self.log.debug('_get_array_details() starting')

        args = dict(zip(['program', 'array'], [self.program, array]))
        cmdline = tables['array_details']['commandline'] % args
        self.log.debug('attempting cmd "%s"' % cmdline)

        try:
            proc = Popen(cmdline.split(), shell=False, stdout=PIPE)
        except OSError, ex:
            self.log.exception('Specified backend command not found')
            return False

        # Skip over first 1 lines, and then parse the table.
        for lineno in range(1):
            if not proc.stdout.next():   # we explicitly don't care about the content of the lines, if any
                # FIXME - should be a more specific error
                raise Exception('parse error')

        d = self._parse_table0(proc.stdout, tables['array_details'])

        # We're not done - after the array details, we get a list of the drives in the array
        # we need their state and name if nothing else.
        # Our previous effort stopped at the headers for this info, so we're perfectly positioned
        
        d['disks'] = self._parse_table1(proc.stdout, tables['disks'])

        return  d


    # FIXME: This is very spartan because I'm developing on a machine with all healthy raids.
    def _check_array_details(self, array):
        log = logging.getLogger('controller._check_array_details')
        cond = Condition(Condition.OK)

        # check the disks (physical drives)
        for disk in self.details[array]['disks'].keys():
            detail = self.details[array]['disks'][disk]
            if detail['state'] != 'active':
                cond.error()
                log.error('array %s disk %s is not ok with state %s' 
                          % (array, disk, detail['state'])) 
                

        detail = self.details[array]
        if detail['Failed Devices'] != '0':
            cond.error()
            log.error('array %s not ok with Failed Devices %s' 
                      % (array, detail['Failed Devices'])) 
            
        if detail['Working Devices'] != detail['Total Devices']:
            cond.warning()
            log.warning('array %s is not ok with Total Devices %s != Working Devices %s' 
                      % (array, detail['Total Devices'], detail['Working Devices'])) 
            
        return cond.state


## END OF LINE ##

