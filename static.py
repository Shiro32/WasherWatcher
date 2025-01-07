#!usr/bin/env python
# -*- coding: utf-8 -*-

def static_sample():
	static_sample.counter += 1

	print( static_sample.counter )


static_sample.counter = -10

static_sample()
static_sample()
static_sample()
static_sample()
static_sample()

