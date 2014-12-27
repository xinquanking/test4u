#! /usr/bin/env monkeyrunner
#coding=utf-8
from __future__ import with_statement
import sys
import logging
from os import path, sep, remove
from subprocess import Popen, PIPE # the default jython included in android sdk does not support check_output

from engine.Tester import Tester
from engine.TestServer import TestServer
from engine.AppTestEngine import AppTestEngine
#from engine.Android import callCmd
from engine.TestUtil import printLog, DEFAULT_TEST_SUITE, TestStatus,APP_NAME, H_LINE, \
                            GREEN_RECEIVERS, YELLOW_RECEIVERS, RED_RECEIVERS, \
                            CRITICAL_TESTCASES, CONFIG_FILE
from pyh import PyH, h3, h4, div, p, table, td, tr

## configurables
import ConfigParser
config = ConfigParser.ConfigParser()
config.readfp(open(CONFIG_FILE))

CLIENT_VERSION_PREFIX=config.get('BUILD', 'CLIENT_VERSION_PREFIX')
BUILD_VERSION=config.get('BUILD', 'BUILD_VERSION')
BUILD_FILENAME=config.get('BUILD', 'BUILD_FILENAME')
# build path info
BUILD_ROOT_PATH = config.get('BUILD', 'BUILD_ROOT_PATH')
#BUILD_LOCAL_ROOT_PATH = config.get('BUILD', 'BUILD_LOCAL_ROOT_PATH')


class AppTester(Tester):

	def __init__(self, suite_name=DEFAULT_TEST_SUITE, build_num='latest'):
		Tester.__init__(self, suite_name, build_num)
		if self.initOK:
			pass

	def __writeHtmlTestResult(self):
		content_format="%-*s%-*s%*s%*s%*s"
		content_format2="%-*s%*s" # '-' means left just (right just by default) http://www.cnblogs.com/zero86/archive/2012/11/22/2783679.html
		content_format3="%-*s%*d"
		self.Total=self.testPool.getTotalCount()
		self.Pass=self.testPool.getPassCount()
		self.Fail=self.testPool.getFailCount()
		## create HTML content
		page = PyH('Test Result')
		page << h3('Overall Result:')
#		table0 = page << table(border='0',id='table_overall')
#		tmpRow = table0 << tr(id='line1')
#		tmpRow << td("Total:") <<td(str(self.Total))
#		tmpRow = table0 << tr(id='line2')
#		tmpRow << td("Pass:") <<td(str(self.Pass))
#		tmpRow = table0 << tr(id='line3')
#		tmpRow << td("Fail:") <<td(str(self.Fail))
#		tmpRow = table0 << tr(id='line4')
#		tmpRow << td("Not Run:") <<td(str(self.Total-self.Pass-self.Fail))
		page << p(content_format3 % (10, 'Total:' , 5, self.Total))
		page << p(content_format3 % (10, 'Pass:' , 5, self.Pass))
		page << p(content_format3 % (10, 'Fail:' , 5, self.Fail))
		page << p(content_format3 % (10, 'Not Run:' , 5, self.Total-self.Pass-self.Fail))
		if self.Fail>0:
			page << h3('Failed Testcase:',style='color:red;')
			table1 = page << table(border='1',cellPadding='5',id='table_failedTest')
			headtr = table1 << tr(id='headline1')
			headtr << td('Test Name') << td('Failure Description') << td('Device')<< td('Start Time')<< td('End Time')

			for tc in self.testPool.queue:
				if tc.result == TestStatus.Fail:
					tmpRow = table1 << tr(id='line1')
					tmpRow << td(tc.name) <<td(tc.errormsg)<<td(tc.device)<<td(tc.start_time)<<td(tc.end_time)
#					page << content_format % (25, tc.name, 45, '\t'+tc.errormsg, 30, '\t'+tc.device, 20, '\t'+tc.start_time, 20, '\t'+tc.end_time)
#			page << H_LINE
		if self.Pass>0:
			page << h3('Passed Testcase:',style='color:green;')
			table2 = page << table(border='1',cellPadding='5',id='table_passedTest')
			headtr = table2 << tr(id='headline2')
			headtr << td('Test Name') << td('Test Description') << td('Device')<< td('Start Time')<< td('End Time')
#			page << content_format % (25, 'Test Name', 45, 'Test Description', 30, "\tDevice", 20, "\tStart Time", 20, "\tEnd Time")
#			page << H_LINE
			for tc in self.testPool.queue:
				if tc.result == TestStatus.Pass:
					tmpRow = table2 << tr(id='line2')
					tmpRow << td(tc.name) <<td(tc.desc)<<td(tc.device)<<td(tc.start_time)<<td(tc.end_time)
#					page << content_format % (25, tc.name, 45, tc.desc, 30, '\t'+tc.device,20, '\t'+tc.start_time, 20, '\t'+tc.end_time)

		## Test time
		mydiv2 = page << div(id='myDiv2')
		mydiv2 << h4('Test build:')+ p(CLIENT_VERSION_PREFIX+str(self.buildnum))
		mydiv2 << h4('Test start:')+ p(self.start_time)
		mydiv2 << h4('Test stop: ')+ p(self.end_time)

		## host info
		mydiv2 << h4('Test Server:  ')+ p(TestServer().getHostname())
