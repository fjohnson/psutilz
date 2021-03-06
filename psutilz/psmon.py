__author__ = 'fjohnson'
import psutil
import sys
import signal
import pscommon
import time
import os
import itertools
from subprocess import Popen, PIPE
from tempfile import NamedTemporaryFile
from itertools import izip

'''This module is designed to allow you to graph a number of different stats for a running process.
This module captures a variety of stats such as cpu utilization, memory utilization, io read/write byteds,
number of children, network connection information, number of allowed cpus and more.

Stats for a process can be captured to a file or they can be graphed with gnuplot or both.
A duration is specfied for collecting stats for the particular process. Stats are also gathered for the
children of child processes and so on (the stats collection is recursive on children)

Refer to the 'plots' dir for example gnuplot code, data and generated plots
'''

class PsmonException(Exception): pass

class Plot():
    '''A class representation of a 2d or 3d gnuplot'''
    def __init__(self):
        self.zlabel = None
        self.ylabel = None
        self.xlabel = None
        self.zrange = None
        self.yrange = None
        self.xrange = None
        self.ztics = None
        self.ytics = None
        self.xtics = None
        self.title = None
        self.datapoints = []
        self.is_3d = False

        self.set_ztics = False
        self.set_ytics = False
        self.set_xtics = False
        self.unset_ztics = False
        self.unset_ytics = False
        self.unset_xtics = False

    def add_datapoint(self,datapoint):
        '''Add a series of columns to plot
        datapoint should resemble something like this
        'system_cpu.dat' using 3:15:4 title 'system' with linespoints
        '''

        if self.datapoints == []:
            if self.is_3d: self.datapoints.append('splot \\')
            else: self.datapoints.append('plot \\')
        self.datapoints.append(datapoint + ',\\' )

    def __str__(self):
        strbuf = []
        if self.zlabel: strbuf.append("set zlabel %s" % self.zlabel)
        if self.ylabel: strbuf.append("set ylabel %s" % self.ylabel)
        if self.xlabel: strbuf.append("set xlabel %s" % self.xlabel)
        if self.zrange: strbuf.append("set zrange %s" % self.zrange)
        if self.yrange: strbuf.append("set yrange %s" % self.yrange)
        if self.xrange: strbuf.append("set xrange %s" % self.xrange)
        if self.ztics: strbuf.append("set ztics %s" % self.ztics)
        if self.ytics: strbuf.append("set ytics %s" % self.ytics)
        if self.xtics: strbuf.append("set xtics %s" % self.xtics)
        if self.title: strbuf.append("set title %s" % self.title)
        if self.unset_ztics: strbuf.append("unset ztics")
        if self.unset_ytics: strbuf.append("unset ytics")
        if self.unset_xtics: strbuf.append("unset xtics")
        if self.set_ztics: strbuf.append("set ztics")
        if self.set_ytics: strbuf.append("set ytics")
        if self.set_xtics: strbuf.append("set xtics")

        for p in self.datapoints[:-1]:
            strbuf.append(p)
        if self.datapoints != []:
            strbuf.append(self.datapoints[-1][:-2]) #strip ,\ off last data point entry

        return '\n'.join(strbuf)

class MultiPlot():
    '''A class representing a gnu multiplot. Contains one or more Plot instances'''

    def __init__(self, layout, title):
        '''Set the multiple properties.
        Properties looks like: set multiplot layout 2,1 title 'System CPU Activity Times'
        '''
        self.layout = "set multiplot layout %s" % layout
        self.title = title
        self.plots = []

    def create_plot(self):
        '''Create a new plot and return it'''
        p = Plot()
        self.plots.append(p)
        return p

    def __str__(self):
        strbuf = [self.layout, 'set title "%s"' % self.title]
        for plot in self.plots:
            strbuf.append(str(plot))
        return '\n\n'.join(strbuf)

