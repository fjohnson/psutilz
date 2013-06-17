from pscommon import psutil,displaypid_info
import sys
import re
import socket

'''Look up and display information about a process using the specified port and (optional) ip address'''

def displayproc(p):
    '''Display basic information about a process'''

    print p.name,p.exe,p.cmdline
    print p.username,p.terminal,p.status
    print p.getcwd()
    print 'mem %% %f'%p.get_memory_percent()
    print 'files: ' + str(p.get_open_files())
    print 'connections: ' + str(p.get_connections())

def proc(port,ip=None):
    '''Display information about a process using a particular ip  (optional) and port'''

    for p in psutil.process_iter():
        cons = p.get_connections()
        found = False
        for c in cons:
            if ip and c.local_address == (ip,port) or not ip and c.local_address[1] == port:
                displaypid_info(p.pid)
                found=True
                break
        if found: break

if __name__ == '__main__':
    usage='usage: ppf [host/ip] port'
    if len(sys.argv) < 2:
        print >> sys.stderr, usage
        sys.exit(1)
    if len(sys.argv)==2:
        ip=None
        port = sys.argv[1]
    else:
        ip = sys.argv[1]
        port = sys.argv[2]
    if ip:
        try:ip=socket.gethostbyname(ip)
        except (socket.gaierror,socket.herror) as e:
            print >> sys.stderr, str(e)
            sys.exit(1)
    try:
        port = int(port)
        if port < 1 or port > 65535:
            raise ValueError
    except ValueError:
        print >> sys.stderr, usage
        sys.exit(1)
    if ip:proc(port,ip)
    else:proc(port)