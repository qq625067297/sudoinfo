#!/usr/bin/env python
import os
import sys
import time
import logging
import subprocess
from multiprocessing import Process, Queue
import pytest


LOGFILE = "networktest_%s.log" % time.strftime("%Y%m%d%H%M%S", time.localtime())
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

linkedports = []
BASE_IP="100.1.1"
NETSERVER_PORT = 9011
runtime = 600


def setup_vfio(pci_addresses):
    """配置 VFIO 设备直通"""
    try:
        # 加载必要的内核模块
        subprocess.run(["modprobe", "vfio-pci"])

        for bus, slot, func in pci_addresses:
            pci_addr = f"{bus}:{slot}.{func}"
            device_path = f"/sys/bus/pci/devices/0000:{pci_addr}"

            # 获取设备的vendor和device ID
            with open(f"{device_path}/vendor", 'r') as f:
                vendor_id = f.read().strip()
            with open(f"{device_path}/device", 'r') as f:
                device_id = f.read().strip()

            # 解绑原有驱动
            if os.path.exists(f"{device_path}/driver"):
                with open(f"{device_path}/driver/unbind", 'w') as f:
                    f.write(f"0000:{pci_addr}")

            # 添加设备ID到vfio-pci
            with open("/sys/bus/pci/drivers/vfio-pci/new_id", 'w') as f:
                f.write(f"{vendor_id[2:]} {device_id[2:]}")

            # 绑定到vfio-pci驱动
            with open(f"{device_path}/driver_override", 'w') as f:
                f.write("vfio-pci")

            with open("/sys/bus/pci/drivers_probe", 'w') as f:
                f.write(f"0000:{pci_addr}")

        return True
    except Exception as e:
        print(f"Error setting up VFIO: {e}")
        return False

def test_PF_under_same_netcard():
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"casename: {casename} start testing...")
    global linkedports
    linkedports = configure_network_interfaces()
    logger.debug(f"linkedports:{linkedports}")
    _ret = run_netperf(linkedports, 0)
    result = ['pass', 'fail'][_ret]
    logger.info(f"casename: {casename} testing {result}...")
    assert _ret == 0, f"{casename} 测试失败"


def test_PF_under_diff_netcard():
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"casename: {casename} start testing...")
    _ret = run_netperf(linkedports, 1)
    result = ['pass', 'fail'][_ret]
    logger.info(f"casename: {casename} testing {result}...")
    assert _ret == 0, f"{casename} 测试失败"

def get_switch_info():
    pipe = subprocess.Popen("lspci -nd 205e: | awk '{if($2==\"0604:\")print $1}'",
                            universal_newlines=True,
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE, shell=True)
    output, error = pipe.communicate(timeout=10)
    if pipe.returncode == 0:
        switchinfo = output.strip().split('\n')

    usplist = []
    dsplist = []

    for i in switchinfo:
        pipe = subprocess.Popen(f"lspci -vvvs {i} | grep -i 'Downstream Port'",
                                universal_newlines=True,
                                stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE, shell=True)
        output, error = pipe.communicate(timeout=10)
        if output:
            dsplist.append(i)
        else:
            usplist.append(i)
    eplist = []
    for i in dsplist:
        pipe = subprocess.Popen(f"lspci -nPP  | awk '{{print $1}}' | egrep -o '{i}/(.*?)' | cut -d'/' -f2",
                                universal_newlines=True,
                                stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE, shell=True)
        output, error = pipe.communicate(timeout=10)
        if output:
            eplist += output.strip().split()

    return [usplist, dsplist, eplist]

def get_switch_networkinfo():
    '''
    get network port with network cable
    :return:
    '''
    pipe = subprocess.Popen("ip link show | grep -i 'state UP'  | grep -E '^[0-9]+:' "
                            "| awk -F': ' '{print $2}'| grep -E '^en'",
                            universal_newlines=True,
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE, shell=True)
    output, error = pipe.communicate(timeout=10)
    if pipe.returncode == 0:
        netportlist = output.strip().split()
    else:
        raise Exception("get networkinfo failed")
    networklist = []
    eplist = get_switch_info()[-1]
    for port in netportlist:
        pipe = subprocess.Popen(f"ethtool -i {port} | grep -i bus-info",
                                universal_newlines=True,
                                stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE, shell=True)
        output, error = pipe.communicate(timeout=10)
        for ep in eplist:
            if ep in output:
                networklist.append([ep, port])

    return networklist


