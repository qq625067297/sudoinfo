from utils import *
import pytest

devices = []
logger = setup_logger(
    log_name="protocol",
    sub_dir="slot",
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
def test_PCIe_SYS_SLOT_002():
    COUNT = 0
    for device in devices:
        if device.type == 'DSP':
            COUNT += 1
            ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | egrep 'SltCap:|SltCtl:|SltSta:' | wc -l")
            assert int(int(msg.strip(), 16)) == 3, f"DSP {device.device_bdf} Slot Capability & Control check failed"
    assert COUNT, f"no Dsp found"


@log_decorator(logger=logger)
def test_PCIe_SYS_SLOT_003():
    COUNT = 0
    for device in devices:
        if device.type == 'DSP':
            COUNT += 1
            # 修改 DSP 端口的 Slot Control 是否能修改,值的对应反应是否符合预期
            ret, base_addr = callcmd(logger, f"lspci -vvs {device.device_bdf}| grep Downstream |awk -F '[' '{{gsub("
                                             f"/].*$/,\"\",$2);print$NF}}'")
            callcmd(logger, f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.w=13ff")
            res, msg = callcmd(logger, f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.w")
            assert res == "13ff", f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.w=13ff fail!"
            callcmd(logger, f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.w=13f1")
            res, msg = callcmd(logger, f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.w")
            assert res == "13ff", f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.w=13ff fail!"

            # ret, msg = callcmd(logger, f"lspci -vvvs {device.device_bdf} | egrep  -A1 'SltCap:")
    assert COUNT, f"no dsp found"


@log_decorator(logger=logger)
def test_PCIe_SYS_SLOT_009():
    COUNT = 0
    for device in devices:
        if device.type == 'DSP':
            COUNT += 1
            ret, base_addr = callcmd(logger, f"lspci -vvs {device.device_bdf}| grep Downstream |awk -F '[' '{{gsub("
                                             f"/].*$/,\"\",$2);print$NF}}'")
            # 修改 DSP 端口的 Slot Control 的Command Completed Interrupt Enable & Status
            callcmd(logger, f"lspci -vvs {device.device_bdf} |grep SltCap -A 1 |grep -w NoCompl |awk -F ' "
                            f"' '{{print $NF}}'")
            res, slot = callcmd(logger, f"lspci -vvs {device.device_bdf} |grep Slot: |awk -F ' ' '{{print $NF}}'")
            if res == "NoCompl-":
                ret, d0 = callcmd(logger, f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.b")
                callcmd(logger, f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.b=e1")
                ret, d1 = callcmd(logger, f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.b")
                assert d1 == "e1", f"CmdCplt-->0 set fail!\ninfo: src={d0}, res={d1}"
                callcmd(logger, f"dmesg -c && echo 0 > /sys/bus/pci/slots/{slot}/power")
                ret, dmg = callcmd("dmesg")
                assert "pciehp: Timeout on hotplug command" not in dmg, f"dmesg find 'pciehp: Timeout on hotplug...'\ninfo:\n{dmg}"
                callcmd(logger, f"dmesg -c && echo 1 > /sys/bus/pci/slots/{slot}/power")
                dmg = callcmd(logger, "dmesg")
                assert f"pciehp: Slot({slot}): Link Up" in dmg, f"dmesg not find 'slot...Link Up...'\ninfo:\n{dmg}"
            else:
                assert False, f"NoCompl status error!\ninfo:{res}"
    assert COUNT, f"no DSP found"


@log_decorator(logger=logger)
def test_PCIe_SYS_SLOT_010():
    COUNT = 0
    for device in devices:
        if device.type == 'DSP':
            COUNT += 1
            ret, base_addr = callcmd(logger, f"lspci -vvs {device.device_bdf}| grep Downstream |awk -F '[' '{{gsub("
                                             f"/].*$/,\"\",$2);print$NF}}'")
            ret, res = callcmd(logger, f"lspci -vvs {device.device_bdf} |grep SltCap -A 1 |grep -w HotPlug |awk -F ' "
                                       f"' '{{print $7}}'")
            if res == "HotPlug+":
                d0 = callcmd(logger, f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.b")
                callcmd(logger, f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.b=d1")
                ret, d1 = callcmd(logger, f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.b")
                assert d1 == "d1", f"HPIrq-->0 set fail!\ninfo: src={d0}, res={d1}"

                callcmd(logger, f"dmesg -c && echo 0 > /sys/bus/pci/slots/{device.slot}/power")
                ret, dmg = callcmd(logger, "dmesg")
                assert "pciehp: Timeout on hotplug command" not in dmg, f"dmesg is not None!\ninfo:\n{dmg}"
                callcmd(logger, f"dmesg -c && echo 1 > /sys/bus/pci/slots/{device.slot}/power")
                ret, dmg = callcmd(logger, "dmesg")
                assert f"pciehp: Slot({device.slot}): Link Up" not in dmg, f"dmesg is not None!\ninfo:\n{dmg}"
            else:
                assert False, f"{res} not support hot plug!"

    assert COUNT, f"no DSP found"


@log_decorator(logger=logger)
def test_PCIe_SYS_SLOT_011():
    COUNT = 0
    for device in devices:
        if device.type == 'DSP':
            COUNT += 1
            ret, base_addr = callcmd(logger, f"lspci -vvs {device.device_bdf}| grep Downstream |awk -F '[' '{{gsub("
                                             f"/].*$/,\"\",$2);print$NF}}'")
            # 修改 DSP 端口的 Slot Control 的PowerControl
            ret, nvme = callcmd(logger, f"ls -l /sys/class/block/ |grep {device.device_bdf} |awk -F ' ' '{{print $9}}'")
            nvme = nvme[:5]
            ret, res_hotplug = callcmd(logger, f"lspci -vvs {device.device_bdf} |grep SltCap -A 1 |grep -w HotPlug "
                                               f"|awk -F ' ' '{{print $7}}'")
            assert res_hotplug == "HotPlug+", f"SltCap HotPlug is {res_hotplug}, test stop!"
            ret, res_pwrctrl = callcmd(logger,
                                       f"lspci -vvs {device.device_bdf} |grep SltCap -A 1 |grep -w PwrCtrl |awk -F "
                                       f"' ' '{{print $3}}'")
            assert res_pwrctrl == "PwrCtrl+", f"SltCap PwrCtrl is {res_pwrctrl}, test stop!"

            ret, d0 = callcmd(logger, f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.w")
            callcmd(logger, f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.w=17f1")
            ret, d1 = callcmd(logger, f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.w")
            assert d1 == "17f1", f"Power-->1(off) set fail!\ninfo: src={d0}, res={d1}"
            time.sleep(5)
            res = callcmd(logger, f"dd if=/dev/{nvme}n1 of=/dev/null count=1000 bs=1024")
            assert "error" in res, f"src={d0}, set 17f1(power off), but dd success, fail!"

            ret, d0 = callcmd(logger, f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.w")
            callcmd(logger, f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.w=13f1")
            ret, d1 = callcmd(logger, f"setpci -s {device.device_bdf} 0x{base_addr}+0x18.w")
            assert d1 == "13f1", f"Power-->0(on) set fail!\ninfo: src={d0}, res={d1}"
            time.sleep(5)
            res = callcmd(logger, f"dd if=/dev/{nvme}n1 of=/dev/null count=1000 bs=1024")
            assert "1024000" in res, f"src={d0}, set 13f1(power on), but dd fail!"

    assert COUNT, f"no DSP found"


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