class Procstat():
    '''stats for a single process'''


    stats_of_interest=[
      'sample_time',#time sample has been taken
      'status', #process status
      'io_readbytes', #read bytes
      'io_writebytes', #write bytes
      'io_nice_priority', #io priority for io_nice_class
      'io_nice_class', #io priority class. See IOPRIO_CLASS* constants
      'nthreads', #number of threads
      'nfds', #number of fds
      'ctx_switches', #context switch count
      'cpu_percent', #cpu utilization of this process
      'cpu_affinity', #number of cpus process is allowed to use
      'cpu_user', #time spent in userspace
      'cpu_kernel',#time spent in the kernel
      'rss', #memory rss
      'vms', #memory vms
      'mem_percent', #memory as percent based on rss to system memory
      'nchildren', #number of children (all descendents, not just direct)
      'nconnections', #number of network connections. all types
    ]

    def __init__(self, process):

        self.p = process

        #cache these so that when we query dead processes for their pid and name
        #psutils.error.NoSuchProcess is not thrown
        self.pid = self.p.pid
        self.name = self.p.name

        self.statmap={}
        for k in Procstat.stats_of_interest: self.statmap[k]=[]

    def __setitem__(self,item,val):
        self.statmap[item]=val

    def __getitem__(self,item):
        return self.statmap[item]

cpu_time_modes=[
    #system wide times spent by the cpu in the following modes
    'system_cpu_user',
    'system_cpu_system',
    'system_cpu_idle',
    'system_cpu_nice',
    'system_cpu_iowait',
    'system_cpu_irq',
    'system_cpu_softirq'
]

#stats for total system utilization
_sys_stats = {
    #total system cpu use
    'system_cpu_percent' :[],
    'sample_time':[]#time sample has been taken
}
for k in cpu_time_modes: _sys_stats[k] = []


sample_interval=.1 #cpu sample interval

_iopmap=dict([(psutil.IOPRIO_CLASS_NONE,'IOPRIO_CLASS_NONE'),
             (psutil.IOPRIO_CLASS_RT,'IOPRIO_CLASS_RT'),
             (psutil.IOPRIO_CLASS_BE,'IOPRIO_CLASS_BE'),
             (psutil.IOPRIO_CLASS_IDLE,'IOPRIO_CLASS_IDLE')])

global _file #output file
global _proc_list #list of alive procs
global _dead_proc_list #list of dead procs
global _stime #capture start time

def get_stats(pstatobj):
    '''Collect stats at this time point for a process and add them to its Procstat instance'''

    def sof(key,item):pstatobj[key].append(item)

    p=pstatobj.p

    sof('status',str(p.status))
    ioc=p.get_io_counters()
    sof('io_readbytes',ioc.read_bytes)
    sof('io_writebytes',ioc.write_bytes)


    ion=p.get_ionice()
    sof('io_nice_priority',ion.value)
    sof('io_nice_class',_iopmap[ion.ioclass])

    sof('nthreads',p.get_num_threads())
    sof('nfds',p.get_num_fds())
    ctx_switch = p.get_num_ctx_switches()
    sof('ctx_switches',ctx_switch.voluntary+ctx_switch.involuntary)
    sof('cpu_percent',p.get_cpu_percent(sample_interval))
    sof('cpu_affinity',len(p.get_cpu_affinity()))

    cpuspace = p.get_cpu_times()
    sof('cpu_user',cpuspace.user)
    sof('cpu_kernel',cpuspace.system)

    meminfo=p.get_memory_info()
    sof('rss',meminfo.rss)
    sof('vms',meminfo.vms)
    sof('mem_percent',p.get_memory_percent())
    sof('nchildren',len(p.get_children(recursive=True)))
    sof('nconnections',len(p.get_connections(kind='all')))

def print_matrix(m):
    for r in xrange(len(m)):
        print ','.join(m[r])

def matrix(proc_stat_objs,items,additional_data=[]):
    '''Convert data collected into a matrix readable by gnuplot'''

    accumulator = []
    nrows = get_num_rows(proc_stat_objs,additional_data)

    for k,ps in enumerate(proc_stat_objs):
        accumulator.append(list([k+1]*nrows)) #add xtics
        for i in items:
            accumulator.append(ps[i])
    for d in additional_data:
        accumulator.append(d)
    return matrix_from_lists(accumulator,nrows)

