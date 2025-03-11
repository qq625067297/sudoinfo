from utils import *
import pytest

devices = []
logger = setup_logger(
    log_name="protocol",
    sub_dir="cfg",
    log_dir="protocol_logs"  # 可指定绝对路径
)

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


@log_decorator(logger=logger)
def test_PCIe_SYS_CFG_001():
    offset = 288
    COUNT = 0
    for device in devices:
        if device.type == 'EP':
            status = False
            ret, msg = callcmd(logger,
                               f"lspci -vvvs {device.device_bdf} | grep '64-bit, prefetchable' | grep 'size' | egrep "
                               f"-v 'ignored|disabled'")
            if ret:
                COUNT += 1
                addresslist = re.findall(r"Memory at ([0-9a-f]{8,})", msg)
                for address in addresslist:
                    address_offset = hex(int(address, 16) + offset)
                    data = 0x0
                    ret, msg = callcmd(logger, f"devmem2 {address_offset} w {data}")
                    retdata = re.search(r"Written 0x([0-9A-F]+); readback 0x([0-9A-F]+)", msg)
                    if retdata.group(1) == retdata.group(2):
                        status = True
                        break
                assert status, f"{device.devcie_bdf} write data to bar memory by devmem2 failed"
    assert COUNT, f"no ep has 64-bit, prefetchable"


@log_decorator(logger=logger)
def test_PCIe_SYS_CFG_002():
    COUNT = 0
    for device in devices:
        if device.type == 'EP':
            status = False
            ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep '64-bit, non-prefetchable' | grep "
                                       f"'size' | egrep -v 'ignored|disabled'")
            if ret:
                COUNT += 1
                addresslist = re.findall(r"Memory at ([0-9a-f]{8,})", msg)
                for address in addresslist:
                    address_offset = hex(int(address, 16) + 288)
                    data = 0x0
                    ret, msg = callcmd(logger, f"devmem2 {address_offset} w {data}")
                    retdata = re.search(r"Written 0x([0-9A-F]+); readback 0x([0-9A-F]+)", msg)
                    if retdata.group(1) == retdata.group(2):
                        status = True
                        break
                assert status, f"{device.device_bdf} write data to bar memory by devmem2 failed"
    assert COUNT, f"no ep has 64-bit, non-prefetchable"


@log_decorator(logger=logger)
def test_PCIe_SYS_CFG_003():
    COUNT = 0
    for device in devices:
        if device.type == 'EP':
            status = False
            ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep '32-bit, prefetchable' | grep 'size' "
                                       f"| egrep -v 'ignored|disabled'")
            if ret:
                COUNT += 1
                addresslist = re.findall(r"Memory at ([0-9a-f]{8,})", msg)
                for address in addresslist:
                    address_offset = hex(int(address, 16) + 288)
                    data = 0x0
                    ret, msg = callcmd(logger, f"devmem2 {address_offset} w {data}")
                    retdata = re.search(r"Written 0x([0-9A-F]+); readback 0x([0-9A-F]+)", msg)
                    if retdata.group(1) == retdata.group(2):
                        status = True
                        break
                assert status, f"{device.device_bdf} write data to bar memory by devmem2 failed"
    assert COUNT, f"no ep has 32-bit, prefetchable"


@log_decorator(logger=logger)
def test_PCIe_SYS_CFG_004():
    COUNT = 0
    for device in devices:
        if device.type == 'EP':
            status = False
            ret, msg = callcmd(logger,
                               f"lspci -vvvs {device.device_bdf} | grep '32-bit, non-prefetchable' | grep 'size' | egrep -v "
                               f"'ignored|disabled'")
            if ret:
                COUNT += 1
                addresslist = re.findall(r"Memory at ([0-9a-f]{8,})", msg)
                for address in addresslist:
                    address_offset = hex(int(address, 16) + 288)
                    data = 0x0
                    ret, msg = callcmd(logger, f"devmem2 {address_offset} w {data}")
                    retdata = re.search(r"Written 0x([0-9A-F]+); readback 0x([0-9A-F]+)", msg)
                    if retdata.group(1) == retdata.group(2):
                        status = True
                        break
                assert status, f"{device.device_bdf} write data to bar memory by devmem2 failed"
    assert COUNT, f"no ep has 32-bit, non-prefetchable"


@log_decorator(logger=logger)
def test_PCIe_SYS_CFG_005():
    COUNT = 0
    ret, msg = callcmd(logger, f"dd if=/dev/urandom of=1G.txt bs=1M count=1024", timeout=600)
    if ret:
        logger.info("create 1G file success")
    else:
        assert False, "create 1G file fail"

    for device in devices:
        if device.type == 'EP':
            if device.driver == 'nvme':
                ret, msg = callcmd(logger, f'ls /sys/bus/pci/devices/{device.device_bdf}/nvme | grep nvme')
                if not ret:
                    continue
                COUNT += 1
                diskname = f'/dev/{msg.strip()}n1'
                logger.info(f"start to write 1G file to {diskname}")
                ret, msg = callcmd(logger, f"dd if=1G.txt of={diskname} bs=1M count=1024")
                if ret:
                    logger.info(f"write 1G file to {diskname} successes")
                else:
                    assert False, f"write 1G file to {diskname} fail"
                logger.info(f"start to read {diskname} to 1G file")
                ret, msg = callcmd(logger, f"dd if={diskname} of=1G.tmp bs=1M count=1024", timeout=600)
                if ret:
                    logger.info(f"read {diskname} to 1G file success")
                else:
                    assert False, f"read {diskname} to 1G file fail"

                ret, msg = callcmd(logger, f"md5sum 1G.txt 1G.tmp | awk '{{print $1}}' | uniq | wc -l", timeout=600)
                if ret:
                    logger.info("get md5sum success")
                else:
                    assert False, "get md5sum fail"
                assert msg.strip() == '1', f"md5sum check pass"

    assert COUNT, "no nvme disk found"


def setup_module():
    ret, msg = callcmd(logger, "which devmem2")
    if not ret:
        logger.info("devmem2 not installed")
        ret, msg = callcmd(logger, "apt install devmem2", timeout=60)
        if ret:
            logger.info("install devmem2 successed")
        else:
            logger.error("install devmem2 failed")
    logger.info("init environment")
    global devices
    devices = get_switch_info(logger)
    save_data_file(devices, 'pcie_tree.json')


def teardown_module():
    devices_aftertest = get_switch_info(logger)
    save_data_file(devices_aftertest, 'pcie_tree_aftertest.json')


def setup():
    pass


def teardown():
    pass


if __name__ == '__main__':
    get_switch_info(logger)
