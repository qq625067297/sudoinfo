import os
import subprocess
import logging
import time
import sys
from functools import wraps
import re

import pytest

os.system('rm -rf protocol_log/mem; mkdir -p protocol_log/mem')
LOGFILE = "protocol_log/mem/protocoltest_%s.log" % time.strftime("%Y%m%d%H%M%S", time.localtime())
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
                eplist.update({ep: [classid, vd, driver]})

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
def test_PCIe_SYS_MEM_001():
    COUNT = 0
    eps = switchinfo[2]
    for ep in eps:
        if eps[ep][1] in [mep_vd, dma0_vd, dma1_vd]:
            continue
        status = False
        ret, msg = callcmd(
            f"lspci -vvvs {ep} | grep '64-bit, prefetchable' | grep 'size' | egrep -v 'ignored|disabled'")
        if ret:
            COUNT += 1
            addresslist = re.findall(r"Memory at ([0-9a-f]{8,})", msg)
            for address in addresslist:
                address_offset = hex(int(address, 16) + 288)
                data = 0x0
                ret, msg = callcmd(f"devmem2 {address_offset} w {data}")
                retdata = re.search(r"Written 0x([0-9A-F]+); readback 0x([0-9A-F]+)", msg)
                if retdata.group(1) == retdata.group(2):
                    status = True
                    break
            assert status, f"{ep} write data to bar memory by devmem2 failed"
    assert COUNT, f"no ep has 64-bit, prefetchable"


@decorator
def test_PCIe_SYS_MEM_002():
    COUNT = 0
    eps = switchinfo[2]
    for ep in eps:
        if eps[ep][1] in [mep_vd, dma0_vd, dma1_vd]:
            continue
        status = False
        ret, msg = callcmd(f"lspci -vvvs {ep} | grep '64-bit, non-prefetchable' | grep 'size' | egrep -v "
                           f"'ignored|disabled'")
        if ret:
            COUNT += 1
            addresslist = re.findall(r"Memory at ([0-9a-f]{8,})", msg)
            for address in addresslist:
                address_offset = hex(int(address, 16) + 288)
                data = 0x0
                ret, msg = callcmd(f"devmem2 {address_offset} w {data}")
                retdata = re.search(r"Written 0x([0-9A-F]+); readback 0x([0-9A-F]+)", msg)
                if retdata.group(1) == retdata.group(2):
                    status = True
                    break
            assert status, f"{ep} write data to bar memory by devmem2 failed"
    assert COUNT, f"no ep has 64-bit, non-prefetchable"


@decorator
def test_PCIe_SYS_MEM_003():
    COUNT = 0
    eps = switchinfo[2]
    for ep in eps:
        if eps[ep][1] in [mep_vd, dma0_vd, dma1_vd]:
            continue
        status = False
        ret, msg = callcmd(
            f"lspci -vvvs {ep} | grep '32-bit, prefetchable' | grep 'size' | egrep -v 'ignored|disabled'")
        if ret:
            COUNT += 1
            addresslist = re.findall(r"Memory at ([0-9a-f]{8,})", msg)
            for address in addresslist:
                address_offset = hex(int(address, 16) + 288)
                data = 0x0
                ret, msg = callcmd(f"devmem2 {address_offset} w {data}")
                retdata = re.search(r"Written 0x([0-9A-F]+); readback 0x([0-9A-F]+)", msg)
                if retdata.group(1) == retdata.group(2):
                    status = True
                    break
            assert status, f"{ep} write data to bar memory by devmem2 failed"
    assert COUNT, f"no ep has 32-bit, prefetchable"


