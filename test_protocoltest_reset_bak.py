import os
import subprocess
import logging
import time
import sys
from functools import wraps
import re

import pytest

os.system('rm -rf protocol_log/reset; mkdir -p protocol_log/reset')
LOGFILE = "protocol_log/reset/protocoltest_%s.log" % time.strftime("%Y%m%d%H%M%S", time.localtime())
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

switchinfo = []
mep_vd = '205e:0101'
dma0_vd = '205e:1234'
dma1_vd = '205e:5678'
syspath = "/sys/bus/pci/devices/"

PCI_CLASS_MASKS = {
    # https://pcisig.com/sites/default/files/files/PCI_Code-ID_r_1_11__v24_Jan_2019.pdf
    # ordered by class hex, not alphabetically
    "scsi_controller": (0x010000, 0xFFFF00),
    "ide_interface": (0x010100, 0xFFFF00),
    "raid": (0x010400, 0xFFFFFF),
    "sata_controller": (0x010600, 0xFFFF00),
    "serial_scsi_controller": (0x010700, 0xFFFF00),
    "nvme": (0x010802, 0xFFFFFF),
    "network": (0x020000, 0xFF0000),
    "ethernet": (0x020000, 0xFFFFFF),
    "gpu": (0x030000, 0xFF0000),
    "usb": (0x0C0300, 0xFFFF00),
    "fibre_channel": (0x0C0400, 0xFFFFFF),
    "accelerators": (0x120000, 0xFF0000),
}

def decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        functionname = func.__name__
        casename = functionname.replace("test_", "")
        logger.info(f"casename: {casename} start testing...")
        func(*args, **kwargs)
        logger.info(f"casename: {casename} test finished...")
    return wrapper

def callcmd(command, timeout=10, ignore=False):
    pipe = subprocess.Popen(command, universal_newlines=True, stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE, start_new_session=True, shell=True)
    output, error = pipe.communicate(timeout=timeout)
    ret = pipe.returncode
    if ret != 0:
        error = error.replace("\n", "").replace("\r", "")
        logger.error(
            "Execute command %s failed.\n %s" % (command, error))
        return False, error
    else:
        logger.info(
            "Execute command %s succeed.\n %s" % (command, output))
        return True, output

def get_switch_info():
    ret, msg = callcmd("lspci -Dnd 205e: | awk '{if($2==\"0604:\")print $1}'")
    if ret:
        switchinfo = msg.strip().split('\n')
    else:
        assert False, f"no sudo switch found, detail is {msg}"

    usplist = []
    dsplist = []

    for i in switchinfo:
        ret, msg = callcmd(f"lspci -vvvs {i} | grep -i 'Downstream Port'")
        if ret:
            dsplist.append(i)
        else:
            usplist.append(i)


    eplist = {}
    for i in dsplist:
        ret, msg = callcmd(f"ls -l {syspath} | egrep -o '{i}/(.*?)' | cut -d'/' -f2")
        if ret:
            for ep in msg.strip().split():
                classid = get_classcode(ep)
                vd = get_vd(ep)
                driver = get_driver(ep)
                eplist.update({ ep: [ classid, vd, driver ]})

    return [usplist, dsplist, eplist]


def get_vd(bdf):
    ret, msg = callcmd(f"lspci -n -s {bdf} | awk '{{print $3}}'")

    return msg.strip()


def get_driver(bdf):
    ret, msg = callcmd(f"lspci -ks {bdf} | grep -i 'Kernel driver in use:' | awk '{{print $5}}'")

    return msg.strip()

def get_classcode(bdf):
    devicepath = os.path.join(f'{syspath}', f'{bdf}', 'class')
    with open(devicepath) as f:
        classcode = f.read().strip()[2:4]
    return classcode

@decorator
def test_PCIe_SYS_RST_001():
    pytest.skip("test covered by reboot test...")


@decorator
def test_PCIe_SYS_RST_002():
    pytest.skip("test covered by reboot test...")


@decorator
def test_PCIe_SYS_RST_003():
    usplist = switchinfo[0]
    for usp in usplist:
        sbr_set(usp)
        ret = read_config_lspci(usp)
        assert ret == False, "usp sbr test failed"


@decorator
def test_PCIe_SYS_RST_004():
    dsplist = switchinfo[1][:-3]
    for dsp in dsplist:
        sbr_set(dsp)
        ret = read_config_lspci(dsp)
        assert ret == False, "dsp sbr test failed"


