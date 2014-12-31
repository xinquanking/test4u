#! /usr/bin/env monkeyrunner
# /usr/bin/python
#-*- encoding: utf-8 -*-
'''
@author Shawn Wang, Wu Gao

Android Device

This module executes commands from script files and emulates the UI action 
requested. all the available actions are ecapsulations of monkeyrunner APIs 
defined as python functions starts with "do_". A general action script consists
of 3 mandatory sections: @SETUP, @VALIDATION and @TEARDOWN.
Other sections include: @TITLE, @TESTID, etc.
'''
from __future__ import with_statement
import os
import sys
import time
import traceback
import logging
import re
import filecmp
import java.lang
import java.net
from shutil import copy

from Android import Android
from TestUtil import printLog

## 3rd party modules
#sys.path.append('/usr/lib/python2.7/dist-packages')
from PIL import Image

## Imports the monkeyrunner modules
from com.android.monkeyrunner import MonkeyRunner, MonkeyDevice#, MonkeyImage
from com.android.monkeyrunner.easy import EasyMonkeyDevice, By
#from com.android.chimpchat.hierarchyviewer import HierarchyViewer
#from com.dtmilano.android.viewclient import ViewClient

LOG_LEVEL=logging.DEBUG
SNAPSHOT_WIDTH=480
CONNECT_TIMEOUT=10
REPEAT_TIMES_ON_ERROR=2
DEFAULT_INTERVAL=0.5

class AndroidDevice(Android):

    def __init__(self, device_id):
        #interval(seconds) between commands
        self.INTERVAL=DEFAULT_INTERVAL
        Android.__init__(self, device_id)
        self.resultFlag=False
        self.androidVersion =self.getDeviceAndroidVersion()
        self.make           =self.getDeviceMake()
        self.model          =self.getDeviceModel()
        self.operator       =self.getDeviceOperator()
        self.idle           =True
        self.threadName='<'+self.model+'_'+ device_id+'> '
        # Connect to the current device
        printLog(self.threadName+'[AndroidDevice] Connecting to device %s...' % device_id, logging.INFO)        
        self.__connect()
        printLog(self.threadName+'[AndroidDevice] Device %s init completed.' % device_id)

    def __getDeviceInfo(self, propName):
        cmd= "getprop | awk -F':' '/" + propName + "/ { print $2 }'|tr -d '[] '"
        output=self.runAdbCmd("shell", cmd).splitlines()
        if len(output)>0:
            return output[0].strip()
        else:
            return 'UNKNOWN'

    def getDeviceAndroidVersion(self):
        return self.__getDeviceInfo('build.version.release')
    def getDeviceModelId(self):
        return self.__getDeviceInfo('ril.model_id')
    def getDeviceModel(self):
        return self.__getDeviceInfo('ro.product.model')
    def getDeviceMake(self):
        return self.__getDeviceInfo('ro.product.manufacturer')
    def getDeviceOperator(self):
        return self.__getDeviceInfo('gsm.sim.operator.alpha')

    def getCurrentBuildNumber(self):
        # this is an abstract method. subclasses should implement it.
        raise NotImplementedError('You have not implement getCurrentBuildNumber()')

    def __connect(self):
        try:
            self.md = MonkeyRunner.waitForConnection(timeout=CONNECT_TIMEOUT, deviceId=self.deviceId)
            #print 'Connected.'
            if self.md is None:
                printLog(self.threadName+'[AndroidDevice] Device NOT connected...', logging.ERROR)
                return
            # get phone's screen resolution, once connected, it is fixed
            self.scn_width=int(self.md.getProperty('display.width'))
            self.scn_height=int(self.md.getProperty('display.height'))
            printLog(self.threadName+"[AndroidDevice] Device %s's screen resolution is: %d * %d" % (self.deviceId, self.scn_width, self.scn_height), logging.INFO)
            self.md.wake()
            printLog(self.threadName+'[AndroidDevice] Creating Hierarchy Viewer... ')
            self.hv=self.md.getHierarchyViewer()
            printLog(self.threadName+'[AndroidDevice] Creating easy device... ')
            self.ed = EasyMonkeyDevice(self.md)
            printLog(self.threadName+'[AndroidDevice] Device %s connected.' % self.deviceId, logging.INFO)
            self.resultFlag=True
        except java.lang.NullPointerException, e:
            printLog(self.threadName+'[AndroidDevice] CANNOT access device %s. Please check the USB cable and reconnect the device.' % self.deviceId, logging.ERROR)
            return
        except java.net.SocketException, e:
            printLog(self.threadName+'[AndroidDevice] SocketException: %s' % e.message, logging.ERROR)
            return
        except Exception, e:
            printLog(self.threadName+'[AndroidDevice] Caught Exception during init: %s' % e.message, logging.ERROR)
            return

    def __reconnect(self):
        self.restartAdbServer()
        # reconnect device
        printLog(self.threadName+'[AndroidDevice] Reonnecting to device...', logging.INFO)
        self.__connect()

    def __del__(self):
        self.md=None
        self.ed=None
        self.hv=None


    '''
    compare two image files with specified difference tolerance percentage (2% by default)
    input: two file's name
    @return: True or False
    '''
    def __compareImage(self, file1, file2):