@decorator
def test_PCIe_SYS_MEM_004():
    COUNT = 0
    eps = switchinfo[2]
    for ep in eps:
        if eps[ep][1] in [mep_vd, dma0_vd, dma1_vd]:
            continue
        status = False
        ret, msg = callcmd(f"lspci -vvvs {ep} | grep '32-bit, non-prefetchable' | grep 'size' | egrep -v "
                           f"'ignored|disabled'")
        if ret:
            COUNT += 1
            addresslist = re.findall(r"Memory at ([0-9a-f]{8,})", msg)
            for address in addresslist:
                address_offset = hex(int(address, 16) + 288)
                data = 0x0
                ret, msg = callcmd(f"devmem2 {address_offset} w {data}")
                retdata = re.search(r"Written 0x([0-9A-F]+); readback 0x([0-9A-F]+)", msg)
                if retdata.group(1) == retdata.group(2):
                    status = True
                    break
            assert status, f"{ep} write data to bar memory by devmem2 failed"
    assert COUNT, f"no ep has 32-bit, non-prefetchable"


@decorator
def test_PCIe_SYS_MEM_005():
    COUNT = 0
    eps = switchinfo[2]
    ret, msg = callcmd(f"dd if=/dev/urandom of=1G.txt bs=1M count=1024", timeout=600)
    if ret:
        logger.info("create 1G file success")
    else:
        assert False, "create 1G file fail"

    for ep in eps:
        if eps[ep][1] in [mep_vd, dma0_vd, dma1_vd] or eps[ep][0] != '01':
            continue
        ret, msg = callcmd(f'ls /sys/bus/pci/devices/{ep}/nvme | grep nvme')
        if not ret:
            continue
        COUNT += 1
        diskname = f'/dev/{msg.strip()}n1'
        logger.info(f"start to write 1G file to {diskname}")
        ret, msg = callcmd(f"dd if=1G.txt of={diskname} bs=1M count=1024")
        if ret:
            logger.info(f"write 1G file to {diskname} successes")
        else:
            assert False, f"write 1G file to {diskname} fail"
        logger.info(f"start to read {diskname} to 1G file")
        ret, msg = callcmd(f"dd if={diskname} of=1G.tmp bs=1M count=1024", timeout=600)
        if ret:
            logger.info(f"read {diskname} to 1G file success")
        else:
            assert False, f"read {diskname} to 1G file fail"

        ret, msg = callcmd(f"md5sum 1G.txt 1G.tmp | awk '{{print $1}}' | uniq | wc -l", timeout=600)
        if ret:
            logger.info("get md5sum success")
        else:
            assert False, "get md5sum fail"
        assert msg.strip() == '1', f"md5sum check pass"

    assert COUNT, "no nvme disk found"


@decorator
def test_PCIe_SYS_MEM_006():
    eps = switchinfo[2]
    for ep in eps:
        if eps[ep][1] != mep_vd:
            continue
        ret, msg = callcmd(f"lspci -vvvs {ep} | grep 'Memory at'  | egrep -v 'ignored|disabled'")
        if ret:
            address = re.search(r"Memory at ([0-9a-f]{8,})", msg).group(1)
            address_offset = hex(int(address, 16) + 288)
            data = 0x1
            ret, msg = callcmd(f"devmem2 {address_offset} w {data}")
            retdata = re.search(r"Written 0x([0-9A-F]+); readback 0x([0-9A-F]+)", msg)
            assert retdata.group(1) == retdata.group(2), f"{ep} write data to bar memory by devmem2 failed"
        else:
            assert False, f"mep bar memory is invalid"


@decorator
def test_PCIe_SYS_MEM_007():
    eps = switchinfo[2]
    for ep in eps:
        status = False
        if eps[ep][1] not in [dma0_vd, dma1_vd]:
            continue
        ret, msg = callcmd(f"lspci -vvvs {ep} | grep 'Memory at' | grep 'size' | egrep -v 'ignored|disabled'")
        if ret:
            addresslist = re.findall(r"Memory at ([0-9a-f]{8,})", msg)
            for address in addresslist:
                address_offset = hex(int(address, 16) + 352)
                data = 0x0
                ret, msg = callcmd(f"devmem2 {address_offset} w {data}")
                retdata = re.search(r"Written 0x([0-9A-F]+); readback 0x([0-9A-F]+)", msg)
                if retdata.group(1) == retdata.group(2):
                    status = True
                    break
            assert status, f"{ep} write data to bar memory by devmem2 failed"
        else:
            assert False, "no dma bar found"


