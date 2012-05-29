from cStringIO import StringIO
from os import path
from sys import argv, stderr as SE, stdout as SO

from temoa_graphviz import CreateModelDiagrams

try:
	from coopr.pyomo import *
except:

	import sys
	cpath = path.join('path', 'to', 'coopr', 'executable', 'coopr_python')
	if 'win' not in sys.platform:
		msg = """\
Option 1:
$ PATH=%(cpath)s:$PATH
$ coopr_python %(base)s  [options]  data.dat

Option 2:
$ %(cpath)s  %(base)s  [options]  data.dat
"""

	else:
		msg = """\
Option 1:
C:\\> set PATH=%(cpath)s:%%PATH%%
C:\\> coopr_python  %(base)s  [options]  data.dat

Option 2:
C:\\> %(cpath)s  %(base)s  [options]  data.dat
"""

	base = path.basename( sys.argv[0] )
	msg %= { 'cpath' : cpath, 'base' : base }
	msg = """\
Unable to find coopr.pyomo on the Python system path.  Are you running Coopr's
version of Python?  Here is one way to check:

  # look for items that have to do with the Coopr project
python -c "import sys, pprint; pprint.pprint(sys.path)"

If you aren't running with Coopr's environment for Python, you'll need to either
update your PATH environment variable to use Coopr's Python setup, or always
explicitly use the Coopr path:

%s
""" % msg

	raise ImportError, msg


###############################################################################
# Temoa rule "partial" functions (excised from indidivual constraints for
#   readability)

def CommodityBalanceConstraintErrorCheck ( p, s, d, c, out, inp ):
	if int is type(out):
		flow_in_expr = StringIO()
		inp.pprint( ostream=flow_in_expr )
		msg = ("Unable to meet an interprocess '%s' transfer in (%s, %s, %s).\n"
		  'No flow out.  Constraint flow in:\n   %s\n'
		  'Possible reasons:\n'
		  " - Is there a missing period in set 'time_horizon'?\n"
		  " - Is there a missing tech in set 'tech_resource'?\n"
		  " - Is there a missing tech in set 'tech_production'?\n"
		  " - Is there a missing commodity in set 'commodity_physical'?\n"
		  ' - Are there missing entries in the Efficiency parameter?\n'
		  ' - Does a tech need a longer LifetimeTech parameter setting?')
		raise ValueError, msg % (c, s, d, p, flow_in_expr.getvalue() )


def DemandConstraintErrorCheck ( p, s, d, i, dem ):
	if int is type( i ):
		msg = ("Error: Demand '%s' for (%s, %s, %s) unable to be met by any "
		  'technology.\n\tPossible reasons:\n'
		  ' - Is the Efficiency parameter missing an entry for this demand?\n'
		  ' - Does a tech that satisfies this demand need a longer LifetimeTech?'
		  '\n')
		raise ValueError, msg % (dem, p, s, d)

# End Temoa rule "partials"
###############################################################################

##############################################################################
# Begin validation and initialization routines

def validate_time ( M ):
	from sys import maxint

	if not len( M.time_horizon ):
		msg = ('Set "time_horizon" is empty!  Please specify at least one '
		  'period in set time_horizon.')
		raise ValueError, msg

	if not len( M.time_future ):
		msg = ('Set "time_future" is empty!  Please specify at least one year '
		  'in set time_future, so that the model may ascertain a final period '
		  'period length for optimization and economic accounting.')
		raise ValueError, msg

	""" Ensure that the time_exist < time_horizon < time_future """
	exist    = len( M.time_exist ) and max( M.time_exist ) or -maxint
	horizonl = min( M.time_horizon )  # horizon "low"
	horizonh = max( M.time_horizon )  # horizon "high"
	future   = min( M.time_future )

	if not ( exist < horizonl ):
		msg = ('All items in time_horizon must be larger than in time_exist.\n'
		  'time_exist max:   %s\ntime_horizon min: %s')
		raise ValueError, msg % (exist, horizonl)
	elif not ( horizonh < future ):
		msg = ('All items in time_future must be larger that in time_horizon.\n'
		  'time_horizon max:   %s\ntime_future min:    %s')
		raise ValueError, msg % (horizonh, future)

	return tuple()