#        arg=self.__validateString(str_arg)
#        file1, file2=arg.split(' ', 1)
        img1=None
        img2=None
        try:
            img1=Image.open(file1)
            img2=Image.open(file2)
            if(img1.size!=img2.size):
                return False
            by1=img1.tobytes()
            by2=img2.tobytes()
            #format r,g,b,255,r,g,b,255, 3 bytes = 1 point, 255=separator, total 4 bytes 
            l=len(by1)/4
            #total points and same points
            tp=0
            sp=0
            for j in range(l):
                i=j*4
                tp=tp+1
                if by1[i]==by2[i] and by1[i+1]==by2[i+1] and by1[i+2]==by2[i+2]:
                    sp=sp+1
            # max to 2% diff allowed
            if tp*0.98>sp:
                return False
            else:
                return True
        except Exception, e:
            printLog(self.threadName+"Exception in __compareImage: %s" % e.message, logging.ERROR)
            traceback.print_exc()
            return False
        finally:
            img1=None
            img2=None

    def __compressImage(self, file):
        im=Image.open(file)
        printLog(self.threadName+'compressing snapshot %s...' % file)
        ratio = float(SNAPSHOT_WIDTH)/im.size[0]
        height = int(im.size[1]*ratio)
        printLog(self.threadName+"new image size: %d*%d" % (SNAPSHOT_WIDTH, height))
        os.remove(file)
        im.resize((SNAPSHOT_WIDTH, height), Image.BILINEAR).save(file)

    def __getChildView(self, parentId, childSeq):
        child_view=None
        str_getChildView="self.hv.findViewById('" + parentId +"')"    
        for index in childSeq:
            str_getChildView+=('.children[' + str(index) + ']')         
        exec 'child_view=' + str_getChildView
        return child_view

    def __getChildViewText(self, parentId, childSeq):
        child_view=self.__getChildView(parentId, childSeq)
        if child_view:
            np=child_view.namedProperties
#           print np
            return np.get('text:mText').value.encode(sys.getdefaultencoding())
        else:
            printLog(self.threadName+'[__getChildViewText] view not found.', logging.ERROR)
            self.resultFlag=False
            return ''

    def __clickChildView(self, parentId, childSeq):
        child_view=self.__getChildView(parentId, childSeq)
        if child_view:
            # 2014/09/25: the returned point Y coordinate does not include the status bar height
            # using getAbsolutePositionOfView cannot solve this issue
            # so add 50 to Y
            point=self.hv.getAbsoluteCenterOfView(child_view)
            printLog(self.threadName+'[__clickChildView] clicking device at (%d, %d) ...' % (point.x, point.y+50))
            self.md.touch(point.x, point.y+50, MonkeyDevice.DOWN_AND_UP)
            self.resultFlag=True
        else:
            printLog(self.threadName+'[__clickChildView] view not found.', logging.ERROR)
            self.resultFlag=False

