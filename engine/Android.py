#! /usr/bin/python
#-*- encoding: utf-8 -*-

'''
@author Zhenming Wang, Shawn Wang
the android engine wraps the methods that deal with device on the android system level.
1. app install, remove, start, stop
2. file push, pull, remove
3. directory make, remove
'''
from __future__ import with_statement
#import system modules
import os, shutil
import logging
#from datetime import *
from subprocess import Popen, PIPE
#import threading
from TestUtil import printLog
#from TestServer import callCmd, runShellCmd
from Shell import Shell
MONKEYTEST_LOG_FILE='monkey.txt'

class AdbServer(object):
    def __init__(self, deviceId):
        self.deviceId=deviceId
        
#    @classmethod
    def runAdbCmd(self, action, args):
        return self.runShellCmd('adb -s %s %s %s' % (self.deviceId, action, args))

    def callAdbCmd(self, action, args=''):
        return self.callShellCmd('adb -s %s %s %s' % (self.deviceId, action, args))

    def restartAdbServer(self):
        printLog('Stopping adb-server...', logging.INFO)
        self.callAdbCmd('kill-server')
        printLog('Starting adb-server...', logging.INFO)
        self.callAdbCmd('start-server')

#def formatString(input):
#	if input < 10:
#		output='0'+str(input)
#	else:
#		output=str(input)
#	return output

'''
change the phone date time.
included on Feb 18, 2014.
'''
#def change_phone_time(delta, deviceId):
#    # delta is the time value to be changed in seconds 
#    step_result = False
#    try:
#        phone_date_tmp = runShellCmd('adb -s ' +deviceId + ' shell date')
#        #os.system('adb root')
#        if len(phone_date_tmp)==0:
#            printLog('failed to get phone date. exiting...', logging.ERROR)
#            return step_result
#        phone_date = phone_date_tmp.replace('CST ', '').strip()
#        printLog("Current phone time: %s"% phone_date)
#        phone_time_value=strptime(phone_date, "%a %b %d %H:%M:%S %Y")
#        new_time = phone_time_value + timedelta(seconds=delta) 
#        printLog('{0:<30} {1:>30}'.format("Changing Device time to new phone time:", str(new_time)), logging.INFO)
#        phone_new_time_value=str(new_time.year)+formatString(new_time.month)+ \
#        formatString(new_time.day)+'.'+formatString(new_time.hour)+ \
#        formatString(new_time.minute)+formatString(new_time.second)
#        printLog("change to:")
#        step_result= callCmd('adb -s ' + deviceId + ' shell date -s '+phone_new_time_value)
#
#    #		print "Phone time is changed to %s"%phone_new_time_value
#    except Exception,e:
#        printLog("Fail to get the time and date on the phone: %s" % e.message, logging.ERROR)
#    finally:
#        return step_result


def scanExceptionInFile(path):
	'''
	search for any exception in the file specified in path, 
	and save return the result as a string
	'''
	path=os.path.basename(path)
	printLog('[scanFile] Scanning file %s for exceptions...' % path, logging.INFO)
#	self.exception_string=check_output(r'grep -n "Exception" -A 3 log.txt', shell=True)
	cmdList=["grep", "-n", "ERROR", "-B", "1", "-A", "3", path]
	exception_string=Popen(cmdList, stdout=PIPE).communicate()[0]
#    printLog('[scanFile] exceptions found: %s' % exception_string)
	return exception_string

def truncate_file(fname, size=0):
    '''
    Open a file for writing, and truncate it to specified size in bytes.
    '''
    if not os.path.isfile(fname): return
#	with open(fname, "ab") as f:
#		f.truncate(size)
#		f.close()
    initSize=os.path.getsize(fname)
    printLog('initial size of %s: %d'% (fname, initSize))
    with open(fname, mode='w') as f:
        f.truncate(size)
#		f.write('[log start]\n')
    finalSize=os.path.getsize(fname)
    printLog('final size of %s: %d'% (fname, finalSize))
    printLog('truncated size of %s: %d'% (fname, initSize - finalSize))

def cleanDir(Dir):
    print "Start cleaning dir %s" % Dir
    # clean the specified dir
    if os.path.isdir(Dir):
        paths = os.listdir(Dir)
        for path in paths:
            filePath = os.path.join(Dir, path)
            if os.path.isfile(filePath):
                try:
                    os.remove(filePath)
                except os.error:
                    print "remove %s error." %filePath
            elif os.path.isdir(filePath):
                shutil.rmtree(filePath, True)

class Android(AdbServer, Shell):

    def __init__(self, deviceId):
#        SysEngine.__init__(self)
#        self.deviceId = deviceId
        AdbServer.__init__(self, deviceId)
        Shell.__init__(self)

    def __del__(self):
        pass

    def __convertTime(self, rawtime):
        '''
        Jul 22, split the minute part from second part, and convert to launch time in seconds.
        the input raw time may contain seconds and milliseconds, e.g. 1s12ms
        '''
    #		printLog('[getTime] raw time: %s'% rawtime)
        ## remove the trailing '\n' and 'ms'
        rawtime=rawtime.split('m')[0]
    #		rawtime=rawtime[0:(len(rawtime)-2)]
    #		printLog('[getTime] stripped raw time: %s'% rawtime)
        if not rawtime.isdigit():
            sec, ms=rawtime.split('s')
            rawtime=str(int(sec)*1000+int(ms))
    #		printLog('[getTime] converted time: %s(ms)' % rawtime)
        return rawtime
    
    def getLaunchTime(self, fname):
        '''
        Jul 22, scan logcat log file and retrieve activity launch time data, 
        save a list of (activity, launch time) vp
        '''
        if not os.path.isfile(fname):
            return ''
        self.callShellCmd('./get_ALT.sh '+fname)
        ALTList=[]
        new_fname='logcat.csv'
        with open(new_fname, 'r') as fd:
            lines=filter(lambda x: not x.startswith('\n'), fd.readlines())
        try:
            with open(new_fname, mode='w') as f:
                for line in lines:
