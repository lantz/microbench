#!/usr/bin/python

"""
Analyze and plot results from pair_intervals test


It's actually kind of hard to figure out what to look
at. There are multiple basic types
of (bandwidth) plots to consider, including

1. Individual iperf server Rx bandwidth

This shows the distribution of bandwidth across
multiple iperfs.

2. Total ("aggregate") Rx bandwidth of all iperfs over
   each time interval

This is useful to observe how much bandwidth we can get through
the entire system as we increase the number of links and switches.

Improvements: we now handle multiple runs and multiple
input files.

The rx byte statistics are reported along with the
time of collection.

Originally I looked at variance and standard deviation,
but this has been removed since it didn't seem to add
much value.

Additionally, we can plot CPU usage for individual runs and
for multiple runs.

We might also wish to consider ramp charts, simply plotting how
much has been received by each server over time.

Bob Lantz
"""

import fileinput
from math import sqrt
from json import loads
from optparse import OptionParser
from sys import exit
from operator import and_, add, eq

# We use python-matplotlib and numpy for graphing
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

# Accumulate results and calculate variance

def accumulateIntervals( opts,  entries, field ):
    "Accumulate results and return list of (start, stop, mbps, variance)"
    bws = {}
    totalbw = {}
    variance = {}
    stops = {}
    # Accumulate interval entries
    for entry in entries:
        intervals = entry[ field ]
        for start, stop, bw in intervals:
            if start not in stops:
                stops[ start ] = stop
            if stops[ start ] == stop:
                bws[ start ] = bws.get( start, [] ) + [ bw ]
            else:
                print "warning: ignoring bad interval", start, stop
    # Make sure intervals have same number of entries
    vals = bws.values()
    checklen = len( vals[ 0 ] )
    if not reduce( and_, map( lambda v: len( v ) == checklen, vals ) ):
        print "inconsistent interval set - aborting"
        exit( 1 )
    # Calculate total bw and variance
    for start in bws.keys():
        totalbw[ start ] = sum( bws[ start ] )  # Correct
        variance[ start ] = sigma2( bws[ start ] )   # Not really correct ?
    # Build and return result
    accumulated = [ ( start, stops [ start ],
                    totalbw[ start ], variance[ start ] )
                   for start in sorted( totalbw.keys() ) ]
    return accumulated

def sigma2( nums ):
    "Calculate variance (sigma^2) for a list of numbers"
    n = len( nums )
    total = sum( nums )
    mean = total / n
    sumsq = sum( [ (x - mean) * (x - mean) for x in nums ] )
    variance = sumsq / n
    return variance

def sigma( nums ):
    "Calculate standard deviation for list of numbers"
    return sqrt( sigma2 ( nums ) )

def calculateTotals( opts, results ):
    "Calculate total bps over multiple links"
    totals = []
    for r in results:
        pairs, entries = r[ 'pairs' ], r[ 'results' ]
        r[ 'rxIntervalTotals' ] = [ { 'entries':
            accumulateIntervals( opts, entries, 'rxBwIntervals' ) } ]

# Helper functions

def colorGenerator():
    "Return cycling list of colors"
    colors = [ 'red', 'green', 'blue', 'purple', 'orange', 'cyan']
    index = 0
    while True:
        yield colors[ index ]
        index = ( index + 1 ) % len( colors )

def linkLegend( cgen, colors, pairs ):
    "Return color and label for iperf count or '' if already used"
    if pairs not in colors:
        color = colors[ pairs ] = cgen.next()
        label = '%s iperf' % pairs
        label += 's' if pairs > 1 else ''
    else:
        color, label = colors[ pairs ], None
    return color, label

# Plot results