def configure_network_interfaces():
    networklist = get_switch_networkinfo()
    logger.debug(f"networklist:{networklist}")
    portnames = [ i[1] for i in networklist ]
    logger.debug(f'portnames:{portnames}')
    namespaceinfo = {}
    linkedports = []
    ip_counter = 1
    for port in portnames:
        IP = f"{BASE_IP}.{ip_counter}"
        pipe = subprocess.Popen(f"ip netns add {port} "
                                f"&& ip link set {port} netns {port} "
                                f"&& ip netns exec {port} ip addr flush dev {port} "
                                f"&& ip netns exec {port} ip addr add {IP}/24 dev {port} "
                                f"&& ip netns exec {port} ip link set dev {port} up",
                                universal_newlines=True,
                                stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE, shell=True)
        output, error = pipe.communicate(timeout=30)
        ret = os.system(f"ip netns ls | grep -i {port}")
        if ret == 0:
            logger.info(f"create namespace {port} passed...")
        else:
            logger.info(f"create namespace {port} failed...")
            raise Exception(error)
        namespaceinfo.update({port:IP})
        ip_counter += 1

    for i in range(len(portnames) - 1):
        for j in range(i + 1, len(portnames)):
            pipe = subprocess.Popen(f"ip netns exec {portnames[i]} ping -c 3 {namespaceinfo[portnames[j]]} > /dev/null 2>&1",
                                    universal_newlines=True,
                                    stderr=subprocess.PIPE,
                                    stdout=subprocess.PIPE, shell=True)
            output, error = pipe.communicate(timeout=30)
            if pipe.returncode == 0:
                linkedports.append({portnames[i]:namespaceinfo[portnames[i]], portnames[j]:namespaceinfo[portnames[j]]})
                logger.info(f'{portnames[i]}-IP:{namespaceinfo[portnames[i]]} link to {portnames[j]}-IP:{namespaceinfo[portnames[j]]}')

    return linkedports


def networktest(q, clientport, clientip, serverip, durtime, mode):
    pipe = subprocess.Popen(f"ip netns exec {clientport} netperf -H {serverip} -L {clientip} "
                            f"-l {durtime} -t {mode} -p {NETSERVER_PORT} -D 10 > {clientport}_{mode}.log",
                            universal_newlines=True,
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE, shell=True)
    output, error = pipe.communicate(timeout=durtime+10)
    for line in output.strip().split():
        logger.info(line)
    q.put(pipe.returncode)

def run_netperf(linkedports, mode=1):
    ''''
        mode: 0 :same card different port
            1 :different card
    '''
    samecardlist = []
    differentcardlist = []

    for i in linkedports:
        m, n = list(i)
        if m[:-1] == n[:-1]:
            samecardlist.append(i)
        else:
            differentcardlist.append(i)
    if mode == 0 and len(samecardlist) == 0:
        pytest.skip("no ports in same card,skip testing")
    if mode == 1 and len(differentcardlist) == 0:
        pytest.skip("no ports in different card,skip testing")
    processes = []
    q = Queue()
    test_modes = ["TCP_RR", "TCP_CRR", "UDP_RR", "UDP_STREAM", "TCP_STREAM"]
    for portdict in [samecardlist, differentcardlist][mode]:
        logger.debug(f'portdict:{portdict}')
        server, client = list(portdict)
        pipe = subprocess.Popen(f"ip netns exec {server} netserver -p {NETSERVER_PORT} -D > {server}_netserver.log",
                                universal_newlines=True,
                                stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE, shell=True)
        time.sleep(1)
        ret = os.system("ps aux | grep -v grep | grep netserver > /dev/null 2>&1")
        assert ret == 0, "start netserver failed..."
        logger.info("start netserver successed...")

        processes += [Process(target=networktest, args=(q, client, portdict[client], portdict[server], runtime, mode)) for mode in test_modes]

    for p in processes:
        p.start()

    for p in processes:
        p.join()

    return sum([q.get() for _ in processes])

def setup_module():
    logger.info("init environment")
    os.system("pkill -9 netserver > /dev/null 2>&1")
    os.system("pkill -9 netperf > /dev/null 2>&1")
    os.system("ip -all netns delete > /dev/null 2>&1")
    os.system("rm *.log > /dev/null 2>&1")
    time.sleep(5)
    networklist = get_switch_networkinfo()
    if len(networklist) == 0:
        assert False, "no network ports found..."
    for net in networklist:
        logger.info(f"network ports in switch:{net[0]}->{net[1]}")


def teardown_module():
    os.system("zip testlog.zip *.log")


def setup():
    pass

def teardown():
    pass


if __name__ == '__main__':
    portinfolist = configure_network_interfaces()
    run_netperf(portinfolist)