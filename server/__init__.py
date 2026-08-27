"""LineTwin.ai FastAPI layer: a thin, read-mostly JSON wrapper around the
existing simulation + analytics code. This module adds no inference logic of
its own and never writes to any plant system (there is deliberately no path to
do so - see app.analytics.whatif.PLCAdapter)."""
