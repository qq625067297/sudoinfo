from utils import *
import pytest

devices = []
logger = setup_logger(
    log_name="protocol",
    sub_dir="pm",
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
def test_PCIe_SYS_PM_001():
    COUNT = 0
    for device in devices:
        if device.type in ['DSP', 'USP']:
            COUNT += 1
            ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep -A1 'Power Management version' | grep "
                                       f"Flags:")
            pme = re.search(r'PME\(.*?\)', msg).group(0)
            assert ret, f"{device.type} {device.device_bdf} has not PM capability and support PME, PME:{pme.split(',')}, check failed"
    assert COUNT, f"no dsp or usp found"


@log_decorator(logger=logger)
def test_PCIe_SYS_PM_002():
    COUNT = 0
    for device in devices:
        if device.type in ['DSP', 'USP']:
            COUNT += 1
            ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep PME-Enable")
            pmestatus = msg.split()[3]
            if pmestatus == 'PME-Enable-':
                cfg_set(device.device_bdf, 'CAP_PM+4', 0x100, 'w', logger, True)
            elif pmestatus == 'PME-Enable+':
                cfg_set(device.device_bdf, 'CAP_PM+4', 0x100, 'w', logger, False)

            ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep PME-Enable")
            pmestatus_afterset = msg.split()[3]
            assert pmestatus == pmestatus_afterset, f'{device.type} {device.device_bdf} pme-enable set failed'
            # ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | egrep  -A1 'SltCap:")
    assert COUNT, f"no dsp or usp found"


@log_decorator(logger=logger)
def test_PCIe_SYS_PM_004():
    COUNT = 0
    for device in devices:
        if device.type in ['DSP', 'USP']:
            COUNT += 1
            ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep 'ASPM L0s L1'")
            assert ret, f'{device.type} {device.device_bdf} ASPM not support L0s and L1'
            # ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | egrep  -A1 'SltCap:")
    assert COUNT, f"no dsp or usp found"


@log_decorator(logger=logger)
def test_PCIe_SYS_PM_011():
    COUNT = 0
    for device in devices:
        if device.type == 'EP':
            COUNT += 1
            if device.driver == 'nvme':
                ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep 'ASPM not supported'")
                assert ret, f'{device.type} {device.device_bdf} ASPM not support test failed'
    assert COUNT, f"no nvme EP found"


@log_decorator(logger=logger)
def test_PCIe_SYS_PM_015():
    COUNT = 0
    for device in devices:
        if device.type == 'EP':
            if device.driver == 'nvme':
                COUNT += 1
                cfg_set(device.device_bdf, 'CAP_PM+4', 3, 'w', logger, True)
                ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep 'Status: D3'")
                assert ret, f"set {device.type} {device.device_bdf} to D3 status failed"
                cfg_set(device.device_bdf, 'CAP_PM+4', 3, 'w', logger, False)
                ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep 'Status: D0'")
                assert ret, f"set {device.type} {device.device_bdf} to D0 status failed"
    assert COUNT, f"no EP found"


@log_decorator(logger=logger)
def test_PCIe_SYS_PM_016():
    pytest.skip("not support D1 D2")


@log_decorator(logger=logger)
def test_PCIe_SYS_PM_017():
    COUNT = 0
    for device in devices:
        if device.type == 'EP':
            if device.driver == 'nvme':
                COUNT += 1
                cfg_set(device.device_bdf, 'CAP_PM+4', 3, 'w', logger, True)
                ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep 'Status: D3'")
                assert ret, f"set {device.type} {device.device_bdf} to D3 status failed"
                cfg_set(device.device_bdf, 'CAP_PM+4', 3, 'w', logger, False)
                ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep 'Status: D0'")
                assert ret, f"set {device.type} {device.device_bdf} to D0 status failed"
    assert COUNT, f"no EP found"


@log_decorator(logger=logger)
def test_PCIe_SYS_PM_018():
    COUNT = 0
    for device in devices:
        if device.type == 'EP':
            if device.driver == 'nvme':
                COUNT += 1
                cfg_set(device.device_bdf, 'CAP_PM+4', 3, 'w', logger, True)
                ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep 'Status: D3'")
                assert ret, f"set {device.type} {device.device_bdf} to D3 status failed"
                ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | egrep 'Region [0-9]: Memory at ' | sed "
                                           f"-n 1p")
                bar_address = msg.split()[4]
                data = devmem2_addr(True, bar_address, 288, logger, 'w')
                assert data == '0xFFFFFFFF', f"devmem2 get data not expected"
                error_data = check_error(device.device_bdf, logger)
                assert 'UnsupReq+' in error_data['DevSta:'], (f'{device.device_bdf}:{error_data["DevSta:"]}, no '
                                                              f'UnsupReq+ found')
    assert COUNT, f"no EP found"


@log_decorator(logger=logger)
def test_PCIe_SYS_PM_019():
    COUNT = 0
    for device in devices:
        if device.type in ['DSP', 'USP']:
            COUNT += 1
            cfg_set(device.device_bdf, 'CAP_PM+4', 3, 'w', logger, True)
            ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep 'Status: D3'")
            assert ret, f"set {device.type} {device.device_bdf} to D3 status failed"
            cfg_set(device.device_bdf, 'CAP_PM+4', 3, 'w', logger, False)
            ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep 'Status: D0'")
            assert ret, f"set {device.type} {device.device_bdf} to D0 status failed"
    assert COUNT, f"no EP found"


@log_decorator(logger=logger)
def test_PCIe_SYS_PM_020():
    COUNT = 0
    for device in devices:
        if device.type == 'USP':
            COUNT += 1
            cfg_set(device.device_bdf, 'CAP_PM+4', 3, 'w', logger, True)
            ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep 'Status: D3'")
            assert ret, f"set {device.type} {device.device_bdf} to D3 status failed"
            ret, bar_address = check_bar(device.device_bdf, 'mem', 'USP', logger)
            assert ret, f"check {device.type}:{device.device_bdf} bar failed"
            bar_address = bar_address.split()[4].split('-')[0]
            data = devmem2_addr(True, bar_address, 288, logger, 'w')
            assert data == '0xFFFFFFFF', f"devmem2 get data not expected"
            error_data = check_error(device.device_bdf, logger)
            assert 'UnsupReq+' in error_data['DevSta:'], (f'{device.device_bdf}:{error_data["DevSta:"]}, no '
                                                          f'UnsupReq+ found')
    assert COUNT, f"no USP found"


@log_decorator(logger=logger)
def test_PCIe_SYS_PM_021():
    COUNT = 0
    for device in devices:
        if device.type == 'EP':
            COUNT += 1
            cfg_set(device.device_bdf, 'CAP_PM+4', 3, 'w', logger, True)
            ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep 'Status: D3'")
            assert ret, f"set {device.type} {device.device_bdf} to D3 status failed"
            cfg_set(device.device_bdf, 'CAP_PM+4', 3, 'w', logger, False)
            ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | grep 'Status: D0'")
            assert ret, f"set {device.type} {device.device_bdf} to D0 status failed"
            ret, msg = callcmd(logger, f'lspci -vvvs {device.device_bdf} | grep NoSoftRst')
            assert 'NoSoftRst+' in msg, f'D0uninitialized check failed'
    assert COUNT, f"no EP found"


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