#					printLog('[scanLogcat] current line: %s'% line)
                    # Oct 23: changed method to get activity name and time
                    # use ':' to split columns in get_ALT.sh and '+' to split
                    # activity name and launch time
                    activity, ltime=line.split('(')[0].split('+')
                    activity=activity.split(' ')[2]
                    ltime=self.__convertTime(ltime.rstrip('\n'))
                    ALTList.append((activity, ltime))
                    f.write(activity+','+ltime+'\n')
        except Exception, e:
            printLog('[scanLogcat] Caught exception while writing launch time data to file: %s' % e.message, logging.ERROR)
        finally:
            return ALTList

    # TODO: make configurable
    def runMonkeyTest(self, pkgName, count):
        if os.path.isfile(MONKEYTEST_LOG_FILE):
            os.remove(MONKEYTEST_LOG_FILE)
        cmd='monkey -p ' + pkgName + ' -s 2 --throttle 300' + \
        ' --pct-touch 50 --pct-motion 20 --pct-trackball 20 --pct-syskeys 10 ' \
        + str(count) + ' > ' + MONKEYTEST_LOG_FILE
        self.callAdbCmd('shell', cmd)
        exception=scanExceptionInFile(MONKEYTEST_LOG_FILE)
        if exception=='':
            os.remove(MONKEYTEST_LOG_FILE)
            return True
        else:
#            testcase.cmd=cmd
#            testcase.errormsg='monkey test errors, check monkey.txt'
            return False      

    def installApp(self, apkName):
        printLog("Installing app from %s..."% apkName)
        self.callAdbCmd('install',apkName)

    ''' abstract function'''
    def updateApp(self):
#        printLog("This is a abstract function, you need to implement it in your engine class.", logging.ERROR)
        raise NotImplementedError("updateApp() is a abstract function, you need to implement it in your engine class.")

    def upgradeApp(self, apkName):
        printLog("[upgradeApp] upgrading app from %s..."% apkName)
        return self.callAdbCmd('install', '-r '+apkName)

    def pullFile(self, src, tgt='.'):
        if tgt=='.':
            tgt='./'+os.path.basename(src)
        self.callAdbCmd('pull',src+' '+tgt)
        if os.path.isfile(tgt):
            return 0
        else:
            printLog("[pullFile] Failed to get file '%s' via adb." % src,logging.ERROR)
            return 1
    
    def pushFile(self, src, tgt):
        self.callAdbCmd('push',src+' '+tgt)

    def removeApp(self, pkgName):
        printLog("Removing package %s ..." % pkgName)
        try:
            if (self.runAdbCmd('uninstall',pkgName).strip()=='Failure'):
                printLog('failed to remove %s.' % pkgName)
                return False
            else:
                printLog('%s is removed.' % pkgName)
                return True
        except Exception, e:
            printLog('Exception during remove:'+ e, logging.ERROR)
            return False

    def removeFile(self, tgt):
        self.callAdbCmd('shell', 'rm '+tgt)

    def removeDirectory(self, tgt):
        self.callAdbCmd('shell', 'rm -rf '+tgt)
        
    def startApp(self, activity):
        self.openActivity(activity)
#        self.do_sleep(str(sleepTimer))
#        time.sleep(sleepTimer)
        
    def stopApp(self, pkgName):
        self.callAdbCmd('shell', 'am force-stop ' + pkgName)

    def __getpkgNameByApk(self, apkName):
        '''
        Get the package name from .apk file
        '''
        cmd="aapt dump badging "+apkName+" |grep package:|awk -F ' ' '{print $2}'|awk -F '=' '{print $2}'|tr -d \"'\""
        pkgName=self.runShellCmd(cmd)
        if pkgName is None: 
            printLog('Cannot get package name from apk file.', logging.ERROR)
            return False

    def __installApp(self, apkPath, removeBeforeInstall):
        '''
        Jan 24, 2013: swang
        rewrite as a common method to install apk to user part
        '''
        if not os.path.isfile(apkPath):
            printLog(apkPath + ' is not found.')
            return False
        ## need to remove the package first so that policy file could be updated.
        pkgName=self.__getpkgNameByApk(apkPath)
        #print pkgName
        if removeBeforeInstall:
            if not self.removeApp(pkgName):
                return False
        try:
            printLog("Installing application %s ..." % apkPath)
            self.installApp(apkPath)
            printLog('installation is done.')
            return True
        except Exception, e:
            printLog('Exception during install:'+ e, logging.ERROR)
            return False

    def openActivity(self, activity):
        self.callAdbCmd('shell', 'am start -n %s' % activity)
        
    def disableWiFi(self):
        self.callAdbCmd('shell', 'svc wifi disable')
    def enableWiFi(self):
        self.callAdbCmd('shell', 'svc wifi enable')
    def disableMobileData(self):
        self.callAdbCmd('shell', 'svc data disable')
    def enableMobileData(self):
        self.callAdbCmd('shell', 'svc data enable')

# -----------------------AndroidEngine Class END-------------------------------



#class TestDevice(object):
#    def __init__(self, id):
#        self.deviceId       =id
#        self.androidVersion =getDeviceAndroidVersion(id)
#        self.make           =getDeviceMake(id)
#        self.model          =getDeviceModel(id)
#        self.operator       =getDeviceOperator(id)
##        self.modelId        =getDeviceModelId(id)
#        self.idle           =True
    

