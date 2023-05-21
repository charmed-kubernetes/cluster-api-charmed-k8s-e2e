import logging
import pytest

log = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
async def test_build_and_deploy(
    ops_test,
    helpers,
    microk8s_unit,
    cloned_branches,
    build_dependencies,
    docker,
    proxy,
    kubeconfig,
    gh_token,
    cluster_resources,
    credentials,
):
    infra_image = "localhost:32000/capi-juju-controller:latest"
    control_plane_image = (
        "localhost:32000/capi-control-plane-charmed-k8s-controller:latest"
    )
    bootstrap_image = "localhost:32000/capi-bootstrap-charmed-k8s-controller:latest"

    await helpers.run_cmd(
        microk8s_unit,
        "Building infra docker image...",
        f"cd /home/ubuntu/providers/infra && HOME=/home/ubuntu http_proxy={proxy} https_proxy={proxy} docker build -t {infra_image} --build-arg http_proxy={proxy} --build-arg https_proxy={proxy} .",
        "Failed to build infra image",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Pushing infra docker image...",
        f"docker push {infra_image}",
        "Failed to push infra image",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Building control plane docker image...",
        f"cd /home/ubuntu/providers/control-plane && HOME=/home/ubuntu http_proxy={proxy} https_proxy={proxy} docker build -t {control_plane_image} --build-arg http_proxy={proxy} --build-arg https_proxy={proxy} .",
        "Failed to build control plane image",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Pushing control plane docker image...",
        f"docker push {control_plane_image}",
        "Failed to push control plane image",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Building bootstrap docker image...",
        f"cd /home/ubuntu/providers/bootstrap && HOME=/home/ubuntu http_proxy={proxy} https_proxy={proxy} docker build -t {bootstrap_image} --build-arg http_proxy={proxy} --build-arg https_proxy={proxy} .",
        "Failed to build bootstrap image",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Pushing bootstrap docker image...",
        f"docker push {bootstrap_image}",
        "Failed to push bootstrap image",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Running clusterctl init...",
        f"http_proxy={proxy} https_proxy={proxy} GITHUB_TOKEN={gh_token} clusterctl init --kubeconfig {kubeconfig}",
        "Failed to run clusterctl init",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Deploying infra provider...",
        f"HOME=/home/ubuntu http_proxy={proxy} https_proxy={proxy} GITHUB_TOKEN={gh_token} KUBECONFIG={kubeconfig} make -C /home/ubuntu/providers/infra deploy DEPLOY_IMG={infra_image}",
        "Failed to deploy infra provider",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Waiting for infra provider deployment to be ready...",
        f"KUBECONFIG={kubeconfig} kubectl rollout status -n capi-juju-system deployment/capi-juju-controller-manager --timeout 1m",
        "Infra provider deployment was not ready in time",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Deploying control plane provider...",
        f"HOME=/home/ubuntu http_proxy={proxy} https_proxy={proxy} GITHUB_TOKEN={gh_token} KUBECONFIG={kubeconfig} make -C /home/ubuntu/providers/control-plane deploy DEPLOY_IMG={control_plane_image}",
        "Failed to deploy control plane provider",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Waiting for control plane provider deployment to be ready...",
        f"KUBECONFIG={kubeconfig} kubectl rollout status -n capi-charmed-k8s-control-plane-system deployment/capi-ck8s-control-plane-controller-manager --timeout 1m",
        "Control plane provider deployment was not ready in time",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Deploying bootstrap provider...",
        f"HOME=/home/ubuntu http_proxy={proxy} https_proxy={proxy} GITHUB_TOKEN={gh_token} KUBECONFIG={kubeconfig} make -C /home/ubuntu/providers/bootstrap deploy DEPLOY_IMG={bootstrap_image}",
        "Failed to deploy bootstrap provider",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Waiting for bootstrap provider deployment to be ready...",
        f"KUBECONFIG={kubeconfig} kubectl rollout status -n capi-charmed-k8s-bootstrap-system deployment/capi-charmed-k8s-bootstrap-controller-manager --timeout 1m",
        "Bootstrap provider deployment was not ready in time",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Creating credentials file...",
        f"echo '{credentials}' >> creds.yaml",
        "Failed to create credentials file",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Creating credentials secret from file...",
        f"KUBECONFIG={kubeconfig} kubectl create secret generic jujucluster-sample-credential-secret --from-file=value=./creds.yaml -n default",
        "Failed to create credentials secret",
    )

    await helpers.run_cmd(
        microk8s_unit,
        "Creating cluster resources...",
        f"echo '{cluster_resources}' | kubectl apply -f -",
        "Failed to create cluster resources",
        True,
    )


async def test_cluster_ready(ops_test, helpers, kubeconfig, microk8s_unit):
    await helpers.run_cmd(
        microk8s_unit,
        "Waiting for jujucluster to be ready...",
        f"KUBECONFIG={kubeconfig} kubectl wait --for=jsonpath='{{.status.ready}}'=true jujucluster --all --timeout=1800s",
        "Failed to wait for jujucluster to become ready",
        True,
    )


async def test_control_plane_initialized(ops_test, helpers, kubeconfig, microk8s_unit):
    await helpers.run_cmd(
        microk8s_unit,
        "Waiting for control plane to be initialized...",
        f"KUBECONFIG={kubeconfig} kubectl wait --for=jsonpath='{{.status.initialized}}'=true charmedk8scontrolplane --all --timeout=2700s",
        "Failed to wait for control plane to become initialized",
        True,
    )


async def test_machines_running(ops_test, helpers, kubeconfig, microk8s_unit):
    await helpers.run_cmd(
        microk8s_unit,
        "Waiting for all machines to be running...",
        f"KUBECONFIG={kubeconfig} kubectl wait --for=jsonpath='{{.status.phase}}'=Running machine --all --timeout=600s",
        "Failed to wait for machines to become ready",
        True,
    )


async def test_delete_cluster(ops_test, helpers, kubeconfig, microk8s_unit):
    await helpers.run_cmd(
        microk8s_unit,
        "Deleting cluster...",
        f"KUBECONFIG={kubeconfig} kubectl delete cluster --all --timeout=1800s",
        "Failed to delete cluster. Manual removal of cluster machines may be required",
        True,
    )
