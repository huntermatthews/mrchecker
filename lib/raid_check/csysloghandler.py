import logging
import syslog
import types

__version__ = '1.0'


class CSysLogHandler(logging.Handler):

    def __init__(self, facility=syslog.LOG_USER, ident='', logopts=0):
        logging.Handler.__init__(self)

        self.formatter = None
        syslog.openlog(ident, logopts, facility)

    def _convertPriorityName(self, priority):
        priority_names = {
            "alert":    syslog.LOG_ALERT,
            "crit":     syslog.LOG_CRIT,
            "critical": syslog.LOG_CRIT,
            "debug":    syslog.LOG_DEBUG,
            "emerg":    syslog.LOG_EMERG,
            "err":      syslog.LOG_ERR,
            "error":    syslog.LOG_ERR,        #  DEPRECATED
            "info":     syslog.LOG_INFO,
            "notice":   syslog.LOG_NOTICE,
            "panic":    syslog.LOG_EMERG,      #  DEPRECATED
            "warn":     syslog.LOG_WARNING,    #  DEPRECATED
            "warning":  syslog.LOG_WARNING,
            }
        
        if type(priority) == types.StringType:
            priority = priority_names[priority]
        return priority
        
    def emit(self, record):
        msg = self.format(record)
        priority = self._convertPriorityName(record.levelname.lower())
        syslog.syslog(priority, msg)

    def close(self):
        syslog.closelog()

       
## END OF LINE ##
