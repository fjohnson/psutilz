__author__ = 'fjohnson'

import unittest
from psutilz.psmon import Procstat, create_cpu_util_chart

class ChartCreationTests(unittest.TestCase):
    def test_cpu_chart(self):
        class processp:
            pid = '1'
            name = '2'
        p1 = Procstat(processp())
        p2 = Procstat(processp())
        p3 = Procstat(processp())
        p1.statmap['sample_time'] = [1,2,3]
        p1.statmap['cpu_percent'] = [30, 45, 43]
        p1.statmap['cpu_affinity'] = [4,4,4]
        p1.statmap['cpu_user'] = [50,55,60]
        p1.statmap['cpu_kernel'] = [60,65,70]

        p1.statmap['sample_time'] = [1,2,3]
        p1.statmap['cpu_percent'] = [15,7,12]
        p1.statmap['cpu_affinity'] = [3,4,4]
        p1.statmap['cpu_user'] = [60,65,78]
        p1.statmap['cpu_kernel'] = [78,89,105]

        p1.statmap['sample_time'] = [1,2,3]
        p1.statmap['cpu_percent'] = [16, 89, 88]
        p1.statmap['cpu_affinity'] = [3,3,3]
        p1.statmap['cpu_user'] = [23,54,70]
        p1.statmap['cpu_kernel'] = [43,65,65]

        def dummy():pass
        dummy.name ='dummy'
        mp, m = create_cpu_util_chart([p1,p2,p3], dummy)
        assert False, str(mp)



if __name__ == '__main__':
    unittest.main()
