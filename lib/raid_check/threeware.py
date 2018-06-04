
from subprocess import Popen, PIPE
import logging

from raid_check.controller import Controller
from raid_check.condition import Condition


__version__ = '1.0'


tables = {
    'cntrs': (['controller', 'model', 'ports', 'drives', 'units', 'notopt', 'rrate', 'vrate', 'bbu_status'],
              ['Ctl   Model        (V)Ports  Drives   Units   NotOpt  RRate   VRate  BBU',
               'Ctl   Model        Ports   Drives   Units   NotOpt   RRate   VRate   BBU',
               '------------------------------------------------------------------------']),
    'units': (['unit', 'type', 'status', 'rebuild_complete', 'VIM', 'strip_size', 'size', 'cache', 'auto_verify'],
              ['Unit  UnitType  Status         %RCmpl  %V/I/M  Stripe  Size(GB)  Cache  AVrfy',
               '------------------------------------------------------------------------------']),
    'ports': (['port', 'status', 'unit', 'size', 'size units', 'blocks', 'serial number'],
              ['Port   Status           Unit   Size        Blocks        Serial',
               '---------------------------------------------------------------']),
    'bbus':  (['name', 'onlinestate', 'bbuready', 'status', 'volt', 'temp', 'hours', 'lastcaptest'],
              ['Name  OnlineState  BBUReady  Status    Volt     Temp     Hours  LastCapTest',
               '---------------------------------------------------------------------------'])
}


program_list = ['tw_cli']


class Threeware(Controller):
    
    def __init__(self, program_name):
        super(Threeware, self).__init__(program_name, program_list)
        log = logging.getLogger('Controller.Threeware.init')

        log.debug('Controller.Threeware.init ending')


    def setup(self):
        log = logging.getLogger('Controller.Threeware.setup')

        self.ctrl_list = self._get_controller_list()
        if not self.ctrl_list:
            return False
        self.details = dict()
        for ctrl in self.ctrl_list.keys():
            self.details[ctrl] = self._get_controller_details(ctrl)
            if not self.ctrl_list:
                return False
        return True


    def check_all(self):
        log = logging.getLogger('controller.threeware.check_all')
        cond = Condition()

        rc = self._check_controller_list()
        #log.info('_check_controller_list said %s' % rc)
        cond.set(rc)

        for ctrl in self.ctrl_list.keys():
            rc = self._check_controller_details(ctrl)
            #log.info('_check_controller_details on %s said %s' % (ctrl, rc))
            cond.set(rc)

        return cond.state


    def _parse_table(self, iter, fields, ignore_lines):
        d = dict()

        for line in iter:
            line = line.strip()
            if not line:            # blank line means end of table
                return d
            if not line in ignore_lines:
                info = line.split()
                name = info[0]   
                d[name] = dict(zip(fields, info))


    def _get_controller_list(self):
        log = logging.getLogger('controller.threeware._get_controller_list')

        cmd = "%s show" % self.program
        log.debug('attempting cmd "%s"' % cmd)

        try:
            proc = Popen(cmd, shell=True, stdout=PIPE)
            iter = proc.stdout
        except OSError, ex:
            log.exception('Specified backend command not found')
            return False

        # Skip over first line, and then parse the table.
        if not iter.next() == '\n':
            # FIXME
            raise Exception('parse error')

        return self._parse_table(iter, tables['cntrs'][0], tables['cntrs'][1])


    def _get_controller_details(self, ctrl):
        log = logging.getLogger('controller.threeware._get_controller_details')

        cmd = "%s /%s show" % (self.program, ctrl)
        log.debug('attempting cmd "%s"' % cmd)

        d = dict()
        try:
            proc = Popen(cmd, shell=True, stdout=PIPE)
            iter = proc.stdout
        except OSError, ex:
            log.exception('Specified backend command not found')
            return False

        # Skip over first line, and then parse the table.
        if not iter.next() == '\n':
            # FIXME
            raise Exception('parse error')

        # First table is the unit table
        for table in ['units', 'ports', 'bbus']:
            d[table] = self._parse_table(iter, tables[table][0], tables[table][1])

        return d

    def _check_controller_list(self):
        log = logging.getLogger('controller.threeware._check_controller_list')
        cond = Condition(Condition.OK)

        for ctrl in self.ctrl_list.keys():
            if self.ctrl_list[ctrl]['notopt'] != '0':
                cond.error()
                log.error('%s controller has a raid in non-optimal state' % ctrl)
            if self.ctrl_list[ctrl]['bbu_status'] != 'OK':
                cond.error()
                log.error('%s controller has a battery problem of "%s"' % (ctrl, self.ctrl_list[ctrl]['bbu_status']))
        return cond.state


    def _check_controller_details(self, ctrl):
        log = logging.getLogger('controller.threeware._check_controller_details')
        cond = Condition(Condition.OK)

        # check the raid units themselves
        for unit in self.details[ctrl]['units'].keys():
            detail = self.details[ctrl]['units'][unit]
            if detail['status'] != 'OK':
                cond.error()
                log.error('%s raid unit %s is not ok with status %s' % (ctrl, unit, detail['status'])) 
            if detail['cache'] != 'ON' and detail['type'] != 'SPARE':
                cond.error()
                log.error('%s raid unit %s has its cache turned off' % (ctrl, unit))
            if detail['auto_verify'] != 'ON' and detail['type'] != 'SPARE':
                cond.warning()
                log.warning('%s raid unit %s does not have auto verify on' % (ctrl, unit))

        for port in self.details[ctrl]['ports'].keys():
            detail = self.details[ctrl]['ports'][port]
            # This one is a double check - if the port has an issue but doesn't belong to an active
            # raid, its not a problem  - at most a warning
            if detail['status'] != 'OK' and detail['unit'] != '-':
                cond.error()
                log.error('%s port %s has a status of %s' % (ctrl, port, detail['status']))

        for bbu in self.details[ctrl]['bbus'].keys():
            detail = self.details[ctrl]['bbus'][bbu]
            if detail['status'] != 'OK':
                cond.error()
                log.error('%s bbu %s has a status of %s' % (ctrl, bbu, detail['status']))
            if detail['bbuready'] != 'Yes':
                cond.error()
                log.error('%s bbu %s is not ready' % (ctrl, bbu))
            if detail['lastcaptest'] == 'xx-xxx-xxxx':
                cond.warning()
                log.warn('%s bbu %s has not been capacity tested' % (ctrl, bbu))
            if detail['onlinestate'] != 'On':
                cond.error()
                log.error('%s bbu %s is not online' % (ctrl, bbu))
            if detail['temp'] != 'OK':
                cond.error()
                log.error('%s bbu %s has a temp problem (%s)' % (ctrl, bbu, detail['temp']))
            if detail['volt'] != 'OK':
                cond.error()
                log.error('%s bbu %s has a voltage problem (%s)' % (ctrl, bbu, detail['volt']))

        return cond.state


## END OF LINE ##