#		page << h4(content_format2 % (11, 'Test start:', 30, self.start_time), cl='left')
#		page << h4(content_format2 % (11, 'Test stop: ', 30, self.end_time), cl='left')
#		page << h4(content_format2 % (11, 'Build:', 30, CLIENT_VERSION_PREFIX+str(self.buildnum)), cl='left')
		## Test device
		mydiv2 << h4('Test Devices:')
		count=0
		table_device = mydiv2 << table(cellSpacing='1', cellPadding='5', border='1',borderColor='#666666', id='table_device')
		table_device.attributes['cellSpacing'] = 1

		headtr = table_device << tr(id='headline5')
		headtr << td('No.') << td('Make') << td('Model') << td('Android Version') << td('ID')
		for device in self.devicePool.queue:
			count+=1
			tmpRow = table_device << tr(id='line1')
			tmpRow << td(str(count)) <<td(device.make)<<td(device.model)<<td(device.androidVersion)<<td(device.deviceId)
#			page << h5(content_format2 % (11, 'Device'+str(count)+":\t", 50, \
#			device.make+' '+device.model+' '+device.androidVersion+' ' + device.deviceId))
		## write file
		page.printOut(file=self.suiteName+'.html')
		

	def getBuild(self):
		'''
		# implement: get build from mainline/release server
		'''
		result=False
		## remove any existing build file
		if path.isfile(BUILD_FILENAME):
			remove(BUILD_FILENAME)
		if self.buildnum=='latest':
			self.buildnum=AppTestEngine.getLatestBuildNumber()
		if self.buildnum==0:
			printLog('[getBuild] invalid build number specified or build location not accessible.', logging.ERROR)
			return result
		#TODO: customize the target file path
		target=BUILD_ROOT_PATH+sep+BUILD_VERSION+sep+APP_NAME+'-'+str(self.buildnum)+sep+BUILD_FILENAME
		printLog('[getBuild] Downloading build %s from %s...' % (str(self.buildnum), target), logging.INFO)
		try:
			self.testServer.callShellCmd(r'cp '+target+' .')
			if path.isfile(BUILD_FILENAME):
				printLog('[getBuild] Build %s is downloaded.' % str(self.buildnum), logging.INFO)
				result=True
		except IOError, e:
			printLog('[getBuild] Build %s download failed: %s' % e.message, logging.ERROR)
#			self.appTestEngine.buildnum=0
		return result

#	def generateTestReport(self):
#        # TODO: customize your own report
#		self.__writeHtmlTestResult()


    

def main(argv):
    '''
    @param argv include:
    1. the test suite name(optional). e.g. unittest (if test suite not provided, use the default test suite)
    2. build number
    '''
    print H_LINE
    buildnum='latest'
    suite=DEFAULT_TEST_SUITE
    if len(argv) >= 2:
        if argv[1]=='-h':
            print 'Usage: AppTester.py [suite] [buildnum]'
            return
        suite=argv[1]
        print '[Main] Test suite specified:', suite
    else:
        print '[Main] Test suite not specified, use default test suite:', suite

    if len(argv) >= 3:
        buildnum=argv[2]
        print '[Main] Build number specified:', buildnum
        if not buildnum.isdigit() and buildnum != 'latest':
            print '[Main] Invalid build number! Quit...'
            return
    else:
        print '[Main] Build number not specified, use latest build.'

    print H_LINE
    tester = AppTester(suite, buildnum)
    if tester.initOK:
        tester.getBuild()
        ret=tester.start()
    else:
        print('[Main] Tester init failed.')
        return
#    to=[MAIL_ADMIN_ADDRESS]
    prefix='Automation Test - %s %s (build %s%d)' % (APP_NAME, suite, CLIENT_VERSION_PREFIX, tester.buildnum)
    subject=''
    do_deploy=True
    DO_SEND_MAIL=False
    status=''
    if ret<0:
        print('Test aborted!')
        status='RED'
        subject=prefix+r': RED (Test aborted! PLEASE CHECK THE TEST SERVER!)'
        to=RED_RECEIVERS

    elif ret==0 and len(tester.exception_string) <= 0:
        print 'All Test PASS!'
        status='GREEN'
        subject='%s: GREEN'% (prefix)
        to=GREEN_RECEIVERS
        DO_SEND_MAIL=False
    elif tester.testPool.isFatalErrorHappened(CRITICAL_TESTCASES):
        print 'Test has fatal error!'
        status='RED'
        subject='%s: RED (Found fatal error)'% (prefix)
        to=RED_RECEIVERS
        do_deploy=False
    elif float(ret)/float(tester.Total) >= 0.5:
        status='RED'
        print 'Test has failures (Fail: %d of %d)' % (ret, tester.Total)
        subject='%s: RED (Fail: %d of %d)'% (prefix, ret, tester.Total)
        to=RED_RECEIVERS
    else:
        status='YELLOW'
        print 'Test has failures (Fail: %d of %d)' % (ret, tester.Total)
        subject='%s: YELLOW (Fail: %d of %d)'% (prefix, ret, tester.Total)
        to=YELLOW_RECEIVERS
    ## do deploy
#	if do_deploy:
		#TODO: implement the deploy logic
    if DO_SEND_MAIL:
        try:
            print('[Main] mail subject: %s' % subject)
            cmd=' '.join('python', 'mail.py', suite, buildnum, status)
            try:
                p=Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
                out, err=p.communicate()
                printLog("[runShellCmd] Command returns:\noutput:%s\n" % out)
                if len(err)>0:
                    printLog('[runShellCmd] error:%s' % err, logging.ERROR)
            except:
                printLog("[runShellCmd] Exception when run cmd '%s'." % cmd, logging.ERROR)
                return None		
            tester.sendmail(subject, to)
        except Exception, e:
    #		print '[Main] Exception during mail send:%s' % (e.message)
            pass

if __name__ == "__main__":
    main(sys.argv)
