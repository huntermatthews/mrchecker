

class Condition(object):
    (OK, WARNING, ERROR) = range(0,3)

    def __init__(self, initial=OK):
        self.state = initial
        
    def set(self, state):
        if self.state < state:
            self.state = state
            
    def ok(self, state=OK):
        self.set(state)
    
    def warning(self, state=WARNING):
        self.set(state)
    
    def error(self, state=ERROR):
        self.set(state)

    def __str__(self):
        if self.state == self.OK:
            return 'OK'
        elif self.state == self.WARNING:
            return 'WARNING'
        elif self.state == self.ERROR:
            return 'ERROR'
        else:
            raise Exception('invalid state')


## END OF LINE ##
