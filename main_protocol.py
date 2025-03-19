import os
import sys
import subprocess
import logging
import time
import paramiko
import json
import socket
import xml.etree.ElementTree as ET
from utils import dmadriver

os.system("[ ! -d /protocol_logs ] && mkdir protocol_logs")
LOGFILE = "protocol_logs/main_%s.log" % time.strftime("%Y%m%d%H%M%S", time.localtime())
# 设置日志打印格式
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


def callcmd(command, timeout=10, ignore=False):
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


def remotecmd(cmd, ip='192.168.10.67', username='root', password='1', port=22):
    """
    :param port:
    :param cmd: remote command or script
    :param ip: remote server ip
    :param username: remote server os username
    :param password: remote server os password
    :return:
    """
    status = False
    # 创建SSH客户端
    client = paramiko.SSHClient()
    # 自动添加未知的服务器密钥及策略
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        # 连接SSH服务端
        client.connect(hostname=ip, port=port, username=username, password=password, timeout=30)
        # 执行命令
        stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
        # 实时读取输出
        while True:
            # 读取标准输出
            if stdout.channel.recv_ready():
                sys.stdout.write(stdout.channel.recv(1024).decode())
                sys.stdout.flush()
            # 读取标准错误
            if stdout.channel.recv_stderr_ready():
                sys.stderr.write(stdout.channel.recv_stderr(1024).decode())
                sys.stderr.flush()
            # 检查命令是否结束
            if stdout.channel.exit_status_ready():
                break
        status = stdout.channel.recv_exit_status()
        if status:
            logger.error(f"remote command:{cmd} exec failed, return code is {status}")
        else:
            logger.info(f"remote command:{cmd} exec success")
    except paramiko.AuthenticationException:
        logger.error("认证失败！")
        return None
    except paramiko.SSHException as e:
        logger.error(f"SSH连接错误: {e}")
        return None
    except paramiko.ssh_exception.NoValidConnectionsError as e:
        logger.error(f"连接{ip}失败...")
        return None
    except socket.timeout:
        logger.error(f"连接超时：无法在10秒内连接到 {ip}")
        return None
    finally:
        # 关闭连接
        client.close()
    return status


def remotecp(localfile, remotefile, ip='192.168.10.67', action="put", username='root', password='1', port=22):
    transport = paramiko.Transport(ip, port)
    transport.connect(username=username, password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)
    try:
        if action == "put":
            sftp.put(localfile, remotefile)
        elif action == "get":
            sftp.get(remotefile, localfile)
    except IOError as e:
        logger.error(f"{action} file occurs error: {e}")
        exit(1)
    else:
        logger.info("%s file %s success" % (["upload", "download"][action == "get"], localfile))
    finally:
        sftp.close()


def compare_tree(host, username, password):
    get_jsonfile(host, username, password)
    ret, msg = callcmd('diff pcie_tree.json pcie_tree_aftertest.json')
    return ret, msg


def get_jsonfile(host, username, password):
    # 拷贝测试前pcie_tree文件
    if not os.path.exists("pcie_tree.json"):
        remotecp("pcie_tree.json", "pcie_tree.json", action='get', ip=host, username=username, password=password)
    # 拷贝测试前pcie_tree文件
    remotecp("pcie_tree_aftertest.json", "pcie_tree_aftertest.json", action='get', ip=host, username=username,
             password=password)


def read_data_file(filename):
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def transfer_xml(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    result = []
    for testcase in root.findall(".//testcase"):
        status = "passed"
        if testcase.find("skipped") is not None:
            status = "skipped"
        elif testcase.find("failure") is not None or testcase.find("error") is not None:
            status = "failed"
        result.append(status)
    return result


def reboot_host(host, username, password):
    ret = remotecmd("reboot", ip=host, username=username, password=password)
    if ret is None:
        raise Exception(f"Cannot reboot {host}")
    elif ret == 0 or ret == -1 or ret == 255:
        logger.info(f"{host} reboot success")
    else:
        logger.info(f"{host} reboot failed, ret is {ret}")
    logger.info(f"waiting for {host} up")

    ret = host_isalive(host, username, password)
    if ret == 1:
        logger.error(f"please check {host}")
        raise Exception(f"{host} is not up")


def host_isalive(host, username, password, timeout=600):
    start_time = time.time()
    time.sleep(60)
    while True:
        current_time = time.time()
        if current_time - start_time >= timeout:
            logger.error(f"Cannot link to {host} in {timeout} seconds...")
            return 1
        else:
            ret = remotecmd('ls > /dev/null 2>&1', ip=host, username=username, password=password)
            if ret is None:
                logger.debug(f"waiting {host} up")
                time.sleep(10)
                continue
            else:
                logger.info(f"{host} is up")
                return 0


def get_all_testcase(filename):
    ret, msg = callcmd(f"pytest -q --collect-only {filename} | grep test_")
    if msg:
        return msg.strip().split()


def main(filename, ip, username, password):
    remotecp(filename, filename, ip=ip, action="put", username=username, password=password)
    remotecp('utils.py', 'utils.py', ip=ip, action="put", username=username, password=password)
    remotecp(f'driver/dma/{dmadriver}', f'{dmadriver}', ip=ip, action="put", username=username, password=password)
    all_testcase = get_all_testcase(filename)
    for case in all_testcase:
        logger.info(f"Start test {case}...")
        xml_name = f"{case.split('::')[1]}-test-results.xml"
        ret = remotecmd(
            f"pytest -vvv -s ./{case} --junitxml={xml_name} -s --capture=no "
            f"--alluredir=allure-results/{filename.split('.')[0]}", ip=ip, username=username, password=password)
        if ret is None:
            raise Exception(f"cannot connect to {ip}")
        # copy xml to local, for get result
        remotecp(xml_name, xml_name, ip=ip, action="get", username=username, password=password)
        _data = transfer_xml(xml_name)
        logger.info(f"{case} test status: {_data[0]}")
        ret, msg = compare_tree(ip, username, password)
        if not ret:
            logger.error("pcie_tree is different between pcie_tree.json and pcie_tree_aftertest.json")
            logger.error("reboot host")
            reboot_host(ip, username, password)
        elif _data[0] != 'skipped' and ('test_protocoltest_mem' in case or 'test_protocoltest_reset' in case):
            logger.error("reboot host")
            reboot_host(ip, username, password)


def get_filelist():
    filenames = []
    prefix = 'test_protocol'
    extens = '.py'
    filelist = os.listdir('.')
    for file in filelist:
        if file.startswith(prefix) and file.endswith(extens):
            filenames.append(file)

    return filenames


def get_test_logs(ip, username, password):
    zipfile = "all_logs.zip"
    remotecmd(
        f"zip -r {zipfile} allure-results *-test-results.xml protocol_logs", ip=ip, username=username,
        password=password)
    remotecp(zipfile, zipfile, action='get', ip=ip, username=username, password=password)
    callcmd(f"unzip -qo {zipfile}")


def delete_remote_logs(ip, username, password):
    logger.info('delete logs...')
    remotecmd(
        f"rm -rf allure-results *-test-results.xml protocol_logs all_logs.zip", ip=ip, username=username,
        password=password)


##########main#############
if __name__ == '__main__':
    ip = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    delete_remote_logs(ip, username, password)
    filenames = get_filelist()
    for filename in filenames:
        main(filename, ip, username, password)
    get_test_logs(ip, username, password)
