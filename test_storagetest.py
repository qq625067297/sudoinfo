#!/usr/bin/env python
import os
import sys
import time
import logging
import subprocess
from multiprocessing import Process, Queue
import pytest

DEBUG = False
os.system("rm -rf storagetest_log;mkdir storagetest_log")

LOGFILE = "storagetest_log/storagetest_%s.log" % time.strftime("%Y%m%d%H%M%S", time.localtime())
#设置日志打印格式
# 创建logger
logger = logging.getLogger('logger')
logger.setLevel(logging.DEBUG)  # 设置日志级别
# 创建控制台处理器
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# 创建file handler
fh = logging.FileHandler(LOGFILE)
fh.setLevel(logging.INFO)
# 创建格式器并绑定到处理器
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(lineno)s - %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)
# 将处理器添加到logger
logger.addHandler(ch)
logger.addHandler(fh)

diskname = []
switch_vd = '1eb6:6011'

def create_random_file(file_size):
    """
    创建一个固定大小的随机文件。
    :param file_path: 文件的路径
    :param file_size: 文件的大小（以GB为单位）
    """
    file_path = f'{file_size}G.txt'
    with open(f'{file_path}', 'wb') as file:
        for _ in range(file_size):
            chunk = os.urandom(1024 * 1024 * 1024)
            file.write(chunk)
    os.system(f"md5sum {file_path} | awk '{{print $1}}' > {file_path}.md5.std")


def dd_write_and_read_file(diskname, file_size):
    file_path = f'{file_size}G.txt'
    logger.info(f"write {file_path} to {diskname[0]} by dd command")
    os.system(f"dd if={file_path} of={diskname[0]} bs=1M status=progress")
    logger.info(f"read {diskname[0]} by dd command")
    os.system(f"dd if={diskname[0]} of={file_size}G.tmp bs=1M count={file_size * 1024} status=progress")
    logger.info(f"get md5sum of {file_size}G.tmp")
    os.system(f"md5sum {file_size}G.tmp | awk '{{print $1}}' > {file_path}.md5.tmp")
    logger.info("compare md5sum")
    ret = os.system(f"diff {file_path}.md5.tmp {file_path}.md5.std")
    return ret


def get_switch_disk():
    #get nvme disk
    pipe = subprocess.Popen("nvme list | grep /dev/nvme | awk '{print $1}'",
                            universal_newlines=True,
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE, shell=True)
    output, error = pipe.communicate(timeout=10)
    if pipe.returncode == 0:
        nvmedisk = output.strip().split()
    else:
        raise Exception("No disk found")

    pipe = subprocess.Popen(f"lspci -Dnd {switch_vd} | sed -n 1p | awk '{{print $1}}'",
                            universal_newlines=True,
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE, shell=True)
    output, error = pipe.communicate(timeout=10)
    USPBDF = output.strip()
    if not USPBDF:
        raise Exception("No Switch found")
    for disk in nvmedisk:
        pipe = subprocess.Popen(f"udevadm info --query=path {disk[:-2]} | grep {USPBDF}",
                                universal_newlines=True,
                                stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE, shell=True)
        output, error = pipe.communicate(timeout=10)
        if pipe.returncode == 0:
            global diskname
            diskname.append(disk)


def test_PCIe_SYS_Storage_002():
    if DEBUG:
        pytest.skip("test skipped")
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"casename: {casename} start testing...")
    for i in [25, 50, 100]:
        create_random_file(i)
        ret = dd_write_and_read_file(diskname, i)
        logger.info(f"casename: {casename}-{i}G testing finished...")
        assert ret == 0
        os.system(f"rm -rf {i}G.txt {i}G.tmp > /dev/null 2>&1")


def test_PCIe_SYS_Storage_005():
    if DEBUG:
        pytest.skip("test skipped")
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"casename: {casename} start testing...")
    logger.info("fio write test...")
    ret = os.system(f"fio --filename={diskname[0]} --ioengine=libaio "
                    f"--name=write_test --direct=1 --thread=1 --iodepth=512 "
                    f"--rw=write --bs=1M --numjobs=1 --size=10% "
                    f"--norandommap --fallocate=none --output=storagetest_log/${casename}_write.log")
    logger.info("fio write test %s" % ['success', 'failed'][ret and 1])
    assert ret == 0, "fio write test failed...."
    logger.info("fio read test...")
    ret = os.system(f"fio --filename={diskname[0]} --ioengine=libaio "
                    f"--name=read_test --direct=1 --thread=1 --iodepth=512 "
                    f"--rw=read --bs=1M --numjobs=1 --size=10% "
                    f"--norandommap --fallocate=none --output=storagetest_log/${casename}_read.log")
    logger.info("fio read test %s" % ['success', 'failed'][ret and 1])
    assert ret == 0, "fio read test failed...."