def matrix_from_lists(lists,nrows):
    '''Take lists and turn each list into a column in a matrix

    i.e if lists = [[1,2,3],[4,5],[7,8,9]]
    return [[1,4,7],[2,5,8],[3,'',9]]

    nrows = max number of datapoints of any list
    '''
    ncols = len(lists)
    m = []
    for i in xrange(nrows): #initialize matrix
        m.append(list(itertools.repeat('',len(lists))))

    for c in xrange(ncols):
        for r,item in enumerate(lists[c]):
            m[r][c] = str(item)

    return m

def get_num_rows(psobjs,additional=[]):
    '''Return the max number of rows this matrix should have

    numrows = maximum number of collected time points of any process'''

    maxd = get_max_num_sample_time(psobjs)

    for k in additional:
        maxd = max(maxd,len(k))
    return maxd

def write_matrix(data_matrix, data_file):
    '''write out a matrix into a csv gnu plot dat file'''

    data_file.seek(0)
    data_file.truncate()
    for r in data_matrix:
        data_file.write(','.join(r))
        data_file.write('\n')
    data_file.flush()
    os.fsync(data_file.fileno())

inst_file = NamedTemporaryFile() #gnuplot instructions
def create_chart(plot, img_filename, terminal):

    inst_file.seek(0)
    inst_file.truncate()
    inst_file.write('set terminal %s\n' % terminal)
    inst_file.write('set datafile separator ","\n')
    inst_file.write('set output "%s"\n'%img_filename)
    inst_file.write(str(plot))
    inst_file.flush()
    os.fsync(inst_file.fileno())

    print >> sys.stderr, 'Generating plot "%s"'%plot.title
    p = Popen(['gnuplot',inst_file.name], stdout = PIPE, stderr = PIPE)
    stdout, stderr = p.communicate()
    if p.returncode:
        raise PsmonException('Warning: gnuplot "%s" returned code %d\nstdout:%s\nstderr:%s'
                             %(plot.title,p.returncode, stdout, stderr))

def get_max_num_sample_time(proc_stat_objs):
    '''Return the maximum number of samples collected of any process'''
    return reduce(lambda last,p: max(last, len(p['sample_time'])), proc_stat_objs[1:],
                  len(proc_stat_objs[0]['sample_time']))

def get_max_cpu_affinity(proc_stat_objs):
    '''Return the maximum available cpus that any process at any point in time was allowed to use'''
    maxc = -1
    for p in proc_stat_objs:
        maxc = max(maxc, max(p['cpu_affinity']))
    return maxc

def create_ticks(proc_stat_objs):
    '''Create the tics used for axis'''

    pids = pid_list(proc_stat_objs)
    buf=['(']
    for i,v in enumerate(pids):
        buf.append('"%s" %d' % (v,i+1))
        if i != len(pids)-1:
            buf.append(', ')
    buf.append(')')
    return ''.join(buf)

def pid_list(proc_stat_objs):
    '''Return a list of pids derived from a list of proc stat objects'''
    return map(lambda p: p.pid, proc_stat_objs)

