import os
import subprocess
import logging
import time
import sys
from functools import wraps
import re
from collections import namedtuple
import json

# devices = []
switch_vendorid = '205e'
mep_vd = '205e:0030'
dma_vd = '205e:0020'
syspath = "/sys/bus/pci/devices/"


def setup_logger(log_name='protocol', sub_dir='enum', log_dir='protocol_log'):
    """初始化日志配置并返回Logger对象"""
    # 确保日志目录存在
    full_log_dir = os.path.join(log_dir, sub_dir)
    os.makedirs(full_log_dir, exist_ok=True)

    # 动态生成日志文件名
    log_file = os.path.join(
        full_log_dir,
        f"{log_name}_{time.strftime('%Y%m%d%H%M%S')}.log"
    )

    # 创建Logger（使用唯一名称避免冲突）
    logger = logging.getLogger(f"{log_name}_{sub_dir}")
    logger.setLevel(logging.DEBUG)  # 设置总日志级别

    # 避免重复添加Handler
    if not logger.handlers:
        # 控制台处理器（DEBUG级别）
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        # 文件处理器（INFO级别）
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.INFO)

        # 统一格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(lineno)d - %(message)s'
        )
        ch.setFormatter(formatter)
        fh.setFormatter(formatter)

        # 添加处理器
        logger.addHandler(ch)
        logger.addHandler(fh)

    return logger  # 返回logger对象


def log_decorator(logger=None):
    """装饰器工厂，可接收特定logger"""

    def actual_decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 自动获取函数名作为用例名
            casename = func.__name__.replace("test_", "")

            # 使用传入的logger或默认root logger
            used_logger = logger if logger else logging.getLogger()

            used_logger.info(f"Case [{casename}] start testing...")
            try:
                result = func(*args, **kwargs)
                used_logger.info(f"Case [{casename}] test passed")
                return result
            except Exception as e:
                used_logger.error(f"Case [{casename}] failed: {str(e)}", exc_info=True)
                raise

        return wrapper

    return actual_decorator


def callcmd(logger, command, timeout=10, ignore=False):
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


def get_switch_info(logger):
    devices = []
    ret, msg = callcmd(logger, f"lspci -Dnd {switch_vendorid}: | awk '{{if($2==\"0604:\")print $1}}'")
    if ret:
        switchinfo = msg.strip().split('\n')
    else:
        assert False, f"no sudo switch found, detail is {msg}"

    usplist = []

    for dev in switchinfo:
        ret, msg = callcmd(logger, f"lspci -vvvs {dev} | grep -i 'Upstream Port'")
        if ret:
            usplist.append(dev)

    dma_p = []
    mep_p = ''
    for usp in usplist:
        uspbdf, dspbdf_list, epbdf_list = get_all_device(usp, logger)
        devices.append(get_device(usp, 'USP', logger))
        for ep in epbdf_list:
            device = get_device(ep, 'EP', logger)
            if device.type == 'DMA':
                dma_p.append(device.parent)
            elif device.type == 'MEP':
                mep_p = device.parent
            devices.append(device)
        for dsp in dspbdf_list:
            if dsp in dma_p:
                device = get_device(dsp, 'DMA_IDSP', logger)
            elif dsp == mep_p:
                device = get_device(dsp, 'MEP_IDSP', logger)
            else:
                device = get_device(dsp, 'DSP', logger)
            devices.append(device)

    return devices


def save_data_file(data, filename):
    data = [d._asdict() for d in data]
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, sort_keys=True)


