import logging
import pytest
import os
import base64

log = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption("--infra-branch", action="store", default="main")

    parser.addoption("--control-plane-branch", action="store", default="main")

    parser.addoption("--bootstrap-branch", action="store", default="main")

    parser.addoption(
        "--metallb-ip-range",
        action="store",
        required=True,
        help="IP range in the format xxx.xxx.xxx.xxx-xxx.xxx.xxx.xxx",
    )


@pytest.fixture(scope="module")
def proxy():
    return "http://squid.internal:3128"


@pytest.fixture(scope="module")
def kubeconfig():
    return "/var/snap/microk8s/current/credentials/client.config"


@pytest.fixture(scope="module")
def infra_branch(request):
    return request.config.getoption("--infra-branch")


@pytest.fixture(scope="module")
def control_plane_branch(request):
    return request.config.getoption("--control-plane-branch")


@pytest.fixture(scope="module")
def bootstrap_branch(request):
    return request.config.getoption("--bootstrap-branch")


@pytest.fixture(scope="module")
def metallb_ip_range(request):
    return request.config.getoption("--metallb-ip-range")


@pytest.fixture(scope="module")
def gh_token(request):
    if os.environ.get("GH_TOKEN") is None:
        pytest.fail("Environment variable GH_TOKEN must be set to your Github PAT")
    return os.environ.get("GH_TOKEN")


@pytest.fixture(scope="module")
def cluster_resources(request):
    if os.environ.get("B64_RESOURCES") is None:
        pytest.fail(
            "Environment variable B64_RESOURCES must be set to your base64 encoded resources to be applied"
        )

    b64_resc = os.environ.get("B64_RESOURCES")
    b64_resc_bytes = b64_resc.encode("utf-8")
    resc_bytes = base64.b64decode(b64_resc_bytes)
    return resc_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def credentials(request):
    if os.environ.get("B64_CREDS") is None:
        pytest.fail(
            "Environment variable B64_CREDS must be set to your base64 encoded credentials"
        )

    b64_creds = os.environ.get("B64_CREDS")
    b64_creds_bytes = b64_creds.encode("utf-8")
    creds_bytes = base64.b64decode(b64_creds_bytes)
    return creds_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def dockerhub_username(request):
    if os.environ.get("DOCKERHUB_USERNAME") is None:
        pytest.fail("Environment variable DOCKERHUB_USERNAME must be set")
    return os.environ.get("DOCKERHUB_USERNAME")


@pytest.fixture(scope="module")
def dockerhub_password(request):
    if os.environ.get("DOCKERHUB_PASSWORD") is None:
        pytest.fail(
            "Environment variable DOCKERHUB_PASSWORD must be set to your docker hub password or token"
        )
    return os.environ.get("DOCKERHUB_PASSWORD")


class Helpers:
    @staticmethod
    async def run_cmd(unit, cmd_desc, cmd_string, fail_msg, log_results=False):
        log.info(cmd_desc)
        action = await unit.run(cmd_string)
        action await action.wait()
        if log_results:
            log.info(action.results)
        code = action.results.get("Code", self.results.get("return-code"))
        if code is None:
            log.error(f"Failed to find the return code in {action.results}")
            pytest.fail(f"Failed to find the return code in {action.results}")
        if code != 0:
            log.error(action.results)
            pytest.fail(fail_msg)


@pytest.fixture(scope="module")
def helpers():
    return Helpers


@pytest.fixture(scope="module")
async def microk8s_unit(
    ops_test, helpers, proxy, metallb_ip_range, dockerhub_username, dockerhub_password
):
    await ops_test.model.set_config(
        {
            "juju-http-proxy": proxy,
            "apt-http-proxy": proxy,
            "snap-http-proxy": proxy,
            "juju-https-proxy": proxy,
            "apt-https-proxy": proxy,
            "snap-https-proxy": proxy,
            "apt-no-proxy": "localhost,127.0.0.1,ppa.launchpad.net,launchpad.net",
            "juju-no-proxy": "localhost,127.0.0.1,0.0.0.0,ppa.launchpad.net,launchpad.net,10.0.8.0/24",
            "force-vm-hardware-version": "17",
        }
    )

    charm_config = {}
    charm_config["containerd_env"] = "\n".join(
        [
            "ulimit -n 65536 || true",
            "ulimit -l 16834 || true",
            f"HTTP_PROXY={proxy}",
            f"HTTPS_PROXY={proxy}",
            "NO_PROXY=localhost,127.0.0.1,0.0.0.0,ppa.launchpad.net,launchpad.net,10.0.8.0/24,192.168.0.0/16,10.246.154.0/24,10.246.153.0/24,10.152.183.0/24",
            f"https_proxy=h{proxy}",
            f"http_proxy={proxy}",
            "no_proxy=localhost,127.0.0.1,0.0.0.0,ppa.launchpad.net,launchpad.net,10.0.8.0/24,192.168.0.0/16,10.246.154.0/24,10.246.153.0/24,10.152.183.0/24",
        ]
    )
    charm_config[
        "custom_registries"
    ] = f'[{{"host": "docker.io", "url": "registry-1.docker.io", "username": "{dockerhub_username}", "password": "{dockerhub_password}"}}]'
    charm_config["addons"] = "dns ingress registry"
    log.info("Deploying charm...")

    microk8s_app = await ops_test.model.deploy(
        "microk8s",
        application_name="microk8s",
        series="focal",
        channel="edge",  # need edge for custom registries
        config=charm_config,
        constraints="mem=4G root-disk=20G cores=2",
        num_units=1,
    )
    await ops_test.model.wait_for_idle(status="active", timeout=60 * 60)

    unit = microk8s_app.units[0]

    # For some reason enabling metallb via addons config does not seem to work (maybe because the of the colon arguments to the addon)
    # workaround is to just run the enable command on the unit
    await helpers.run_cmd(
        unit,
        "Enabling metallb...",
        f"/snap/bin/microk8s enable metallb:{metallb_ip_range}",
        "Failed to enable metallb",
    )

    await ops_test.model.wait_for_idle(status="active", timeout=60 * 60)

    return unit