def plotBw( plotopts, fignum, entries, title='' ):
    """Plot bandwidth over time
       fignum: figure number
       pairs: number of parallel links (for legend)
       entries: [[pairCount, [(start, stop, bw)...]]...]
       title: Mininet: <title>"""
    fig = plt.figure( fignum )
    fig.canvas.set_window_title( title + ': ' + str( plotopts.args ) )
    cgen, colors = colorGenerator(), {}
    for pairs, intervals in entries:
        xvals = reduce( add, [ ( i[ 0 ], i[ 1 ] ) for i in intervals ] )
        bwvals = reduce( add, [ ( i[ 2 ], i[ 2 ] ) for i in intervals ] )
        color, label = linkLegend( cgen, colors, pairs )
        plt.plot( xvals, bwvals, label=label, color=color )
    plt.ylabel( 'Mbps' )
    plt.title( 'Mininet: %s' % title )
    plt.xlabel( 'time (s)' )
    plt.grid( True )
    if not plotopts.nolegend:
        plt.legend()

def convertToBw( stats ):
    "Convert list of (s, bytes) to list of (start, stop, mbps)"
    start, lastbytes = stats[ 0 ]
    result = []
    for stop, bytes in stats[ 1: ]:
        dt = stop - start
        mbps = ( ( bytes - lastbytes ) * 8 * 1e-6 ) / dt
        result += [ ( start, stop, mbps ) ]
        start, lastbytes = stop, bytes
    return result

def calculateRxBw( results ):
    "Calculate rx bandwidth for results"
    for r  in results:
        pairs = r[ 'pairs' ]
        entries = r[ 'results' ]
        for e in entries:
            stats = [ ( s, rxbytes ) for s, txbytes, rxbytes in
                     e[ 'destStats(s,txbytes,rxbytes)' ] ]
            e[ 'rxBwIntervals' ] =  convertToBw( stats )

def plotBwIntervals( plotopts, results, fignum, title, entryField,
                    intervalField ):
    "Plot bandwidth over time"
    data = []
    for r in results:
        pairs = r[ 'pairs' ]
        entries = r[ entryField ]
        data += [ ( pairs, entry[ intervalField ] ) for entry in entries ]
    plotBw( plotopts, fignum, data, title )

def plotIntervals( plotopts, results ):
    "Plot individual iperf bandwidth over time"
    plotBwIntervals( plotopts, results,
        5, 'Raw RX bandwidth over time',
        'results', 'rxBwIntervals' )

def plotIntervalTotals( plotopts, results ):
    plotBwIntervals( plotopts, results,
        6, 'Total Raw RX bandwidth over time',
        'rxIntervalTotals', 'entries' )

def dictPush( d, key, entry ):
    "Append a new element into a dictionary of lists"
    d[ key ] = d.get( key, [] ) + [ entry ]

def dictAppend( d, key, entries, label='runs' ):
    "Append an new list of entries into a dictionary of lists"
    d[ key ] = d.get( key, [] ) + entries

def dictPlot( d, barchart=True, label='run', **plotargs ):
    "Plot an n to many mapping"
    xvals = sorted( d.keys() )
    yvals = [ d[ x ] for x in xvals ]
    ind = np.arange( len( yvals ) )
    width = .35
    indcenter = ind + .5 * width
    plt.xticks( indcenter, [ str( x ) for x in xvals ] )
    # Use box plot unless bar chart was specified
    if not barchart:
        plt.boxplot( yvals )
        return
    # If we only have one run, just plot bars
    if not reduce( and_, [ len( y ) > 1 for y in yvals ] ):
        plt.bar( ind, [ y[ 0 ] for y in yvals ], width )
        return
    # Otherwise, scatter plot points
    # was: plt.plot( ind + .5 * width, yvals, 'o', **plotargs )
    for x, y in zip( indcenter, yvals ):
        plt.plot( [ x ] * len( y ), y, 'o', **plotargs )
    # hack - is there a better way to add legend?
    plt.plot( indcenter[ 0 ], yvals[ 0 ][ 0 ], 'o',
             label=label, **plotargs )
    # And plot a bar chart of the means
    means = [ sum( y ) / len( y ) for y in yvals ]
    plt.bar( ind, means, width, label='mean' )

