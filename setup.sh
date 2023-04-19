#!/usr/bin/env bash
set -euxo pipefail

# This script sets up an environment for running e2e tests with a local
# microk8s cluster. Assumes that make, gcc/clang, and docker are already installed

# It installs microk8s, kubectl, and juju and then clones the specified infrastructure, control plane, and bootstrap repos

# ./setup.sh https://github.com/charmed-kubernetes/cluster-api-provider-juju.git https://github.com/charmed-kubernetes/cluster-api-control-plane-provider-charmed-k8s.git https://github.com/charmed-kubernetes/cluster-api-bootstrap-provider-charmed-k8s.git

[ $# -ne 3 ] && { echo "not enough arguments provided, must provide infrastructure provider, control plane provider, and bootstrap provider URLs as positional arguments"; exit 1; }

sudo snap install juju --classic
sudo snap install microk8s --classic
sudo snap install go --channel 1.19/stable --classic
sudo snap install kubectl --classic

sudo tee -a /var/snap/microk8s/current/args/containerd-template.toml > /dev/null << EOF
[plugins."io.containerd.grpc.v1.cri".registry.configs."registry-1.docker.io".auth]
username = ${DOCKER_USERNAME}
password = ${DOCKER_TOKEN}
EOF

sudo cat var/snap/microk8s/current/args/containerd-template.toml

sudo microk8s stop
sudo microk8s start
sudo microk8s status --wait-ready
sudo microk8s enable registry
sudo microk8s enable "metallb:10.246.153.243-10.246.153.243"
mkdir -p "$HOME/.kube"
sudo cat /var/snap/microk8s/current/credentials/client.config > "$HOME/.kube/config"

git clone $1 infra
git clone $2 control_plane
git clone $3 bootstrap