def test_ext4_test():
    if DEBUG:
        pytest.skip("test skipped")
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    mountdir = "/mnt/ext4"
    logger.info(f"casename: {casename} start testing...")
    logger.info("ext4 write test...")
    ret = os.system(f"echo y | sudo mkfs.ext4 {diskname[0]}")
    assert ret == 0, f"echo mkfs.ext4 {diskname[0]} failed..."
    ret = os.system(f"[ ! -f {mountdir} ] && mkdir {mountdir};umount {mountdir};mount {diskname[0]} {mountdir}")
    logger.info("mount ext4 filesystems test %s" % ['success', 'failed'][ret])
    assert ret == 0, "mount ext4 filesystems test failed...."
    ret = os.system(f"fio --directory={mountdir} --ioengine=libaio "
                    f"--name=write_test --direct=1 --thread=1 --iodepth=512 "
                    f"--rw=write --bs=1M --numjobs=1 --size=1G "
                    f"--norandommap --fallocate=none --output=storagetest_log/${casename}_write.log")
    logger.info("fio write test %s" % ['success', 'failed'][ret and 1])
    assert ret == 0, "fio write test failed...."
    logger.info("fio read test...")
    ret = os.system(f"fio --directory={mountdir} --ioengine=libaio "
                    f"--name=read_test --direct=1 --thread=1 --iodepth=512 "
                    f"--rw=read --bs=1M --numjobs=1 --size=1G "
                    f"--norandommap --fallocate=none --output=storagetest_log/${casename}_read.log")
    logger.info("fio read test %s" % ['success', 'failed'][ret and 1])
    time.sleep(10)
    os.system(f"umount {mountdir}")
    assert ret == 0, "fio read test failed...."
    logger.info(f"casename: {casename} test finished...")


def test_ext3_test():
    if DEBUG:
        pytest.skip("test skipped")
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    mountdir = "/mnt/ext3"
    logger.info(f"casename: {casename} start testing...")
    logger.info("ext4 write test...")
    ret = os.system(f"echo y | sudo mkfs.ext3 {diskname[0]}")
    assert ret == 0, f"echo mkfs.ext3 {diskname[0]} failed..."
    ret = os.system(f"[ ! -f {mountdir} ] && mkdir {mountdir};umount {mountdir};mount {diskname[0]} {mountdir}")
    logger.info("mount ext3 filesystems test %s" % ['success', 'failed'][ret])
    assert ret == 0, "mount ext3 filesystems test failed...."
    ret = os.system(f"fio --directory={mountdir} --ioengine=libaio "
                    f"--name=write_test --direct=1 --thread=1 --iodepth=512 "
                    f"--rw=write --bs=1M --numjobs=1 --size=1G "
                    f"--norandommap --fallocate=none --output=storagetest_log/${casename}_write.log")
    logger.info("fio write test %s" % ['success', 'failed'][ret and 1])
    assert ret == 0, "fio write test failed...."
    logger.info("fio read test...")
    ret = os.system(f"fio --directory={mountdir} --ioengine=libaio "
                    f"--name=read_test --direct=1 --thread=1 --iodepth=512 "
                    f"--rw=read --bs=1M --numjobs=1 --size=1G "
                    f"--norandommap --fallocate=none --output=storagetest_log/${casename}_read.log")
    logger.info("fio read test %s" % ['success', 'failed'][ret and 1])
    time.sleep(10)
    os.system(f"umount {mountdir}")
    assert ret == 0, "fio read test failed...."
    logger.info(f"casename: {casename} test finished...")


