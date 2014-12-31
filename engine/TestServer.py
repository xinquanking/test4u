#! /usr/bin/env python
#coding=utf-8

from TestUtil import printLog
from Shell import Shell

class TestServer(Shell):
    
    def __init__(self):
        Shell.__init__(self)
    
    def getDeviceIdList(self):
        cmd=r"adb devices|awk -F'\t' '{print $1}'"
        devices=self.runShellCmd(cmd)
        deviceIdList=filter(lambda x: not len(x)==0, devices.splitlines()[1:]) #.split('\t',1)[0]
        printLog('List of devices attached: \n'+ str(deviceIdList))
        return deviceIdList
    
    def getHostname(self):
        return self.runShellCmd(r"hostname")
    
