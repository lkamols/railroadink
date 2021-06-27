# -*- coding: utf-8 -*-
"""
Created on Sun Jun 27 10:36:30 2021

@author: Luke Kamols
"""

import json

def a(b, c=5):
    print(b, c)
    
def k(**kwargs):
    a(**kwargs)
    
if __name__ == "__main__":
    args = {"b" : 3}
    k(**args)
    with open('settings.txt') as f:
        data = json.load(f)
   
    print(data['BASE'])
    print(data['TURN 5'])
    
    #with open('s.txt', 'w') as configFile:
    #    config.write(configFile)