def validate_SegFrac ( M ):

	total = sum( M.SegFrac.data().values() )

	if abs(float(total) - 1.0) > 1e-15:
		# We can't explicitly test for "!= 1.0" because of incremental roundoff
		# errors inherent in float manipulations and representations, so instead
		# compare against an epsilon value of "close enough".

		def get_str_padding ( obj ):
			return len(str( obj ))
		key_padding = max(map( get_str_padding, M.SegFrac.data().keys() ))

		format = "%%-%ds = %%s" % key_padding
			# Works out to something like "%-25s = %s"

		items = sorted( M.SegFrac.data().items() )
		items = '\n   '.join( format % (str(k), v) for k, v in items )

		msg = ('The values of the SegFrac parameter do not sum to 1.  Each item '
		  'in SegFrac represents a fraction of a year, so they must total to '
		  '1.  Current values:\n   %s\n\tsum = %s')

		raise ValueError, msg % (items, total)

	return tuple()


def validate_TechOutputSplit ( M ):
	msg = ('A set of output fractional values specified in TechOutputSplit do '
	  'not sum to 1.  Each item specified in TechOutputSplit represents a '
	  'fraction of the input carrier converted to the output carrier, so '
	  'they must total to 1.  Current values:\n   %s\n\tsum = %s')

	split_indices = M.TechOutputSplit.keys()

	for i in M.commodity_physical:
		for t in M.tech_all:
			l_total = sum(
			  value(M.TechOutputSplit[i, t, o])

			  for o in M.commodity_carrier
			  if (i, t, o) in split_indices
			)

			# small enough; likely a rounding error
			if abs(l_total) < 1e-15: continue

			if abs(l_total -1) > 1e-10:
				items = '\n   '.join(
				  "%s: %s" % (
				    str((i, t, o)),
				    value(M.TechOutputSplit[i, t, o])
				  )

				  for o in M.commodity_carrier
				  if (i, t, o) in split_indices
				)

				raise ValueError, msg % (items, l_total)

	return set()


def init_set_time_optimize ( M ):
	items = sorted( M.time_horizon )
	items.extend( sorted( M.time_future ) )

	return items[:-1]


def init_set_vintage_exist ( M ):
	return sorted( M.time_exist )


def init_set_vintage_future ( M ):
	return sorted( M.time_future )


def init_set_vintage_optimize ( M ):
	return sorted( M.time_optimize )


def init_set_vintage_all ( M ):
	return sorted( M.time_all )

# end validation and initialization routines
##############################################################################

##############################################################################
# Begin helper functions

# Global Variables (dictionaries to cache parsing of Efficiency parameter)
g_processInputs  = dict()
g_processOutputs = dict()
g_processVintages = dict()
g_processLoans = dict()
g_activeFlowIndices = None
g_activeActivityIndices = None
g_activeCapacityIndices = None
g_activeCapacityAvailableIndices = None

