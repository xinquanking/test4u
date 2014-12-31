#! /usr/bin/env python
#coding=utf-8

from os import sep
import logging
import time
import threading
import copy

from TestUtil import printLog, TestStatus, H_LINE, SNAPSHOT_SUBDIR
from TestServer import TestServer
from AndroidDevice import AndroidDevice

class TestEngine(AndroidDevice, threading.Thread):

    def __init__(self, build_num, test_suite, device_id):
        # get idle device
        self.buildnum = build_num
        self.testSuite = copy.deepcopy(test_suite)
        self.testServer = TestServer()
        AndroidDevice.__init__(self, device_id)
#        self.device = AndroidDevice(device_id)
        self.crash = False
        self.threadName='<'+self.model+'_'+self.deviceId+'>  '
        threading.Thread.__init__(self)#, name=self.device.model+'_'+self.device.deviceId)
        if not self.resultFlag:
#            self.devicePool.releaseDevice(self.device.deviceId)
            assert False

    def __del__(self):
        AndroidDevice.__del__()

    '''
    split the input string by space and return the method name and the following arguments
    used by AppTestEngine
    '''
    def __getMethod(self, str):
        list = str.split(' ',1)
        if len(list)==1:
            return [list[0],'']
        else:
            return list

    def __getFailedAction(self, cmds, failedLine):
        if failedLine<=2: return (0,cmds[0])
        ignoreMethodList=['sleep', 'assert']
        tmpLine=failedLine-1
        tmpCmd=cmds[tmpLine-1]
        while (tmpCmd.startswith('#') or tmpCmd.strip()=='' or self.__getMethod(tmpCmd)[0] in ignoreMethodList):
            tmpLine-=1
            if tmpLine==0: break
            tmpCmd=cmds[tmpLine-1]
    #		print 'Found command: %d, %s' % (tmpLine, tmpCmd)
        return (tmpLine, tmpCmd)

    def __executer(self, testcase):
        '''
        test case executor: read and execute command written in the test script file
        return: boolean
        add paramter 'testcase' to return failure details (Jun 25)
        '''
        # take a snapshot before executing the case
        self.do_takesnapshot(''.join((SNAPSHOT_SUBDIR,sep,testcase.name,'_start.png')))
        
        line_number=0
        for step in testcase.steps:
            line_number+=1
            #printLog('line len:%d' % len(step))
            if len(step)<2:
                #skip blank lines
                continue
            if step.startswith("#") or step.startswith("@"):
                # lines starts with "#" or "@" are test step remarks or section indicator. print them out.
                printLog(self.threadName+'###'+step.strip())
                continue
            printLog(self.threadName+"[cmd at line %d: %s]" % (line_number,step.strip()), logging.INFO)
            # save current command and previous command
            testcase.precmd=testcase.cmd
            testcase.cmd=(line_number, step.strip())
            time.sleep(self.INTERVAL)

            # execute the command read from test script(*.ini).
            try:
                method, args=self.__getMethod(step)
                if len(method)==0: continue
                if not method=='assert':
                    self.resultFlag=True
                    self.crash = False
                getattr(self, ''.join(('do_',method)))(args.strip()) # include the arg string for backward compatibility, Feb 18, 2014
                if self.crash:
                    printLog(self.threadName+'APP CRASH DETECTED BY ENGINE!', logging.CRITICAL)
    #                    testcase.cmd=__getFailedAction(lines, testcase.precmd[0])
                    testcase.crash=True
                    testcase.errormsg='APP CRASHED! Line %d: "%s"' % (testcase.cmd[0], testcase.cmd[1])
                if not self.resultFlag and method=='assert':
    #                    print testcase.cmd
                    printLog(self.threadName+'APP FAILURE DETECTED BY ENGINE.', logging.ERROR)
                    testcase.cmd=self.__getFailedAction(testcase.steps,line_number)
                    testcase.errormsg='Error at Line %d: "%s"' % (testcase.cmd[0], testcase.cmd[1])
                    break
            except AttributeError, e:
                testcase.errormsg="Script AttributeError: %s" % (e.message)
                printLog(self.threadName+testcase.errormsg, logging.ERROR)
                self.resultFlag=False
                break
            except ValueError, e:
                testcase.errormsg="Script ValueError: %s" % (e.message)
                printLog(self.threadName+testcase.errormsg, logging.ERROR)
                self.resultFlag=False
                break
            except IndexError, e:
                testcase.errormsg="Script IndexError: %s" % (e.message)
                printLog(self.threadName+testcase.errormsg, logging.ERROR)
                self.resultFlag=False
                break
        printLog(H_LINE)
        if self.resultFlag:
            printLog(self.threadName+'[%s PASS]\n' % testcase.name, logging.INFO)
        else:
            printLog(self.threadName+'[%s FAIL] Failed Step: Line %d, %s' % (testcase.name, testcase.cmd[0], testcase.cmd[1]), logging.INFO)
            # take snapshot before running teardown
            self.do_takesnapshot(''.join((SNAPSHOT_SUBDIR,sep,testcase.name,'_fail.png')))
            # Jul 4, 2014: run the steps in TEARDOWN section to ensure a complete tear down
            for step in testcase.teardownSteps:
                line_number=testcase.steps.index('@TEARDOWN')+1
                if step.startswith("#") or step.startswith("@"):
                    # lines starts with "#" or "@" are test step remarks or section indicator. print them out.
                    printLog(self.threadName+'###'+step.strip())
                    continue
                printLog(self.threadName+"[cmd at line %d: %s]" % (line_number,step.strip()), logging.INFO)
                try:
                    method, args=self.__getMethod(step)
                    if len(method)==0: continue
                    getattr(self, ''.join(('do_',method)))(args.strip()) # include the arg string for backward compatibility, Feb 18, 2014
                except Exception, e:
                    printLog(self.threadName+"Exception in tear down: %s" % e.message, logging.ERROR)
                    self.resultFlag=False
                    break

        return self.resultFlag

    '''
    multi-thread supported, DO NOT RENAME
    '''
    def run(self):
        printLog(H_LINE)
        printLog(self.threadName+"started...")
        if self.testSuite.mutex.acquire(1):
            testcase=self.testSuite.getTestCase()
            self.testSuite.mutex.release()
        if not testcase:
            printLog(self.threadName+"No testcase unexecuted, terminate.")
#            self.devicePool.releaseDevice(self.device.deviceId)
            return
        # execute each testcase in the testSuite
        while testcase:
            testcase.device=self.make+' '+self.model + ' '+ self.deviceId
            printLog(H_LINE)
            printLog(self.threadName+"test %s started..." % (testcase.name), logging.INFO)
            # Jul 16: get test start time
            testcase.start_time=time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))
            # execute testcase
            ret=self.__executer(testcase)
            # Jul 16: get test end time
            testcase.end_time=time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))
            if ret:
                printLog(self.threadName+'Testcase %s Passed.' % (testcase.name))
                testcase.result=TestStatus.Pass
            else:
                printLog(self.threadName+'Testcase %s Failed.' % (testcase.name), logging.ERROR)
                testcase.result=TestStatus.Fail
    #            printLog(self.threadName+'Test device is: %s' % testcase.device)
            logging.info(H_LINE)
            # take snapshot for later debug
    #            self.do_takesnapshot(''.join((SNAPSHOT_SUBDIR,sep,testcase.name,'_end.png')))

            if self.testSuite.mutex.acquire(1):
                testcase=self.testSuite.getTestCase()
                self.testSuite.mutex.release()
        printLog(self.threadName+"No testcase unexecuted, terminate.")
#        self.devicePool.releaseDevice(self.device.deviceId)

