import os
import subprocess
import logging
import time
import sys
from functools import wraps
import re
import pytest
from collections import namedtuple
import json

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
switch_vendorid = '205e'
mep_vd = '205e:0030'
dma_vd = '205e:0020'
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
    devices = []
    ret, msg = callcmd(f"lspci -Dnd {switch_vendorid}: | awk '{{if($2==\"0604:\")print $1}}'")
    if ret:
        switchinfo = msg.strip().split('\n')
    else:
        assert False, f"no sudo switch found, detail is {msg}"

    usplist = []

    for dev in switchinfo:
        ret, msg = callcmd(f"lspci -vvvs {dev} | grep -i 'Upstream Port'")
        if ret:
            usplist.append(dev)

    dma_p = []
    mep_p = ''
    for usp in usplist:
        uspbdf, dspbdf_list, epbdf_list = get_all_device(usp)
        devices.append(get_device(usp, Type='USP'))
        for ep in epbdf_list:
            device = get_device(ep, Type='EP')
            if device.type == 'DMA':
                dma_p.append(device.parent)
            elif device.type == 'MEP':
                mep_p = device.parent
            devices.append(device)
        for dsp in dspbdf_list:
            if dsp in dma_p:
                device = get_device(dsp, Type='DMA_IDSP')
            elif dsp == mep_p:
                device = get_device(dsp, Type='MEP_IDSP')
            else:
                device = get_device(dsp, Type='DSP')
            devices.append(device)

    return [device._asdict() for device in devices]


def save_data_file(data, filename):
    data = [d._asdict() for d in data]
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, sort_keys=True)


def read_data_file(filename):
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def get_device(bdf, Type):
    device = namedtuple('device', ['device_bdf', 'device_id', 'vendor_id', 'type', 'class_code',
                                   'cap_speed', 'cap_width', 'current_speed', 'current_width', 'driver', 'parent', 'children'])
    vendor_id, device_id = get_vendor_deviceid(bdf)
    class_code = get_classcode(bdf)
    cap_speed, cap_width, current_speed, current_width = get_speed_width(bdf)
    parent = get_parent_device(bdf)
    children = get_children_device(bdf)
    if Type == 'EP':
        if f'{vendor_id}:{device_id}' == dma_vd:
            Type = 'DMA'
        if f'{vendor_id}:{device_id}' == mep_vd:
            Type = 'MEP'
    driver = get_driver(bdf)
    return device(bdf, device_id, vendor_id, Type, class_code, cap_speed,
                  cap_width, current_speed, current_width, driver, parent, children)


def get_all_device(bdf):
    """
    :param bdf: usp bdf
    :return:
    """
    ret, dsp = callcmd(
        f"ls -d /sys/bus/pci/devices/{bdf}/*/ | egrep '(([0-9a-f]+:)+[0-9a-f]{{2}}.[0-7]/){{2}}' | awk -F/ '{{print $(("
        f"NF-1))}}'")
    if 'No such file or directory' in dsp:
        dsp = []
    else:
        dsp = dsp.strip().split()

    ret, ep = callcmd(
        f"ls -d /sys/bus/pci/devices/{bdf}/*/*/ | egrep '(([0-9a-f]+:)+[0-9a-f]{{2}}.[0-7]/){{3}}' | awk -F/ '{{print "
        f"$((NF-1))}}'")
    if 'No such file or directory' in ep:
        ep = []
    else:
        ep = ep.strip().split()

    return [bdf, dsp, ep]


def get_all_ep(bdf):
    """
    :param bdf: dsp bdf
    :return:
    """
    ret, msg = callcmd(
        f"ls -d /sys/bus/pci/devices/{bdf}/*/ | egrep '(([0-9a-f]+:)+[0-9a-f]{{2}}.[0-7]/){{2}}' | awk -F/ '{{print $(("
        f"NF-1))}}'")
    if 'No such file or directory' in msg:
        msg = []
    else:
        msg = msg.strip().split()
    return msg


def get_vendor_deviceid(bdf):
    ret, msg = callcmd(f"lspci -ns {bdf} | awk '{{print $3}}'")
    if ret:
        vendor_id, device_id = msg.strip().split(':')
    else:
        assert False, f"no sudo switch found, detail is {msg}"

    return f"{vendor_id}", f"{device_id}"


def get_parent_device(bdf):
    ret, msg = callcmd(
        f"ls -d /sys/bus/pci/devices/*/{bdf}/ | egrep '(([0-9a-f]+:)+[0-9a-f]{{2}}.[0-7]/){{2}}' | awk -F/ '{{print $(("
        f"NF-2))}}'")
    if 'No such file or directory' in msg:
        msg = ''
    else:
        msg = msg.strip()
    return msg


def get_children_device(bdf):
    ret, msg = callcmd(
        f"ls -d /sys/bus/pci/devices/{bdf}/*/ | egrep '(([0-9a-f]+:)+[0-9a-f]{{2}}.[0-7]/){{2}}' | awk -F/ '{{print $(("
        f"NF-1))}}'")
    if 'No such file or directory' in msg:
        msg = []
    else:
        msg = msg.strip().split()
    return msg


def get_speed_width(bdf):
    ret, current = callcmd(
        f"lspci -vvvs {bdf} | grep LnkSta: | awk '{{print $3\" \"$6}}'")
    current = current.strip().split()
    ret, cap = callcmd(
        f"lspci -vvvs {bdf} | grep LnkCap: | awk '{{print $5\" \"$7}}'")
    cap = cap.strip().replace(',', ' ').split()
    return cap + current


def get_driver(bdf):
    ret, msg = callcmd(f"lspci -ks {bdf} | grep -i 'Kernel driver in use:' | awk '{{print $5}}'")

    return msg.strip()


def get_classcode(bdf):
    devicepath = os.path.join(f'{syspath}', f'{bdf}', 'class')
    with open(devicepath) as f:
        classcode = f.read().strip()
    return classcode


def reboothost():
    pass

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
    print(get_switch_info())
