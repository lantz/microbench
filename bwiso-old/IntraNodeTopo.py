#!/usr/bin/python

"""
Single switch topology for bandwidth test
"""

from mininet.topo import Topo

class IntraNodeTopo( Topo ):
    '''Topology for a group of hosts connected by a single switch.'''

    def __init__( self, N ):
        '''Constructor'''

        # Add default members to class.
        super( IntraNodeTopo, self ).__init__()

        # Create switch and host nodes
        hosts = [ 'h%s' for h in range(1, 2*N + 1) ]
        switch = 2*N + 1
        for h in hosts:
            self.add_node( h )
        self.add_node( switch )

        # Wire up hosts
        for h in hosts:
            self.add_edge( h, switch)


if __name__ == '__main__':
    sizes = [ 1, 10, 20 ]
    for n in sizes:
        print "*** Printing IntraNodeTopo : size ", n
        topo = InterNodeTopo(n)
        print "Nodes: ", topo.nodes()
        print "Switches: ", topo.switches()
        print "Hosts: ", topo.hosts()
        print "Edges: ", topo.edges()