@pytest.fixture(scope="module")
async def cloned_branches(
    ops_test,
    helpers,
    microk8s_unit,
    proxy,
    infra_branch,
    control_plane_branch,
    bootstrap_branch,
):
    await helpers.run_cmd(
        microk8s_unit,
        "Setting git http proxy settings...",
        f"git config --system http.proxy {proxy} && git config --system https.proxy {proxy}",
        "Failed to set git proxy settings",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Cloning infra provider...",
        f"git clone -b {infra_branch} https://github.com/charmed-kubernetes/cluster-api-provider-juju.git /home/ubuntu/providers/infra",
        "Failed to clone infra provider",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Cloning control plane provider...",
        f"git clone -b {control_plane_branch} https://github.com/charmed-kubernetes/cluster-api-control-plane-provider-charmed-k8s.git /home/ubuntu/providers/control-plane",
        "Failed to clone clone control plane provider",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Cloning bootstrap provider...",
        f"git clone -b {bootstrap_branch} https://github.com/charmed-kubernetes/cluster-api-bootstrap-provider-charmed-k8s.git /home/ubuntu/providers/bootstrap",
        "Failed to clone clone bootstrap provider",
    )


@pytest.fixture(scope="module")
async def build_dependencies(ops_test, helpers, microk8s_unit, proxy):
    await helpers.run_cmd(
        microk8s_unit,
        "Installing build-essential...",
        "apt-get install -y build-essential",
        "Failed to install build-essential",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Downloading clusterctl...",
        f"curl -L --proxy {proxy} https://github.com/kubernetes-sigs/cluster-api/releases/download/v1.4.2/clusterctl-linux-amd64 -o clusterctl",
        "Failed to download clusterctl",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Installing clusterctl...",
        "install -o root -g root -m 0755 clusterctl /usr/local/bin/clusterctl",
        "Failed to install clusterctl",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Checking clusterctl version...",
        "clusterctl version",
        "Failed to check clusterctl version",
        True,
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Installing go...",
        "snap install go --channel 1.19/stable --classic",
        "Failed to install go snap",
    )


@pytest.fixture(scope="module")
async def docker(ops_test, helpers, microk8s_unit, proxy):
    await helpers.run_cmd(
        microk8s_unit,
        "Installing docker installation requirements...",
        "apt-get install -y ca-certificates curl gnupg",
        "Failed to install docker installation requirements",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Adding Docker GPG Key...",
        f"sudo install -m 0755 -d /etc/apt/keyrings && curl -fsSL --proxy {proxy} https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && chmod a+r /etc/apt/keyrings/docker.gpg",
        "Failed to add docker GPG key",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Adding Docker repository...",
        'echo "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null',
        "Failed to add docker repository",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Installing docker...",
        "apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",
        "Failed to install docker",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Creating systemd service configuration file for docker...",
        "sudo mkdir -p /etc/systemd/system/docker.service.d && touch /etc/systemd/system/docker.service.d/http-proxy.conf",
        "Failed to create docker configuration file",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Editing systemd service configuration file for docker...",
        f'echo -e "[Service]\nEnvironment="HTTP_PROXY={proxy}"\nEnvironment="HTTPS_PROXY={proxy}"\nEnvironment="NO_PROXY=localhost"\n" >> /etc/systemd/system/docker.service.d/http-proxy.conf',
        "Failed to edit configuration file",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Restarting docker...",
        "sudo systemctl daemon-reload && sudo systemctl restart docker",
        "Failed to restart docker",
    )