def test_xfs_test():
    if DEBUG:
        pytest.skip("test skipped")
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    mountdir = "/mnt/xfs"
    logger.info(f"casename: {casename} start testing...")
    logger.info("xfs write test...")
    ret = os.system(f"echo y | sudo mkfs.xfs -f {diskname[0]}")
    assert ret == 0, f"echo mkfs.xfs {diskname[0]} failed..."
    ret = os.system(f"[ ! -f {mountdir} ] && mkdir {mountdir};umount {mountdir};mount {diskname[0]} {mountdir}")
    logger.info("mount xfs filesystems test %s" % ['success', 'failed'][ret])
    assert ret == 0, "mount xfs filesystems test failed...."
    ret = os.system(f"fio --directory={mountdir} --ioengine=libaio "
                    f"--name=write_test --direct=1 --thread=1 --iodepth=512 "
                    f"--rw=write --bs=1M --numjobs=1 --size=1G "
                    f"--norandommap --fallocate=none --output=storagetest_log/${casename}_write.log")
    logger.info("fio write test %s" % ['success', 'failed'][ret and 1])
    assert ret == 0, "fio write test failed...."
    logger.info("fio read test...")
    ret = os.system(f"fio --directory={mountdir} --ioengine=libaio "
                    f"--name=read_test --direct=1 --thread=1 --iodepth=512 "
                    f"--rw=read --bs=1M --numjobs=1 --size=1G "
                    f"--norandommap --fallocate=none --output=storagetest_log/${casename}_read.log")
    logger.info("fio read test %s" % ['success', 'failed'][ret and 1])
    time.sleep(10)
    os.system(f"umount {mountdir}")
    assert ret == 0, "fio read test failed...."
    logger.info(f"casename: {casename} test finished...")


def multi_write_with_verify(q, disk, name):
    # functionname = sys._getframe().f_code.co_name
    ret = os.system(f"fio --filename={disk} --ioengine=libaio --name=write_test "
                    f"--direct=1 --thread=1 --iodepth=512 --rw=write --bs=1M --numjobs=1 "
                    f"--size=10% --norandommap --fallocate=none --verify=md5 --do_verify=1 "
                    f"--verify_dump=1 --output=storagetest_log/{name}_{disk.split('/')[-1]}.log")
    q.put(ret)


def test_multi_disk_write():
    if DEBUG:
        pytest.skip("test skipped")
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    if len(diskname) <= 1:
        pytest.skip("only found 1 pcs nvme disk, test skipped!!!")
    q = Queue()
    processes = [Process(target=multi_write_with_verify, args=(q, i, casename)) for i in diskname]

    for p in processes:
        p.start()

    for p in processes:
        p.join()

    results = [q.get() for _ in processes]
    assert sum(results) == 0, "test failed"

def test_random_blocksize_rw():
    if DEBUG:
        pytest.skip("test skipped")
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"start {casename} testing...")
    ret = os.system(f"fio --name=test_bs --ioengine=libaio --iodepth=16 --rw=read --bsrange=4k-128k "
              f"--direct=1 --size=1G --numjobs=1 --runtime=60 --group_reporting "
              f"--filename={diskname[0]} --output-format=terse --output=storagetest_log/{casename}_nvme_read.txt")
    assert ret == 0, f"{casename} fio read test failed"
    ret = os.system(f"fio --name=test_bs --ioengine=libaio --iodepth=16 --rw=write --bsrange=4k-128k "
              f"--direct=1 --size=1G --numjobs=1 --runtime=60 --group_reporting "
              f"--filename={diskname[0]} --output-format=terse --output=storagetest_log/{casename}_nvme_write.txt")
    assert ret == 0, f"{casename} fio write test failed"
    logger.info(f"{casename} test finished...")


def test_random_blocksize_randrw():
    if DEBUG:
        pytest.skip("test skipped")
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"start {casename} testing...")
    ret = os.system(f"fio --name=test_bs --ioengine=libaio --iodepth=16 --rw=randread --bsrange=4k-128k "
              f"--direct=1 --size=1G --numjobs=1 --runtime=60 --group_reporting "
              f"--filename={diskname[0]} --output-format=terse --output=storagetest_log/{casename}_nvme_read.txt")
    assert ret == 0, f"{casename} fio read test failed"
    ret = os.system(f"fio --name=test_bs --ioengine=libaio --iodepth=16 --rw=randwrite --bsrange=4k-128k "
              f"--direct=1 --size=1G --numjobs=1 --runtime=60 --group_reporting "
              f"--filename={diskname[0]} --output-format=terse --output=storagetest_log/{casename}_nvme_write.txt")
    assert ret == 0, f"{casename} fio write test failed"
    logger.info(f"{casename} test finished...")


def test_random_blocksize_mixrw():
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"start {casename} testing...")
    ret = os.system(f"fio --name=test_bs --ioengine=libaio --iodepth=16 --rw=randrw "
                    f"--rwmixread=70 --bsrange=4k-128k --direct=1 --size=1G "
                    f"--numjobs=1 --runtime=60 --group_reporting --filename={diskname[0]} "
                    f"--output-format=terse --output=storagetest_log/{casename}_results_nvme_rw.txt")
    assert ret == 0, f"{casename} fio test failed"
    logger.info(f"{casename} test finished...")


