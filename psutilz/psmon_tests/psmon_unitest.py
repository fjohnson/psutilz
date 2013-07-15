__author__ = 'fjohnson'

import unittest
import difflib
import psutilz
from psutilz.psmon import Procstat, create_cpu_util_chart, matrix, create_chart, write_matrix, get_max_num_sample_time,\
    create_iorw_chart, create_memory_chart, create_process_status_chart

from tempfile import NamedTemporaryFile

class MatrixTests(unittest.TestCase):
    '''Tests for determining if data matrix are being created correctly from Procstat instances'''

    def test_matrix_create(self):
        '''simple instance'''

        def dummyobj():pass
        dummyobj.pid=0
        dummyobj.name=0
        p1 = Procstat(dummyobj)
        p1['cpu_percent']=[10,20,30]
        p1['cpu_user']=[100,200,300]
        p1['sample_time']=[1,2,3]
        p2 = Procstat(dummyobj)
        p2['cpu_percent']=[40,50,60]
        p2['cpu_user']=[400,500,600]
        p2['sample_time']=[4,5,6]
        d=[[7,8,9],[70,80,90]]
        m=matrix([p1,p2],('sample_time','cpu_user','cpu_percent'),d)
        assert m == [['1', '1', '100', '10', '2', '4', '400', '40', '7', '70'],
                     ['1', '2', '200', '20', '2', '5', '500', '50', '8', '80'],
                     ['1', '3', '300', '30', '2', '6', '600', '60', '9', '90']], m

    def test_matrix_create2(self):
        '''Instance where a certain column has missing data.
        This would happen for instance if a process died before stats could be gathered'''

        def dummyobj():pass
        dummyobj.pid=0
        dummyobj.name=0
        p1 = Procstat(dummyobj)
        p1['cpu_percent']=[10,20,30]
        p1['cpu_user']=[100,200]
        p1['sample_time']=[1,2,3]
        p2 = Procstat(dummyobj)
        p2['cpu_percent']=[40,50]
        p2['cpu_user']=[400,500]
        p2['sample_time']=[4,5]
        d=[[7,8,9],[70]]
        m=matrix([p1,p2],('sample_time','cpu_user','cpu_percent'),d)
        assert m == [['1', '1', '100', '10', '2', '4', '400', '40', '7', '70'],
                     ['1', '2', '200', '20', '2', '5', '500', '50', '8', ''],
                     ['1', '3',    '', '30', '2',  '',    '',   '', '9', '']],m


