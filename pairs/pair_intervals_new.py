#!/usr/bin/python

"""
pair_intervals.py: test bandwidth through a single pair of hosts,
connected either via a switch or raw links, over time.

Bob Lantz
"""

import re
from time import sleep, time
from sys import exit, stdout, stderr
from optparse import OptionParser
from json import dumps

from mininet.net import Mininet
from mininet.node import Controller, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info, warn, output

from mininet.topo import Topo, Node, Edge
from mininet.net import Mininet
from mininet.node import Host
from mininet.util import quietRun

from decimal import Decimal

# Simple topologies: sets of host pairs

class PairTopo( Topo ):
    "A set of host pairs connected by single links"
    
    def __init__( self, pairs, useSwitches, bw=None, cpu=-1):
        super( PairTopo, self ).__init__()
        self.template_host = Node(is_switch=False, cpu=cpu, in_namespace=True)
        self.template_switch = Node(is_switch=True, in_namespace=False)
        self.template_link = Edge(bw=bw)
        for h in range( 1, pairs + 1 ):
            if useSwitches:
                self.addSwitchPair(str(h), str(pairs + h), str(pairs + pairs + h))
            else:
                self.addPair(str(h), str(pairs + h))
        self.enable_all()

    def addPair( self, h1, h2 ):
        "Add a pair of linked hosts, h1 <-> h2"
        self.add_node( h1, self.template_host)
        self.add_node( h2, self.template_host)
        self.add_edge( h1, h2, self.template_link )

    def addSwitchPair( self, h1, h2, s1 ):
        "Add a pair of linked hosts, h1 <-> s1 <-> h2"
        self.add_node( h1, self.template_host)
        self.add_node( h2, self.template_host)
        self.add_node( s1, self.template_switch)        
        self.add_edge( h1, s1, self.template_link )
        self.add_edge( h2, s1, self.template_link )


def pairNet( pairs=1, useSwitches=False, bw=None, cpu=-1, **kwargs ):
    "Convenience function for creating pair networks"
    # This is a bit ugly - a lot of work to avoid flushing
    # routes; I think we should rethink how that works.
    class MyHost( Host ):
        "Put clients in root namespace and DON'T flush routes"
        count = 0
        def __init__( self, name, **kwargs ):
            # First N (=pairs) hosts are clients, in root NS
            MyHost.count += 1
            ns = kwargs.pop('inNamespace', True)
            #ns = MyHost.count > pairs
            ns = int(name) > pairs
            Host.__init__( self, name, inNamespace=ns, **kwargs )
            self.hostID = MyHost.count
        def setDefaultRoute( self, intf ):
            "Hack of sorts: don't set or flush route"
            pass
    #topo = PairTopo( pairs, useSwitches )
    topo = PairTopo( pairs, useSwitches, bw=bw, cpu=cpu)
    #net = Mininet( topo, host=MyHost, **kwargs )
    net = Mininet( topo, switch=OVSKernelSwitch, host=MyHost, **kwargs )
    info( "*** Configuring host routes\n" )
    hosts = hostArray(net)
    clients = [hosts[i] for i in range(1, pairs+1)]
    servers = [hosts[i] for i in range(pairs+1, 2*pairs+1)]
    for client, server in zip( clients, servers ):
        client.setHostRoute( server.IP(), client.defaultIntf() )
        server.setHostRoute( client.IP(), server.defaultIntf() )
    return net

# iperf test for host pairs

def hostArray( net ):
    "Return array[1..N] of net.hosts"
    hosts = {}
    count = len( net.hosts )
    #index = 1
    #for host in net.hosts:
    #    hosts[ index ] = host
    #    index += 1
    for i in range(1, count+1):
        hosts[i] = net.getNodeByName(str(i))
    return hosts

def listening( src, dest, port=5001 ):
    "Return True if we can connect from src to dest on port"
    cmd = 'echo A | telnet -e A %s %s' % (dest.IP(), port)
    result = src.cmd( cmd )
    return 'Connected' in result