def create_systems_times_chart(sys_stats, data_file):
    mp = MultiPlot("2,1", 'System CPU Activity Times')
    st_col = 15 #Sample time column
    stats = ["user", "system", "idle", "nice", "io wait", "irq", "soft irq"]

    sys3d = mp.create_plot()
    sys3d.zlabel = '"Time\n (seconds)"'
    sys3d.xlabel = "'Activity'"
    sys3d.xrange = '[0:8] #number of cpu stats +-1'
    sys3d.ylabel = '"Sample Time (seconds)"'
    sys3d.xtics = '"user" 1, "system" 2, "idle" 3, "nice" 4, "io wait" 5, "irq" 6, "soft irq" 7)'
    sys3d.is_3d = True

    i = 1
    for stat in stats:
        sys3d.add_datapoint("'%s' using %d:%d:%d '%s' with linespoints" %
                            (data_file.name, i,st_col,i+1, stat))
        i += 2

    sys2d = mp.create_plot()
    sys2d.xlabel = '"Sample Time (seconds)'""
    sys2d.xrange = '[0:%d]' % sample_time_max
    sys2d.ylabel = '"Time Spent (seconds)"'
    sys2d.yrange = '[0:%d]' % sample_time_max
    sys2d.unset_xtics = True
    sys2d.set_xtics = True

    i = 2
    for stat in stats:
        sys2d.add_datapoint("'%s' using %d:%d '%s' with linespoints" %
                            (data_file.name, st_col, i, stat))
        i += 2

    #matrix dims are rows,cols = len(sys_stats['sample_time']), len(stats)*2+1
    sample_times = sys_stats.pop('sample_time')
    rows = len(sample_times)
    cols = len(stats) * 2 + 1
    m = []
    for r in xrange(rows):
        m.append(list(['']*cols))
        for c,stat in enumerate(sys_stats):
            m[r][c*2] = c+1 #system stat xtic
            stat_array = sys_stats[stat]
            if r < len(stat_array):
                m[r][c*2+1] = stat_array[r]
        m[r][c+2] = sample_times[r]

    sys_stats['sample_time'] = sample_times
    return mp,m

def create_process_status_chart(proc_stat_objs, data_file):
    mp = MultiPlot("2,1", 'Process Status Over Time')
    ticks = create_ticks(proc_stat_objs)

    pstat3d = mp.create_plot()
    pstat3d.xlabel = "'PID'"
    pstat3d.xrange = '[0:%d]' % (len(proc_stat_objs) + 1)
    pstat3d.xtics = ticks
    pstat3d.ylabel = '"Sample Time (seconds)"'
    pstat3d.ztics = '("running" 0, "sleeping" 1, "disk sleep" 2, "stopped" 3, "tracing stop" 4, "zombie" 5,\
           "dead" 6, "wake kill" 7, "waking" 8, "idle" 9, "locked" 10, "waiting" 11)'
    pstat3d.is_3d = True

    i = 1
    for p in proc_stat_objs:
        pstat3d.add_datapoint("'%s' using %d:%d:%d title '%s,%s' with step" %
                            (data_file.name, i,i+1,i+2, p.pid, p.name))
        i += 3

    pstat2d = mp.create_plot()
    pstat2d.xrange = '[0:%d]' % sample_time_max
    pstat2d.unset_xtics = True
    pstat2d.set_xtics = True
    pstat2d.ylabel = '"Status"'
    pstat2d.yrange = '[-.5:5.5]'
    pstat2d.ytics = '("running" 0, "sleeping" 1, "disk sleep" 2, "stopped" 3, "tracing stop" 4, "zombie" 5,\
           "dead" 6, "wake kill" 7, "waking" 8, "idle" 9, "locked" 10, "waiting" 11)'

    i = 2
    for p in proc_stat_objs:
        pstat2d.add_datapoint("'%s' using %d:%d title '%s,%s' with points" %
                            (data_file.name, i, i+1, p.pid, p.name))
        i += 3

    m = matrix(proc_stat_objs, ['sample_time', 'status'])
    return mp,m

