sudo tee -a docker.yaml > /dev/null << EOF
[plugins."io.containerd.grpc.v1.cri".registry.configs."registry-1.docker.io".auth]
username = ${DOCKERHUB_USERNAME}
password = ${DOCKERHUB_PASSWORD}
EOF