def InitializeProcessParameters ( M ):
	global g_processInputs
	global g_processOutputs
	global g_processVintages
	global g_processLoans
	global g_activeFlowIndices
	global g_activeActivityIndices
	global g_activeCapacityIndices
	global g_activeCapacityAvailableIndices

	l_first_period = min( M.time_horizon )
	l_exist_indices = M.ExistingCapacity.keys()
	l_used_techs = set()

	for i, t, v, o in M.Efficiency.keys():
		l_process = (t, v)
		l_lifetime = value(M.LifetimeTech[ l_process ])

		if v in M.vintage_exist:
			if l_process not in l_exist_indices:
				msg = ('Warning: %s has a specified Efficiency, but does not '
				  'have any existing install base (ExistingCapacity)\n.')
				SE.write( msg % str(l_process) )
				continue
			if 0 == M.ExistingCapacity[ l_process ]:
				msg = ('Notice: Unnecessary specification of ExistingCapacity '
				  '%s.  If specifying a capacity of zero, you may simply '
				  'omit the declaration.\n')
				SE.write( msg % str(l_process) )
				continue
			if v + l_lifetime <= l_first_period:
				msg = ('\nWarning: %s specified as ExistingCapacity, but its '
				  'LifetimeTech parameter does not extend past the beginning of '
				  'time_horizon.  (i.e. useless parameter)'
				  '\n\tLifetime:     %s'
				  '\n\tFirst period: %s\n')
				SE.write( msg % (l_process, l_lifetime, l_first_period) )
				continue

		eindex = (i, t, v, o)
		if 0 == M.Efficiency[ eindex ]:
			msg = ('\nNotice: Unnecessary specification of Efficiency %s.  If '
			  'specifying an efficiency of zero, you may simply omit the '
			  'declaration.\n')
			SE.write( msg % str(eindex) )
			continue

		l_used_techs.add( t )

		for p in M.time_optimize:
			# can't build a vintage before it's been invented
			if p < v: continue

			pindex = (p, t, v)

			if v in M.time_optimize:
				l_loan_life = value(M.LifetimeLoan[ l_process ])
				if v + l_loan_life >= p:
					g_processLoans[ pindex ] = True

			# if tech is no longer "alive", don't include it
			if v + l_lifetime <= p: continue

			if pindex not in g_processInputs:
				g_processInputs[  pindex ] = set()
				g_processOutputs[ pindex ] = set()
			if (p, t) not in g_processVintages:
				g_processVintages[p, t] = set()

			g_processVintages[p, t].add( v )
			g_processInputs[ pindex ].add( i )
			g_processOutputs[pindex ].add( o )
	l_unused_techs = M.tech_all - l_used_techs
	if l_unused_techs:
		msg = ("Notice: '{}' specified as technology, but it is not utilized in "
		       'the Efficiency parameter.\n')
		for i in sorted( l_unused_techs ):
			SE.write( msg.format( i ))

	g_activeFlowIndices = set(
	  (p, s, d, i, t, v, o)

	  for p in M.time_optimize
	  for t in M.tech_all
	  for v in ProcessVintages( p, t )
	  for i in ProcessInputs( p, t, v )
	  for o in ProcessOutputs( p, t, v )
	  for s in M.time_season
	  for d in M.time_of_day
	)
	g_activeActivityIndices = set(
	  (p, t, v)

	  for p in M.time_optimize
	  for t in M.tech_all
	  for v in ProcessVintages( p, t )
	)
	g_activeCapacityIndices = set(
	  (t, v)

	  for p in M.time_optimize
	  for t in M.tech_all
	  for v in ProcessVintages( p, t )
	)
	g_activeCapacityAvailableIndices = set(
	  (p, t)

	  for p in M.time_optimize
	  for t in M.tech_all
	  if ProcessVintages( p, t )
	)

	return set()

##############################################################################
# Sparse index creation functions

# These functions serve to create sparse index sets, so that Coopr need only
# create the parameter, variable, and constraint indices with which it will
# actually operate.  This *tremendously* cuts down on memory usage, which
# decreases time and increases the maximum specifiable problem size.

##############################################################################
# Parameters

def CapacityFactorIndices ( M ):
	indices = set(
	  (t, v)

	  for i, t, v, o in M.Efficiency.keys()
	)

	return indices


def CostFixedIndices ( M ):
	return g_activeActivityIndices


def CostMarginalIndices ( M ):
	return g_activeActivityIndices


def CostInvestIndices ( M ):
	indices = set(
	  (t, v)

	  for p, t, v in g_processLoans
	)

	return indices


def DiscountRateIndices ( M ):
	return set( M.CostInvest.keys() )


def EmissionActivityIndices ( M ):
	indices = set(
	  (e, i, t, v, o)

	  for i, t, v, o in M.Efficiency.keys()
	  for e in M.commodity_emissions
	)

	return indices


