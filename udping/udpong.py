#!/usr/bin/env python

from optparse import OptionParser
from time import sleep, time
import re
import os
from sys import stdout

from mininet.log import lg, setLogLevel, info, warn, output
from mininet.net import Mininet, init
from mininet.node import OVSKernelSwitch, Host, Controller
from mininet.test.microbenchmarks.CPUIsolationLib import sanityCheck
from mininet.test.microbenchmarks.CPUIsolationLib import intListCallback
#from mininet.test.microbenchmarks.CPUIsolationLib import initOutput
from mininet.test.microbenchmarks.CPUIsolationLib import parse_cpuacct
#from mininet.test.microbenchmarks.CPUIsolationLib import appendOutput
from mininet.util import getCmd, quietRun, numCores
from mininet.topo import Topo, Node, Edge


def parseOptions():
    "Parse command line options"
    parser = OptionParser()
    parser.add_option( '-o', '--outdir', dest='outdir',
        default='', help='write output to dir' )
    parser.add_option( '-c', '--counts', dest='counts',
        action='callback', callback=intListCallback, default=[ 2 ],
        type='string', help='specify node counts, e.g. 10,20,40' )
    parser.add_option( '-n', '--nonamespace', dest='nonamespace',
                      default=False, action='store_true',
                      help='don\'t run hosts in namespace' )
    parser.add_option( '-s', '--static', dest='static',
                      default=False, action='store_true',
                      help='statically allocate CPU to each host' )
    parser.add_option( '-b', '--bwcpu', dest='sched',
                      default='cfs', type='string',
                      help='CPU bandwidth limiting=cfs|rt|none' )
    parser.add_option( '-i', '--interval', dest='interval',
        type='float', default=0.0, help='time interval between successive pings' )
    parser.add_option ('-l', '--loaded', dest='loaded',
                       default=False, action='store_true',
                       help='also run cpu stress processes on client and server' )
    parser.add_option('-p', '--pings', dest='pings',
                      default=1000, type='int',
                      help='number of pings')
    parser.add_option('-e', '--period', dest='period',
                      default=100000, type='int',
                      help='enforcement period (us) for CPU bandwidth limiting')
    ( options, args ) = parser.parse_args()
    return options, args

class PingPongTopo(Topo):

    def __init__( self, N, cpu=0.2, in_namespace=True):
        '''Constructor'''

        # Add default members to class.
        super( PingPongTopo, self ).__init__()
        self.template_host = Node(is_switch=False, cpu=cpu, in_namespace=in_namespace)

        # Create host nodes
        hosts = [str(i) for i in range(1, N+1)]
        for h in hosts:
            self.add_node(h, self.template_host)

        self.add_edge(str(1), str(2), Edge())

        # Consider all switches and hosts 'on'
        self.enable_all()

def custom(Class, **params):
    "Returns a custom object factory"
    def factory(*args, **kwargs):
        kwargs.update(**params)
        return Class(*args, **kwargs)
    return factory

def pingpongtest(opts):
    "UDP ping latency test"
    cpustress = 'cpu/cpu-stress'
    cpumonitor = 'cpu/cpumonitor'
    udping = '../nsdi/udp-ping/udping'
    results = []
    #initOutput( opts.outfile, opts )
    if opts.outdir and not os.path.exists(opts.outdir):
        os.makedirs(opts.outdir)

    info('*** killing off any cpu stress processes\n')
    quietRun('pkill -9 %s > /dev/null' % cpustress)
    print quietRun('pgrep cpu')

    info( "*** running ping test" )
    opts.time = opts.pings
    numprocs = numCores()
    for n in opts.counts:
        opts.cpu = 0.5 / n
        net = Mininet(topo=PingPongTopo(n, 
            cpu=opts.cpu, 
            in_namespace=(not opts.nonamespace)), 
            switch=OVSKernelSwitch,
            host=custom(Host, sched=opts.sched, period_us=opts.period),
            setStaticCPU=opts.static)
        net.start()

        info('*** Starting cpu stress processes\n')
        result = [''] * n
        cmd = [None] * n*numprocs
        # For the "loaded" configuration we run stress procs everywhere;
        # Otherwise they don't run on the udping client or server
        start = 1 if opts.loaded else 3
        for i in xrange(start, n+1):
            server = net.getNodeByName(str(i))
            scmd = cpustress
            for j in range(numprocs):
                # was:  cmd[i*numprocs + j] = server.lxcSendCmd(scmd)
                server.cmd( scmd + '&' )
            info('.')
        info('\n')

        # info('*** Waiting 10 seconds for cpu stress processes to stabilize\n')
        # sleep(10)

        info('*** Checking connectivity and creating OpenFlow route\n')
        h1 = net.getNodeByName(str(1))
        h2 = net.getNodeByName(str(2))
        h1.cmd('ping -nc%d %s' % (1, h2.IP()))

        info('*** Starting udping server and waiting 5 seconds\n')
        h2.cmd('%s > /dev/null &' % udping)
        sleep(5)

        info('*** Running udping client for %s pings\n' % opts.pings)
        start = time()
        pout = h1.cmd('%s %s %s' % (udping, h2.IP(), opts.pings))
        end = time()
        if opts.outdir:
            f = open( '%s/u-%d' % (opts.outdir, n), 'w' )
            print >>f, pout
            f.close()
        elapsed = end - start

        # Compute average ping latency and overall average ping time
        values = [float(s) for s in pout.splitlines()]
        avgnetms = sum(values)/len(values) * 1000.0
        info( '*** Average per-ping latency %.3f ms\n' % avgnetms )
        info('*** %s pings completed in %.3f seconds\n' % (opts.pings, elapsed ) )
        avgms  = (elapsed/opts.pings * 1000.0)
        info( '*** Average ping time overall: %.3f ms\n' % avgms )
        info('*** Killing cpu stress processes and udping server')
        print quietRun( 'pkill -9 ' + cpustress )
        print quietRun( 'pkill -9 udping' )

        net.stop()

if __name__ == '__main__':
    init()
    setLogLevel( 'info' )
    opts, args = parseOptions()
    sanityCheck()
    pingpongtest(opts)
