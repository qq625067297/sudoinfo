from utils import *
import pytest

devices = []
logger = setup_logger(
    log_name="protocol",
    sub_dir="mem",
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
def test_PCIe_SYS_MEM_001():
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
def test_PCIe_SYS_MEM_002():
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
def test_PCIe_SYS_MEM_003():
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
def test_PCIe_SYS_MEM_004():
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
def test_PCIe_SYS_MEM_005():
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


@log_decorator(logger=logger)
def test_PCIe_SYS_MEM_006():
    offset = 288
    for device in devices:
        if device.type == 'MEP':
            ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep 'Memory at'  | egrep -v "
                                       f"'ignored|disabled'")
            if ret:
                address = re.search(r"Memory at ([0-9a-f]{8,})", msg).group(1)
                address_offset = hex(int(address, 16) + offset)
                data = 0x1
                ret, msg = callcmd(logger, f"devmem2 {address_offset} w {data}")
                retdata = re.search(r"Written 0x([0-9A-F]+); readback 0x([0-9A-F]+)", msg)
                assert retdata.group(1) == retdata.group(2), (f"{device.device_bdf} write data to bar memory by "
                                                              f"devmem2 failed")
            else:
                assert False, f"mep bar memory is invalid"


@log_decorator(logger=logger)
def test_PCIe_SYS_MEM_007():
    offset = 352
    for device in devices:
        if device.type == 'DMA':
            status = False
            ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep 'Memory at' | grep 'size' | egrep -v "
                                       f"'ignored|disabled'")
            if ret:
                addresslist = re.findall(r"Memory at ([0-9a-f]{8,})", msg)
                for address in addresslist:
                    address_offset = hex(int(address, 16) + offset)
                    data = 0x0
                    ret, msg = callcmd(logger, f"devmem2 {address_offset} w {data}")
                    retdata = re.search(r"Written 0x([0-9A-F]+); readback 0x([0-9A-F]+)", msg)
                    if retdata.group(1) == retdata.group(2):
                        status = True
                        break
                assert status, f"{device.device_bdf} write data to bar memory by devmem2 failed"
            else:
                assert False, "no dma bar found"


@log_decorator(logger=logger)
def test_PCIe_SYS_MEM_008():
    for device in devices:
        if device.type == 'USP':
            ret, msg = callcmd(logger, f'nvme list | grep /dev/ | wc -l')
            orgcount = int(msg.strip())
            bme_set(device.device_bdf, logger, status=False)
            ret, msg = callcmd(logger, f'nvme list | grep /dev/ | wc -l', timeout=120)
            newcount = int(msg.strip())
            assert orgcount > newcount, f"usp:{device.device_bdf} bme test failed"


@log_decorator(logger=logger)
def test_PCIe_SYS_MEM_009():
    for device in devices:
        if device.type == 'DSP':
            ret, msg = callcmd(logger, f'ls /sys/bus/pci/devices/{device.device_bdf}/*/nvme')
            if ret:
                diskname = f'/dev/{msg.strip()}n1'
                logger.info(f"{diskname} is linked to {device.device_bdf}")
                bme_set(device.device_bdf, logger, status=False)
                ret, msg = callcmd(logger, f'nvme list | grep {diskname}', timeout=120)
                assert ret, f"dsp:{device.device_bdf} bme test failed"
            else:
                logger.info(f"no nvme disk linked to {device.device_bdf}")


@log_decorator(logger=logger)
def test_PCIe_SYS_MEM_010():
    """
    待统一测试方法
    :return:
    """
    pass


@log_decorator(logger=logger)
def test_PCIe_SYS_MEM_011():
    offset = 288
    for device in devices:
        if device.type == 'USP':
            status = False
            mem_set(device.device_bdf, logger, status=False)
            ret, msg = callcmd(logger,
                               f"lspci -vvvs {device.device_bdf} | grep 'Memory behind bridge'")
            if ret:
                addresslist = re.findall(r"Memory at ([0-9a-f]{8,})", msg)
                for address in addresslist:
                    address_offset = hex(int(address, 16) + offset)
                    data = 0x0
                    ret, msg = callcmd(logger, f"devmem2 {address_offset} w {data}")
                    retdata = re.search(r"Written 0x([0-9A-F]+); readback 0x([0-9A-F]+)", msg)
                    if retdata.group(1) == retdata.group(2):
                        status = True
                        break
                assert status, f"{device.device_bdf} write data to bar memory by devmem2 failed"