def create_memory_chart(proc_stat_objs, data_file):
    mp = MultiPlot("2,2", 'Memory Utilization %')
    ticks = create_ticks(proc_stat_objs)
    
    mem_util3d = mp.create_plot()
    mem_util3d.title = "'Memory Utilization %'"
    mem_util3d.ylabel = '"Sample Time (second)"'
    mem_util3d.zlabel = '"Mem %" offset -1,0,0'
    mem_util3d.xlabel = "'PID'"
    mem_util3d.xrange = '[0:%d]' % (len(proc_stat_objs) + 1)
    mem_util3d.xtics = ticks
    mem_util3d.is_3d = True

    i = 1
    for p in proc_stat_objs:
        mem_util3d.add_datapoint("'%s' using %d:%d:%d title '%s,%s' with linespoints" %
                            (data_file.name, i,i+1,i+2, p.pid, p.name))
        i += 5
    
    mem_util2d = mp.create_plot()
    mem_util2d.title = "'Memory Utilization %'"
    mem_util2d.xlabel = "'Sample Time (seconds)'"
    mem_util2d.xrange = '[0:%d]' % (len(proc_stat_objs) + 1)
    mem_util2d.unset_xtics = True
    mem_util2d.set_xtics = True
    
    i = 2
    for p in proc_stat_objs:
        mem_util2d.add_datapoint("'%s' using %d:%d title '%s,%s' with linespoints" %
                            (data_file.name, i,i+1, p.pid, p.name))
        i += 5
        
    rss = mp.create_plot()
    rss.title = '"Memory RSS"'
    rss.ylabel = '"Sample Time (seconds)"'
    rss.zlabel = '"RSS\\n(bytes)" offset -2,0,0'
    rss.xlabel = "'PID'"
    rss.xrange = '[0:%d]' % (len(proc_stat_objs) + 1)
    rss.xtics = ticks
    rss.is_3d = True

    i = 1
    for p in proc_stat_objs:
        rss.add_datapoint("'%s' using %d:%d:%d title '%s,%s' with linespoints" %
                            (data_file.name, i,i+1,i+3, p.pid, p.name))
        i += 5

    vm = mp.create_plot()
    vm.title = '"Memory VM"'
    vm.zlabel = '"VM\\n(bytes)" offset -2,0,0'
    vm.is_3d = True

    i = 1
    for p in proc_stat_objs:
        vm.add_datapoint("'%s' using %d:%d:%d title '%s,%s' with linespoints" %
                            (data_file.name, i,i+1,i+4, p.pid, p.name))
        i += 5

    m = matrix(proc_stat_objs, ['sample_time', 'mem_percent', 'rss', 'vms'])
    return mp,m

def create_iorw_chart(proc_stat_objs, data_file):
    mp = MultiPlot("2,2", 'IO R/W Utilization')
    ticks = create_ticks(proc_stat_objs)

    iorw3d = mp.create_plot()
    iorw3d.title = '"IO Read/Write"'
    iorw3d.ylabel = '"Sample Time (seconds)"'
    iorw3d.zlabel = '"IO (Bytes)" offset -2,0,0'
    iorw3d.xlabel = "'PID'"
    iorw3d.xrange = "[0:%d]" % len(proc_stat_objs)
    iorw3d.xtics = ticks
    iorw3d.is_3d = True

    i = 1
    for p in proc_stat_objs:
        iorw3d.add_datapoint("'%s' using %d:%d:%d title '%s,%s,read' with linespoints" %
                            (data_file.name, i,i+1,i+2, p.pid, p.name))
        iorw3d.add_datapoint("'%s' using %d:%d:%d title '%s,%s,write' with linespoints" %
                            (data_file.name, i,i+1,i+3, p.pid, p.name))
        i += 6

    ionpc = mp.create_plot()
    ionpc.title = '"IO Nice Priority Class"'
    ionpc.ylabel = '"Priority Class"'
    ionpc.yrange = '[-.5:3.5]'
    ionpc.ytics = '("None" 0, "Real Time" 1,"Best Effort" 2,"Idle" 3)'
    ionpc.xlabel = "'Sample Time (seconds)'"
    ionpc.xrange = '[0:%d]' % sample_time_max
    ionpc.unset_xtics = True
    ionpc.set_xtics = True

    i = 2
    for p in proc_stat_objs:
        ionpc.add_datapoint("'%s' using %d:%d title '%s,%s' with steps" %
                            (data_file.name, i,i+3, p.pid, p.name))
        i += 6

    iorw2d = mp.create_plot()
    iorw2d.title =  '"IO Read/Write"'
    iorw2d.xlabel = "'Sample Time (seconds)'"
    iorw2d.ylabel = '"IO (Bytes)"'
    iorw2d.yrange = '[*:*]'
    iorw2d.unset_ytics = True
    iorw2d.set_ytics = True

    i = 2
    for p in proc_stat_objs:
        iorw2d.add_datapoint("'%s' using %d:%d title '%s,%s,read' with linespoints" %
                            (data_file.name, i,i+1, p.pid, p.name))
        iorw2d.add_datapoint("'%s' using %d:%d title '%s,%s,write' with linespoints" %
                            (data_file.name, i,i+2, p.pid, p.name))
        i += 6

    ionpl = mp.create_plot()
    ionpl.title =  '"IO Nice Priority Level"'
    ionpl.ylabel = '"Priority Level"'
    ionpl.yrange = '[-.5:7.5]'
    ionpl.xlabel = "'Sample Time (seconds)'"

    i = 2
    for p in proc_stat_objs:
        ionpl.add_datapoint("'%s' using %d:%d title '%s,%s' with steps" %
                            (data_file.name, i,i+4, p.pid, p.name))
        i += 6

    m = matrix(proc_stat_objs, ['sample_time', 'io_readbytes', 'io_writebytes', 'io_nice_class', 'io_nice_priority'])
    return mp,m

