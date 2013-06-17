__author__ = 'fjohnson'
import subprocess
import os
import shutil
import sys
import signal

try:
    import psutil
except ImportError: #automatically install psutils with yum if not found
    resp=''
    while resp != 'y' and resp != 'n':
        resp=raw_input('psutil not installed. install? (y/n)')
    if resp == 'n':
        print 'exiting.'
    if os.geteuid() != 0:
        print >> sys.stderr, 'exiting. must be root.'
        sys.exit(1)
    curd=os.getcwd()
    os.chdir('/tmp')
    p=subprocess.Popen('yum install python-devel'.split())
    p.wait()
    p=subprocess.Popen('wget http://psutil.googlecode.com/files/psutil-0.6.1.tar.gz'.split())
    p.wait()
    p=subprocess.Popen('tar xzvf psutil-0.6.1.tar.gz'.split())
    p.wait()
    os.chdir('psutil-0.6.1')
    p=subprocess.Popen('python setup.py install'.split())
    p.wait()
    os.chdir('/tmp')
    shutil.rmtree('psutil-0.6.1')
    os.unlink('psutil-0.6.1.tar.gz')
    os.chdir(curd)

    print 'restart.'
    sys.exit(0)

#map of signal values to names
signal_map=dict((k, v) for v, k in signal.__dict__.iteritems() if v.startswith('SIG') and not v.startswith('SIG_'))

def displaypid_info(pid):

    p=psutil.Process(pid)
    attrdict=p.as_dict(ad_value='permission denied')
    print 'pid:%d ppid:%d name: %s' % (p.pid,p.ppid,p.name)
    print 'exe:%s cmdline:%s' %(p.exe,p.cmdline)
    print 'cwd:%s'%attrdict['cwd']
    print p.uids
    print p.gids
    print 'owner(real uid):%s term:%s' % (p.username,p.terminal)
    print 'status:%s nice:%d' % (p.status,p.get_nice())
    print 'create_time:%f ' % p.create_time

    print
    print 'cpu_affinity:%s cpu_percent:%f cpu_times:%s' % (p.get_cpu_affinity(),p.get_cpu_percent(),p.get_cpu_times())
    rss,vms=p.get_memory_info()
    rss=(rss/1024.0)/1024
    vms=(vms/1024.0)/1024
    print 'memory_info: rss=%fMB vms=%fMB memory_percent:%%%f' %(rss,vms,p.get_memory_percent())
    print 'ext_memory_info:'+str(p.get_ext_memory_info())

    print
    print 'num_threads:%d' % attrdict['num_threads']
    #print 'threads:%s' % attrdict['threads']
    print 'direct children: %s' % p.get_children()

    print 'num_fds:%d'%attrdict['num_fds']
    io=attrdict['io_counters']
    if io.read_bytes>1024 and io.read_bytes <1024*1024:
        read_bytes=str(io.read_bytes/1024)+'KB'
    elif io.read_bytes > 1024*1024:
        read_bytes = str(io.read_bytes/1024.0/1024)+'MB'
    else:
        read_bytes=io.read_bytes
    if io.write_bytes>1024 and io.write_bytes <1024*1024:
        write_bytes=str(io.write_bytes/1024)+'KB'
    elif io.write_bytes > 1024*1024:
        write_bytes = str(io.write_bytes/1024.0/1024)+'MB'
    else:
        write_bytes = io.write_bytes
    print 'io: %s %s' % (read_bytes,write_bytes)
    print attrdict['ionice']

    files = attrdict['open_files']
    if files:
        print
        print 'Files'
        for f in files: print f
    connections=attrdict['connections']
    if connections:
        print
        print 'Connections'
        for c in connections: print c

    #for m in p.get_memory_maps(grouped=True): print m