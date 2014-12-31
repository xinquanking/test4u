#! /usr/bin/env monkeyrunner

from __future__ import with_statement

import time
import logging
import java.lang
import threading
import traceback
from os import path, remove, getcwd, mkdir, listdir

from TestServer import TestServer
from AppTestEngine import AppTestEngine, BUILD_VERSION, CLIENT_VERSION_PREFIX
from TestUtil import printLog, createLogger, TestStatus, TestSuite, H_LINE, \
					TC_SUBDIR, SNAPSHOT_SUBDIR, \
					MAIL_SERVER_ADDRESS, MAIL_SENDER_ADDRESS, MAIL_SENDER_PASSWORD, MAIL_ADMIN_ADDRESS, \
					MONKEYLOG_FILE, TESTER_DEBUG_LOG_FILE, \
					APPLOG_FILE, ADBLOG_FILE, DEFAULT_TEST_SUITE, CONFIG_FILE
from MailUtil import send_mail

## configurables
THREAD_WAIT_INTERVAL=10

class Tester(object):
	'''
	The Tester class plays a tester role -- It manages test build, testcase,
	test devices, and test results. It uses AppTestEngine to execute testcases.
	@author: Shawn Wang
	@param:
	1. test suite name
	2. build number
	'''

	def __init__(self, suite_name=DEFAULT_TEST_SUITE, build_num=0):
		'''
		@param string suite
		@param string buildnum
		'''
		self.initOK=False
		## do input validation
		self.buildnum=build_num
		self.suiteName=suite_name

		self.Pass=0
		self.Fail=0
		self.Total=0
		self.ALTList=[]
		self.start_time=None
		self.end_time=None
		self.exception_string=''
		## do environment validation
#		if not path.isfile(self.__class__.__name__+'.py'):
#			print('Please run %s from the directory where is resides.' % (self.__class__.__name__+'.py'))
#			return
#		if not path.isdir(SETUP_SUBDIR):
#			print 'Required directory %s does not exist. please check and run again.' % SETUP_SUBDIR
#			return
		if not path.isfile(CONFIG_FILE):
			print('Config file %s does not exist. please check and run again.' % CONFIG_FILE)
			return
		if not path.isdir(TC_SUBDIR):
			print('Required directory %s does not exist. please check and run again.' % TC_SUBDIR)
			return
		if not path.isdir(SNAPSHOT_SUBDIR):
			mkdir(SNAPSHOT_SUBDIR)
		## remove old log file
		if path.isfile(TESTER_DEBUG_LOG_FILE):
			print('Removing old log file...')
			remove(TESTER_DEBUG_LOG_FILE)
#			truncate_file(TESTER_DEBUG_LOG_FILE)

		## create new log file
		self.logHandler=createLogger(self.buildnum)

		## build device pool
		self.testServer=TestServer()
		self.devicePool=self.testServer.getDeviceIdList()
		if len(self.devicePool)==0:
			printLog('NO DEVICE FOUND. QUIT.', logging.ERROR)
			return

		## build testcase suite
		try:
			self.testPool=TestSuite(self.suiteName)
			if self.testPool.getTotalCount()==0:
				printLog('NO TESTCASE IN THE TEST SUITE. QUIT.', logging.ERROR)
				return
		except Exception, e:
			printLog('Failed to create test pool: %s' % e.message, logging.ERROR)
			return
		self.testEngineList=[]
		self.initOK=True


	def __del__(self):
		print '%s is deleted.' % self.__class__.__name__
		del self.testPool
		del self.appTestEngine
		del self.ALTList
		self.logHandler.close()
		logging.shutdown()

	def __reset(self):
		'''
		reset counters and remove result file and temp files
		Note: execution log file is not removed at the beginning of each run,
		but during the init.
		'''
		self.Pass=0
		self.Fail=0
		self.Total=0
		self.ALTList=[]
		self.start_time=None
		self.end_time=None

		if path.isfile(self.suiteName+'.txt'):
			print 'Removing old result file %s ...' % (self.suiteName+'.txt')
			remove(self.suiteName+'.txt')
		if path.isfile(APPLOG_FILE):
			print 'Removing old app log file %s ...' % APPLOG_FILE
			remove(APPLOG_FILE)
		if path.isfile(ADBLOG_FILE):
			print 'Removing old ADB log file %s ...' % ADBLOG_FILE
			remove(ADBLOG_FILE)
		## remove temp png files
		self.testServer.callShellCmd(r'rm *.png')
		self.testServer.callShellCmd(r'rm snapshot/*.png')
		## reset test pool status
		self.testPool.resetTestStatus()

	def __writeTextTestResult(self):
		content_format="%-*s%-*s%*s%*s%*s"
		content_format2="%-*s%*s" # '-' means left just (right just by default) http://www.cnblogs.com/zero86/archive/2012/11/22/2783679.html
		content_format3="%-*s%*d"
		self.Total=self.testPool.getTotalCount()
		self.Pass=self.testPool.getPassCount()
		self.Fail=self.testPool.getFailCount()

		with open(self.suiteName+'.txt', mode='w') as f:
			f.write(H_LINE + '\n')
		#		f.write("             "+APP_NAME+' Test Report             ')
			f.write(content_format2 % (11, 'Test start:', 30, self.start_time) +'\n')
			f.write(content_format2 % (11, 'Test stop: ', 30, self.end_time) +'\n')
			f.write(content_format2 % (11, 'Build:     ', 30, CLIENT_VERSION_PREFIX+str(self.buildnum))+'#\n')
			count=0
			for testEng in self.testEngineList:
				count+=1
				ts=testEng.testSuite
				f.write(content_format2 % (11, 'Device'+str(count)+":\t", 50, testEng.make+' '+testEng.model+' '+testEng.androidVersion+' ' + testEng.deviceId) +'\n')
				f.write(H_LINE + '\n')
				f.write(content_format3 % (10, 'Total:' , 5, ts.getTotalCount()) +'\n')
				f.write(content_format3 % (10, 'Pass:' , 5, ts.getPassCount()) + '\n')
				f.write(content_format3 % (10, 'Fail:' , 5, ts.getFailCount()) + '\n')
				f.write(content_format3 % (10, 'Not Run:' , 5, ts.getTotalCount()-ts.getPassCount()-ts.getFailCount()) + '\n')
				f.write(H_LINE + '\n')
				if ts.getFailCount()>0:
					f.write("Failed Testcase:\n\n")
					f.write(content_format % (25, 'Test Name', 45, "\tFailure Description", 30, "\tDevice", 20, "\tStart Time", 20, "\tEnd Time") + '\n')
					f.write(H_LINE + '\n')
					failedTests=filter(lambda x:x.result==TestStatus.Fail,ts.queue) 
					for tc in failedTests:
						f.write(content_format % (25, tc.name, 45, '\t'+tc.errormsg, 30, '\t'+tc.device, 20, '\t'+tc.start_time, 20, '\t'+tc.end_time) +'\n')
					f.write(H_LINE + '\n')
				if ts.getPassCount()>0:
					f.write("\nPassed Testcase:\n\n")
					f.write(content_format % (25, 'Test Name', 45, "\tTest Description", 30, "\tDevice", 20, "\tStart Time", 20, "\tEnd Time") +'\n')
					f.write(H_LINE + '\n')
					passedTests=filter(lambda x:x.result==TestStatus.Pass,ts.queue) 					
					for tc in passedTests:
						f.write(content_format % (25, tc.name, 45, tc.desc, 30, '\t'+tc.device,20, '\t'+tc.start_time, 20, '\t'+tc.end_time) + '\n')
					f.write(H_LINE + '\n')
			f.write(H_LINE + '\n')
	

	def getBuild(self):
		'''
		get the specified build file to current directory
		'''
		#TODO: this is an abstract method. subclasses should implement it.
		raise NotImplementedError('You have not implement getBuild()')
	
	def generateTestReport(self):
		#TODO: This is the default implementation. you may want to implement your own logic in AppTester.
		self.__writeTextTestResult()
		
	def start(self):
		'''
		@return: number of failed testcases
		@rtype: integer
		'''
		self.__reset()
		self.start_time=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
		##start multi-threads
		deadThread=0
		for i in range(len(self.devicePool)):
			try:
				appTestEngine=AppTestEngine(self.buildnum, self.testPool, self.devicePool[i])
				self.testEngineList.append(appTestEngine)
				appTestEngine.start()
			except AssertionError, e:
				printLog('Init test engine %d of %d failed: %s' % (i, len(self.devicePool), e.message), logging.ERROR)
				deadThread+=1
		c=threading.activeCount()-1-deadThread
		while c>0:
			printLog('=================================================================')
			printLog('<Main Thread> Waiting %d seconds for %d test threads to finish...' % (THREAD_WAIT_INTERVAL,c))