def plotTotalBw( plotopts, results, entriesToTotalBw, aggregate=True ):
    "Bar/box chart of total bandwidth"
    fig = plt.figure( 3 if not aggregate else 4 )
    fig.canvas.set_window_title(
        'total bw: ' + str( plotopts.args ) if aggregate
        else 'bw per iperf: ' + str( plotopts.args ) )
    defaults = { 'color': 'black' }  # was: { 'linewidth': 2 }
    # Calculate total bandwidth
    totals = {}
    for r in results:
        pairs, entries = r[ 'pairs' ], r[ 'results' ]
        bws = entriesToTotalBw( entries )
        if aggregate:
            # Add up bws to plot total
            dictPush( totals, pairs, sum( bws ) )
        else:
            # Plot bw for each individual iperf
            dictAppend( totals, pairs, bws )
    # Plot
    if aggregate:
        plt.title( 'Mininet: total iperf bandwidth' )
    else:
        plt.title( 'Mininet: average bandwidth per iperf' )
    plt.ylabel( 'Mbps' )
    label = 'runs' if aggregate else 'iperfs'
    dictPlot( totals, barchart=plotopts.bar, label=label, **defaults )
    plt.xlabel( 'iperfs' )
    # Turn on y grid only
    ax = fig.add_subplot( 111 )
    ax.yaxis.grid( True )
    # And blast x tick lines
    for l in ax.get_xticklines():
        l.set_markersize( 0 )
    if not plotopts.nolegend:
        plt.legend()

def plotTotal( plotopts, results, aggregate=False ):
    "Bar/box chart of total bandwidth"
    def iperfTotals( entries ):
        return [ e[ 'iperfTotalBw(mbps)' ] for e in entries ]
    if plotopts.iperf:
        plotTotalBw( plotopts, results, iperfTotals, aggregate )

def plotVals( entry, fields ):
    "Return xvals, yvals for interval list"

def addPlotFeatures( plotopts ):
    "Add our standard plot features"
    plt.grid()
    if plotopts.nolegend:
       return
    leg = plt.legend()
    ltext  = leg.get_texts()
    plt.setp( ltext, fontsize='small' )

def plotCpu( fignum, plotopts, results ):
    "Plot CPU usage"
    defaults = { 'linewidth': 2 }
    # Accumulate cpu stats based on pair count
    entries = {}
    header = ( 'cpu(start,stop,user%,nice%,sys%,idle%,iowait%,'
                 'irq%,sirq%,steal%,guest%)' )
    fields = header[ 4 : -1 ].split( ',' )
    for r in results:
        pairs = r[ 'pairs' ]
        cpu = r[ header ]
        entries[ pairs ] = entries.get( pairs, [] ) + [ cpu ]
    # Plot for each pair count
    colors = ( None, None, 'red', 'green', 'blue', 'gray',
              'purple','yellow', 'pink', 'brown', 'cyan' )
    for pairs in sorted( entries.keys() ):
        labelUsed = {}
        fig = plt.figure( fignum )
        for entry in entries[ pairs ]:
            xvals = [ ( e[ 0 ], e[ 1 ] ) for e in entry ]
            xvals = reduce( add, xvals )
            for i in range( 2, len( fields ) ):
                yvals = [ ( e[ i ], e[ i ] ) for e in entry ]
                yvals = reduce( add, yvals )
                label = fields[ i ]
                if label in labelUsed:
                    label=''
                else:
                    labelUsed[ label ] = True
                plt.plot( xvals, yvals, color=colors[ i ],
                     label=label,
                    **defaults )
        plt.xlabel( 'time (s)' )
        plt.ylabel( 'CPU usage (%)' )
        title = 'Mininet: CPU usage for %d iperf test' % pairs
        plt.title( title )
        fig.canvas.set_window_title( title + ' (lines)' )
        addPlotFeatures( plotopts )
        fignum += 1
    return fignum