def read_data_file(filename):
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def get_device(bdf, Type, logger):
    device = namedtuple('device', ['device_bdf', 'device_id', 'vendor_id', 'type', 'class_code',
                                   'cap_speed', 'cap_width', 'current_speed', 'current_width', 'driver', 'slot',
                                   'parent', 'children'])
    vendor_id, device_id = get_vendor_deviceid(bdf, logger)
    class_code = get_classcode(bdf)
    cap_speed, cap_width, current_speed, current_width = get_speed_width(bdf, logger)
    parent = get_parent_device(bdf, logger)
    children = get_children_device(bdf, logger)
    if Type == 'EP':
        if f'{vendor_id}:{device_id}' == dma_vd:
            Type = 'DMA'
        if f'{vendor_id}:{device_id}' == mep_vd:
            Type = 'MEP'
    driver = get_driver(bdf, logger)
    slot = get_slot(bdf, logger)
    return device(bdf, device_id, vendor_id, Type, class_code, cap_speed,
                  cap_width, current_speed, current_width, driver, slot, parent, children)


def get_all_device(bdf, logger):
    """
    :param bdf: usp bdf
    :return:
    """
    ret, dsp = callcmd(logger,
                       f"ls -d /sys/bus/pci/devices/{bdf}/*/ | egrep '(([0-9a-f]+:)+[0-9a-f]{{2}}.[0-7]/){{2}}' | awk -F/ '{{print $(("
                       f"NF-1))}}'")
    if 'No such file or directory' in dsp:
        dsp = []
    else:
        dsp = dsp.strip().split()

    ret, ep = callcmd(logger,
                      f"ls -d /sys/bus/pci/devices/{bdf}/*/*/ | egrep '(([0-9a-f]+:)+[0-9a-f]{{2}}.[0-7]/){{3}}' | awk -F/ '{{print "
                      f"$((NF-1))}}'")
    if 'No such file or directory' in ep:
        ep = []
    else:
        ep = ep.strip().split()

    return [bdf, dsp, ep]


def get_all_ep(bdf, logger):
    """
    :param bdf: dsp bdf
    :return:
    """
    ret, msg = callcmd(logger,
                       f"ls -d /sys/bus/pci/devices/{bdf}/*/ | egrep '(([0-9a-f]+:)+[0-9a-f]{{2}}.[0-7]/){{2}}' | awk -F/ '{{print $(("
                       f"NF-1))}}'")
    if 'No such file or directory' in msg:
        msg = []
    else:
        msg = msg.strip().split()
    return msg


def get_vendor_deviceid(bdf, logger):
    ret, msg = callcmd(logger, f"lspci -ns {bdf} | awk '{{print $3}}'")
    if ret:
        vendor_id, device_id = msg.strip().split(':')
    else:
        assert False, f"no sudo switch found, detail is {msg}"

    return f"{vendor_id}", f"{device_id}"


def get_parent_device(bdf, logger):
    ret, msg = callcmd(logger,
                       f"ls -d /sys/bus/pci/devices/*/{bdf}/ | egrep '(([0-9a-f]+:)+[0-9a-f]{{2}}.[0-7]/){{2}}' | awk "
                       f"-F/ '{{print $((NF-2))}}'")
    if 'No such file or directory' in msg:
        msg = ''
    else:
        msg = msg.strip()
    return msg


def get_children_device(bdf, logger):
    ret, msg = callcmd(logger,
                       f"ls -d /sys/bus/pci/devices/{bdf}/*/ | egrep '(([0-9a-f]+:)+[0-9a-f]{{2}}.[0-7]/){{2}}' | awk "
                       f"-F/ '{{print $((NF-1))}}'")
    if 'No such file or directory' in msg:
        msg = []
    else:
        msg = msg.strip().split()
    return msg


def get_speed_width(bdf, logger):
    ret, current = callcmd(logger,
                           f"lspci -vvvs {bdf} | grep LnkSta: | awk '{{print $3\" \"$6}}'")
    current = current.strip().split()
    ret, cap = callcmd(logger,
                       f"lspci -vvvs {bdf} | grep LnkCap: | awk '{{print $5\" \"$7}}'")
    cap = cap.strip().replace(',', ' ').split()
    return cap + current


def get_driver(bdf, logger):
    ret, msg = callcmd(logger, f"lspci -ks {bdf} | grep -i 'Kernel driver in use:' | awk '{{print $5}}'")

    return msg.strip()