def LoanLifeFracIndices ( M ):
	"""\
Returns the set of (period, tech, vintage) tuples of process loans that die
between period boundaries.  The tuple indicates the last period in which a
process is active.
"""
	periods = set( M.time_optimize )
	max_year = max( M.time_future )

	indices = set()
	for t, v in M.LifetimeLoanIndices:
		death_year = v + value(M.LifetimeLoan[t, v])
		if death_year < max_year and death_year not in periods:
			p = max( yy for yy in M.time_optimize if yy < death_year )
			indices.add( (p, t, v) )

	return indices


def TechLifeFracIndices ( M ):
	"""\
Returns the set of (period, tech, vintage) tuples of processes that die between
period boundaries.  The tuple indicates the last period in which a process is
active.
"""
	periods = set( M.time_optimize )
	max_year = max( M.time_future )

	indices = set()
	for t, v in g_activeCapacityIndices:
		death_year = v + value(M.LifetimeTech[t, v])
		if death_year < max_year and death_year not in periods:
			p = max( yy for yy in M.time_optimize if yy < death_year )
			indices.add( (p, t, v) )

	return indices


def LifetimeTechIndices ( M ):
	"""\
Based on the Efficiency parameter's indices, this function returns the set of
process indices that may be specified in the LifetimeTech parameter.
"""
	indices = set(
	  (t, v)

	  for i, t, v, o in M.Efficiency.keys()
	)

	return indices


def LifetimeLoanIndices ( M ):
	"""\
Based on the Efficiency parameter's indices and time_horizon parameter, this
function returns the set of process indices that may be specified in the
CostInvest parameter.
"""
	min_period = min( M.vintage_optimize )

	indices = set(
	  (t, v)

	  for i, t, v, o in M.Efficiency.keys()
	  if v >= min_period
	)

	return indices


def LoanIndices ( M ):
	"""\
Returns the set of possible process (tech, vintage) investments the optimizer
may make.

This function is deprecated and may soon be removed from the API.
"""
	return set( M.CostInvest.keys() )

# End parameters
##############################################################################

##############################################################################
# Variables

def CapacityVariableIndices ( M ):
	return g_activeCapacityIndices

def CapacityAvailableVariableIndices ( M ):
	return g_activeCapacityAvailableIndices

def FlowVariableIndices ( M ):
	return g_activeFlowIndices


def ActivityVariableIndices ( M ):
	activity_indices = set(
	  (p, s, d, t, v)

	  for p, t, v in g_activeActivityIndices
	  for s in M.time_season
	  for d in M.time_of_day
	)

	return activity_indices


def CapacityByOutputVariableIndices ( M ):
	indices = set(
	  (t, v, o)

	  for p in M.time_optimize
	  for t in M.tech_all
	  for v in ProcessVintages( p, t )
	  for o in ProcessOutputs( p, t, v )
	)

	return indices


### Reporting variables


def ActivityByPeriodTechAndVintageVarIndices ( M ):
	return g_activeActivityIndices


def ActivityByPeriodTechAndOutputVariableIndices ( M ):
	indices = set(
	  (p, t, o)

	  for p in M.time_optimize
	  for t in M.tech_all
	  for v in ProcessVintages( p, t )
	  for o in ProcessOutputs( p, t, v )
	 )

	return indices


def ActivityByPeriodTechVintageAndOutputVariableIndices ( M ):
	indices = set(
	  (p, t, v, o)

	  for p in M.time_optimize
	  for t in M.tech_all
	  for v in ProcessVintages( p, t )
	  for o in ProcessOutputs( p, t, v )
	)

	return indices


def ActivityByTechAndOutputVariableIndices ( M ):
	indices = set(
	  (t, o)

	  for p, t, v in g_activeActivityIndices
	  for o in ProcessOutputs( p, t, v )
	)

	return indices


def ActivityByInputAndTechVariableIndices ( M ):
	indices = set(
	  (i, t)

	  for p, t, v in g_activeActivityIndices
	  for i in ProcessInputs( p, t, v )
	)

	return indices


def ActivityByPeriodInputAndTechVariableIndices ( M ):
	indices = set(
	  (p, i, t)

	  for p, t, v in g_activeActivityIndices
	  for i in ProcessInputs( p, t, v )
	)

	return indices