def test_fio_psync():
    if DEBUG:
        pytest.skip("test skipped")
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"start {casename} testing...")
    ret = os.system(f"cd app/yundu_swtest && rm -rf logs; bash SWTest.sh {diskname[0]} 1")
    os.system(f'cp -r app/yundu_swtest/logs storagetest_log/{casename}_logs')
    assert ret == 0, f"{casename} test failed"
    logger.info(f"{casename} test finished...")


def multi_read_and_write(q, disk, mode, name):
    ret = os.system(f'fio --filename={disk} --ioengine=libaio --name={mode}_test --direct=1 '
                    f'--thread=1 --iodepth=512 --rw={mode} --bs=1M --numjobs=1 --size=10% '
                    f'--norandommap --fallocate=none --output=storagetest_log/{name}_{mode}.log')
    q.put(ret)


def test_fio_libaio():
    if DEBUG:
        pytest.skip("test skipped")
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    if len(diskname) <= 1:
        pytest.skip("only found 1 pcs nvme disk, test skipped!!!")
    q = Queue()
    processes = [Process(target=multi_read_and_write,
                         args=(q, i, ['write', 'read'][diskname.index(i) % 2] ,casename))
                         for i in diskname]

    for p in processes:
        p.start()

    for p in processes:
        p.join()

    results = [q.get() for _ in processes]
    assert sum(results) == 0, "{casename} test failed"


def test_fio_mixrw():
    if DEBUG:
        pytest.skip("test skipped")
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"start {casename} testing...")
    ret = os.system(f"fio --name=test_bs --ioengine=libaio --iodepth=16 --rw=randrw --rwmixread=70"
                    f" --bs=4k --direct=1 --size=1G --numjobs=1 --runtime=120 --group_reporting "
                    f"--filename={diskname[0]} --output-format=terse --output=storagetest_log/{casename}_results_nvme_rw.txt")
    assert ret == 0, f"{casename} fio test failed"
    logger.info(f"{casename} test finished...")


def test_difference_blocksize():
    if DEBUG:
        pytest.skip("test skipped")
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"start {casename} testing...")
    for bs in [4, 8, 16, 32, 64]:
        ret = os.system(f"fio --filename={diskname[0]} --ioengine=libaio --name=write_test --direct=1 "
                        f"--thread=1 --iodepth=512 --rw=write --bs={bs}k --numjobs=1 --size=10% "
                        f"--norandommap --fallocate=none --output=storagetest_log/{casename}_{bs}k_write_test.log")
        assert ret == 0, f"{casename}_{bs}k fio test failed"
    logger.info(f"{casename} test finished...")


def test_Orion():
    if DEBUG:
        pytest.skip("test skipped")
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"start {casename} testing...")
    with open(f"app/{casename}.lun", "w") as f:
        f.writelines(i + '\n' for i in diskname)
    ret = os.system(f"cd app/ && rm -rf logs; ./orion_linux_x86-64 -run simple -testname {casename} -num_disks {len(diskname)}")
    os.system(f'cp -r app/{casename}*.txt storagetest_log')
    assert ret == 0, f"{casename} test failed"
    logger.info(f"{casename} test finished...")