class ChartCreationTests(unittest.TestCase):

    class processp:
            def __init__(self, pid, name):
                self.pid = pid
                self.name = name

    def setUp(self):
        self.datamatrix_file = NamedTemporaryFile()

    def tearDown(self):
        self.datamatrix_file.close()

    def test_system_times_chart(self):
        stats = ["user", "system", "idle", "nice", "io wait", "irq", "soft irq", "sample_time"]
        statsm = [[i+1]*4 for i in xrange(len(stats)-1)]
        statsm.append([1,2,3,4])
        sys_stats = dict(zip(stats,statsm))
        assert False

    def test_process_status(self):
        p1 = Procstat(ChartCreationTests.processp(1,'example1'))
        p2 = Procstat(ChartCreationTests.processp(2,'example2'))

        p1.statmap['sample_time'] = [1,2,3]
        p1.statmap['status'] = [3,3,4]

        p2.statmap['sample_time'] = [1,2,3]
        p2.statmap['status'] = [2,2,5]

        sample_time_max =  get_max_num_sample_time([p1,p2])
        psutilz.psmon.sample_time_max = max(1,sample_time_max * .05) + sample_time_max
        mp, m = create_process_status_chart([p1,p2], self.datamatrix_file)
        assert m == [['1', '1', '3', '2', '1', '2'],
                     ['1', '2', '3', '2', '2', '2'],
                     ['1', '3', '4', '2', '3', '5']], m
        diff = ''.join(difflib.unified_diff(str(mp).split(),
'''set multiplot layout 2,1

set title "Process Status Over Time"

set ylabel "Sample Time (seconds)"
set xlabel 'PID'
set xrange [0:3]
set ztics ("running" 0, "sleeping" 1, "disk sleep" 2, "stopped" 3, "tracing stop" 4, "zombie" 5,           "dead" 6, "wake kill" 7, "waking" 8, "idle" 9, "locked" 10, "waiting" 11)
set xtics ("1" 1, "2" 2)
splot \\
'dummy' using 1:2:3 title '1,example1' with step,\\
'dummy' using 4:5:6 title '2,example2' with step

set ylabel "Status"
set yrange [-.5:5.5]
set xrange [0:4]
set ytics ("running" 0, "sleeping" 1, "disk sleep" 2, "stopped" 3, "tracing stop" 4, "zombie" 5,           "dead" 6, "wake kill" 7, "waking" 8, "idle" 9, "locked" 10, "waiting" 11)
unset xtics
set xtics
plot \\
'dummy' using 2:3 title '1,example1' with points,\\
'dummy' using 5:6 title '2,example2' with points'''
.replace('dummy', self.datamatrix_file.name).split()))
        assert not diff, diff

        write_matrix(m, self.datamatrix_file)
        create_chart(mp,'/tmp/procstat.svg', 'svg size 1024,1536 mouse standalone')

    def test_mem_chart(self):
        p1 = Procstat(ChartCreationTests.processp(1,'example1'))
        p2 = Procstat(ChartCreationTests.processp(2,'example2'))
        p3 = Procstat(ChartCreationTests.processp(3,'example3'))

        p1.statmap['sample_time'] = [1,2,3]
        p1.statmap['mem_percent'] = [30,40,50]
        p1.statmap['rss'] = [800,880,700]
        p1.statmap['vms'] = [900,990,980]

        p2.statmap['sample_time'] = [1,2,3]
        p2.statmap['mem_percent'] = [15,8,21]
        p2.statmap['rss'] = [400,443,200]
        p2.statmap['vms'] = [800,890,890]

        p3.statmap['sample_time'] = [1,2,3]
        p3.statmap['mem_percent'] = [21,24,23]
        p3.statmap['rss'] = [300,400,450]
        p3.statmap['vms'] = [500,500,500]

        sample_time_max =  get_max_num_sample_time([p1,p2,p3])
        psutilz.psmon.sample_time_max = max(1,sample_time_max * .05) + sample_time_max
        mp, m = create_memory_chart([p1,p2, p3], self.datamatrix_file)
        assert m == [['1', '1', '30', '800', '900', '2', '1', '15', '400', '800', '3', '1', '21', '300', '500'],
                     ['1', '2', '40', '880', '990', '2', '2', '8',  '443', '890', '3', '2', '24', '400', '500'],
                     ['1', '3', '50', '700', '980', '2', '3', '21', '200', '890', '3', '3', '23', '450', '500']], m
        diff = ''.join(difflib.unified_diff(str(mp).split(),
'''
set multiplot layout 2,2

set title "Memory Utilization %"

set zlabel "Mem %" offset -1,0,0
set ylabel "Sample Time (seconds)"
set xlabel 'PID'
set xrange [0:4]
set xtics ("1" 1, "2" 2, "3" 3)
set title 'Memory Utilization %'
splot \\
'dummy' using 1:2:3 title '1,example1' with linespoints,\\
'dummy' using 6:7:8 title '2,example2' with linespoints,\\
'dummy' using 11:12:13 title '3,example3' with linespoints

set xlabel 'Sample Time (seconds)'
set xrange [0:4]
set title 'Memory Utilization %'
unset xtics
set xtics
plot \\
'dummy' using 2:3 title '1,example1' with linespoints,\\
'dummy' using 7:8 title '2,example2' with linespoints,\\
'dummy' using 12:13 title '3,example3' with linespoints

set zlabel "RSS\\n(bytes)" offset -2,0,0
set ylabel "Sample Time (seconds)"
set xlabel 'PID'
set xrange [0:4]
set xtics ("1" 1, "2" 2, "3" 3)
set title "Memory RSS"
splot \\
'dummy' using 1:2:4 title '1,example1' with linespoints,\\
'dummy' using 6:7:9 title '2,example2' with linespoints,\\
'dummy' using 11:12:14 title '3,example3' with linespoints

set zlabel "VM\\n(bytes)" offset -2,0,0
set title "Memory VM"
splot \\
'dummy' using 1:2:5 title '1,example1' with linespoints,\\
'dummy' using 6:7:10 title '2,example2' with linespoints,\\
'dummy' using 11:12:15 title '3,example3' with linespoints'''
.replace('dummy', self.datamatrix_file.name).split()))

        assert not diff, diff

        write_matrix(m, self.datamatrix_file)
        create_chart(mp,'/tmp/memchart.svg', 'svg size 2048,1536 mouse standalone')
        
    def test_io_chart(self):
        p1 = Procstat(ChartCreationTests.processp(1,'example1'))
        p2 = Procstat(ChartCreationTests.processp(2,'example2'))

        p1.statmap['sample_time'] = [1,2,3]
        p1.statmap['io_readbytes'] = [200,300,400]
        p1.statmap['io_writebytes'] = [416,765,800]
        p1.statmap['io_nice_class'] = [0,3,3]
        p1.statmap['io_nice_priority'] = [2,6,1]

        p2.statmap['sample_time'] = [1,2,3]
        p2.statmap['io_readbytes'] = [100,150,390]
        p2.statmap['io_writebytes'] = [215,750]
        p2.statmap['io_nice_class'] = [1,2]
        p2.statmap['io_nice_priority'] = [3,5]

        sample_time_max =  get_max_num_sample_time([p1,p2])
        psutilz.psmon.sample_time_max = max(1,sample_time_max * .05) + sample_time_max
        mp, m = create_iorw_chart([p1,p2], self.datamatrix_file)
        assert m == [['1', '1', '200', '416', '0', '2', '2', '1', '100', '215', '1', '3'],
                     ['1', '2', '300', '765', '3', '6', '2', '2', '150', '750', '2', '5'],
                     ['1', '3', '400', '800', '3', '1', '2', '3', '390', '', '', '']], m
        #open('/tmp/out','w').write(str(mp))
        diff = ''.join(difflib.unified_diff(str(mp).split(),
'''
set multiplot layout 2,2

set title "IO R/W Utilization"

set zlabel "IO (Bytes)" offset -2,0,0
set ylabel "Sample Time (seconds)"
set xlabel 'PID'
set xrange [0:2]
set xtics ("1" 1, "2" 2)
set title "IO Read/Write"
splot \\
'dummy' using 1:2:3 title '1,example1,read' with linespoints,\\
'dummy' using 1:2:4 title '1,example1,write' with linespoints,\\
'dummy' using 7:8:9 title '2,example2,read' with linespoints,\\
'dummy' using 7:8:10 title '2,example2,write' with linespoints

set ylabel "Priority Class"
set xlabel 'Sample Time (seconds)'
set yrange [-.5:3.5]
set xrange [0:4]
set ytics ("None" 0, "Real Time" 1,"Best Effort" 2,"Idle" 3)
set title "IO Nice Priority Class"
unset xtics
set xtics
plot \\
'dummy' using 2:5 title '1,example1' with steps,\\
'dummy' using 8:11 title '2,example2' with steps

set ylabel "IO (Bytes)"
set xlabel 'Sample Time (seconds)'
set yrange [*:*]
set title "IO Read/Write"
unset ytics
set ytics
plot \\
'dummy' using 2:3 title '1,example1,read' with linespoints,\\
'dummy' using 2:4 title '1,example1,write' with linespoints,\\
'dummy' using 8:9 title '2,example2,read' with linespoints,\\
'dummy' using 8:10 title '2,example2,write' with linespoints

set ylabel "Priority Level"
set xlabel 'Sample Time (seconds)'
set yrange [-.5:7.5]
set title "IO Nice Priority Level"
plot \\
'dummy' using 2:6 title '1,example1' with steps,\\
'dummy' using 8:12 title '2,example2' with steps'''
.replace('dummy', self.datamatrix_file.name).split()))
        assert not diff, diff

        write_matrix(m, self.datamatrix_file)
        create_chart(mp,'/tmp/iochart.svg', 'svg size 2048,1300 mouse standalone')

    def test_cpu_chart(self):
        '''cpu chart creation test'''


        p1 = Procstat(ChartCreationTests.processp(1,'example1'))
        p2 = Procstat(ChartCreationTests.processp(2,'example2'))
        p3 = Procstat(ChartCreationTests.processp(3,'example3'))
        p1.statmap['sample_time'] = [1,2,3]
        p1.statmap['cpu_percent'] = [30]
        p1.statmap['cpu_affinity'] = [4,4,4]
        p1.statmap['cpu_user'] = [50,55,60]
        p1.statmap['cpu_kernel'] = [60,65,70]

        p2.statmap['sample_time'] = [1,2,3]
        p2.statmap['cpu_percent'] = [15,7,12]
        p2.statmap['cpu_affinity'] = [3,4,4]
        p2.statmap['cpu_user'] = [60,65,78]
        p2.statmap['cpu_kernel'] = [78,89,105]

        p3.statmap['sample_time'] = [1,2,3]
        p3.statmap['cpu_percent'] = [16, 89, 88]
        p3.statmap['cpu_affinity'] = [3,3,3]
        p3.statmap['cpu_user'] = [23,54,70]
        p3.statmap['cpu_kernel'] = [43,65,65]

        sample_time_max = get_max_num_sample_time([p1,p2,p3])
        psutilz.psmon.sample_time_max = max(1,sample_time_max * .05) + sample_time_max
        mp, m = create_cpu_util_chart([p1,p2,p3], self.datamatrix_file)
        assert m == [['1', '1', '30', '4', '50', '60', '2', '1', '15', '3', '60', '78', '3', '1', '16', '3', '23', '43'],
                     ['1', '2', '',   '4', '55', '65', '2', '2', '7',  '4', '65', '89', '3', '2', '89', '3', '54', '65'],
                     ['1', '3', '',   '4', '60', '70', '2', '3', '12', '4', '78', '105','3', '3', '88', '3', '70', '65']], m
        #open('/tmp/out','w').write(str(mp))
        diff = ''.join(difflib.unified_diff(str(mp).split(),
'''
set multiplot layout 3,2

set title "CPU Utilization"

set zlabel "CPU %" offset -1,0,0
set ylabel 'Sample Time (seconds)'
set xlabel 'PID'
set xrange [0:3] # number of pids +1
set xtics ("1" 1, "2" 2, "3" 3)
set title "CPU % Utilization"
splot \\
'dummy' using 1:2:3 title '1,example1' with linespoints,\\
'dummy' using 7:8:9 title '2,example2' with linespoints,\\
'dummy' using 13:14:15 title '3,example3' with linespoints

set ylabel "CPU %"
set xlabel 'Sample Time (seconds)'
set yrange [*:*]
set xrange [0:4] #Set time -+ small amount
set title "CPU % Utilization"
unset xtics
set xtics
plot \\
'dummy' using 2:3 title '1,example1' with linespoints,\\
'dummy' using 8:9 title '2,example2' with linespoints,\\
'dummy' using 14:15 title '3,example3' with linespoints

set zlabel "Time\\n(seconds)" offset -2,0,0
set ylabel 'Sample Time (seconds)'
set xlabel 'PID'
set xrange [0:3] # number of pids +-1
set xtics ("1" 1, "2" 2, "3" 3)
set title "CPU User/Kernel Time"
splot \\
'dummy' using 1:2:5 title '1,example1,user' with linespoints,\\
'dummy' using 1:2:6 title '1,example1,kernel' with linespoints,\\
'dummy' using 7:8:11 title '2,example2,user' with linespoints,\\
'dummy' using 7:8:12 title '2,example2,kernel' with linespoints,\\
'dummy' using 13:14:17 title '3,example3,user' with linespoints,\\
'dummy' using 13:14:18 title '3,example3,kernel' with linespoints

set ylabel "Time\\n(seconds)"
set xlabel 'Sample Time (seconds)'
set yrange [*:*]
set xrange [0:4] #Set time -+ small amount
set title "CPU User/Kernel Time"
unset xtics
set xtics
plot \\
'dummy' using 2:5 title '1,example1,user' with linespoints,\\
'dummy' using 2:6 title '1,example1,kernel' with linespoints,\\
'dummy' using 8:11 title '2,example2,user' with linespoints,\\
'dummy' using 8:12 title '2,example2,kernel' with linespoints,\\
'dummy' using 14:17 title '3,example3,user' with linespoints,\\
'dummy' using 14:18 title '3,example3,kernel' with linespoints

set ylabel "Number of CPUs"
set yrange [.5:4.500000] #num cpus +.5
set title "Allowed number of CPUs"
plot \\
'dummy' using 2:4 title '1,example1' with linespoints,\\
'dummy' using 8:10 title '2,example2' with linespoints,\\
'dummy' using 14:16 title '3,example3' with linespoints'''
.replace('dummy', self.datamatrix_file.name).split()))
        assert not diff, diff

        write_matrix(m, self.datamatrix_file)
        create_chart(mp,'/tmp/cpuchart.svg', 'svg size 2048,1300 mouse standalone')


if __name__ == '__main__':
    unittest.main()