def ActivityByPeriodInputTechAndVintageVariableIndices ( M ):
	indices = set(
	  (p, i, t, v)

	  for p, t, v in g_activeActivityIndices
	  for i in ProcessInputs( p, t, v )
	)

	return indices


def EmissionActivityByTechVariableIndices ( M ):
	indices = set(
	  (e, t)

	  for e, i, t, v, o in M.EmissionActivity.keys()
	)

	return indices

def EmissionActivityByPeriodAndTechVariableIndices ( M ):
	indices = set(
	  (e, p, t)

	  for e, i, t, v, o in M.EmissionActivity.keys()
	  for p in M.time_optimize
	  if ValidActivity( p, t, v )
	)

	return indices


def EmissionActivityByTechAndVintageVariableIndices ( M ):
	indices = set(
	  (e, t, v)

	  for e, i, t, v, o in M.EmissionActivity.keys()
	)

	return indices


def EnergyConsumptionByTechAndOutputVariableIndices ( M ):
	indices = set(
	  (t, o)

	  for i, t, v, o in M.Efficiency.keys()
	)

	return indices


def EnergyConsumptionByPeriodAndTechVariableIndices ( M ):
	indices = set(
	  (p, t)

	  for i, t, v, o in M.Efficiency.keys()
	  for p in M.time_optimize
	  if ValidActivity( p, t, v )
	)

	return indices


def EnergyConsumptionByPeriodInputAndTechVariableIndices ( M ):
	indices = set(
	  (p, i, t)

	  for i, t, v, o in M.Efficiency.keys()
	  for p in M.time_optimize
	  if ValidActivity( p, t, v )
	)

	return indices


def EnergyConsumptionByPeriodTechAndOutputVariableIndices ( M ):
	indices = set(
	  (p, t, o)

	  for i, t, v, o in M.Efficiency.keys()
	  for p in M.time_optimize
	  if ValidActivity( p, t, v )
	)

	return indices


def EnergyConsumptionByPeriodTechAndVintageVariableIndices ( M ):
	indices = set(
	  (p, t, v)

	  for i, t, v, o in M.Efficiency.keys()
	  for p in M.time_optimize
	  if ValidActivity( p, t, v )
	)

	return indices

# End variables
##############################################################################

##############################################################################
# Constraints


def CapacityByOutputConstraintIndices ( M ):
	indices = set(
	  (p, s, d, t, v, o)

	  for p in M.time_optimize
	  for t in M.tech_all
	  for v in ProcessVintages( p, t )
	  for o in ProcessOutputs( p, t, v )
	  for s in M.time_season
	  for d in M.time_of_day
	)

	return indices


def DemandConstraintIndices ( M ):
	return set( M.Demand.keys() )


def DemandActivityConstraintIndices ( M ):
	indices = set()

	dem_slices = dict()
	for p, s, d, dem in M.Demand.keys():
		if (p, dem) not in dem_slices:
			dem_slices[p, dem] = set()
		dem_slices[p, dem].add( (s, d) )

	for (p, dem), slices in dem_slices.iteritems():
		# No need for this constraint if demand is only in one slice.
		if not len( slices ) > 1: continue
		slices = sorted( slices )
		first = slices[0]
		tmp = set(
		  (p, s, d, t, v, dem, first[0], first[1])

		  for s, d in slices[1:]
		  for Fp, Fs, Fd, i, t, v, Fo in M.FlowVarIndices
		  if Fp == p and Fs == s and Fd == d and Fo == dem
		)
		indices.update( tmp )

	return indices


def EmissionConstraintIndices ( M ):
	return set( M.EmissionLimit.keys() )

def MaxCapacityConstraintIndices ( M ):
	return set( M.MaxCapacity.keys() )

def MinCapacityConstraintIndices ( M ):
	return set( M.MinCapacity.keys() )

def ResourceConstraintIndices ( M ):
	return set( M.ResourceBound.keys() )


