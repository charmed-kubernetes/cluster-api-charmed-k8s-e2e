import logging
import pytest
import shlex

log = logging.getLogger(__name__)

@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test):
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
           "snap install microk8s"
    )
    retcode, stdout, stderr = await ops_test.run(*shlex.split(cmd))
    if retcode != 0:
        log.error(f"retcode: {retcode}")
        log.error(f"stdout:\n{stdout.strip()}")
        log.error(f"stderr:\n{stderr.strip()}")
        pytest.fail("Failed to install microk8s")
    
    log.info(f"installation results: {stdout}")

    await ops_test.model.wait_for_idle()


async def test_status(ops_test):
    assert ops_test.model.applications["ubuntu"].units[0].workload_status == "active"