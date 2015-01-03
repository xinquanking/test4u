test4u
======

test4u is an android App automate test framework designed for middle-sized agile team/group.

##What you can get from test4u?
1. quick runnable testcases to cover your smoke test
2. test logic in natural language
3. flexible testcases to maintain
4. extensible modules to add test functions

##Environment Setup

test4u is verified on Ubuntu LTS 12.04 and 14.04. I don't have a plan to support Windows yet.

###Setup Your Ubuntu Test Server

####1. install open-ssh server

```bash
sudo apt-get install openssh-server
```
####2. install Java 7

```bash
sudo add-apt-repository ppa:webupd8team/java
sudo apt-get update
sudo apt-get install oracle-java7-installer
...
export JAVA_HOME=/usr/lib/jvm/java-7-oracle
```
Reference: http://blog.csdn.net/longshengguoji/article/details/38466915

####3. configure JDK7
http://www.linuxidc.com/Linux/2014-05/101038.htm

####4. install ia32 libs
```bash
sudo apt-get install -y libc6-i386 lib32stdc++6 lib32gcc1 lib32ncurses5 lib32z1
```
Reference: http://www.cnblogs.com/sink_cup/archive/2011/10/31/ubuntu_x64_android_sdk_java.html

####5. install Android SDK
```bash
cd ~/Downloads/
wget http://dl.google.com/android/android-sdk_r22.6.2-linux.tgz
tar -zxvf android-sdk_r22.6.2-linux.tgz
echo 'export ANDROID_HOME="'$HOME'/Downloads/android-sdk-linux"' >> ~/.bashrc
echo 'export PATH="$PATH:$ANDROID_HOME/tools:$ANDROID_HOME/platform-tools"' >> ~/.bashrc
```

### Setup test4u
unzip the package you downloaded to a directory, e.g. /home/your_name/test4u

#### test your environment
```bash
cd /home/your_name/test4u
./AppTester.py smoke
```
make sure you get something like below from the output.
```bash
swang@uautoqa0:~/workspace/git/test4u$ ./AppTester.py smoke
---------------------------------------------------------------------------------------------------------------
[Main] Test suite specified: smoke
[Main] Build number not specified, use latest build.
---------------------------------------------------------------------------------------------------------------
DEBUG    [runShellCmd] Running cmd:adb devices|awk -F'\t' '{print $1}'
DEBUG    [runShellCmd] Command returns:
output:List of devices attached 
014697590A01F00F

DEBUG    List of devices attached: 
['014697590A01F00F']

```
If you encounter other error, check your server setup first and contact me whenever necessary. Make sure you send me the full log output so I can help.

## tester's guide
With test4u, a tester is not required to be familiar with monkeyrunner APIs. The only prerequisit is basic python/jython programming abilities.
### start customizing test4u for your App and run your first automated test
#### configure t4uenv.ini
 * 
#### organize your testcases and test suites
  * 
#### implement necessary functions in AppTester.py
#### add your own functions (optional)

## developer's guide
coming soon.
