
from subprocess import Popen, PIPE
import logging
from pprint import pprint

from raid_check.controller import Controller
from raid_check.condition import Condition
from raid_check.parser import row_hybrid_split, row_delimiter_split

__version__ = '1.0'


# FIXME: we mix the table, entry and row data in one dict here - very MESSY - seperate them
tables = {
    'zpools': { 'commandline': 'zpool list -H',
                'row_split': row_hybrid_split,
                'name_field': 'name',
                'fields_list': [('name', 0),
                                ('size', 1),
                                ('used', 2),
                                ('avail', 3),
                                ('capacity', 4),
                                ('health', 5),
                                ('altroot', 6)],
                # 'strip_list': [None, '.'],
                },
    
    'zpool_details': { 'commandline': 'zpool status %(zpool)s',
                      'row_split': row_delimiter_split,
                      'delimiter': ':',
                      'name_field': 0,
                      'value_field': 1,
                      'strip_list': [None],
                      },
    
    'disks': { 'commandline': None,    # we got the data from the pool_details command...
               'row_split': row_hybrid_split,
               'name_field': 'name',
               'fields_list': [('name', 0),
                               ('state', 1),
                               ('read_errors', 2),
                               ('write_errors', 3),
                               ('checksum_errors', 4)],
               'strip_list': [None],
               },

    # Should we also include zfs actually?
    }


program_list = ['zpool']


class ZPool(Controller):
    
    def __init__(self, program_name):
        super(ZPool, self).__init__(program_name, program_list)  

        self.log = logging.getLogger('Controller.ZPool')
        self.log.debug('__init__ starting')
        self.log.debug('__init__ ending')


    def setup(self):
        # Usually we do this by controller - in zpool/zfs, the OS _IS_ the controller,
        # so there can only be one. (VM's are their own OS, so thats irrelevant here I hope).
        self.log.debug('setup() starting')

        self.details = dict()
        zpool_list = self._get_zpool_list()

        if not zpool_list:
            self.log.debug('setup() ending - didnt find any zpools - returning False')
            return False

        for zpool in zpool_list.keys():
            self.details[zpool] = self._get_zpool_details(zpool)
            self.details[zpool]['summary'] = zpool_list[zpool]
            if not self.details[zpool]:
                self.log.debug('setup() ending - didnt find any details for a controller - returning False')
                return False

        self.log.debug('setup() ending - found zpool and details - returning True')
        return True


    def check_all(self):
        self.log.debug('check_all() starting')

        cond = Condition()
        for zpool in self.details.keys():
            rc = self._check_zpool_details(zpool)
#            self.log.info('_check_zpool_details on %s said %s' % (zpool, rc))
            cond.set(rc)

        self.log.debug('check_all() ending')
        return cond.state


    def _parse_zpool_table(self, iter, table_spec):
        self.log.debug('parse_zpool_table() starting')
        
        d = dict()

        for line in iter:
            line = line.strip()
            self.log.debug('  line is %s' % line)
            self.log.debug('  table row - adding to dict')
            (name, value) = table_spec['row_split'](line, table_spec)
            d[name] = value

        return d


    def _get_zpool_list(self):
        self.log.debug('_get_zpool_list() starting')

        cmdline = tables['zpools']['commandline'] 
        self.log.debug('attempting cmd "%s"' % cmdline)

        d = dict()
        try:
            proc = Popen(cmdline.split(), shell=False, stdout=PIPE)
        except OSError, ex:
            self.log.exception('Specified backend command not found')
            return False

        d = self._parse_zpool_table(proc.stdout, tables['zpools'])
        self.log.debug('_get_zpool_list() ending')
        return d
    

    def _parse_table0(self, iter, table_spec):
        self.log.debug('parse_table0() starting')
        
        d = dict()

        for line in iter:
            line = line.strip()
            self.log.debug('  line is %s' % line)
            if line.count('config:'):
                self.log.debug('parse_table0() ending')
                return d 
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
            if not line:
                return d 
            self.log.debug('  table row - adding to dict')
            (name, value) = table_spec['row_split'](line, table_spec)
            d[name] = value

        return d
    

    def _get_zpool_details(self, zpool):
        self.log.debug('_get_zpool_details() starting')

        args = dict(zip(['zpool'], [zpool]))
        cmdline = tables['zpool_details']['commandline'] % args
        self.log.debug('attempting cmd "%s"' % cmdline)

        try:
            proc = Popen(cmdline.split(), shell=False, stdout=PIPE)
        except OSError, ex:
            self.log.exception('Specified backend command not found')
            return False

        d = self._parse_table0(proc.stdout, tables['zpool_details'])

        # We're not done - after the zpool details, we get a list of the drives/vdevs in the zpool
        # we need their state and name if nothing else.

        # Skip over lines until we hit the table header
        for line in proc.stdout:
            line = line.strip()
            if line.count('NAME'):
                break

        d['disks'] = self._parse_table1(proc.stdout, tables['disks'])

        return  d


    # FIXME: This is very spartan because I'm developing on a machine with all healthy raids.
    def _check_zpool_details(self, zpool):
        log = logging.getLogger('controller._check_zpool_details')
        cond = Condition(Condition.OK)

        # check the disks (physical drives)
        for disk in self.details[zpool]['disks'].keys():
            detail = self.details[zpool]['disks'][disk]
            if detail['state'] != 'ONLINE':
                cond.error()
                log.error('zpool %s disk %s is not ok with state %s' 
                          % (zpool, disk, detail['state'])) 
            if detail['checksum_errors'] != '0':
                cond.warning()
                log.warning('zpool %s disk %s is not ok with checksum_errors %s' 
                          % (zpool, disk, detail['checksum_errors'])) 
            if detail['write_errors'] != '0':
                cond.warning()
                log.warning('zpool %s disk %s is not ok with write_errors %s' 
                          % (zpool, disk, detail['write_errors'])) 
            if detail['read_errors'] != '0':
                cond.warning()
                log.warning('zpool %s disk %s is not ok with read_errors %s' 
                          % (zpool, disk, detail['read_errors'])) 
                

        detail = self.details[zpool]
        if detail['state'] != 'ONLINE':
            cond.error()
            log.error('zpool %s not ok with state %s' 
                      % (zpool, detail['state'])) 
            
            
        return cond.state


## END OF LINE ##

