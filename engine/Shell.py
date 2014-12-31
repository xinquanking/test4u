#! /usr/bin/env python
#coding=utf-8
from TestUtil import printLog
from subprocess import Popen, PIPE, call
import logging

class Shell(object):
    def __init__(self):
        pass

    '''
    used to get the command output
    '''
    def runShellCmd(self, cmd):
        printLog("[runShellCmd] Running cmd:"+ cmd)
        try:
            p=Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
            out, err=p.communicate()
            printLog("[runShellCmd] Command returns:\noutput:%s\n" % out)
            if len(err)>0:
                printLog("[runShellCmd] error:%s" % err, logging.ERROR)
        except:
            printLog("[runShellCmd] Exception when run cmd '%s'." % cmd, logging.ERROR)
            return None
        return out

    '''
    used to determine if the command succeed
    '''
    def callShellCmd(self, cmd):
        printLog("[callShellCmd] Running cmd:"+ cmd)
        if call(cmd, shell=True)==0:
            printLog("[callShellCmd] Command succeed. returns 0")
            return True
        else:
            printLog("[callShellCmd] Failed to execute command '%s'." % cmd, logging.ERROR)
            return False