def BaseloadDiurnalConstraintIndices ( M ):
	indices = set(
	  (p, s, d, t, v)

	  for p in M.time_optimize
	  for t in M.tech_baseload
	  for v in ProcessVintages( p, t )
	  for s in M.time_season
	  for d in M.time_of_day
	)

	return indices


### Additions to match MARKAL

def MARKAL_SegFrac_CapacityByOutput_indices ( M ):
	indices = set(
	  (p, s, d, t, v, o)

	  for p, t, v in g_activeActivityIndices
	  if t in M.tech_electric    # This is major difference from Temoa
	  for o in ProcessOutputs( p, t, v )
	  for s in M.time_season
	  for d in M.time_of_day
	)

	return indices


def MARKAL_No_SegFrac_CapacityByOutput_indices ( M ):
	indices = set(
	  (p, t, v)

	  for p, t, v in g_activeActivityIndices
	  if t not in M.tech_electric  # This is major difference from Temoa
	)

	return indices


def MARKAL_SegFrac_CapacityLifetimeConstraint_indices ( M ):
	indices = set(
	  (l_per, l_season, l_tod, l_carrier)

	  for l_per in M.time_optimize
	  for l_tech in M.tech_electric
	  for l_vin in ProcessVintages( l_per, l_tech )
	  for l_carrier in ProcessOutputs( l_per, l_tech, l_vin )
	  for l_inp in ProcessInputsByOutput( l_per, l_tech, l_vin, l_carrier )
	  for l_season in M.time_season
	  for l_tod in M.time_of_day
	)

	return indices

def MARKAL_No_SegFrac_CapacityLifetimeConstraint_indices ( M ):
	indices = set(
	  (l_per, l_carrier)

	  for l_per in M.time_optimize
	  for l_tech in M.tech_all
	  if l_tech not in M.tech_electric
	  for l_vin in ProcessVintages( l_per, l_tech )
	  for l_carrier in ProcessOutputs( l_per, l_tech, l_vin )
	  for l_inp in ProcessInputsByOutput( l_per, l_tech, l_vin, l_carrier )
	)

	return indices


### End additions to match MARKAL


def FractionalLifeActivityLimitConstraintIndices ( M ):
	indices = set(
	  (p, s, d, t, v, o)

	  for p, t, v in M.TechLifeFracIndices
	  for o in ProcessOutputs( p, t, v )
	  for s in M.time_season
	  for d in M.time_of_day
	)

	return indices


def CommodityBalanceConstraintIndices ( M ):
	indices = set(
	  (p, s, d, o)

	  for p in M.time_optimize
	  for t in M.tech_all
	  for v in ProcessVintages( p, t )
	  for i in ProcessInputs( p, t, v )
	  for o in ProcessOutputsByInput( p, t, v, i )
	  for s in M.time_season
	  for d in M.time_of_day
	)

	return indices


def ExistingCapacityConstraintIndices ( M ):
	indices = set(
	  (t, v)

	  for t in M.tech_all
	  for v in M.vintage_exist
	  if (t, v) in g_activeCapacityIndices
	)
	return indices


def ProcessBalanceConstraintIndices ( M ):
	indices = set(
	  (p, s, d, i, t, v, o)

	  for p in M.time_optimize
	  for t in M.tech_all
	  if t not in M.tech_storage
	  for v in ProcessVintages( p, t )
	  for i in ProcessInputs( p, t, v )
	  for o in ProcessOutputsByInput( p, t, v, i )
	  for s in M.time_season
	  for d in M.time_of_day
	)

	return indices


def StorageConstraintIndices ( M ):
	indices = set(
	  (p, s, i, t, v, o)

	  for p in M.time_optimize
	  for t in M.tech_storage
	  for v in ProcessVintages( p, t )
	  for i in ProcessInputs( p, t, v )
	  for o in ProcessOutputsByInput( p, t, v, i )
	  for s in M.time_season
	)

	return indices


