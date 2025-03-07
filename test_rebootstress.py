#!/usr/bin/env python
import os
import logging
import time
import sys

import pytest

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
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"start {casename} stress test....")
    with open("param.txt") as f:
        param = f.read().strip()
    _ret = os.system("bash ./reboottest_asic.sh %s" % ' '.join(param.split()[:3]))
    assert _ret == 0, f"{casename} stress test failed"
    logger.info(f"{casename} stress test finished...")


def test_coldreboot():
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"start {casename} stress test....")
    with open("param.txt") as f:
        param = f.read().strip()
    if len(param.split()) != 6:
        pytest.skip("no bmc information, cold reboot skipped")
    _ret = os.system("bash ./reboottest_asic.sh %s" % param)
    assert _ret == 0, f"{casename} stress test failed"
    logger.info(f"{casename} stress test finished...")

def setup_module():
    logger.info("clean log...")
    # os.system("rm -rf reboottest_asic*.log")
    os.system("rm -rf reboot_testlog.zip")

def teardown_module():
    logger.info("collect log")
    os.system("zip -r reboot_testlog.zip reboottest_log")
    logger.info("reboot stress test finished...")
    time.sleep(120)