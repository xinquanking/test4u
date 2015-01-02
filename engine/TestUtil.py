#! /usr/bin/env python
#coding=utf-8
from __future__ import with_statement
from os import path, sep
import threading
import logging

## !!DO NOT CHANGE BELOW PARAMETERS !! ##
H_LINE="----------------------------------------------------------------------\
-----------------------------------------"
TC_SUBDIR='testcase'
TS_SUBDIR='suite'
SETUP_SUBDIR='setup'
SNAPSHOT_SUBDIR='snapshot'
LOGS_SUBDIR='logs'
TESTDATA_SUBDIR='testdata'
EXT_TEST_SUITE='.ts'
EXT_TEST_CASE='.t4u'
MONKEYLOG_FILE='monkey.txt'
TESTER_DEBUG_LOG_FILE='debug_log.txt'
ADBLOG_FILE='logcat.log'
CONFIG_FILE='t4uenv.ini'
TESTCASE_SECTION_SETUP='@SETUP'
TESTCASE_SECTION_VALIDATION='@VALIDATION'
TESTCASE_SECTION_TEARDOWN='@TEARDOWN'

## configurables
import ConfigParser
config = ConfigParser.ConfigParser()
config.readfp(open(CONFIG_FILE))

MAIL_SERVER_ADDRESS = config.get('MAIL', 'MAIL_SERVER_ADDRESS').strip()
if MAIL_SERVER_ADDRESS.strip()=='':
    raise ValueError('MAIL_SERVER_ADDRESS is not properly configured!')
MAIL_SENDER_ADDRESS = config.get('MAIL', 'SENDER_ADDRESS').strip()
if MAIL_SENDER_ADDRESS.strip()=='':
    raise ValueError('MAIL_SENDER_ADDRESS is not properly configured!')
MAIL_SENDER_PASSWORD = config.get('MAIL', 'SENDER_PASSWORD').strip()
if MAIL_SENDER_PASSWORD.strip()=='':
    raise ValueError('MAIL_SENDER_PASSWORD is not properly configured!')
MAIL_ADMIN_ADDRESS = config.get('MAIL', 'ADMIN_ADDRESS').strip()
if MAIL_ADMIN_ADDRESS.strip()=='':
    raise ValueError('MAIL_ADMIN_ADDRESS is not properly configured!')
GREEN_RECEIVERS = config.get('MAIL', 'GREEN_RECEIVERS').strip().split(',')
YELLOW_RECEIVERS = config.get('MAIL', 'YELLOW_RECEIVERS').strip().split(',')
if len(YELLOW_RECEIVERS)==0:
    YELLOW_RECEIVERS=[MAIL_ADMIN_ADDRESS]
RED_RECEIVERS = config.get('MAIL', 'RED_RECEIVERS').strip().split(',')
if len(RED_RECEIVERS)==0:
    RED_RECEIVERS=[MAIL_ADMIN_ADDRESS]
APP_NAME=config.get('APP', 'APP_NAME').strip()
APP_PKG_NAME=config.get('APP', 'APP_PKG_NAME').strip()
APPLOG_FILE=config.get('APP', 'APPLOG_FILE').strip()

DEFAULT_TEST_SUITE=config.get('TEST', 'DEFAULT_TEST_SUITE').strip()
CRITICAL_TESTCASES=config.get('TEST', 'CRITICAL_TESTCASES').strip().split(',')
THREAD_WAIT_INTERVAL = config.get('TEST', 'THREAD_WAIT_INTERVAL').strip()
if not THREAD_WAIT_INTERVAL.strip().isDigit():
    raise ValueError('THREAD_WAIT_INTERVAL is not properly configured!')
#    return False
UPGRADE_APP_ON_TEST_START=False
LOG_LEVEL=logging.DEBUG     # control the current log level

def createLogger(buildnum):
    logging.basicConfig(\
        level    = LOG_LEVEL,\
        format   = '%(asctime)s %(levelname)-8s %(message)s',\
        datefmt  = '%m-%d %H:%M:%S',\
        filename = TESTER_DEBUG_LOG_FILE,\
        filemode = 'w')
    logger=logging.getLogger(str(buildnum)) # Oct 21: need to assign a different logger id each time, otherwise it will use the existing one which will be closed at the end of run()
    handler=logging.FileHandler(TESTER_DEBUG_LOG_FILE)
    logger.addHandler(handler)
    return handler

def printLog(content, loglevel=logging.DEBUG):
    if loglevel>=LOG_LEVEL:
        level={
            logging.DEBUG:'DEBUG',
            logging.INFO:'INFO',
            logging.WARNING:'WARNING',
            logging.ERROR:'ERROR',
            logging.CRITICAL:'CRITICAL',
            logging.FATAL:'FATAL'            
            }[loglevel]
        getattr(logging, level.lower())(content)
#        print("{0: ^5} {1}".format(level,content))
        print("%-8s %s" % (level,content))


#http://stackoverflow.com/questions/36932/how-can-i-represent-an-enum-in-python?rq=1
#from enum import Enum
#TestStatus = Enum('TestStatus', 'NotRun Running Pass Fail')
class TestStatus(object):
    NotRun='Not Run'
    Running='Running'
    Pass='Pass'
    Fail='Fail'