def test_alldisktest():
    if DEBUG:
        pytest.skip("test skipped")
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"start {casename} testing...")
    for disk in diskname:
        ret = os.system(f"fio --filename={disk}  --ioengine=libaio --name=rand_read_test --direct=1 "
                        f"--thread=1 --iodepth=128 --rw=randread --bs=4k --numjobs=1 --size=10%  "
                        f"--norandommap --fallocate=none --do_verify=1 --verify_dump=1 --group_reporting "
                        f"--output=storagetest_log/{casename}_rand_read_test.log")
        assert ret == 0, f"{casename} fio test failed"
        ret = os.system(f"fio --filename={disk}  --ioengine=libaio --name=rand_write_test --direct=1 "
                        f"--thread=1 --iodepth=128 --rw=randwrite --bs=4k --numjobs=1 --size=10%  "
                        f"--norandommap --fallocate=none --do_verify=1 --verify_dump=1 --group_reporting "
                        f"--output=storagetest_log/{casename}_rand_write_test.log")
        assert ret == 0, f"{casename} fio test failed"
        ret = os.system(f"fio --filename={disk}  --ioengine=libaio --name=rand_rw_test --direct=1 "
                        f"--thread=1 --iodepth=128 --rw=randrw --bs=4k --numjobs=1 --size=10%  "
                        f"--norandommap --fallocate=none --do_verify=1 --verify_dump=1 --group_reporting "
                        f"--output=storagetest_log/{casename}_rand_rw_test.log")
        assert ret == 0, f"{casename} fio test failed"
        ret = os.system(f"fio --filename={disk}  --ioengine=libaio --name=read_test --direct=1 "
                        f"--thread=1 --iodepth=128 --rw=read --bs=128k --numjobs=1 --size=10%  "
                        f"--norandommap --fallocate=none --do_verify=1 --verify_dump=1 --group_reporting "
                        f"--output=storagetest_log/{casename}_read_test.log")
        assert ret == 0, f"{casename} fio test failed"
        ret = os.system(f"fio --filename={disk}  --ioengine=libaio --name=write_test --direct=1 "
                        f"--thread=1 --iodepth=128 --rw=write --bs=128k --numjobs=1 --size=10%  "
                        f"--norandommap --fallocate=none --do_verify=1 --verify_dump=1 --group_reporting "
                        f"--output=storagetest_log/{casename}_write_test.log")
        assert ret == 0, f"{casename} fio test failed"
        ret = os.system(f"fio --filename={disk}  --ioengine=libaio --name=read_write_test --direct=1 "
                        f"--thread=1 --iodepth=128 --rw=rw --bs=4k --numjobs=1 --size=10%  "
                        f"--norandommap --fallocate=none --do_verify=1 --verify_dump=1 --group_reporting "
                        f"--output=storagetest_log/{casename}_read_write_test.log")
        assert ret == 0, f"{casename} fio test failed"
        ret = os.system(f"fio --filename={disk}  --ioengine=libaio --name=rand_block_test --direct=1 "
                        f"--thread=1 --iodepth=128 --rw=rw --bsrange=4k-128k --numjobs=1 --size=10%  "
                        f"--norandommap --fallocate=none --do_verify=1 --verify_dump=1 --group_reporting "
                        f"--output=storagetest_log/{casename}_rand_block_test.log")
        assert ret == 0, f"{casename} fio test failed"
        ret = os.system(f"fio --filename={disk}  --ioengine=libaio --name=rand_rw_block_test --direct=1 "
                        f"--thread=1 --iodepth=128 --rw=randrw --rwmixread=70 --bs=4k-128k --numjobs=1 --size=10%  "
                        f"--norandommap --fallocate=none --do_verify=1 --verify_dump=1 --group_reporting "
                        f"--output=storagetest_log/{casename}_rand_rw_block_test.log.log")
        assert ret == 0, f"{casename} fio test failed"
    logger.info(f"{casename} test finished...")


def test_storage_performance():
    if DEBUG:
        pytest.skip("test skipped")
    functionname = sys._getframe().f_code.co_name
    casename = functionname.replace("test_", "")
    logger.info(f"start {casename} testing...")
    ret = os.system(f'fio --filename={diskname[0]} --ioengine=libaio --name=rw_test --direct=1 --thread=1 '
                    f'--iodepth=128 --rw=randread --bs=1M --numjobs=32 --size=16G --runtime=300 --time_based'
                    f'  --norandommap --fallocate=none --group_reporting --output=storagetest_log/{casename}_write.log')
    assert ret == 0, f"{casename}_write fio test failed"
    ret = os.system(f'fio --filename={diskname[0]}  --ioengine=libaio --name=rw_test --direct=1 --thread=1 '
                    f'--iodepth=128 --rw=randwrite --bs=1M --numjobs=32 --size=16G --runtime=300 --time_based  '
                    f'--norandommap --fallocate=none --group_reporting --output=storagetest_log/{casename}_read.log')
    assert ret == 0, f"{casename}_read fio test failed"
    logger.info(f"{casename} test finished...")


def setup_module():
    logger.info("clean old logs...")
    # os.system(f"ls *.log | grep -v {LOGFILE} | xargs rm -rf")
    os.system("rm -rf storage_testlog.zip > /dev/null 2>&1")
    ret = os.system("which mkfs.xfs")
    if ret:
        os.system("apt install xfsprogs")
    get_switch_disk()
    assert len(diskname) != 0, "not found nvme disk under switch"
    os.system(f'umount -A {diskname[0]}')


def teardown_module():
    logger.info("collect log")
    os.system("zip -r storage_testlog.zip storagetest_log")


def setup():
    pass


def teardown():
    pass