def parseIperfIntervals( opts, output, interval=0.5 ):
    "parse iperf -i output and return list of (start, stop, tcpbw)"
    
    timeseries = re.compile( r'\[\s*\d+\]\s+([\d\.]+)-\s*([\d\.]+)\s+sec.*\s'
                            '([\d\.]+ [KMG]*bits/sec)' )
    results = []
    totalbw = 0
    for line in output.split( '\n' ):
        # Check for time series output from background TCP iperf
        m = timeseries.search(line)
        if m:
            start, stop  = [ float(x) for x in m.group(1, 2) ]
            mbps = toBps( m.group(3) ) / 1e6
            if stop - start == interval:
                results += [ ( start, stop, mbps ) ]
            elif start == 0.0 and stop >= float( opts.time ):
                totalbw = mbps
    if totalbw == 0:
        warn( 'warning: parseIperfIntervals: total bandwidth missing from:\n',
             output )
    return results, totalbw

def pct( x ):
    "pretty percent"
    return round(  x * 100.0, 2 )


def parseIntfStats( startTime, stats ):
    """Parse stats; return dict[intf] of (s, rxbytes, txbytes)
       and list of ( start, stop, user%... )"""
    spaces = re.compile('\s+')
    colons = re.compile( r'\:' )
    seconds = re.compile( r'(\d+\.\d+) seconds')
    intfEntries, cpuEntries = {}, []
    lastTime = startTime
    entries = [ 0 ] * 9
    for line in stats.split( '\n' ):
        m = seconds.search(line)
        if m:
            s = round( float( m.group( 1 ) ) - startTime, 3 )
        elif '-eth' in line:
            line = spaces.sub( ' ', line ).split()
            intf = colons.sub( '', line[ 0 ] )
            rxbytes, txbytes = int( line[ 1 ] ), int( line[ 9 ] )
            intfEntries[ intf ] = intfEntries.get( intf, [] ) +  [
                    (s, rxbytes, txbytes ) ]
        elif 'cpu ' in line:
            line = spaces.sub( ' ', line ).split()
            lastEntries = entries
            entries = map( float, line[ 1 : ] )
            dtotal = sum( entries ) - sum( lastEntries )
            deltaPct = [ pct( ( x1 - x0) / dtotal )
                        for x1, x0 in zip( entries, lastEntries) ]
            interval = s - lastTime
            if interval > 0:
                cpuEntries += [ [ lastTime, s ] + deltaPct ]
            lastTime = s
    return intfEntries, cpuEntries

def scale( num, unit ):
    "Adjust for Gbits, Mbits or Kbits; note base 10 for networking"
    unit = unit.lower()[ 0 ]
    scales = { 'k': 1e3, 'm': 1e6, 'g': 1e9 }
    num = float( num ) * scales.get( unit, 1.0 )
    return num

def toBps( bwString ):
    "Convert bandwidth string '1.0 Mbits/sec' to 1e6"
    num, unit = bwString.split()
    return scale( num, unit )

def iperfPairs( opts, hosts ):
    "Run iperf semi-simultaneously one way for all pairs"
    pairs = len( hosts ) / 2
    plist = [ ( hosts[ h ], hosts[ h + pairs ] ) 
             for h in range( 1, pairs + 1 ) ]
    info( "*** Shutting down old iperfs\n")
    quietRun( "pkill -9 iperf" )
    info( "*** Starting iperf servers\n" )
    for src, dest in plist:
        dest.cmd( "iperf -s &" )
    info( "*** Waiting for servers to start listening\n" )
    for src, dest in plist:
        info( dest.name, '' )
        while not listening( src, dest ):
            info( '.' )
            sleep( .5 )
    info( '\n' )
    info( "*** Starting iperf clients\n" )
    for src, dest in plist:
        src.sendCmd( "sleep 1; iperf -t %s -i .5 -c %s" % (
            opts.time, dest.IP() ) )
    info( '*** Running packet count monitor\n' )
    startTime = int( time() )
    stats = quietRun( "./packetcount %s .5" % ( opts.time + 2 ) )
    intfEntries, cpuEntries = parseIntfStats( startTime, stats )
    info( "*** Waiting for clients to complete\n" )
    results = []
    for src, dest in plist:
        result = src.waitOutput()
        dest.cmd( "kill -9 %iperf" )
        # Wait for iperf to terminate
        dest.cmd( "wait" )
        parsed, totalbw = parseIperfIntervals( opts, result )
        # We look at the stats for the remote side of the destination's
        # default intf, as it is 1) now in the root namespace and easy to 
        # read and 2) guaranteed by the veth implementation to have
        # the same rx and tx byte stats as the local side. Otherwise
        # we would have to spawn a packetcount process on each server.
        remote, remoteIntf = dest.connection[ dest.defaultIntf() ]
        destbytes = intfEntries[ remoteIntf ]
        results += [ { 'src': src.name, 'dest': dest.name, 
                    'iperfIntervals(start,stop,mbps)': parsed,
                    'iperfTotalBw(mbps)': totalbw,
                    'destStats(s,rxbytes,txbytes)': destbytes } ]
    return results, cpuEntries

        
