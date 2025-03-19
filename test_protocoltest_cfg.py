import os

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
    COUNT = 0
    for device in devices:
        if device.type == 'USP':
            COUNT += 1
            path = f'/sys/bus/pci/devices/{device.device_bdf}/config'
            cfg_set(device.device_bdf, '0x4', 7, 'w', logger, False)
            ret_data = parse_pci_config(path, 'command', logger)
            assert int(ret_data, 16) & 7 == 0, "config space is update after setpci"
            cfg_set(device.device_bdf, '0x4', 7, 'w', logger, True)
            ret_data = parse_pci_config(path, 'command', logger)
            assert int(ret_data, 16) & 7 == 7, "config space is update after setpci"
    assert COUNT, f"no usp found"


@log_decorator(logger=logger)
def test_PCIe_SYS_CFG_002():
    COUNT = 0
    for device in devices:
        if device.type == 'DSP':
            COUNT += 1
            path = f'/sys/bus/pci/devices/{device.device_bdf}/config'
            cfg_set(device.device_bdf, '0x4', 7, 'w', logger, False)
            ret_data = parse_pci_config(path, 'command', logger)
            assert int(ret_data, 16) & 7 == 0, "config space is update after setpci"
            cfg_set(device.device_bdf, '0x4', 7, 'w', logger, True)
            ret_data = parse_pci_config(path, 'command', logger)
            assert int(ret_data, 16) & 7 == 7, "config space is update after setpci"
    assert COUNT, f"no dsp found"


@log_decorator(logger=logger)
def test_PCIe_SYS_CFG_003():
    COUNT = 0
    for device in devices:
        if device.type == 'DMA':
            COUNT += 1
            path = f'/sys/bus/pci/devices/{device.device_bdf}/config'
            cfg_set(device.device_bdf, '0x4', 6, 'w', logger, False)
            ret_data = parse_pci_config(path, 'command', logger)
            assert int(ret_data, 16) & 6 == 0, "config space is update after setpci"
            cfg_set(device.device_bdf, '0x4', 6, 'w', logger, True)
            ret_data = parse_pci_config(path, 'command', logger)
            assert int(ret_data, 16) & 6 == 6, "config space is update after setpci"
    assert COUNT, f"no DMA found"


@log_decorator(logger=logger)
def test_PCIe_SYS_CFG_004():
    COUNT = 0
    for device in devices:
        if device.type == 'MEP':
            COUNT += 1
            path = f'/sys/bus/pci/devices/{device.device_bdf}/config'
            cfg_set(device.device_bdf, '0x4', 6, 'w', logger, False)
            ret_data = parse_pci_config(path, 'command', logger)
            assert int(ret_data, 16) & 6 == 0, "config space is update after setpci"
            cfg_set(device.device_bdf, '0x4', 6, 'w', logger, True)
            ret_data = parse_pci_config(path, 'command', logger)
            assert int(ret_data, 16) & 6 == 6, "config space is update after setpci"
    assert COUNT, f"no MEP found"


@log_decorator(logger=logger)
def test_PCIe_SYS_CFG_005():
    COUNT = 0
    for device in devices:
        if device.type == 'EP':
            if device.class_code in ['0x010802', '0x020000']:
                COUNT += 1
                path = f'/sys/bus/pci/devices/{device.device_bdf}/config'
                cfg_set(device.device_bdf, '0x4', 6, 'w', logger, False)
                ret_data = parse_pci_config(path, 'command', logger)
                assert int(ret_data, 16) & 6 == 0, "config space is update after setpci"
                cfg_set(device.device_bdf, '0x4', 6, 'w', logger, True)
                ret_data = parse_pci_config(path, 'command', logger)
                assert int(ret_data, 16) & 6 == 6, "config space is update after setpci"
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
    save_data_file(devices, 'pcie_tree_before.json')
    if os.path.exists("pcie_tree.json"):
        ret, msg = callcmd(logger, 'diff pcie_tree_before.json pcie_tree.json')
        assert ret, "pcie tree check failed"
    else:
        os.rename("pcie_tree_before.json", 'pcie_tree.json')


def teardown_module():
    devices_aftertest = get_switch_info(logger)
    save_data_file(devices_aftertest, 'pcie_tree_aftertest.json')


def setup():
    pass


def teardown():
    pass


if __name__ == '__main__':
    get_switch_info(logger)
