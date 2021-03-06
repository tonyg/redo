#!/usr/bin/env python2
#
# Copyright 2010-2018 Avery Pennarun and contributors
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import sys, os, traceback
import options
from helpers import atoi

optspec = """
redo [targets...]
--
j,jobs=    maximum number of jobs to build at once
d,debug    print dependency checks as they happen
v,verbose  print commands as they are read from .do files (variables intact)
x,xtrace   print commands as they are executed (variables expanded)
k,keep-going  keep going as long as possible even if some targets fail
shuffle    randomize the build order to find dependency bugs
no-details only show 'redo' recursion trace (to see more later, use redo-log)
no-status  don't display build summary line at the bottom of the screen
no-log     don't capture error output, just let it flow straight to stderr
no-pretty  don't pretty-print logs, show raw @@REDO output instead
no-color   disable ANSI color; --color to force enable (default: auto)
debug-locks  print messages about file locking (useful for debugging)
debug-pids   print process ids as part of log messages (useful for debugging)
version    print the current version and exit
"""
o = options.Options(optspec)
(opt, flags, extra) = o.parse(sys.argv[1:])

targets = extra

if opt.version:
    import version
    print version.TAG
    sys.exit(0)
if opt.debug:
    os.environ['REDO_DEBUG'] = str(opt.debug or 0)
if opt.verbose:
    os.environ['REDO_VERBOSE'] = '1'
if opt.xtrace:
    os.environ['REDO_XTRACE'] = '1'
if opt.keep_going:
    os.environ['REDO_KEEP_GOING'] = '1'
if opt.shuffle:
    os.environ['REDO_SHUFFLE'] = '1'
if opt.debug_locks:
    os.environ['REDO_DEBUG_LOCKS'] = '1'
if opt.debug_pids:
    os.environ['REDO_DEBUG_PIDS'] = '1'

# This is slightly tricky: the log and pretty options default to true.  We
# want to inherit that 'true' value from parent processes *unless* someone
# explicitly specifies the reverse.
if opt.no_log:
    os.environ['REDO_LOG'] = '0'
    if opt.no_pretty:
        os.environ['REDO_PRETTY'] = '0'
    if opt.no_color:
        os.environ['REDO_COLOR'] = '0'

import vars_init
vars_init.init(targets)

import vars, state, builder, jwack
from logs import warn, err

try:
    if vars_init.is_toplevel:
        builder.start_stdin_log_reader(status=opt.status, details=opt.details,
            pretty=opt.pretty, color=opt.color,
            debug_locks=opt.debug_locks, debug_pids=opt.debug_pids)
    for t in targets:
        if os.path.exists(t):
            f = state.File(name=t)
            if not f.is_generated:
                warn('%s: exists and not marked as generated; not redoing.\n'
                     % f.nicename())
    state.rollback()
    
    j = atoi(opt.jobs or 1)
    if j < 1 or j > 1000:
        err('invalid --jobs value: %r\n' % opt.jobs)
    jwack.setup(j)
    try:
        assert(state.is_flushed())
        retcode = builder.main(targets, lambda t: (True, True))
        assert(state.is_flushed())
    finally:
        try:
            state.rollback()
        finally:
            try:
                jwack.force_return_tokens()
            except Exception, e:
                traceback.print_exc(100, sys.stderr)
                err('unexpected error: %r\n' % e)
                retcode = 1
    if vars_init.is_toplevel:
        builder.await_log_reader()
    sys.exit(retcode)
except KeyboardInterrupt:
    if vars_init.is_toplevel:
        builder.await_log_reader()
    sys.exit(200)