#			for item in threading.enumerate():
#			    printLog('<Main Thread> ' +repr(item))
			printLog('=================================================================')
			time.sleep(THREAD_WAIT_INTERVAL)
			c=threading.activeCount()-1
		#TODO:  capture logcat in ASYNC mode and get activity launch time (Planned)

		printLog('============================================================')
		printLog('<Main Thread> all test finished!')
		printLog('============================================================')
		self.end_time=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))

		#TODO: scan app log for exceptions (Planned to support multi-device later)
		
		## generate result report
		self.generateTestReport()
		
		return self.Fail
	
	def sendmail(self, subject, to=[MAIL_ADMIN_ADDRESS]):
		mailserver={}
		mailserver['name']=MAIL_SERVER_ADDRESS
		mailserver['user']=MAIL_SENDER_ADDRESS
		mailserver['password']=MAIL_SENDER_PASSWORD
		fro=MAIL_SENDER_ADDRESS
		attachList=[]
		if self.Fail>0 or len(str(self.exception_string))>0:
			for file in [APPLOG_FILE,ADBLOG_FILE,MONKEYLOG_FILE]: #TESTER_DEBUG_LOG_FILE
				if path.isfile(file):
					attachList.append(file)
			## get the snapshot file list
			for i in listdir(path.join(getcwd(), 'snapshot')):
				attachList.append(path.join(getcwd(), 'snapshot', i))
		## open result file and read the result
		try:
			print('reading %s...' % (self.suiteName+'.html'))
			with open(self.suiteName+'.html') as fd:
				text=fd.read()
#				content=''.join(text)
			send_mail(mailserver, fro, to, subject, text, attachList)
			print '[sendmail] Mail sent out to %s with attachment %s' % (to, attachList)
		except IOError, e:
			print('[sendmail] IOError: %s' % e.message)
			traceback.print_exc()
			send_mail(mailserver, fro, [MAIL_ADMIN_ADDRESS], \
			'Build %s_%d: Failed to send automation email' % \
			(BUILD_VERSION, self.buildnum), e.message)
		except java.lang.OutOfMemoryError, e:
			print '[sendmail] OutOfMemoryError during mail send.\n%s' % (e.message)
			send_mail(mailserver, fro, [MAIL_ADMIN_ADDRESS], \
			'Build %s_%d: Failed to send automation email' % \
			(BUILD_VERSION, self.buildnum), e.message)
		except Exception, e:
			print '[sendmail] Exception during mail send.\n%s' % (e.message)
			send_mail(mailserver, fro, [MAIL_ADMIN_ADDRESS], \
			'Build %s_%d: Failed to send automation email' % \
			(BUILD_VERSION, self.buildnum), e.message)

