#!/usr/bin/env bash
set -euo pipefail

[[ -z "${CREDENTIALS}" ]]&& { echo "CREDENTIALS env var is not set"; exit 1; }

REGISTRY="localhost:32000"

# deploy the infra provider
echo "deploying infra provider"
cd ./infra
IMG="$REGISTRY/capi-juju-controller:latest"
make docker-build docker-push deploy "IMG=$IMG" "DEPLOY_IMG=$IMG"
kubectl rollout status -n capi-juju-system deployment/capi-juju-controller-manager --timeout 1m
echo "infra provider deployed"

# deploy the control plane provider
echo "deploying control plane provider"
cd ../control_plane
IMG="$REGISTRY/capi-control-plane-charmed-k8s-controller:latest"
make docker-build docker-push deploy "IMG=$IMG" "DEPLOY_IMG=$IMG"
kubectl rollout status -n capi-charmed-k8s-control-plane-system deployment/capi-ck8s-control-plane-controller-manager --timeout 1m
echo "control plane provider deployed"

# deploy the bootstrap provider
echo "deploying bootstrap provider"
cd ../bootstrap
IMG="$REGISTRY/capi-bootstrap-charmed-k8s-controller:latest"
make docker-build docker-push deploy "IMG=$IMG" "DEPLOY_IMG=$IMG"
kubectl rollout status -n capi-charmed-k8s-bootstrap-system deployment/capi-charmed-k8s-bootstrap-controller-manager --timeout 1m
echo "bootstrap provider deployed"

echo "creating cloud secret"
echo $CREDENTIALS | base64 -d > ./credentials.yaml
kubectl create secret generic jujucluster-sample-credential-secret --from-file=value=./credentials.yaml -n default
echo "cloud secret created"

# apply the cluster sample from the control plane repo
# cd ../control_plane
# kubectl apply -f config/samples/infrastructure_v1beta1_jujucluster.yaml -n default

# wait for the cluster to be ready
# kubectl wait clusters --all -n default --for condition=Ready --timeout=1801s

# # apply the control plane sample from the control plane repo
# kubectl apply -f config/samples/controlplane_v1beta1_charmedk8scontrolplane.yaml -n default

# # apply the worker machine template from the infra repo
# cd ../infra
# kubectl apply -f config/samples/infrastructure_v1beta1_machinedeployment.yaml -n default

# # wait for the machines to be ready
# kubectl wait machines --all -n default --for condition=Ready --timeout=3600s

# # log into the juju controller
# kubectl get secret <your-cluster-name>-registration-secret -o jsonpath='{.data}' -n default
# REGISTRATION_STRING=$(kubectl get secret db-user-pass -o jsonpath='{.data.registration-string}' | base64 --decode)

# juju register "$REGISTRATION_STRING"

# # might not need to register
# # https://cloud.garr.it/support/kb/juju/juju_login_to_controller/