#!/usr/bin/env python
import os
import sys
import logging
import time

os.system("rm -rf reboottest_log;mkdir reboottest_log")

LOGFILE = "reboottest_log/reboottest_%s.log" % time.strftime("%Y%m%d%H%M%S", time.localtime())
#设置日志打印格式
# 创建logger
logger = logging.getLogger('logger')
logger.setLevel(logging.DEBUG)  # 设置日志级别
# 创建控制台处理器
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
#创建file handler
fh = logging.FileHandler(LOGFILE)
fh.setLevel(logging.INFO)
# 创建格式器并绑定到处理器
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(lineno)s - %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)
# 将处理器添加到logger
logger.addHandler(ch)
logger.addHandler(fh)

def test_warmreboot():
    logger.info("start warm reboot stress test....")
    with open("param.txt") as f:
        param = f.read().strip()
    _ret = os.system("bash ./reboottest_asic.sh %s" % ' '.join(param.split()[:3]))
    assert _ret == 0, "warm reboot stress failed..."
    logger.info("warm reboot stress test finished...")


def test_coldreboot():
    logger.info("start cold reboot stress test....")
    with open("param.txt") as f:
        param = f.read().strip()
    _ret = os.system("bash ./reboottest_asic.sh %s" % param)
    assert _ret == 0
    logger.info("cold reboot stress test finished...")

def setup_module():
    logger.info("clean log...")
    # os.system("rm -rf reboottest_asic*.log")
    os.system("rm -rf reboot_testlog.zip")

def teardown_module():
    print("collect log")
    os.system("zip reboot_testlog.zip reboottest_log")
    print("reboot stress test finished...")
