import logging
import pytest

log = logging.getLogger(__name__)

@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test):
    log.info("Deploying ubuntu charm")
    await ops_test.model.deploy(
        'ubuntu',
        application_name='ubuntu',
        series='jammy',
        channel='stable',
    )
    await ops_test.model.wait_for_idle()

async def test_status(ops_test):
    assert ops_test.model.applications["ubuntu"].units[0].workload_status == "active"