# Run a set of tests

def pairTest( opts ):
    """Run a set of tests for a series of counts, returning
        accumulated iperf bandwidth per interval for each test."""
    results = []
    initOutput( opts.outfile )
    # 9 categories in linux 2.6+
    cpuHeader = ( 'cpu(start,stop,user%,nice%,sys%,idle%,iowait%,'
                 'irq%,sirq%,steal%,guest%)' )
    for pairs in opts.counts:
        cpu = 4./pairs if opts.cpu else -1
        bw = opts.bw if (opts.bw > 0) else None
        net = pairNet( pairs=pairs, useSwitches=opts.switches, cpu=cpu, bw=bw)
        #net = pairNet( pairs=pairs, useSwitches=opts.switches )
        net.start()
        hosts = hostArray( net )
        intervals, cpuEntries = iperfPairs( opts, hosts )
        net.stop()
        # Write output incrementally in case of failure
        result = { 'pairs': pairs, 'results': intervals, 
            cpuHeader: cpuEntries }
        appendOutput( opts, [ result ] )
        results += [ result ]
    return results

# Parse command line options and dump results

def intListCallback( option, opt, value, parser ):
    "Callback for parseOptions"
    value = [ int( x ) for x in value.split( ',' ) ]
    setattr( parser.values, option.dest, value )

def parseOptions():
    "Parse command line options"
    parser = OptionParser()
    parser.add_option( '-o', '--output', dest='outfile',
        default=None, help='write output to file' )
    parser.add_option( '-t', '--time', dest='time',
        type='int', default=10, help='select iperf time interval' )
    parser.add_option( '-r', '--runs', dest='runs',
        default=1, help='specify number of runs of each test' )
    parser.add_option( '-c', '--counts', dest='counts',
        action='callback', callback=intListCallback, default=[ 1 ],
        type='string',
        help='specify pair counts, e.g. 10,20,40' )
    parser.add_option( '-s', '--switches', dest='switches',
        action='store_true', default=False, 
        help='connect hosts with switches rather than bare links' )
    parser.add_option( '-b', '--bw', dest='bw', type='int',
        default=0, help='use bandwidth limiting' )
    parser.add_option( '-p', '--cpu', dest='cpu', 
        action='store_true', default=False, 
        help='use cpu isolation' )
    ( options, args ) = parser.parse_args()
    return options, args

# Floating point madness; thanks stackoverflow

class PrettyFloats( float ):
    def __repr__( self ):
        return '%.15g' % self

def prettyFloats( obj):
    if isinstance( obj, float ):
        return PrettyFloats( obj )
    elif isinstance( obj, dict ):
        return dict((k, prettyFloats(v)) for k, v in obj.items())
    elif isinstance( obj, ( list, tuple ) ):
        return map( prettyFloats, obj )             
    return obj
   

def initOutput( name ):
    "Initialize an output file"
    f =  open( name, 'w') if name else stdout
    print >>f, '# pair_intervals results'
    print >>f, dumps( opts.__dict__ )
    if name:
        f.close()

def appendOutput( opts, totals ):
    "Append results as JSON to stdout or opts.outfile"
    info( '*** Dumping result\n' )
    f = open( opts.outfile, 'a' ) if opts.outfile else stdout
    print >>f, dumps( prettyFloats( totals ) )
    if opts.outfile:
        f.close()

def sanityCheck():
    "Make sure we have stuff we need"
    if quietRun( 'which telnet' ) == '':
        print "Error: cannot find telnet - make sure it is installed."
        exit( 1 )
    if quietRun( 'which ./packetcount' ) == '':
        print ( "Error: cannot find ./packetcount - make sure packetcount.c" 
               " is compiled and installed in the current directory" )
        exit( 1 )

if __name__ == '__main__':
    setLogLevel( 'info' )
    opts, args = parseOptions()
    sanityCheck()
    pairTest( opts )
