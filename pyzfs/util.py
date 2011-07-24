#!/usr/bin/env python

import subprocess

debug = 2
null = open('/dev/null','w')

def Popen(*args, **kwargs):
    if debug:
        print 'Popen: ',args,kwargs
    if debug < 2:
        for pipe in ['stdout','stderr']:
            if pipe not in kwargs:
                kwargs[pipe] = null
    return subprocess.Popen(*args, **kwargs)

def call(*args, **kwargs):
    if debug:
        print 'call: ',args,kwargs
    if debug < 2:
        for pipe in ['stdout','stderr']:
            if pipe not in kwargs:
                kwargs[pipe] = null
    return subprocess.call(*args, **kwargs)