#        point=self.hv.getAbsoluteCenterOfView(child_view)
        #print point.x, ", ", point.y
#        printLog(self.threadName+'[__clickChildView] clicking device at (%d, %d) ...' % (point.x, point.y))
#        self.md.touch(point.x, point.y, MonkeyDevice.DOWN_AND_UP)

    '''
    check if the input point is valid
    @param point: a tuple with 2 int elements
    '''
    def __validatePoint(self, point):
#        print point
        if point[0] > self.scn_width:
            raise ValueError('Bad X coordinate: %d' % point[0])
        if point[1] > self.scn_height:
            raise ValueError('Bad Y coordinate: %d' % point[1])
        return point
    '''
    check if the string parameter is digital, including integer and float.
    return stripped input string if not empty and is digital
    '''
    def __validateDigit(self, str):
        tmpstr=str.strip()
        if '.' in tmpstr:
            if not tmpstr.split('.')[0].isdigit() or not tmpstr.split('.')[1].isdigit():
                raise ValueError('Bad float parameter.')
        elif not tmpstr.isdigit():
            raise ValueError('Bad integer parameter.')
        return str.strip()

    '''
    check if the input string is empty
    return input string if not empty
    '''
    def __validateString(self, str):
        if len(str.strip())==0:
            raise ValueError('Bad string parameter.')
        return str.strip()

    '''
    get a single point coordinates
    return a tuple contain (x, y)
    (kept here for backward compatibility)
    '''
    def __getPointXY(self, str):
        try:
#            print 'input:',str
            pa=re.compile('^\((\d*,\d*)\)$')
            x,y = pa.search(str.strip()).groups()[0].split(',')
