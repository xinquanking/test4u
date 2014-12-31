# /usr/bin/python
#-*- encoding: utf-8 -*-
'''
@author Zhenming Wang, Shawn Wang
TestEngine is a class supporting multiple-threading in order to execute testcases 
on multiple devices using both the abilities from android engine and device engine, 
as well as the new methods added to AppEngine - a customizable subclass of TestEngine.

Tester uses this AppEngine to run test.
'''
from __future__ import with_statement
##import system modules
from os import sep, path, remove
import logging
#from xml.dom import minidom
#import codecs
#import java.lang
#from subprocess import call
from TestUtil import printLog, APP_NAME, APP_PKG_NAME, UPGRADE_APP_ON_TEST_START, CONFIG_FILE
#from Android import runShellCmd
from TestEngine import TestEngine

## configurables
import ConfigParser
config = ConfigParser.ConfigParser()
config.readfp(open(CONFIG_FILE))

APP_MAIN_ACTIVITY=APP_PKG_NAME+'/'+config.get('APP', 'APP_MAIN_ACTIVITY')
CLIENT_VERSION_PREFIX=config.get('BUILD', 'CLIENT_VERSION_PREFIX')
BUILD_VERSION=config.get('BUILD', 'BUILD_VERSION')
BUILD_FILENAME=config.get('BUILD', 'BUILD_FILENAME')
# build path info
BUILD_ROOT_PATH = config.get('BUILD', 'BUILD_ROOT_PATH')
BUILD_LOCAL_ROOT_PATH = config.get('BUILD', 'BUILD_LOCAL_ROOT_PATH')
#TODO: customize the file paths
BUILDNUM_FILE_PATH = path.join(BUILD_ROOT_PATH, BUILD_VERSION, 'latest', 'buildnum.txt')
BUILD_FILE_PATH = path.join(BUILD_ROOT_PATH, BUILD_VERSION, 'latest', BUILD_FILENAME)

class AppTestEngine(TestEngine):

    '''
    @requires each exposed function starts with "do_"
    It is recommended that functions in this class have no argument. If it does, 
    you need to append the argements to the function name in ini file.
    
    Add new "do_" functions to enhance AppEngine's capability for automation 
    purpose as you wish.
    
    @param build_num: int
    @param test_suite: TestSuite
    @param device_id: string
    '''
    def __init__(self, build_num, test_suite, device_id):
        TestEngine.__init__(self, build_num, test_suite, device_id)
        self.currentBuildnum=self.getCurrentBuildNumber()
        printLog(self.threadName+"[AppTestEngine] current build number is %d, target build number is %s" % (self.currentBuildnum, str(self.buildnum)))
        if self.currentBuildnum < build_num:
            # upgrade app to target build
            if UPGRADE_APP_ON_TEST_START:
                printLog(self.threadName+"[AppTestEngine] Upgrading device to build %s..." % self.buildnum)
                assert self.do_upgradeApp()
            else:
                printLog(self.threadName+"[AppTestEngine] Upgrade to build %s skipped..." % self.buildnum)
        else:
            printLog(self.threadName+"[AppTestEngine] use current installed build %s" % self.currentBuildnum)
            self.buildnum=self.currentBuildnum

    def __del__(self):
        TestEngine.__del__()

    @staticmethod
    def getLatestBuildNumber():
        """
        #TODO: implement the logic and return build number in integer
        """
        fd=file
        buildnum= 0
        try:
            # read the buildnum.txt and get the currect build number
            with open(BUILDNUM_FILE_PATH) as fd:
                content=filter(lambda x: not x.startswith('\n'), fd.readlines())
                buildnum=int(content[0].split('-')[1][1:])
        except IOError, e:
            printLog("File %s open error." % BUILDNUM_FILE_PATH, logging.ERROR)
    #	except IndexError,e:
    #		printLog(logger,"File %s format error. reason is %s" % (BUILDNUM_FILE_PATH, e.message))
    #		return 0
        except Exception, e:
            printLog("Exception in getLatestBuildNumber: %s" % e.message, logging.ERROR)
        return buildnum


    def getCurrentBuildNumber(self):
        '''override'''
    	#TODO: implement
        pref_file=self.deviceId+'_preference.xml'
        self.pullFile('/data/data/com.innopath.mobilemd/shared_prefs/com.innopath.mobilemd_preferences.xml', pref_file)
        ## parse the xml file and get version value
        with open(pref_file,'r') as pref:
            line=filter(lambda x:'pref_current_app_version_code' in x, pref.readlines())
            return int(line[0].strip().split(' ')[2].split('=')[1].split('"')[1])