@decorator
def test_PCIe_SYS_MEM_008():
    usps = switchinfo[0]
    for usp in usps:
        ret, msg = callcmd(f'nvme list | grep /dev/ | wc -l')
        orgcount = int(msg.strip())
        bme_set(usp, status=False)
        ret, msg = callcmd(f'nvme list | grep /dev/ | wc -l')
        newcount = int(msg.strip())
        assert orgcount > newcount, f"usp:{usp} bme test failed"


@decorator
def test_PCIe_SYS_MEM_009():
    dsps = switchinfo[1]
    for dsp in dsps:
        ret, msg = callcmd(f'ls /sys/bus/pci/devices/{dsp}/*/nvme')
        if ret:
            diskname = f'/dev/{msg.strip()}n1'
            logger.info(f"{diskname} is linked to {dsp}")
            bme_set(dsp, status=False)
            ret, msg = callcmd(f'nvme list | grep {diskname}', timeout=120)
            assert ret, f"dsp:{dsp} bme test failed"
        else:
            logger.info(f"no nvme disk linked to {dsp}")


@decorator
def test_PCIe_SYS_MEM_010():
    """
    待统一测试方法
    :return:
    """
    dma = get_dma()
    bme_set(dma['dma0'][0], status=False)
    pass


@decorator
def test_PCIe_SYS_MEM_011():
    usplist = switchinfo[0]
    for usp in usplist:
        mem_set(usp, status=False)
        ret, msg = callcmd(
            f"lspci -vvvs {usp} | grep 'Memory behind bridge'")
        if ret:
            addresslist = re.findall(r"Memory at ([0-9a-f]{8,})", msg)
            for address in addresslist:
                address_offset = hex(int(address, 16) + 288)
                data = 0x0
                ret, msg = callcmd(f"devmem2 {address_offset} w {data}")
                retdata = re.search(r"Written 0x([0-9A-F]+); readback 0x([0-9A-F]+)", msg)
                if retdata.group(1) == retdata.group(2):
                    status = True
                    break
            assert status, f"{ep} write data to bar memory by devmem2 failed"


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


def get_dma():
    """
    获取dma信息
    :return:
    """
    dma0_bdf = ''
    dma1_bdf = ''
    eps = switchinfo[2]
    for ep in eps:
        if eps[ep][1] == dma0_vd:
            dma0_bdf = eps[ep][1]
        elif eps[ep][1] == dma1_vd:
            dma1_bdf = eps[ep][1]

    dma0_idsp = get_dsp(dma0_bdf)
    dma1_idsp = get_dsp(dma1_bdf)

    return {'dma0': [dma0_idsp, dma0_bdf], 'dma1': [dma1_idsp, dma1_bdf]}


def get_mep():
    """
    获取mep信息
    :return:
    """
    mep_bdf = ''
    eps = switchinfo[2]
    for ep in eps:
        if eps[ep][1] == mep_vd:
            mep_bdf = eps[ep][1]
            break

    mep_idsp = get_dsp(mep_bdf)

    return {'mep': [mep_idsp, mep_bdf]}


def get_dsp(bdf, is_ep=True):
    """
    通过ep bdf号获取dsp
    :param is_ep: True：使用ep bdf获取；False: 使用sp bdf获取
    :param bdf:
    :return:
    """
    if is_ep:
        ret, msg = callcmd(f"ls -d /sys/bus/pci/devices/*/{bdf} | awk -F/ '{{print $6}}'")
        if ret:
            return msg.strip().split()
        else:
            assert False, f"cannot get dsp "
    else:
        ret, msg = callcmd(f"ls -d /sys/bus/pci/devices/{bdf}/*/ | awk -F/ '{{print $7}}' | egrep -i '([0-9a-f]+:)+["
                           f"0-9a-f]+.[0-7]")
        if ret:
            return msg.strip().split()
        else:
            assert False, f"cannot get dsp"


