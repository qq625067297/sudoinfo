from utils import *
import pytest

devices = []
logger = setup_logger(
    log_name="protocol",
    sub_dir="reset",
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
def test_PCIe_SYS_RST_001():
    pytest.skip("test covered by reboot test...")


@log_decorator(logger=logger)
def test_PCIe_SYS_RST_002():
    pytest.skip("test covered by reboot test...")


@log_decorator(logger=logger)
def test_PCIe_SYS_RST_003():
    for device in devices:
        if device.type == 'USP':
            sbr_set(device.device_bdf)
            ret = read_config_lspci(device.device_bdf, logger)
            assert ret == False, "usp sbr test failed"


@log_decorator(logger=logger)
def test_PCIe_SYS_RST_004():
    for device in devices:
        if device.type == 'DSP':
            sbr_set(device.device_bdf, logger)
            ret = read_config_lspci(device.device_bdf, logger)
            assert ret == False, "dsp sbr test failed"


@log_decorator(logger=logger)
def test_PCIe_SYS_RST_005():
    for device in devices:
        if device.type == 'DMA':
            sbr_set(device.parent, logger)
            ret = read_config_lspci(device.parent, logger)
            assert ret == False, "DMA idsp sbr test failed"


@log_decorator(logger=logger)
def test_PCIe_SYS_RST_006():
    for device in devices:
        if device.type == 'MEP':
            sbr_set(device.parent, logger)
            ret = read_config_lspci(device.parent, logger)
            assert ret == False, "MEP idsp sbr test failed"


@log_decorator(logger=logger)
def test_PCIe_SYS_RST_007():
    pytest.skip("not support...")


@log_decorator(logger=logger)
def test_PCIe_SYS_RST_008():
    pytest.skip("covered by reboot test...")


def setup_module():
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
    get_switch_info()