def TechOutputSplitConstraintIndices ( M ):
	indices = set(
	  (p, s, d, i, t, v, o)

	  for i, t, o in M.TechOutputSplit.keys()
	  for p in M.time_optimize
	  for v in ProcessVintages( p, t )
	  for s in M.time_season
	  for d in M.time_of_day
	)

	return indices

# End constraints
##############################################################################

# End sparse index creation functions
##############################################################################

##############################################################################
# Helper functions

# These functions utilize global variables that are created in
# InitializeProcessParameters, to aid in creation of sparse index sets, and
# to increase readability of Coopr's often programmer-centric syntax.

def ProcessInputs ( p, t, v ):
	index = (p, t, v)
	if index in g_processInputs:
		return g_processInputs[ index ]
	return set()


def ProcessOutputs ( p, t, v ):
	"""\
index = (period, tech, vintage)
	"""
	index = (p, t, v)
	if index in g_processOutputs:
		return g_processOutputs[ index ]
	return set()


def ProcessInputsByOutput ( p, t, v, o ):
	"""\
Return the set of input energy carriers used by a technology (t) to
produce a given output carrier (o).
"""
	index = (p, t, v)
	if index in g_processOutputs:
		if o in g_processOutputs[ index ]:
			return g_processInputs[ index ]

	return set()


def ProcessOutputsByInput ( p, t, v, i ):
	"""\
Return the set of output energy carriers used by a technology (t) to
produce a given input carrier (o).
"""
	index = (p, t, v)
	if index in g_processInputs:
		if i in g_processInputs[ index ]:
			return g_processOutputs[ index ]

	return set()


def ProcessesByInput ( i ):
	"""\
Returns the set of processes that take 'input'.  Note that a process is
conceptually a vintage of a technology.
"""
	processes = set(
	  (t, v)

	  for p, t, v in g_processInputs
	  if i in g_processInputs[p, t, v]
	)

	return processes


def ProcessesByOutput ( o ):
	"""\
Returns the set of processes that take 'output'.  Note that a process is
conceptually a vintage of a technology.
"""
	processes = set(
	  (t, v)

	  for p, t, v in g_processOutputs
	  if o in g_processOutputs[p, t, v]
	)

	return processes


def ProcessesByPeriodAndInput ( p, i ):
	"""\
Returns the set of processes that operate in 'period' and take 'input'.  Note
that a process is conceptually a vintage of a technology.
"""
	processes = set(
	  (t, v)

	  for p, t, v in g_processInputs
	  if p == p
	  if i in g_processInputs[p, t, v]
	)

	return processes


def ProcessesByPeriodAndOutput ( p, o ):
	"""\
Returns the set of processes that operate in 'period' and take 'output'.  Note
that a process is a conceptually a vintage of a technology.
"""
	processes = set(
	  (t, v)

	  for p, t, v in g_processOutputs
	  if p == p
	  if o in g_processOutputs[p, t, v]
	)

	return processes


def ProcessVintages ( A_per, t ):
	index = (A_per, t)
	if index in g_processVintages:
		return g_processVintages[ index ]

	return set()


def ValidActivity ( p, t, v ):
	return (p, t, v) in g_activeActivityIndices


def ValidCapacity ( t, v ):
	return (t, v) in g_activeCapacityIndices


def isValidProcess ( p, i, t, v, o ):
	"""\
Returns a boolean (True or False) indicating whether, in any given period, a
technology can take a specified input carrier and convert it to and specified
output carrier.
"""
	index = (p, t, v)
	if index in g_processInputs and index in g_processOutputs:
		if i in g_processInputs[ index ]:
			if o in g_processOutputs[ index ]:
				return True

	return False


def loanIsActive ( p, t, v ):
	"""\
Return a boolean (True or False) whether a loan is still active in a period.
This is the implementation of imat in the rest of the documentation.
"""
	return (p, t, v) in g_processLoans


# End helper functions
##############################################################################

###############################################################################
# Miscellaneous routines