#    def updateApp(self):
#        '''override'''
#        return self.do_upgradeApp()

    def do_installApp(self, str_arg=''):
        target=BUILD_ROOT_PATH+sep+BUILD_VERSION+sep+APP_NAME+'-'+str(self.buildnum)+sep+BUILD_FILENAME
        if path.isfile(target):
            self.installApp(target)
            return True
        else:
            printLog(self.threadName+"CANNOT ACCESS/FIND BUILD FILE at %s" % target, logging.ERROR)
            return False

    def do_freshInstallApp(self, str_arg=''):
        self.do_removeApp()
        self.do_sleep('1')
        self.do_installApp()

    def do_upgradeApp(self, str_arg=''):
        '''
        1. get the build file
        2. do upgrade
        '''
        #TODO: implement
        target=''
        if not path.isfile(target):
            # TODO: get the build file to BUILD_ROOT_PATH
            pass
            
        if path.isfile(target):
            if self.currentBuildnum< self.buildnum:
                self.resultFlag=self.upgradeApp(target)
            else:
                printLog(self.threadName+"Target build already installed, skip upgrade.")
                self.resultFlag=False
        else:
            printLog(self.threadName+"CANNOT ACCESS/FIND BUILD FILE at %s" % target, logging.ERROR)
            self.resultFlag=False
        return self.resultFlag        

    def do_startApp(self, str_arg=''):
        printLog(self.threadName+"[running command 'startApp %s']" % str_arg)
        self.startApp(APP_MAIN_ACTIVITY)
        self.do_sleep('5')
        
    def do_stopApp(self, str_arg=''):
        printLog(self.threadName+"[running command 'stopApp %s']" % str_arg)
        self.stopApp(APP_PKG_NAME)

    def do_removeApp(self, str_arg=''):
        self.removeApp(APP_PKG_NAME)

    def do_removeAppLog(self, str_arg=''):
        self.do_stopApp(str_arg)
        #TODO: customize the App log file path
        self.removeFile(r'<app log file path>')

    def do_dragDownStatusBar(self, str_arg=''):
        self.do_drag("(400,32), (400,1200)")
    
    def do_checkCrash(self, str_arg=''):
        #TODO: customize the App Name
        App_Name=''
        self.do_check("id/message Unfortunately, %s has stopped." % App_Name)
        self.crash=self.resultFlag
        if self.crash:
            printLog("********APP CRASHED!!!********", logging.ERROR)
#        else:
            #TODO: check if app is still running
        self.resultFlag = True

## functions starts with "do_test*" are usually used in @validation section in action scripts
    def do_testMonkeyTest(self, str_arg=''):
        printLog(self.threadName+'run monkey test.')
        self.resultFlag=self.runMonkeyTest(APP_PKG_NAME, 500)
    
    def do_testAppVersion(self, str_arg=''):
        #TODO: implement
        pass
    
    def do_testAppLog(self, str_arg=''):
        '''
        search app log for specified key words
        '''
        tmpFn="tmp.log"
        #TODO: get the app log file to local
        self.pullFile('<app log file path>', tmpFn)
        cmd="tail -n 100 %s | grep '%s'" % (tmpFn, str_arg)
        output=self.testServer.runShellCmd(cmd)
        
        if str_arg in output:
            self.resultFlag=True
        else:
            self.resultFlag=False
        remove(tmpFn)
