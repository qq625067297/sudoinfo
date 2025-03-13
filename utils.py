import os
import subprocess
import logging
import time
import sys
from functools import wraps
import re
from collections import namedtuple
import json
from ctypes import *


switch_vendorid = '205e'
mep_vd = '205e:0030'
dma_vd = '205e:0020'
syspath = "/sys/bus/pci/devices/"


def setup_logger(log_name='protocol', sub_dir='enum', log_dir='protocol_logs'):
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


def cfg_set(bdf, address, data, bit_width, logger, status):
    _ret = 0
    logger.info(f"read data from BDF:{bdf}")
    ret, orgdata = callcmd(logger, f"setpci -s {bdf} {address}.{bit_width}")
    assert ret, f"read data from {bdf} by setpci failed"
    if status:
        data = hex(int(orgdata, 16) | data)
        ret, msg = callcmd(logger, f"setpci -s {bdf} {address}.{bit_width}={data}")
        assert ret, f"write data to {bdf} by setpci failed"
    else:
        data = hex(int(orgdata, 16) & ~data)
        ret, msg = callcmd(logger, f"setpci -s {bdf} {address}.{bit_width}={data}")
        assert ret, f"write data to {bdf} by setpci failed"
    return ret


def devmem2_addr(read, address, offset, logger, bit_width, data=None):
    """
    :param read:
    :param address:
    :param offset:
    :param logger:
    :param bit_width:
    :param data:
    :return:
    """
    address_with_offset = hex(int(address, 16) + offset)
    if read:
        ret, msg = callcmd(logger, rf"devmem2 {address_with_offset} {bit_width}")
        readdata = re.search(r"Value at address 0x[0-9A-F]+ \(0x[0-9A-F]+\): (0x[0-9A-F]+)", msg)
        return readdata.group(1)
    else:
        ret, msg = callcmd(logger, f"devmem2 {address_with_offset} {bit_width} {data}")
        writedata = re.search(r"Written (0x[0-9A-F]+); readback (0x[0-9A-F]+)", msg)
        return writedata.group(1), writedata.group(2)


def check_bar(bdf, bar, devicetype, logger):
    status = False
    ret, msg = callcmd(logger, rf"lspci -vvvs {bdf} | egrep '\sControl:' | awk '{{print $2,$3}}'")
    iomem = msg.strip().split()
    if bar == 'io':
        if devicetype in ['USP', 'DSP', 'IDSP']:
            ret, msg = callcmd(logger, rf"lspci -vvvs {bdf} | grep 'I/O behind bridge:'")
        else:
            ret, msg = callcmd(logger, rf"lspci -vvvs {bdf} | grep Region | grep 'I/O ports at '")
        if re.findall(r'ignored|disabled', msg) and iomem[0][-1] == '-':
            logger.info(f'Control: {iomem[0]}->{msg.strip()}')
            status = True
        elif not (re.findall(r'ignored|disabled', msg) or iomem[0][-1] == '-'):
            logger.info(f'Control: {iomem[0]}->{msg.strip()}')
            status = True
        else:
            logger.info(f'Control: {iomem[0]}->{msg.strip()}')
            status = False
    elif bar == 'mem':
        if devicetype in ['USP', 'DSP', 'IDSP']:
            ret, msg = callcmd(logger, rf"lspci -vvvs {bdf} | egrep 'Memory behind bridge:'")
        else:
            ret, msg = callcmd(logger, rf"lspci -vvvs {bdf} | egrep 'Region [0-9]+: Memory at' | grep size")
        if re.findall(r'ignored|disabled', msg) and iomem[1][-1] == '-':
            logger.info(f'Control: {iomem[1]}->{msg.strip()}')
            status = True
        elif not (re.findall(r'ignored|disabled', msg) or iomem[1][-1] == '-'):
            logger.info(f'Control: {iomem[1]}->{msg.strip()}')
            status = True
        else:
            logger.info(f'Control: {iomem[1]}->{msg.strip()}')
            status = False
    return status, msg


def check_error(bdf, logger):
    return_data = {}
    ret, msg = callcmd(logger, rf"lspci -vvvs {bdf} | egrep '(DevSta:|UESta:|CESta:)'")
    errstatus = msg.strip().split('\n')
    for line in errstatus:
        line_tmp = line.strip().split()
        return_data.update({line_tmp[0]: line_tmp[1:]})

    return return_data


class PCI_CONFIG(Structure):
    _pack_ = 1  # 禁用字节对齐，确保紧密排列
    _fields_ = [
        # 前16字节（基础信息）
        ("VendorID", c_uint16),  # 0x00: 厂商ID
        ("DeviceID", c_uint16),  # 0x02: 设备ID
        ("Command", c_uint16),  # 0x04: 命令寄存器
        ("Status", c_uint16),  # 0x06: 状态寄存器
        ("RevisionID", c_uint8),  # 0x08: 修订版本号
        ("ClassCode", c_uint8),  # 0x09: 编程接口（Interface）
        ("SubClass", c_uint8),  # 0x0A: 子类（Sub Class）
        ("BaseClass", c_uint8),  # 0x0B: 基类（Base Class）
        ("CacheLineSize", c_uint8),  # 0x0C: 缓存行大小
        ("LatencyTimer", c_uint8),  # 0x0D: 延迟计时器
        ("HeaderType", c_uint8),  # 0x0E: 头部类型（高1位为MF标志）
        ("BIST", c_uint8),  # 0x0F: BIST控制

        # BAR0-BAR5（基地址寄存器）
        ("BAR0", c_uint32),  # 0x10: 基地址寄存器0
        ("BAR1", c_uint32),  # 0x14: 基地址寄存器1
        ("BAR2", c_uint32),  # 0x18: 基地址寄存器2
        ("BAR3", c_uint32),  # 0x1C: 基地址寄存器3
        ("BAR4", c_uint32),  # 0x20: 基地址寄存器4
        ("BAR5", c_uint32),  # 0x24: 基地址寄存器5

        # 其他通用字段
        ("CardbusCIS", c_uint32),  # 0x28: Cardbus CIS指针
        ("SubsystemVendorID", c_uint16),  # 0x2C: 子系统厂商ID
        ("SubsystemID", c_uint16),  # 0x2E: 子系统ID
        ("ExpansionROMBase", c_uint32),  # 0x30: 扩展ROM基地址
        ("CapabilitiesPtr", c_uint8),  # 0x34: 能力列表指针
        ("Reserved0", c_uint8 * 3),  # 0x35-0x37: 保留
        ("InterruptLine", c_uint8),  # 0x38: 中断线
        ("InterruptPin", c_uint8),  # 0x39: 中断引脚
        ("MinGrant", c_uint8),  # 0x3A: Min Grant
        ("MaxLatency", c_uint8),  # 0x3B: Max Latency
    ]

    def get_class_code(self) -> str:
        return f"{self.BaseClass:02x}:{self.SubClass:02x}:{self.ClassCode:02x}"

    def get_command(self) -> str:
        return f"{self.Command:04x}"


def parse_pci_config(path, field, logger):
    try:
        with open(path, "rb") as f:
            raw_data = f.read()

        # 将二进制数据映射到结构体
        config = PCI_CONFIG.from_buffer_copy(raw_data)

        # 输出关键信息
        if field == 'command':
            data = config.get_command()
            logger.info(f"Command:{data}")
            return data

    except Exception as e:
        logger.error(f"Error: {e}")
        return None


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