#            print 'x: %s, y: %s' % (x,y)
            return self.__validatePoint((int(x),int(y)))
        except AttributeError, e:
            raise ValueError('Failed to get point coordinates.')
            return

    '''
    get 2 points coordinates
    return a tuple containing the 2 points ((x, y), (x, y))
    (kept here for backward compatibility)
    '''
    def __getPointXYs(self, str):
        try:
            pa=re.compile('^\((\d*\D*,\D*\d*)\)\D*\((\d*\D*,\D*\d*)\)$')
            points=pa.search(str.strip()).groups()
            startPoint=(int(points[0].split(',')[0].strip()),int(points[0].split(',')[1].strip()))
            endPoint=(int(points[1].split(',')[0].strip()),int(points[1].split(',')[1].strip()))
            return (self.__validatePoint(startPoint), self.__validatePoint(endPoint))
        except AttributeError, e:
            traceback.print_exc()
            raise ValueError('Failed to get point coordinates.')
            return

    def do_assert(self, str_arg):
        arg=self.__validateString(str_arg)
        if arg not in ('pass','fail'):
            self.resultFlag=False
            raise ValueError('Bad parameter.')
        if(arg=='pass' and self.resultFlag==True):
            printLog(self.threadName+'[ASSERT PASS]', logging.DEBUG)
            self.resultFlag=True
            return
        if(arg=='fail' and self.resultFlag==False):
            printLog(self.threadName+'[ASSERT PASS]', logging.DEBUG)
            self.resultFlag=True
            return
        #printLog(self.threadName+'[status=%s]' % self.resultFlag)
        printLog(self.threadName+'[ASSERT FAIL!]', logging.DEBUG)
        self.resultFlag=False

    '''
    check text of child element
    input: the unique parent ID, the path from parent to target child view, the target text
    return: none, but resultFlag indicate the result, yes or not
    e.g.  checkChild id/parent (4,3,2,2) my text is text
    note:  the final text string should be optinal. If without text string, that just means to check child existing or not
    '''
    def do_checkchild(self, str_arg):
        printLog(self.threadName+"[running command 'checkchild %s']" % str_arg)
        arg=self.__validateString(str_arg).strip()
        try:
            #to avoid '  ' two spaces case
            #suppose string like: id/text1 (5,4,2,3,3,3) textfield
            i=arg.index(' ')
            ids=arg[0:i]
            arg=arg[i+1:].strip()
            if ' ' in arg:
                i=arg.index(' ')
                seqs=arg[1:i-1].split(',')
                arg=arg[i+1:].strip()
                texts=arg
                target_text=self.__getChildViewText(ids,seqs)
                printLog(self.threadName+'[text on screen: %s]' % target_text)            
                self.resultFlag=True
                if texts!='':
                    if texts==target_text:
                        self.resultFlag=True
                    else:
                        self.resultFlag=False                
            else:
                seqs=arg[1:-1].split(',')
                if self.____getChildView(ids, seqs):
                    self.resultFlag=True
                else:
                    self.resultFlag=False                

        except java.lang.RuntimeException:
            self.resultFlag=False
            printLog(self.threadName+'Runtime Exception! id not found.',  logging.ERROR)
        except Exception, e:
            #gbk problem
            self.resultFlag=False
            traceback.print_exc()
            printLog(self.threadName+'Exception in do_checkchild: %s' % e.message, logging.ERROR)
        printLog(self.threadName+'[status=%s]' % self.resultFlag)

    '''
    check id visibility, optionally check if the given text is identical with that on the screen.
    '''
    def do_check(self, str_arg):
        printLog(self.threadName+"[running command 'check %s']" % str_arg)
        arg=self.__validateString(str_arg)
        ret=arg.split(' ', 1)
        compID=None
        #check id, just check existing or not
        try:
            compID=By.id(ret[0])
            #all our checked items, must be visible
            if not self.ed.visible(compID):
                self.resultFlag=False
                printLog(self.threadName+'%s is not visible.' % compID,logging.ERROR)
                return
            if len(ret)==2:
                #get element text, and compare it with the given text value
                text_on_screen=self.ed.getText(compID).strip()
                target=ret[1].strip()
                printLog(self.threadName+'[text on screen: %s]' % text_on_screen)
                #have GBK problem, need to solve, or text1 is always gbk in chinese machine
                if not text_on_screen==target.decode('utf-8'):
                    self.resultFlag=False
        except java.lang.RuntimeException:
            self.resultFlag=False
            printLog(self.threadName+'Runtime Exception! %s not found.' % compID, logging.ERROR)
        except Exception, e:
            #gbk problem
            self.resultFlag=False
            printLog(self.threadName+'Exception in do_check: %s' % e.message, logging.ERROR)
        printLog(self.threadName+'[status=%s]' % self.resultFlag)

    '''
    click a certain child for one unique ID
    use it while there are multiple same name ID, but there is one unique root parent
    '''
    def do_clickchild(self, str_arg):
        printLog(self.threadName+"[running 'clickchild %s']" % str_arg)
        arg=self.__validateString(str_arg).strip()
        try:
            #to avoid '  ' two spaces case
            #suppose string like: id/button1 (5,2,3,3,3)
            i=arg.index(' ')
            ids=arg[0:i]
            arg=arg[i+1:].strip()
            seqs=arg[1:-1].split(',')
            self.__clickChildView(ids,seqs)
        except:
            printLog(self.threadName+'do_clickChild: click failed', logging.ERROR)
            traceback.print_exc()
            self.resultFlag=False
            MonkeyRunner.sleep(1)
        finally:
            printLog(self.threadName+'[status=%s]' % self.resultFlag)

    '''
    click by a view id or a point in (x, y) coordinates
    e.g. click id/button
    e.g. click (100, 200)
    '''
    def do_click(self, str_arg):
        #todo, wait for x miliseconds
        arg=self.__validateString(str_arg)
        for tmp in range(REPEAT_TIMES_ON_ERROR):
            try:
                if not '(' in arg:
                    printLog(self.threadName+'[clicking id %s...]' % arg)
                    self.ed.touch(By.id(arg), MonkeyDevice.DOWN_AND_UP)
                else:
                    point=self.__getPointXY(arg)
                    printLog(self.threadName+'[clicking point %s...]' % arg)
                    self.md.touch(point[0],point[1],MonkeyDevice.DOWN_AND_UP)                    
                return
            except java.net.SocketException,e:
                printLog(self.threadName+'do_click: the %dth try failed due to SocketException, will retry.' % tmp, logging.ERROR)
                MonkeyRunner.sleep(1)
                continue
            except:
                printLog(self.threadName+'do_click: the %dth try failed, will retry.' % tmp, logging.ERROR)