def parse_args ( ):
	import argparse

	parser = argparse.ArgumentParser()

	parser.add_argument('dot_dat',
	  type=str,
	  nargs='+',
	  help='AMPL-format data file(s) with which to create a model instance. '
	       'e.g. "data.dat"'
	)

	parser.add_argument( '--graph_format',
	  help='Create a system-wide visual depiction of the model.  The '
	       'available options are the formats available to Graphviz.  To get '
	       'a list of available formats, use the "dot" command: dot -Txxx. '
	       '[Default: None]',
	  action='store',
	  dest='graph_format',
	  default=None)

	parser.add_argument('--show_capacity',
	  help='Choose whether or not the capacity shows up in the subgraphs.  '
	       '[Default: not shown]',
	  action='store_true',
	  dest='show_capacity',
	  default=False)

	parser.add_argument( '--graph_type',
	  help='Choose the type of subgraph depiction desired. The available '
	       'options are "explicit_vintages" and "separate_vintages".  '
	       '[Default: separate_vintages]',
	  action='store',
	  dest='graph_type',
	  default='separate_vintages')

	parser.add_argument('--use_splines',
	  help='Choose whether the subgraph edges needs to be straight or curved.'
	       '  [Default: use straight lines, not splines]',
	  action='store_true',
	  dest='splinevar',
	  default=False)

	options = parser.parse_args()
	return options

# End miscellaneous routines
###############################################################################

###############################################################################
# Direct invocation methods (when modeler runs via "python model.py ..."

def temoa_solve ( model ):
	from sys import argv, version_info

	if version_info < (2, 7):
		msg = ("Temoa requires Python v2.7 to run.\n\nIf you've "
		  "installed Coopr with Python 2.6 or less, you'll need to reinstall "
		  'Coopr, taking care to install with a Python 2.7 (or greater) '
		  'executable.')
		raise SystemExit, msg

	from time import clock

	from coopr.opt import SolverFactory
	from coopr.pyomo import ModelData

	from pformat_results import pformat_results

	options = parse_args()
	dot_dats = options.dot_dat

	opt = SolverFactory('glpk')
	opt.keepFiles = False
	   # output GLPK LP understanding of model
	   #   Potentially want to incorporate this as an actual command line arg.
	# opt.options.wlp = path.basename( options.dot_dat[0] )[:-4] + '.lp'

	SE.write( '[        ] Reading data files.'); SE.flush()
	# Recreate the pyomo command's ability to specify multiple "dot dat" files
	# on the command line
	begin = clock()
	duration = lambda: clock() - begin

	mdata = ModelData()
	for f in dot_dats:
		if f[-4:] != '.dat':
			SE.write( "Expecting a dot dat (data.dat) file, found %s\n" % f )
			raise SystemExit
		mdata.add( f )
	mdata.read( model )
	SE.write( '\r[%8.2f\n' % duration() )

	SE.write( '[        ] Creating Temoa model instance.'); SE.flush()
	# Now do the solve and ...
	instance = model.create( mdata )
	SE.write( '\r[%8.2f\n' % duration() )

	SE.write( '[        ] Solving.'); SE.flush()
	result = opt.solve( instance )
	SE.write( '\r[%8.2f\n' % duration() )

	SE.write( '[        ] Formatting results.' ); SE.flush()
	# ... print the easier-to-read/parse format
	formatted_results = pformat_results( instance, result )
	SE.write( '\r[%8.2f\n' % duration() )
	SO.write( formatted_results )

	if options.graph_format:
		SE.write( '[        ] Creating Temoa model diagrams.' ); SE.flush()
		instance.load( result )
		CreateModelDiagrams( instance, options )
		SE.write( '\r[%8.2f\n' % duration() )

	if not ( SO.isatty() or SE.isatty() ):
		SO.write( "\n\nNotice: You are not receiving 'standard error' messages."
		  "  Temoa uses the 'standard error' file to send meta information "
		  "on the progress of the solve.  If you aren't intentionally "
		  "ignoring standard error messages, you may correct the issue by "
		  "updating coopr/src/coopr.misc/coopr/misc/scripts.py as per this "
		  "coopr changeset: "
		  "https://software.sandia.gov/trac/coopr/changeset/5363\n")


# End direct invocation methods
###############################################################################