@decorator
def test_PCIe_SYS_RST_005():
    dsplist = switchinfo[1][-2:]
    for dsp in dsplist:
        sbr_set(dsp)
        ret = read_config_lspci(dsp)
        assert ret == False, "dma idsp sbr test failed"


@decorator
def test_PCIe_SYS_RST_006():
    dsp = switchinfo[1][-3]
    sbr_set(dsp)
    ret = read_config_lspci(dsp)
    assert ret == False, "mep idsp sbr test failed"

@decorator
def test_PCIe_SYS_RST_007():
    pytest.skip("not support...")


@decorator
def test_PCIe_SYS_RST_008():
    pytest.skip("covered by reboot test...")


def checkdeviceinfo(device):
    width_ret, speed_ret = True, True
    ret, msg = callcmd(f"lspci -vvvs {device} | egrep -i 'lnkcap:|lnksta:'")
    if ret:
        info = re.findall(r'(\d+GT/s|Width x\d+)', msg)
        logger.info(f"{device} Cap -> speed:{info[0]}, width:{info[1]}")
        logger.info(f"{device} Sta -> speed:{info[2]}, width:{info[3]}")
        if info[1] != info[3]:
            logger.info(f"{device} width is not same as expected")
            width_ret = False
        else:
            logger.info(f"{device} width is same as expected")

        classcode = get_classcode(device)
        if classcode[0:2] != '03':
            if info[0] != info[2]:
                logger.info(f"{device} speed is not same as expected")
                speed_ret = False
            else:
                logger.info(f"{device} speed is same as expected")
        else:
            logger.info(f"{device} is gpu, skip test")
    else:
        assert False, f'cannot get {device} by lspci'
    return width_ret & speed_ret

# def check_IO_MEM_BAR(bdf):
#     _ret = 0
#     _, msg = callcmd(f"lspci -vvvs {bdf}")
#     iosta = re.search('I/O.', msg.decode()).group()
#     iobar = re.search(r"Region \d+: I/O | I/O behind bridge", msg.decode()).group()
#     memsta = re.search('Mem.', msg.decode()).group()
#     membar = re.search(r"Region \d+: Memory at | Memory behind bridge", msg.decode()).group()
#     if iosta == 'I/O-' and ('ignored' in iobar or 'disabled' in iobar):
#         logger.info("I/O check passed")
#     elif iosta == 'I/O+' and not ('ignored' in iobar or 'disabled' in iobar):
#         logger.info("I/O check passed")
#     else:
#         logger.info("I/O check failed")
#         _ret = 1
#     if switchinfo[2][bdf][2]:
#         if memsta == 'Mem-' and ('ignored' in iobar or 'disabled' in membar):
#             logger.info("Mem check passed")
#         elif memsta == 'Mem+' and not ('ignored' in iobar or 'disabled' in membar):
#             logger.info("Mem check passed")
#         else:
#             logger.info("Mem check failed")
#             _ret = 1
#
#     return _ret

def read_config_lspci(bdf):
    ret, msg = callcmd(f"lspci -vvvs {bdf} | grep 'Unknown header type'", timeout=120)
    return ret

def sbr_set(bdf):
    _ret = 0
    logger.info(f"read data from BDF:{bdf}")
    ret, orgdata = callcmd(f"setpci -s {bdf} BRIDGE_CONTROL.w")
    assert ret, f"read data from {bdf} by setpci failed"
    ret, msg = callcmd(f"setpci -s {bdf} BRIDGE_CONTROL.w={hex(int(orgdata, 16) | (1<<6))}")
    assert ret, f"write data to {bdf} by setpci failed"
    time.sleep(.1)
    ret, msg = callcmd(f"setpci -s {bdf} BRIDGE_CONTROL.w={hex(int(orgdata, 16) & ~(1<<6))}")
    assert ret, f"write data to {bdf} by setpci failed"
    time.sleep(5)
    logger.info(f"reset {bdf} success")
    return ret


def setup_module():
    logger.info("init environment")
    global switchinfo
    switchinfo = get_switch_info()


def teardown_module():
    os.system("zip -r network_testlog.zip networktest_log")


def setup():
    pass


def teardown():
    pass


if __name__ == '__main__':
    get_switch_info()