#                self.__reconnect()
                MonkeyRunner.sleep(1)
                continue
#                # retry once
#                
#                self.resultFlag=False
#            except Exception, e:
#                printLog(self.threadName+'Exception in do_click: %s' % e.message, logging.ERROR)
#                #usually value/valueFormat error, set testcase fail then go on
#                self.resultFlag=False
            finally:
                printLog(self.threadName+'[status=%s]' % self.resultFlag)
        printLog(self.threadName+'do_click: sorry , still can\'t make the click. please check the id.', logging.CRITICAL)
        self.resultFlag=False

    '''
    compare a snapshot file (*.png) with an expected image file
    if the snapshot file is identical with the expected target file, return True.
    otherwise return False.
    '''
    def do_compare(self, str_arg):
        arg=self.__validateString(str_arg)
        source, target=arg.split(' ', 1)
        if os.path.isfile(source):
            # Mar 27 @swang: if target file doesn't exist, copy source file to setup directory for later test
            if not os.path.isfile(target):
                copy(source, target)
                return
#            if not self.__compareImage(source, target):
            if not filecmp.cmp(source, target):
                printLog(self.threadName+'source file and target file DIFFER!', logging.WARNING)
                self.resultFlag=False
        else:
            self.resultFlag=False
            raise ValueError('source file not found.')

    '''
    compare a snapshot file with a set of expected files
    if the snapshot file is identical with one of the files, return True.
    otherwise return False.
    kept here for backward compatibility
    '''
    def do_comparex(self, str_arg):
        arg=self.__validateString(str_arg)
        file1, fileset=arg.split(' ', 1)
        if len(fileset) == 0:
            self.resultFlag=False
            raise ValueError('Bad parameter. Please check your script.')
        if not os.path.isfile(file1):
            self.resultFlag=False
            raise ValueError(file1+' not exist, Please check your script.')
            return
#        f_list=[pp1 for pp1 in fileset.split(' ') if pp1!='']
        for fn in fileset.split(' '):
#            print file1, f2
            if not os.path.isfile(fn):
                self.resultFlag=False
                raise ValueError(fn+' not exist, Please check your script.')
                break
            if self.__compareImage(file1,fn):
                self.resultFlag=True
                print('[Found match. %s and %s are identical.]' % (file1, fn))
                return
        print('[No match found.]')
        self.resultFlag=False

    '''
    sample: drag (0,1) (100,100)
    '''
    def do_drag(self, str_arg):