def create_cpu_util_chart(proc_stat_objs, data_file):
    '''create the cpu utilization chart
    maps cpu utilization across processes and system time, kernel/user time
    and cpu affinity

    see plots/cpu* for a reference gnuplot, picture and demo data
    '''

    mp = MultiPlot("3,2",'CPU Utilization')
    ticks = create_ticks(proc_stat_objs)

    #create 3d cpu utilization plot

    cpu3d = mp.create_plot()
    cpu3d.title = '"CPU % Utilization"'
    cpu3d.zlabel = '"CPU %" offset -1,0,0'
    cpu3d.xlabel = "'PID'"
    cpu3d.ylabel = "'Sample Time (seconds)'"
    cpu3d.xrange = '[0:%d] # number of pids +1' % len(proc_stat_objs)
    cpu3d.xtics = ticks

    cpu3d.is_3d = True
    i = 1
    for ps in proc_stat_objs:
        cpu3d.add_datapoint("'%s' using %d:%d:%d title '%s,%s' with linespoints" %
                            (data_file.name, i,i+1,i+2, ps.pid, ps.name))
        i+=6

    #create 2d cpu utilization plot

    cpu2d = mp.create_plot()
    cpu2d.title = '"CPU % Utilization"'
    cpu2d.xlabel = "'Sample Time (seconds)'"
    cpu2d.xrange = "[0:%d] #Set time -+ small amount" % sample_time_max
    cpu2d.ylabel = '"CPU %"'
    cpu2d.yrange = '[*:*]'
    cpu2d.unset_xtics = True
    cpu2d.set_xtics = True

    i = 2
    for ps in proc_stat_objs:
        cpu2d.add_datapoint("'%s' using %d:%d title '%s,%s' with linespoints" %
                            (data_file.name, i,i+1, ps.pid, ps.name))
        i+=6

    #create 3d kernel/user time plot

    ku3d = mp.create_plot()
    ku3d.title = '"CPU User/Kernel Time"'
    ku3d.ylabel = "'Sample Time (seconds)'"
    ku3d.zlabel = '"Time\\n(seconds)" offset -2,0,0'
    ku3d.xlabel = "'PID'"
    ku3d.xrange = '[0:%d] # number of pids +-1' % len(proc_stat_objs)
    ku3d.xtics = ticks
    ku3d.is_3d = True

    i = 1
    for ps in proc_stat_objs:
        ku3d.add_datapoint("'%s' using %d:%d:%d title '%s,%s,user' with linespoints" %
                            (data_file.name, i,i+1,i+4, ps.pid, ps.name))
        ku3d.add_datapoint("'%s' using %d:%d:%d title '%s,%s,kernel' with linespoints" %
                            (data_file.name, i,i+1,i+5, ps.pid, ps.name))
        i+=6

    #create 2d kernel/user timeplot

    ku2d = mp.create_plot()
    ku2d.title = '"CPU User/Kernel Time"'
    ku2d.xlabel = "'Sample Time (seconds)'"
    ku2d.xrange = "[0:%d] #Set time -+ small amount" % sample_time_max
    ku2d.ylabel = '"Time\\n(seconds)"'
    ku2d.yrange = '[*:*]'
    ku2d.unset_xtics = True
    ku2d.set_xtics = True

    i = 2
    for ps in proc_stat_objs:
        ku2d.add_datapoint("'%s' using %d:%d title '%s,%s,user' with linespoints" %
                            (data_file.name, i,i+3, ps.pid, ps.name))
        ku2d.add_datapoint("'%s' using %d:%d title '%s,%s,kernel' with linespoints" %
                            (data_file.name, i,i+4, ps.pid, ps.name))
        i+=6

    #create cpu allowance plot
    allowed_cpu = mp.create_plot()
    allowed_cpu.title = '"Allowed number of CPUs"'
    allowed_cpu.ylabel = '"Number of CPUs"'
    max_cpus = get_max_cpu_affinity(proc_stat_objs)
    if max_cpus == 0:
        allowed_cpu.yrange = '[0:0]'
    else:
        allowed_cpu.yrange = '[.5:%f] #num cpus +.5' % (max_cpus + .5)

    i = 2
    for ps in proc_stat_objs:
        allowed_cpu.add_datapoint("'%s' using %d:%d title '%s,%s' with linespoints"%
                                  (data_file.name, i, i+2, ps.pid, ps.name))
        i+=6

    m = matrix(proc_stat_objs, ['sample_time', 'cpu_percent', 'cpu_affinity', 'cpu_user', 'cpu_kernel'])
    return mp,m

