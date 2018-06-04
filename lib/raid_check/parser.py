import logging
import re

# Need to update threeware not to use this - replaced by row_hybrid_split()
def row_whitespace_split(line, fields):
    info = line.split()
    name = info[0]
    value = dict(zip(fields, info))
    return (name, value)


def row_hybrid_split(line, row_spec):
    # split on whitespace
    # option of pulling early and late columns
    # for whitespace containing columns, use fixed positions
    # row_spec = { name_field: name,
    #               fields_list: [
    #                ('name', #)   # 2-tuples are by space splitting
    #                ('name2', #, #) # 3-tuples are by position
    #               ]
    #             }
    log = logging.getLogger('row_hybrid_split')

    log.debug('name_field %s' % row_spec['name_field'])
    log.debug('fields_list %s' % row_spec['fields_list'])
    log.debug(line)
    log.debug('0123456789A123456789B123456789C123456789D123456789E123456789F123456789G123456789H')

    d = dict()
    split_line = line.split()
    for field in row_spec['fields_list']:
        if len(field) == 2:   # 2 tuple, by whitespace split
            log.debug('2-tuple type of line')
            log.debug(field[0])
            log.debug(field[1])
            d[field[0]] = split_line[field[1]]
            log.debug('adding %s with value %s' % (field[0], field[1]))
        elif len(field) == 3:   # 3-tuple, by fixed position
            log.debug('3-tuple type of line')
            d[field[0]] = line[field[1]:field[2]].strip()
            log.debug('adding %s with value %s' % (field[0], d[field[0]]))
        else:
            raise Exception('programming fault, only 2 and 3 tuples allowed')
    return(d[row_spec['name_field']], d)
    
                   
def row_fixed_split(line, row_spec):
    log = logging.getLogger('_row_fixed_split')

    log.debug('name_field %s' % row_spec['name_field'])
    log.debug('fields_list %s' % row_spec['fields_list'])
    log.debug(line)
    log.debug('0123456789A123456789B123456789C123456789D123456789E123456789F123456789G123456789H')

    d = dict()
    for field in row_spec['fields_list']:
        d[field[0]] = line[field[1]:field[2]].strip()
        log.debug('added row was "%s" = "%s"' % (field[0], d[field[0]]))

    return (d[row_spec['name_field']], d)


def row_delimiter_split(line, row_spec):
    log = logging.getLogger('_row_delimiter_split')

    log.debug('delimiter "%s"' % row_spec['delimiter'])
    log.debug('name field %s' % row_spec['name_field'])
    log.debug('value field %s' % row_spec['value_field'])
    log.debug(line)

    d = dict()
    info = line.split(row_spec['delimiter'], 1)   # Specify ONE maxsplit here, as some of our values
                                                  # have embeded delimiters (esp if delim is :) 
    name = info[row_spec['name_field']]
    value = info[row_spec['value_field']]
    for charset in row_spec['strip_list']:
        name = name.strip(charset)
        value = value.strip(charset)
    return (name, value)


        

## END OF LINE ##