#        print str_arg
        (startPoint, endPoint)=self.__getPointXYs(str_arg)
        printLog(self.threadName+'[do_drag] dragging from (%d,%d) to (%d,%d)...' % \
                        (startPoint[0],startPoint[1], endPoint[0],endPoint[1]))
        self.md.drag((startPoint[0],startPoint[1]), (endPoint[0],endPoint[1]),1,10)
        printLog(self.threadName+'[status=%s]' % self.resultFlag)

    '''
    set sleep interval between each action
    kept here for backward compatibility
    '''
    def do_interval(self, str_arg):
        self.INTERVAL=float(self.__validateDigit(str_arg))
        printLog(self.threadName+'[status=%s]' % self.resultFlag)

    '''
    press key
    format: keypress KEYCODE_HOME
    check http://developer.android.com/reference/android/view/KeyEvent.html for the full list
    KEYCODE_DPAD_LEFT 21
    KEYCODE_DPAD_RIGHT 22
    KEYCODE_DPAD_UP 19
    KEYCODE_DPAD_DOWN 20
    KEYCODE_TAB 61
    KEYCODE_ENTER 66
    '''
    def do_keypress(self, str_arg):
        arg=self.__validateString(str_arg)
        self.md.press(arg, MonkeyDevice.DOWN_AND_UP)
        printLog(self.threadName+'[status=%s]' % self.resultFlag)

    '''
    long press a view id or a point
    format: 1. longpress id/xxx [seconds]
            2. longpress (100,200) [seconds]
    Feb 17, 2014
    '''
    def do_longpress(self, str_arg):
        arg=self.__validateString(str_arg)
#        if arg.startswith(r'('):
#            raise ValueError('Bad argument, You may want to use longpress2 with coordinates as auguments.')
        if arg.startswith(r'('):
            mode=2
            point, sec=arg.split(')')
            x,y=self.__getPointXY(point+')')
        else:
            mode=1
            if ' ' in arg:
                id, sec=arg.split(' ')
                if len(sec)>0:
                    seconds=int(self.__validateDigit(sec.strip()))
            else:
                id=arg
                seconds=2

#        for tmp in range(REPEAT_TIMES_ON_ERROR):
        try:
            printLog(self.threadName+"[running 'longpress %s'...]" % str_arg)
            if mode==1:
                self.ed.touch(By.id(id), MonkeyDevice.DOWN)
    #            print 'key down'
                time.sleep(seconds)
    #            print 'sleep'
                self.ed.touch(By.id(id), MonkeyDevice.UP)
    #            print 'key up'
            else:
                self.md.touch(x,y, MonkeyDevice.DOWN)
    #            print 'key down'
                time.sleep(seconds)
    #            print 'sleeped'
                self.md.touch(x,y, MonkeyDevice.UP)
    #            print 'key up'
            return
        except Exception, e:
            pass
#            printLog(self.threadName+'do_longpress: failed(%s).' % (e.message), logging.WARNING)
#                self.__reconnect()
#            MonkeyRunner.sleep(1)
#            continue
        finally:
            printLog(self.threadName+'[status=%s]' % self.resultFlag)
#        printLog(self.threadName+'do_longpress: sorry , still can\'t make the press. please check the id.', logging.ERROR)
#        self.resultFlag=False

    '''
    sleep for given seconds, can be float
    '''
    def do_sleep(self, str_arg):
        printLog(self.threadName+"[running command 'sleep %s']" % str_arg)
        try:
            MonkeyRunner.sleep(float(self.__validateDigit(str_arg)))
        except:
            self.resultFlag=False