class TestCase(object):

    def __init__(self, tcname, suite, steps, desc='', jid=''):
        self.name=tcname
        self.path=suite+sep+tcname+EXT_TEST_CASE
        self.desc=desc
        assert (type(steps)==type([1,2]))
        self.steps=steps
        # extract the steps for teardown, which are used to ensure tear down is completed even if the testcase fails
        self.teardownSteps=self.steps[self.steps.index("@TEARDOWN"):]
        self.result=TestStatus.NotRun
        self.jiraId=jid
        self.start_time=0
        self.end_time=0
        self.requiredDevicePara=''

        self.line=0
        self.preline=0
        self.cmd=''
        self.precmd=''
        self.errormsg=''
        self.crash=False

class TestSuite(object):
    def __init__(self, suite):
        self.suiteName=suite
        self.queue= []
        self.__readTestSuite()
        self.mutex = threading.Lock()
#        self.device=''    # used to tell on which device the testcase was executed

    def __validateTestCase(self, lines, t4uFilename):
        ret=True
        try:
            lines.index(TESTCASE_SECTION_SETUP) & lines.index(TESTCASE_SECTION_VALIDATION) & lines.index(TESTCASE_SECTION_TEARDOWN)
        except AssertionError:
            print("Missing or bad step value in %s." % t4uFilename)
            ret=False
        except ValueError:
            print("Missing or bad section annotation value in %s." % t4uFilename)
            ret=False
        return ret

    def __readTestSuite(self):
        # read the test case list from configuration file and save it to testset
        testSuiteFile=self.suiteName+EXT_TEST_SUITE
        try:
#            tsFilePath=path.abspath('')+sep+testSuiteFile
            tsFilePath=path.join(TS_SUBDIR, testSuiteFile)
            printLog('[readTestSuite] Reading testcase from file %s...' % tsFilePath)
            with open(tsFilePath) as fd:
                content=filter(lambda x: not x.startswith('#') and not x.startswith('\n'), fd.readlines())
                #print content
                testlist=map(lambda x: [x.split(':',1)[0].strip(), x.split(':',1)[1].strip()], content)
                #print testlist
                for test in testlist:
                    printLog('[readTestSuite] adding testcase %s to pool...' % test[0])
                    scptfilename=TC_SUBDIR+'/'+test[0]+EXT_TEST_CASE
#                    dirName, tcName=scptfilename.split('/')
                    try:
                        with open(scptfilename) as sf:
                            lines=map(lambda x:x.strip().strip('\t'), sf.readlines())
                    except Exception, e:
                        printLog("[readTestSuite] Error open and read file %s: %s" % (scptfilename,e.message), logging.ERROR)
                        raise ValueError('Failed to read testcase.')
#                        testcase.cmd=(0, 'open and read script file %s' % scptfilename)
#                        testcase.errormsg="Exception open and read file: %s" % e.message
                    if self.__validateTestCase(lines, scptfilename):
                        tmpTest=TestCase(test[0], self.suiteName, lines, test[1])
                        self.queue.append(tmpTest)
                    else:
                        continue
                #self.testPool=map(lambda x:x.strip(),content)
                self.Total=len(self.queue)
        except IOError, e:
            printLog('File %s open error.' % testSuiteFile, logging.ERROR)
            raise ValueError('Failed to read testcase.')
        except IndexError, e:
            printLog('File %s format error. reason is %s' % (testSuiteFile, e.message), logging.ERROR)
            raise ValueError('Failed to read testcase.')
        printLog('[readTestSuite] %d testcase read...' % (self.Total))
        return True

    def getTestCase(self):
        #TODO: consider using a generator (yield)
        case = None
        for tc in self.queue:
            if tc.result==TestStatus.NotRun:
                #TODO: check the device requirements
                tc.result=TestStatus.Running
                case= tc
                break
        return case

    def getTestCaseByName(self, tcname):
        case = None
        for tc in self.queue:
            if tc.name==tcname:
                case= tc
                break
        return case

    def resetTestStatus(self):
        for tc in self.queue:
        	tc.result=TestStatus.NotRun
        	tc.crash=False

    def setTestResult(self, case):
        tc=self.getTestCaseByName(case.name)
        tc=case

    def printTestResult(self):
        splitter="============================================================================================================================"
        print("\n"+splitter)
        print("%-60s%11s" % ('Testcase', 'Test Result'))
        for tc in self.queue:
            print("%-60s%11s" % (tc.name, tc.result))
        print(splitter+"\n")

    def getTotalCount(self):
        return len(self.queue)
    
    def getPassCount(self):
        num=0
        num=len(filter(lambda x:x.result==TestStatus.Pass, self.queue))
#        for tc in self.queue:
#            if tc.result==TestStatus.Pass:
#                num+=1
        return num
    
    def getFailCount(self):
        num=len(filter(lambda x:x.result==TestStatus.Fail, self.queue))
#        for tc in self.queue:
#            if tc.result==TestStatus.Fail:
#                num+=1
        return num

    def isFatalErrorHappened(self, tcNameTuple):
        '''
        used to determine the test status and inject a status code in test report
        '''
        if len(self.queue)==0:
#            raise ValueError('Please invoke Tester.run() before execute this method.')
            return False
        for tc in self.queue:
            if tc.crash:
                return True
            if tc.result=='FAIL':
                if tc.name in tcNameTuple:
                    return True
        return False