def get_ep(bdf, is_usp=True):
    """
    通过usp/dsp bdf号获取dsp
    :param bdf:
    :param is_usp: True:使用usp bdf号获取ep False: 使用dsp bdf号获取ep
    :return:
    """
    if not is_usp:
        ret, msg = callcmd(
            f"ls -d /sys/bus/pci/devices/*/{bdf}/*/ | egrep -i '(([0-9a-f]+:)+[0-9a-f]+.[0-7]/){3}' | awk -F/ "
            f"'{{print $8}}'")
        if ret:
            return msg.strip().split()
        else:
            assert False, f"cannot get ep"
    else:
        ret, msg = callcmd(
            f"ls -d /sys/bus/pci/devices/{bdf}/*/*/ | egrep -i '(([0-9a-f]+:)+[0-9a-f]+.[0-7]/){3}' | awk -F/ "
            f"'{{print $8}}'")
        if ret:
            return msg.strip().split()
        else:
            assert False, f"cannot get ep"


def read_config_lspci(bdf):
    ret, msg = callcmd(f"lspci -vvvs {bdf} | grep 'Unknown header type'", timeout=120)
    return ret


def sbr_set(bdf):
    _ret = 0
    logger.info(f"read data from BDF:{bdf}")
    ret, orgdata = callcmd(f"setpci -s {bdf} BRIDGE_CONTROL.w")
    assert ret, f"read data from {bdf} by setpci failed"
    ret, msg = callcmd(f"setpci -s {bdf} BRIDGE_CONTROL.w={hex(int(orgdata, 16) | (1 << 6))}")
    assert ret, f"write data to {bdf} by setpci failed"
    time.sleep(.1)
    ret, msg = callcmd(f"setpci -s {bdf} BRIDGE_CONTROL.w={hex(int(orgdata, 16) & ~(1 << 6))}")
    assert ret, f"write data to {bdf} by setpci failed"
    time.sleep(5)
    logger.info(f"reset {bdf} success")
    return ret


def bme_set(bdf, status=True):
    '''
    :param bdf:
    :param status: True:+ False:-
    :return:
    '''
    _ret = 0
    logger.info(f"read data from BDF:{bdf}")
    ret, orgdata = callcmd(f"setpci -s {bdf} 0x04.w")
    assert ret, f"read data from {bdf} by setpci failed"
    if status:
        ret, msg = callcmd(f"setpci -s {bdf} 0x04.w={hex(int(orgdata, 16) | (1 << 2))}")
        assert ret, f"write data to {bdf} by setpci failed"
    else:
        ret, msg = callcmd(f"setpci -s {bdf} 0x04.w={hex(int(orgdata, 16) & ~(1 << 2))}")
        assert ret, f"write data to {bdf} by setpci failed"
        time.sleep(5)
    logger.info(f"set {bdf} bme{['-', '+'][status]} success")
    return ret


def mem_set(bdf, status=True):
    '''
    :param bdf:
    :param status: True:+ False:-
    :return:
    '''
    _ret = 0
    logger.info(f"read data from BDF:{bdf}")
    ret, orgdata = callcmd(f"setpci -s {bdf} 0x04.w")
    assert ret, f"read data from {bdf} by setpci failed"
    if status:
        ret, msg = callcmd(f"setpci -s {bdf} 0x04.w={hex(int(orgdata, 16) | (1 << 1))}")
        assert ret, f"write data to {bdf} by setpci failed"
    else:
        ret, msg = callcmd(f"setpci -s {bdf} 0x04.w={hex(int(orgdata, 16) & ~(1 << 1))}")
        assert ret, f"write data to {bdf} by setpci failed"
        time.sleep(5)
    logger.info(f"set {bdf} mem{['-', '+'][status]} success")
    return ret

def setup_module():
    ret, msg = callcmd("which devmem2")
    if not ret:
        logger.info("devmem2 not installed")
        ret, msg = callcmd("apt install devmem2", timeout=60)
        if ret:
            logger.info("install devmem2 successed")
        else:
            logger.error("install devmem2 failed")
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
