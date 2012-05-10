#!/usr/bin/python

"""
Link bandwidth isolation test.
"""

import sys
flush = sys.stdout.flush
from time import sleep

from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.util import custom
from mininet.log import lg
from InterNodeTopo import *
from IntraNodeTopo import *
from Parser import *

bmarkToTopo = {'inter':(lambda n: InterNodeTopo(n)), 'intra':(lambda n: IntraNodeTopo(n))}

def BWIsolation(bmark, N, runs):

    "Check bandwidth isolation for various topology sizes."

    cliout = [''] * N
    iperf = 'iperf'
    topo = bmarkToTopo[bmark](N)
    host = custom(CPULimitedHost, cpu=.2)
    link = custom(TCLink, bw=100)
    net = Mininet(topo=topo, host=host, link=link, autoSetMacs=True)
    net.start()

    for _ in range(0, runs):
        result = [''] * N
        servercmd = [None] * N
        clientcmd = [None] * N

        #start the servers
        for n in range(0, N):
            server = net.hosts[2*n + 1]
            scmd = iperf + ' -yc -s'
            servercmd[n] = server.popen(scmd)

        sleep(1)
        
        #start the clients
        for n in range(0, N):
            client, server = net.hosts[2*n], net.hosts[2*n + 1]
            ccmd = iperf + ' -yc -t 10 -c ' + server.IP()
            clientcmd[n] = client.popen(ccmd)

        #fetch the client and server results
        for n in range(0, N):
            cout, cerr = clientcmd[n].communicate()
            cliout[n] = cout
            try:
                result[n] = str(getBandwidth(cliout[n]))
            except Exception:
                result[n] = 'NaN'
            servercmd[n].kill()
            servercmd[n].wait()

        print ','.join(result)
        flush()

    net.stop()

def usage():
    print >> sys.stderr, "Usage: python BWIsolation inter|intra"
    exit(1)

if __name__ == '__main__':
    if(len(sys.argv) != 2):
        usage()
    sizes = [1] # [ 1, 2, 3, 5, 10, 20, 40, 80 ]
    trials = 1
    for bm in bmarkToTopo.keys():
        if(re.match(bm, sys.argv[1], re.I) is not None):
            lg.setLogLevel( 'error' )
            print >> sys.stderr, "#*** Running %s-node BWIsolation Benchmark ***" % bm
            for n in sizes:
                print >> sys.stderr, "#Size :", n
                BWIsolation(bm, n, trials)
            exit(0)
    usage()
