#!usr/bin/env python
# -*- coding: utf-8 -*-

import pprint

l = []
pprint.pprint("Nothing")
pprint.pprint(l)

l.append( {"status":"off", "zoom":100, "corr":99} )
l.append( {"status":"2h ", "zoom":100, "corr":50} )
l.append( {"status":"4h ", "zoom":100, "corr":80} )
print( "\n\nAdded" ) 
pprint.pprint( l )

print( "\n\nSorted" ) 
pprint.pprint( sorted(l, key=lambda x:x["corr"]) )




#d = dict(sorted(d.items(), key=lambda x:x[1]))
#print( f"Sorted:{d}" )
