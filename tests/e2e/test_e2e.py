import logging
import pytest
import shlex
import shutil
import os

log = logging.getLogger(__name__)

@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test):
    log.info("data files")
    log.info(os.listdir("tests/data"))
    log.info("copying file")
    shutil.copyfile("tests/data/containerd_proxy_config.txt", ops_test.tmp_path)
    log.info("temp path")
    log.info(os.listdir(ops_test.tmp_path))
    log.info("Deploying ubuntu charm")
    
    ubuntu_app = await ops_test.model.deploy(
        'ubuntu',
        application_name='ubuntu',
        series='jammy',
        channel='stable',
    )
    await ops_test.model.wait_for_idle()

    # get the one and only unit
    assert len(ubuntu_app.units) == 1
    # ubuntu_unit = ubuntu_app.units[0]

    # action = await ubuntu_unit.run('snap install microk8s --classic')
    # log.info(f"action results: {action.results}")
    cmd = (
           "juju exec "
           "--unit ubuntu/0 "
           "'snap install microk8s --classic'"
    )
    retcode, stdout, stderr = await ops_test.run(*shlex.split(cmd))
    if retcode != 0:
        log.error(f"retcode: {retcode}")
        log.error(f"stdout:\n{stdout.strip()}")
        log.error(f"stderr:\n{stderr.strip()}")
        pytest.fail("Failed to install microk8s")
    
    log.info(f"microk8s installation results: {stdout}")

    # copy proxy data to ubuntu machine
    filepath = ops_test.tmp_path / "containerd_proxy_config.txt"
    cmd = (
           "juju scp "
           f"{filepath} containerd_proxy_config.txt ubuntu/0:"
    )
    retcode, stdout, stderr = await ops_test.run(*shlex.split(cmd))
    if retcode != 0:
        log.error(f"retcode: {retcode}")
        log.error(f"stdout:\n{stdout.strip()}")
        log.error(f"stderr:\n{stderr.strip()}")
        pytest.fail("Failed to copy proxy data to ubuntu unit")

    # list directory on unit
    cmd = (
           "juju exec "
           "--unit ubuntu/0 "
           "'ls'"
    )
    retcode, stdout, stderr = await ops_test.run(*shlex.split(cmd))
    if retcode != 0:
        log.error(f"retcode: {retcode}")
        log.error(f"stdout:\n{stdout.strip()}")
        log.error(f"stderr:\n{stderr.strip()}")
        pytest.fail("Failed to list files on ubuntu unit")

    log.info(f"list results: {stdout}")
    
    # sudo bash -c 'cat containerd_proxy_config.txt >> /var/snap/microk8s/current/args/containerd-env'


    await ops_test.model.wait_for_idle()


async def test_status(ops_test):
    assert ops_test.model.applications["ubuntu"].units[0].workload_status == "active"