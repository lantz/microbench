#!/usr/bin/python

"""
2host-1sw topology for bandwidth isolation test.
"""

from mininet.topo import Topo

class InterNodeTopo( Topo ):
    '''Topology for a group of 2host-1sw sets.'''

    def __init__( self, N, cpu=0.2, bw=100):
	'''Constructor'''

	# Add default members to class.
	super( InterNodeTopo, self ).__init__()

	# Create switch and host nodes
	hosts = ['h%s' % i for i in range(1, 2*N+1)]
	switches = ['s%i' % i  for i in range(2*N+1, 3*N+1)]
	for h in hosts:
	    self.add_host(h)
	for s in switches:
	    self.add_switch(s)

	# Wire up hosts
	for i in range(0, N):
	    self.add_link(hosts[2*i], switches[i])
	    self.add_link(hosts[2*i + 1], switches[i])


if __name__ == '__main__':
    sizes = [ 1, 10, 20 ]
    for n in sizes:
	print "*** Printing InterNodeTopo : size ", n
	topo = InterNodeTopo(n)
	print "Nodes: ", topo.nodes()
	print "Switches: ", topo.switches()
	print "Hosts: ", topo.hosts()
	print "Edges: ", topo.edges()
