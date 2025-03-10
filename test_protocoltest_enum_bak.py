import os
import subprocess
import logging
import time
import sys
from functools import wraps
import re
from typing import List, Any

os.system('rm -rf protocol_log/enum; mkdir -p protocol_log/enum')
LOGFILE = "protocol_log/enum/protocoltest_%s.log" % time.strftime("%Y%m%d%H%M%S", time.localtime())
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
def test_PCIe_SYS_ENUM_001():
    eps = switchinfo[2]
    assert eps, f"no ep found..."
    for ep in eps:
        _ret = checkdeviceinfo(ep)
        assert _ret, f"{sys._getframe().f_code.co_name} test failed"


@decorator
def test_PCIe_SYS_ENUM_002():
    eps = switchinfo[2]
    assert eps, f"no ep found..."
    for ep in eps:
        if eps[ep][0] in ['02', '01']:
            ret, msg = callcmd(f"lspci -vv -s {ep} | grep 'Physical Slot' | awk '{{print $NF}}'")
            if ret and msg:
                slot = msg.strip()
                logger.info(f"power off slot {slot}")
                ret, msg = callcmd(f"echo 0 > /sys/bus/pci/slots/{slot}/power")
                assert ret, f"poweroff slot {slot} failed, detail is {msg.strip()}"
                logger.info(f"power on slot {slot}")
                ret, msg = callcmd(f"echo 1 > /sys/bus/pci/slots/{slot}/power")
                assert ret, f"poweron slot {slot} failed, detail is {msg.strip()}"


@decorator
def test_PCIe_SYS_ENUM_003():
    usplist, dsplist = switchinfo[:2]
    logger.debug(f"usplist:{usplist}")
    assert usplist, "no usp found..."
    logger.debug(f"dsplist:{dsplist}")
    assert dsplist, "no dsp found..."


@decorator
def test_PCIe_SYS_ENUM_004():
    eps = switchinfo[2]
    for ep in eps:
        if eps[ep][1] == mep_vd:
            logger.debug("this is mep device")
            assert eps[ep][0] == '01', "mep device check failed"
        if eps[ep][1] in [dma0_vd, dma1_vd]:
            logger.debug("this is dma device")
            assert eps[ep][0] == '08', "dma device check failed"


@decorator
def test_PCIe_SYS_ENUM_005():
    eps = switchinfo[2]
    assert eps, f"no ep found..."
    for ep in eps:
        if eps[ep][0] in ['01']:
            if eps[ep][2]:
                ret, msg = callcmd(f"echo {ep} > /sys/bus/pci/drivers/{eps[ep][2]}/unbind")
                if ret:
                    driver = get_driver(ep)
                    assert driver == "", f'unbind {ep} driver failed'
                ret, msg = callcmd(f"echo {ep} > /sys/bus/pci/drivers/{eps[ep][2]}/bind")
                if ret:
                    driver = get_driver(ep)
                    assert driver, f'bind {ep} driver failed'


@decorator
def test_PCIe_SYS_ENUM_006():
    eps = switchinfo[2]
    assert eps, f"no ep found..."
    for ep in eps:
        if eps[ep][0] in ['01']:
            if eps[ep][2]:
                ret, msg = callcmd(f"echo {ep} > /sys/bus/pci/drivers/{eps[ep][2]}/unbind")
                if ret:
                    driver = get_driver(ep)
                    assert driver == "", f'unbind {ep} driver failed'
                ret, msg = callcmd(f"echo {ep} > /sys/bus/pci/drivers/{eps[ep][2]}/bind")
                if ret:
                    driver = get_driver(ep)
                    assert driver, f'bind {ep} driver failed'


@decorator
def test_PCIe_SYS_ENUM_007():
    count = 0
    eps = switchinfo[2]
    for ep in eps:
        if eps[ep][1] == mep_vd:
            count += 1
            logger.debug("this is mep device")
        if eps[ep][1] in [dma0_vd, dma1_vd]:
            count += 1
            logger.debug("this is dma device")
    assert count == 3, 'iep device check failed'
    logger.info("DMA MEP vendor id and device id check pass")


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


def setup_module():
    logger.info("init environment")
    global switchinfo
    switchinfo = get_switch_info()


def check_IO_MEM_BAR(bdf):
    _ret = 0
    _, msg = callcmd(f"lspci -vvvs {bdf}")
    iosta = re.search('I/O.', msg.decode()).group()
    iobar = re.search(r"I/O behind bridge:", msg.decode()).group()
    memsta = re.search('Mem.', msg.decode()).group()
    membar = re.search(r"Region \d+: Memory at ([0-9a-f]{8,})", msg.decode()).group()
    if iosta == 'I/O-' and ('ignored' in iobar or 'disabled' in iobar):
        logger.info("I/O check passed")
    elif iosta == 'I/O+' and not ('ignored' in iobar or 'disabled' in iobar):
        logger.info("I/O check passed")
    else:
        logger.info("I/O check failed")
        _ret = 1
    if switchinfo[2][bdf][2]:
        if memsta == 'Mem-' and ('ignored' in iobar or 'disabled' in membar):
            logger.info("Mem check passed")
        elif memsta == 'Mem+' and not ('ignored' in iobar or 'disabled' in membar):
            logger.info("Mem check passed")
        else:
            logger.info("Mem check failed")
            _ret = 1

    return _ret


def teardown_module():
    # os.system("zip -r network_testlog.zip networktest_log")
    pass


def setup():
    pass


def teardown():
    pass


if __name__ == '__main__':
    get_switch_info()