def plotCpuBars( fignum, plotopts, results ):
    "Plot CPU usage as bar graph"
    defaults = { }
    # Accumulate cpu stats based on pair count
    entries = {}
    header = ( 'cpu(start,stop,user%,nice%,sys%,idle%,iowait%,'
              'irq%,sirq%,steal%,guest%)' )
    fields = header[ 4 : -1 ].split( ',' )
    for r in results:
        pairs = r[ 'pairs' ]
        cpu = r[ header ]
        entries[ pairs ] = entries.get( pairs, [] ) + [ cpu ]
    # Plot for each pair count
    colors = ( None, None, 'red', 'green', 'blue', 'gray',
              'purple','yellow', 'pink', 'brown', 'cyan' )
    for pairs in sorted( entries.keys() ):
        for entry in entries[ pairs ]:
            fig = plt.figure( fignum )
            labelUsed = {}
            xvals = np.array( [ e[ 0 ] for e in entry ] )
            ybase = xvals * 0
            interval = e[ 1 ] - e[ 0 ]
            for i in range( 2, len( fields ) ):
                yvals = np.array( [ e[ i ] for e in entry ] )
                label = fields[ i ]
                if label in labelUsed:
                    label=''
                else:
                    labelUsed[ label ] = True
                plt.bar( xvals, yvals, color=colors[ i ],
                         label=label, width=interval, bottom=ybase,
                         **defaults )
                ybase += yvals
            plt.xlabel( 'time (s)' )
            plt.ylabel( 'CPU usage (%)' )
            title = 'Mininet: CPU usage for %d iperf test' % pairs
            plt.title( title )
            fig.canvas.set_window_title( title + ' (bars)' )
            addPlotFeatures( plotopts )
            fignum += 1

def parseOptions():
    "Parse command line options"
    parser = OptionParser( 'usage: %prog [options] [input files]' )
    parser.add_option( '-l', '--links', dest='links',
                      default=False, action='store_true',
                      help='plot individual link bandwidth over time' )
    parser.add_option( '-s', '--system', dest='aggregate',
                      default=False, action='store_true',
                      help='plot aggregate system bandwidth over time' )
    parser.add_option( '-n', '--nolegend', dest='nolegend',
                      default=False, action='store_true',
                      help="don't add legend to plots" )
    #parser.add_option( '-b', '--bar', dest='bar',
    #                  default=False, action='store_true',
    #                  help="use bar charts rather than box plots" )
    parser.add_option( '-c', '--cpu', dest='cpu',
                      default=False, action='store_true',
                      help="plot CPU usage" )
    parser.add_option( '-p', '--cpubars', dest='cpubars',
                      default=False, action='store_true',
                      help="plot CPU usage as strip chart" )
    parser.add_option( '-a', '--all', dest='all',
                      default=False, action='store_true',
                      help='create all available plots' )
    ( options, args ) = parser.parse_args()
    plotFlags = [ 'links', 'aggregate', 'cpu', 'cpubars' ]
    if options.all:
        for opt in plotFlags:
            if getattr( options, opt ) is False:
                setattr( options, opt,  True )
    doPlots = ( options.cpu or options.cpubars or
        options.links or options.aggregate )
        # or options.total
    if not doPlots:
        print 'No plots selected - please select a plot option.'
        parser.print_help()
        exit( 1 )
    return options, args

def readData( files ):
    "Read input data from pair_intervals run"
    results = []
    opts = {}
    for line in fileinput.input( files ):
        if line[ 0 ] == '#':
            continue
        data = loads( line )
        if type( data ) == dict:
            opts = loads(line)
        elif type( data ) == list:
            results +=  data
    return results, opts

if __name__ == '__main__':
    plotopts, args = parseOptions()
    plotopts.args = args
    results, opts = readData( files=args )
    calculateRxBw( results )
    if plotopts.links:
        plotIntervals( plotopts, results )
    if plotopts.aggregate:
        calculateTotals( plotopts, results )
        plotIntervalTotals( plotopts, results )
    #if plotopts.entire:
    # plotTotal( plotopts, results, aggregate=False )
    fignum = 10
    if plotopts.cpu:
        fignum = plotCpu( fignum, plotopts, results )
    if plotopts.cpubars:
        plotCpuBars( fignum, plotopts, results )
    plt.show()