def get_slot(bdf, logger):
    ret, msg = callcmd(logger, f"lspci -vvvs {bdf} | grep -i 'Physical Slot:' | awk '{{print $3}}'")

    return msg.strip()


def get_classcode(bdf):
    devicepath = os.path.join(f'{syspath}', f'{bdf}', 'class')
    with open(devicepath) as f:
        classcode = f.read().strip()
    return classcode


def read_config_lspci(bdf, logger):
    ret, msg = callcmd(logger, f"lspci -vvvs {bdf} | grep 'Unknown header type'", timeout=120)
    return ret


def sbr_set(bdf, logger):
    _ret = 0
    logger.info(f"read data from BDF:{bdf}")
    ret, orgdata = callcmd(logger, f"setpci -s {bdf} BRIDGE_CONTROL.w")
    assert ret, f"read data from {bdf} by setpci failed"
    ret, msg = callcmd(logger, f"setpci -s {bdf} BRIDGE_CONTROL.w={hex(int(orgdata, 16) | (1 << 6))}")
    assert ret, f"write data to {bdf} by setpci failed"
    time.sleep(.1)
    ret, msg = callcmd(logger, f"setpci -s {bdf} BRIDGE_CONTROL.w={hex(int(orgdata, 16) & ~(1 << 6))}")
    assert ret, f"write data to {bdf} by setpci failed"
    time.sleep(5)
    logger.info(f"reset {bdf} success")
    return ret


def bme_set(bdf, logger, status=True):
    """
    :param logger:
    :param bdf:
    :param status: True:+ False:-
    :return:
    """
    _ret = 0
    logger.info(f"read data from BDF:{bdf}")
    ret, orgdata = callcmd(logger, f"setpci -s {bdf} 0x04.w")
    assert ret, f"read data from {bdf} by setpci failed"
    if status:
        ret, msg = callcmd(logger, f"setpci -s {bdf} 0x04.w={hex(int(orgdata, 16) | (1 << 2))}")
        assert ret, f"write data to {bdf} by setpci failed"
    else:
        ret, msg = callcmd(logger, f"setpci -s {bdf} 0x04.w={hex(int(orgdata, 16) & ~(1 << 2))}")
        assert ret, f"write data to {bdf} by setpci failed"
        time.sleep(5)
    logger.info(f"set {bdf} bme{['-', '+'][status]} success")
    return ret


def mem_set(bdf, logger, status=True):
    """
    :param logger:
    :param bdf:
    :param status: True:+ False:-
    :return:
    """
    _ret = 0
    logger.info(f"read data from BDF:{bdf}")
    ret, orgdata = callcmd(logger, f"setpci -s {bdf} 0x04.w")
    assert ret, f"read data from {bdf} by setpci failed"
    if status:
        ret, msg = callcmd(logger, f"setpci -s {bdf} 0x04.w={hex(int(orgdata, 16) | (1 << 1))}")
        assert ret, f"write data to {bdf} by setpci failed"
    else:
        ret, msg = callcmd(logger, f"setpci -s {bdf} 0x04.w={hex(int(orgdata, 16) & ~(1 << 1))}")
        assert ret, f"write data to {bdf} by setpci failed"
        time.sleep(5)
    logger.info(f"set {bdf} mem{['-', '+'][status]} success")
    return ret


dmadriver = 'yd_dma.tar.gz'


def install_driver(driver, logger):
    """
    :param driver: dma： dma dirver, mep: mep driver , ntb: ntb driver
    :param logger:
    :return:
    """
    logger.info(f"unzip {driver} driver file")
    if driver == 'dma':
        callcmd(logger, f"tar xvf {dmadriver} -C .", timeout=120)
        ret, msg = callcmd(logger, f"cd yd_dma;make clean;make;insmod yundu_dma.ko", timeout=120)
        return ret
