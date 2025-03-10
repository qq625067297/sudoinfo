from utils import *


devices = []
logger = setup_logger(
    log_name="protocol",
    sub_dir="enum",
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
def test_PCIe_SYS_ENUM_001():
    ep_list = []
    for device in devices:
        if device.type == 'EP':
            ep_list.append(device)
    assert len(ep_list), f"no ep found..."
    for ep in ep_list:
        if ep.class_code == '0x030000':
            _ret = ep.cap_width == ep.current_width
        else:
            _ret = [ep.cap_width, ep.cap_speed] == [ep.current_width, ep.current_speed]
        assert _ret, f"{sys._getframe().f_code.co_name} test failed"


@log_decorator(logger=logger)
def test_PCIe_SYS_ENUM_002():
    ep_list = []
    for device in devices:
        if device.type == 'EP' and device.class_code in ['0x010802', '0x020000']:
            ep_list.append(device)
    assert len(ep_list), f"no ep found..."
    for ep in ep_list:
        logger.info(f"power off slot {ep.slot}")
        ret, msg = callcmd(logger, f"echo 0 > /sys/bus/pci/slots/{ep.slot}/power")
        assert ret, f"poweroff slot {ep.slot} failed, detail is {msg.strip()}"
        logger.info(f"power on slot {ep.slot}")
        ret, msg = callcmd(logger, f"echo 1 > /sys/bus/pci/slots/{ep.slot}/power")
        assert ret, f"poweron slot {ep.slot} failed, detail is {msg.strip()}"


@log_decorator(logger=logger)
def test_PCIe_SYS_ENUM_003():
    for device in devices:
        if device.type in ['USP', 'DSP', 'IDSP']:
            assert device.class_code == '0x060400', f"{device.device_bdf} class_code check failed"


@log_decorator(logger=logger)
def test_PCIe_SYS_ENUM_004():
    for device in devices:
        if device.type == 'MEP':
            assert device.class_code == '0x010800', f"{device.device_bdf} class_code check failed"
        if device.type == 'DMA':
            assert device.class_code == '0x088000', f"{device.device_bdf} class_code check failed"


@log_decorator(logger=logger)
def test_PCIe_SYS_ENUM_005():
    for device in devices:
        if device.class_code == '0x010802':
            if device.driver:
                ret, msg = callcmd(logger, f"echo {device.deice_bdf} > /sys/bus/pci/drivers/{device.driver}/unbind")
                if ret:
                    driver = get_driver(device.device_bdf, logger)
                    assert driver == "", f'unbind {device.device_bdf} driver failed'
                ret, msg = callcmd(logger, f"echo {device.deice_bdf} > /sys/bus/pci/drivers/{device.driver}/bind")
                if ret:
                    driver = get_driver(device.device_bdf, logger)
                    assert driver, f'bind {device.device_bdf} driver failed'


@log_decorator(logger=logger)
def test_PCIe_SYS_ENUM_006():
    install_driver('dma', logger)
    dmadevice = ''
    for device in devices:
        if device.type == 'DMA':
            dmadevice = device
            break

    driver = get_driver(dmadevice.device_bdf, logger)
    if driver:
        ret, msg = callcmd(logger, f"echo {dmadevice.deice_bdf} > /sys/bus/pci/drivers/{driver}/unbind")
        if ret:
            driver = get_driver(dmadevice.device_bdf, logger)
            assert driver == "", f'unbind {dmadevice.device_bdf} driver failed'
        ret, msg = callcmd(logger, f"echo {dmadevice.deice_bdf} > /sys/bus/pci/drivers/{driver}/bind")
        if ret:
            driver = get_driver(dmadevice.device_bdf, logger)
            assert driver, f'bind {dmadevice.device_bdf} driver failed'
    else:
        assert False, "not dma driver found"


@log_decorator(logger=logger)
def test_PCIe_SYS_ENUM_007():
    count = 0
    for device in devices:
        if device.type in ['DMA', 'MEP']:
            count += 1
            logger.debug(f"this is {device.type} device")
    assert count == 3, 'iep device check failed'
    logger.info(f"DMA MEP vendor id and device id check pass")


def setup_module():
    logger.info("init environment")
    global devices
    devices = get_switch_info(logger)
    save_data_file(devices, 'pcie_tree.json')


def teardown_module():
    # os.system("zip -r network_testlog.zip networktest_log")
    devices_aftertest = get_switch_info(logger)
    save_data_file(devices_aftertest, 'pcie_tree_aftertest.json')


def setup():
    pass


def teardown():
    pass


if __name__ == '__main__':
    get_switch_info()
