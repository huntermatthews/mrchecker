import logging
import os.path

from raid_check.condition import Condition

paths = ['/usr/sbin', '/usr/bin', '/sbin', '/bin' ] 

class Controller(object):

    def __init__(self, program_name, program_list):
        self.logname = 'Controller'
        self.name = self.__class__.__name__
        self.set_program(program_name, program_list)


    def set_program(self, program_name, program_list):
        log = logging.getLogger('.'.join([self.logname, 'set_program']))

        if program_name == None:
            for prog in program_list:
                pathname = self.find_exec(prog)   # returns None if not found
                if pathname:
                    self.program = pathname
                    log.debug('program found in built-in path: %s' % self.program)
                    return
            # not found yet
            self.program = program_list[0]    # blind shot in the dark
            log.debug('program not found in built-in path, using %s' % self.program)
        else:
            self.program = program_name
            log.debug('program set by command line option, using %s' % self.program)


    def find_exec(self, name):
        for path in paths:
            pathname = os.path.join(path, name)
            if os.path.exists(pathname):
                return pathname

        return None


    # API
    def setup(self):
        pass


    # API
    def teardown(self):
        log = logging.getLogger('.'.join([self.logname, 'teardown']))
        log.debug('teardown() starting')
        # nothing to do here
        log.debug('teardown() ending')


    # API
    def check_all(self):
        pass


    # API
    def dump_details(self):
        return self.details


## END OF LINE ##
