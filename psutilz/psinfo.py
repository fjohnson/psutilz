__author__ = 'fjohnson'

import sys
from pscommon import psutil
from pscommon import displaypid_info

'''Display basic information about a specified pid'''

def pidinfo_dict(pid):
    p=psutil.Process(pid)
    for k,v in p.as_dict(ad_value='denied').items():
        print k + ':' + str(v)

if __name__ == '__main__':
    usage = 'pinfo pid'
    try: pid = int(sys.argv[1])
    except IndexError,ValueError:
        print >> sys.stderr, usage
        sys.exit(1)

    displaypid_info(pid)
    #pidinfo_dict(pid)