def create_charts(proc_stat_objs):
    '''Create gnuplots out of collected stats'''

    data_file_list = []
    generated_plots = []
    for chart in [create_cpu_util_chart]:
        df = NamedTemporaryFile() #file will hold data to plot
        multiplot, data_matrix = chart(proc_stat_objs, df)
        generated_plots.append(multiplot)
        write_matrix(df, data_matrix)
        data_file_list.append(df)

    combined_mp = MultiPlot()
    combined_mp.title = "Process stats"
    for mp in generated_plots:
        for p in mp.plots:
            combined_mp.append(p)
    if len(combined_mp.plots) % 2 != 0:
        rows = len(combined_mp.plots)+1
    else:
        rows = len(combined_mp.plots)
    combined_mp.layout = str(rows)+',2'

    global sample_time_max
    #set the maximum value for the sample time axis
    sample_time_max =  get_max_num_sample_time(proc_stat_objs)
    #add 5% to the xrange or 1 sec
    sample_time_max = max(1,sample_time_max * .05) + sample_time_max

    create_chart(combined_mp, 'mega.png','png size 2048')


def end(signum,frame):
    '''Handle termination. Write out collected stats and/or create charts'''

    if signum in pscommon.signal_map:
        print >> sys.stderr, 'Caught signal %s' % pscommon.signal_map[signum]

    print >> sys.stderr, 'Writing captured info...'
    elapsed_time = time.time() - _stime
    _file.write('Elapsed time: %s' % elapsed_time)

    procs = _proc_list+_dead_proc_list
    for ps in procs:
        _file.write('pid:%s cmd:%s\n'%(ps.pid,ps.name))
        for k in sorted(ps.statmap):
            _file.write(k+':'+','.join(map(lambda v : str(v), ps.statmap[k])))
            _file.write('\n')
        _file.write('\n')

    for k in sorted(_sys_stats):
        _file.write(k+':'+','.join(map(lambda v : str(v), _sys_stats[k])))
        _file.write('\n')
    _file.write('\n')

    print >> sys.stderr, 'Done.'

    if not options['stats_only']:
        create_charts(procs,elapsed_time)

    sys.exit(0)