#        printLog(self.threadName+"[status=%s]" % self.resultFlag)

    def do_slideleft(self, str_arg):
        arg='(%d,%d) (%d,%d)' % (int(self.scn_width*0.9), int(self.scn_height*0.5), int(self.scn_width*0.1),int(self.scn_height*0.5) )
        self.do_drag(arg)

    def do_slideright(self, str_arg):
        arg='(%d,%d) (%d,%d)' % (int(self.scn_width*0.1), int(self.scn_height*0.5), int(self.scn_width*0.9),int(self.scn_height*0.5) )
        self.do_drag(arg)

    def do_slideup(self, str_arg):
        arg='(%d,%d) (%d,%d)' % (int(self.scn_width*0.5), self.scn_height-200, int(self.scn_width*0.5),0 )
        self.do_drag(arg)

    def do_slidedown(self, str_arg):
        arg='(%d,%d) (%d,%d)' % (int(self.scn_width*0.5), 100, int(self.scn_width*0.5),self.scn_height )
        self.do_drag(arg)
    '''
    start an activity
    '''
    def do_start(self, str_arg):
        printLog(self.threadName+"[running command 'start %s']" % str_arg)
        try:
            self.md.startActivity(self.__validateString(str_arg))
        except:
            self.resultFlag=False
        printLog(self.threadName+'[status=%s]' % self.resultFlag)

    def do_takesnapshot(self, str_arg):
        img=None
        fname=self.__validateString(str_arg)
        try:
            self.md.wake()
            printLog(self.threadName+'taking snapshot (0,50,%d,%d) ...' % \
            (self.scn_width, int(self.scn_height)))
            img=self.md.takeSnapshot().getSubImage((0, 50, \
                self.scn_width, int(self.scn_height)))
            img.writeToFile(fname, 'png')
#            if self.scn_width>SNAPSHOT_WIDTH:
#                self.__compressImage(fname)
#                os.remove(fname)
#                im.save(fname)
                
            printLog(self.threadName+'snapshot saved as %s' % fname)
        except:
            self.resultFlag=False
            traceback.print_exc()
        finally:
            img=None
        printLog(self.threadName+'[status=%s]' % self.resultFlag)

    """
    take snap shot of the given area
    format: takesnapshotx (0,0) (400,400) a1.png
    """
    def do_takesnapshotx(self, str_arg):
        img=None
        fname=""
        args=self.__validateString(str_arg)
#        print args
        try:
            pa=re.compile('^(\(\d*,\d*\))\D*(\(\d*,\d*\))(.+)$')
            matches=pa.search(args.strip()).groups()
#            print matches
            point1=self.__getPointXY(matches[0])
            point2=self.__getPointXY(matches[1])
            fname=matches[2].strip()
        except AttributeError, e:
            print e.message
            raise ValueError('Bad parameter.')
        try:
            self.md.wake()
            img=self.md.takeSnapshot()
            printLog(self.threadName+'getting sub image: x0=%d, y0=%d, width=%d, height=%d' % \
                    (int(point1[0]),\
                    int(point1[1]),\
                    (int(point2[0])-int(point1[0])),\
                    (int(point2[1])-int(point1[1]))))
            img=img.getSubImage(\
                    (int(point1[0]),\
                    int(point1[1]),\
                    (int(point2[0])-int(point1[0])),\
                    (int(point2[1])-int(point1[1]))))
            img.writeToFile(fname, 'png')
            img=None
        except Exception, e:
            self.resultFlag=False
            printLog(self.threadName+'Exception: %s' % e.message, logging.ERROR)
        printLog(self.threadName+'[status=%s]' % self.resultFlag)

    def do_type(self, str_arg):
        try:
            self.md.type(self.__validateString(str_arg))
        except:
            self.resultFlag=False
        printLog(self.threadName+'[status=%s]' % self.resultFlag)

#	'''
#	get the UI text of the specified UI id
#	'''
#    def getText(self, id):
#        text1=None
#    #		print 'in gettext'
#        try:
#            compID=By.id(id)
#            #all our checked items, must be visible
#            if not self.ed.visible(compID):
#                self.resultFlag=False
#                printLog(self.threadName+'[%s not found.]' % compID, logging.ERROR)
#                return text1
#        except Exception, e:
#            printLog(self.threadName+'Failed to get text by id %s, exception: %s' % (id, e.message), logging.ERROR)
#            return text1
#        try:
#            #get id text
#            text1=self.ed.getText(compID)
#            printLog(self.threadName+'[text on screen: %s]' % text1)
#        except java.lang.RuntimeException:
#            printLog(self.threadName+'Runtime Exception! %s not found' % compID,logging.ERROR)
#        except Exception, e:
#            printLog(self.threadName+e.message,logging.ERROR)
#        finally:
#            return text1

