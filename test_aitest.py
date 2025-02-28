#!/usr/bin/env python
import os
import sys
import time
import logging

os.system("rm -rf aitest_log;mkdir aitest_log")

LOGFILE = "aitest_log/aitest_%s.log" % time.strftime("%Y%m%d%H%M%S", time.localtime())
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


def test_PCIe_SYS_AI_performance_002():
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"casename: {casename} start testing...")
    toolpath = "cuda-samples*/Samples/0_Introduction/matrixMul"
    tool = toolpath.split('/')[-1]
    _ret = os.system(f"/bin/bash -c 'cd {toolpath};make clean;make;cd -;{toolpath}/{tool} | tee {functionname}.log; exit ${{PIPESTATUS[0]}}'")
    logger.info(f"casename: {casename}-{tool} testing finished...")
    assert _ret == 0


def test_PCIe_SYS_AI_performance_001():
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"casename: {casename} start testing...")
    toolpath = "cuda-samples*/Samples/3_CUDA_Features/cudaTensorCoreGemm"
    tool = toolpath.split('/')[-1]
    _ret = os.system(f"/bin/bash -c 'cd {toolpath};make clean;make;cd -;{toolpath}/{tool} | tee aitest_log/{functionname}.log; exit ${{PIPESTATUS[0]}}'")
    logger.info(f"casename: {casename}-{tool} testing finished...")
    assert _ret == 0


def test_PCIe_SYS_AI_performance_004():
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"casename: {casename} start testing...")
    toolpath = "cuda-samples*/Samples/4_CUDA_Libraries/batchCUBLAS"
    tool = toolpath.split('/')[-1]
    _ret = os.system(f"/bin/bash -c 'cd {toolpath};make clean;make;cd -;{toolpath}/{tool} | tee aitest_log/{functionname}.log; exit ${{PIPESTATUS[0]}}'")
    logger.info(f"casename: {casename}-{tool} testing finished...")
    assert _ret == 0


def test_PCIe_SYS_AI_004():
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"casename: {casename} start testing...")
    toolpath = "cuda-samples*/Samples/5_Domain_Specific/p2pBandwidthLatencyTest"
    tool = toolpath.split('/')[-1]
    _ret = os.system(f"/bin/bash -c 'cd {toolpath};make clean;make;cd -;{toolpath}/{tool} | tee aitest_log/{functionname}.log; exit ${{PIPESTATUS[0]}}'")
    logger.info(f"casename: {casename}-{tool} testing finished...")
    assert _ret == 0


def test_PCIe_SYS_AI_005():
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"casename: {casename} start testing...")
    toolpath = "cuda-samples*/Samples/0_Introduction/simpleMultiCopy"
    tool = toolpath.split('/')[-1]
    _ret = os.system(f"/bin/bash -c 'cd {toolpath};make clean;make;cd -;{toolpath}/{tool} | tee aitest_log/{functionname}.log; exit ${{PIPESTATUS[0]}}'")
    logger.info(f"casename: {casename}-{tool} testing finished...")
    assert _ret == 0


def test_PCIe_SYS_AI_006():
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"casename: {casename} start testing...")
    toolpath = "cuda-samples*/Samples/1_Utilities/bandwidthTest"
    tool = toolpath.split('/')[-1]
    _ret = os.system(f"/bin/bash -c 'cd {toolpath};make clean;make;cd -;{toolpath}/{tool} | tee aitest_log/{functionname}.log; exit ${{PIPESTATUS[0]}}'")
    logger.info(f"casename: {casename}-{tool} testing finished...")
    assert _ret == 0


def test_PCIe_SYS_AI_007():
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"casename: {casename} start testing...")
    toolpath = "cuda-samples*/Samples/0_Introduction/simpleP2P"
    tool = toolpath.split('/')[-1]
    _ret = os.system(f"/bin/bash -c 'cd {toolpath};make clean;make;cd -;{toolpath}/{tool} | tee aitest_log/{functionname}.log; exit ${{PIPESTATUS[0]}}'")
    logger.info(f"casename: {casename}-{tool} testing finished...")
    assert _ret == 0


def test_streamOrderedAllocation():
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"casename: {casename} start testing...")
    toolpath = "cuda-samples*/Samples/2_Concepts_and_Techniques/streamOrderedAllocation"
    tool = toolpath.split('/')[-1]
    _ret = os.system(f"/bin/bash -c 'cd {toolpath};make clean;make;cd -;{toolpath}/{tool} | tee aitest_log/{functionname}.log; exit ${{PIPESTATUS[0]}}'")
    logger.info(f"casename: {casename}-{tool} testing finished...")
    assert _ret == 0


def test_simpleStreams():
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"casename: {casename} start testing...")
    toolpath = "cuda-samples*/Samples/0_Introduction/simpleStreams"
    tool = toolpath.split('/')[-1]
    _ret = os.system(f"/bin/bash -c 'cd {toolpath};make clean;make;cd -;{toolpath}/{tool} | tee aitest_log/{functionname}.log; exit ${{PIPESTATUS[0]}}'")
    logger.info(f"casename: {casename}-{tool} testing finished...")
    assert _ret == 0


def test_vectorAdd():
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"casename: {casename} start testing...")
    toolpath = "cuda-samples*/Samples/0_Introduction/vectorAdd"
    tool = toolpath.split('/')[-1]
    _ret = os.system(f"/bin/bash -c 'cd {toolpath};make clean;make;cd -;{toolpath}/{tool} | tee aitest_log/{functionname}.log; exit ${{PIPESTATUS[0]}}'")
    logger.info(f"casename: {casename}-{tool} testing finished...")
    assert _ret == 0


def test_UnifiedMemoryPerf():
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"casename: {casename} start testing...")
    toolpath = "cuda-samples*/Samples/6_Performance/UnifiedMemoryPerf"
    tool = toolpath.split('/')[-1]
    _ret = os.system(f"/bin/bash -c 'cd {toolpath};make clean;make;cd -;{toolpath}/{tool} | tee aitest_log/{functionname}.log; exit ${{PIPESTATUS[0]}}'")
    logger.info(f"casename: {casename}-{tool} testing finished...")
    assert _ret == 0


def setup_module():
    logger.info("clean old logs...")
    os.system(f"rm -rf ai_testlog.zip")
    logger.info("unzip cuda-samples")
    os.system("tar xvf cuda-samples*.tar.gz > /dev/null 2>&1")


def teardown_module():
    os.system("zip -r ai_testlog.zip aitest_log")
    logger.info("clean logs...")
    # os.system("rm -rf *.log")


def setup():
    pass

def teardown():
    pass