def argparser():
    from optparse import OptionParser
    parser = OptionParser('usage: %prog [options] pid')

    parser.add_option("--file", action='store',
                       help='Output stats file. Default goes to STDOUT.')
    parser.add_option("--seconds", action='store',default=0,type='int',
                       help='Collect data for X seconds. Default (0 seconds) runs forever.')
    parser.add_option('--stats-only',action='store_true',default=False,
                      help='Dump stats only. Do not create charts. Default false.')
    parser.add_option('--chart-dir',action='store',
                      help='Directory to store charts. Created if it DNE. Default cwd.' )
    parser.add_option('--suppress-output',action='store_true',default=False,
                      help='Suppress displaying statistic outputs to STDOUT.')
    return parser



if __name__ == '__main__':

    global options

    parser=argparser()
    options,args=parser.parse_args()

    if len(args) == 0:
        parser.print_help()
        sys.exit(0)

    if len(args) != 1:
        parser.print_usage()
        sys.exit(1)

    options=vars(options)

    try:
        pid = int(args[0])
        if pid < 0: raise ValueError
    except ValueError:
        print >> sys.stderr, 'pid must be a positive int'
        sys.exit(1)

    global _file
    if options['file']:
        _file = open(options['file'],'w')
    else:
        _file = sys.stdout

    if options['suppress_output'] and _file is sys.stdout:
        _file = open('/dev/null','w')

    chartpath = options['chart_dir']
    if chartpath and options['stats_only']:
        print >> sys.stderr, 'Mixing --stats-only and --chart-dir'
        sys.exit(1)

    if chartpath:
        chartpath = os.path.expanduser(chartpath)
        if os.path.exists(chartpath):
            if os.path.isdir(chartpath):
                if not os.access(chartpath, os.X_OK | os.W_OK ):
                    raise os.error('Cannot write to dir: ' + chartpath)
            else:
                raise os.error('%s is not a directory.' % chartpath)
        else: os.mkdir(chartpath)
    else:
        chartpath = os.getcwd()

    sec = options['seconds']
    if sec < 0:
        print >> sys.stderr, 'seconds to run must be a positive int'
        sys.exit(1)

    global _proc_list
    global _dead_proc_list
    _dead_proc_list = []
    _proc_list=[Procstat(psutil.Process(pid))]
    root_proc=_proc_list[0].p
    alive_pids=set()
    alive_pids.add(root_proc.pid)

    signal.signal(signal.SIGTERM,end)
    signal.signal(signal.SIGINT,end)
    signal.signal(signal.SIGQUIT,end)
    signal.signal(signal.SIGALRM,end)
    signal.alarm(sec) #if sec==0, the alarm is not set

    global _stime
    _stime=time.time()

    #begin collecting stats here.
    #the following takes into account recycled pids

    while True:
        #get stats for all spawned processes starting at the root process
        #this must be done on each timing iteration in case new processes have
        #been spawned
        try:
            children=root_proc.get_children(recursive=True)
        except psutil.NoSuchProcess:
            end(-1,0) #root proc dead,stop tracking.
        for c in children:
            if not c.pid in alive_pids:
                #print >> sys.stderr, 'adding pid %d' % c.pid #debug
                _proc_list.append(Procstat(c))
                alive_pids.add(c.pid)

        #Collect system stats in a different structure
        ct=psutil.cpu_times()
        _sys_stats['sample_time'].append(time.time()-_stime)
        for i in cpu_time_modes:
            _sys_stats[i].append(ct.__getattribute__(i.partition('system_cpu_')[2]))
        _sys_stats['system_cpu_percent'].append(psutil.cpu_percent(sample_interval))

        temp_dead_list=[]
        for pstatobj in _proc_list:
            try:
                pstatobj.statmap['sample_time'].append(time.time()-_stime)
                get_stats(pstatobj) #populate pstat objects
            except psutil.NoSuchProcess:
                temp_dead_list.append(pstatobj)

        #stop tracking dead process and allow for tracking of processes with recycled pids
        for dead in temp_dead_list:
            _proc_list.remove(dead)
            alive_pids.remove(dead.p.pid)
            #print >> sys.stderr, 'adding pid %d to dead procs' % c.pid #debug
            _dead_proc_list.append(dead)