@log_decorator(logger=logger)
def test_PCIe_SYS_MEM_012():
    offset = 288
    for device in devices:
        if device.type == 'DSP':
            status = False
            mem_set(device.device_bdf, logger, status=False)
            ret, msg = callcmd(logger,
                               f"lspci -vvvs {device.device_bdf} | grep 'Memory behind bridge'")
            if ret:
                addresslist = re.findall(r"Memory at ([0-9a-f]{8,})", msg)
                for address in addresslist:
                    address_offset = hex(int(address, 16) + offset)
                    data = 0x0
                    ret, msg = callcmd(logger, f"devmem2 {address_offset} w {data}")
                    retdata = re.search(r"Written 0x([0-9A-F]+); readback 0x([0-9A-F]+)", msg)
                    if retdata.group(1) == retdata.group(2):
                        status = True
                        break
                assert status, f"{device.device_bdf} write data to bar memory by devmem2 failed"


@log_decorator(logger=logger)
def test_PCIe_SYS_MEM_013():
    pytest.skip()


@log_decorator(logger=logger)
def test_PCIe_SYS_MEM_014():
    pytest.skip()


@log_decorator(logger=logger)
def test_PCIe_SYS_MEM_015():
    pytest.skip("Cannot Build test scenarios")


@log_decorator(logger=logger)
def test_PCIe_SYS_MEM_016():
    offset = 288
    for device in devices:
        if device.type == 'MEP':
            mem_set(device.device_bdf, logger, False)
            time.sleep(.1)
            ret, msg = check_bar(device.device_bdf, 'mem', 'MEP', logger)
            if ret:
                address_list = re.findall(r' ([0-9a-f]]{8,})', msg)
                for address in address_list:
                    ret_data = devmem2_addr(True, address, offset, logger, 'b')
                    assert ret_data == '0x'.ljust(len(ret_data))
                    error_data = check_error(device.device_bdf, logger)
                    assert 'UnsupReq+' in error_data['DevSta:']


@log_decorator(logger=logger)
def test_PCIe_SYS_MEM_017():
    offset = 288
    for device in devices:
        if device.type == 'DMA':
            mem_set(device.device_bdf, logger, False)
            time.sleep(.1)
            ret, msg = check_bar(device.device_bdf, 'mem', 'DMA', logger)
            if ret:
                address_list = re.findall(r' ([0-9a-f]]{8,})', msg)
                for address in address_list:
                    ret_data = devmem2_addr(True, address, offset, logger, 'b')
                    assert ret_data == '0x'.ljust(len(ret_data))
                    error_data = check_error(device.device_bdf, logger)
                    assert 'UnsupReq+' in error_data['DevSta:']


@log_decorator(logger=logger)
def test_PCIe_SYS_MEM_018():
    offset = 288
    for device in devices:
        if device.type == 'MEP':
            mem_set(device.parent[0], logger, False)
            time.sleep(.1)
            ret, msg = check_bar(device.device_bdf, 'mem', 'MEP', logger)
            if ret:
                address_list = re.findall(r' ([0-9a-f]]{8,})', msg)
                for address in address_list:
                    ret_data = devmem2_addr(True, address, offset, logger, 'b')
                    assert ret_data == '0x'.ljust(len(ret_data))
                    error_data = check_error(device.parent[0], logger)
                    assert 'UnsupReq+' in error_data['DevSta:']


@log_decorator(logger=logger)
def test_PCIe_SYS_MEM_019():
    offset = 352
    for device in devices:
        if device.type == 'DMA':
            mem_set(device.parent[0], logger, False)
            time.sleep(.1)
            ret, msg = check_bar(device.device_bdf, 'mem', 'DMA', logger)
            if ret:
                address_list = re.findall(r' ([0-9a-f]]{8,})', msg)
                for address in address_list:
                    ret_data = devmem2_addr(True, address, offset, logger, 'b')
                    assert ret_data == '0x'.ljust(len(ret_data))
                    error_data = check_error(device.parent[0], logger)
                    assert 'UnsupReq+' in error_data['DevSta:']


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
