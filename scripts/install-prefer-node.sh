#!/bin/sh
set -eu

target_arch="${1:-${TARGETARCH:-amd64}}"
node_version="24.19.0"
case "$target_arch" in
  amd64)
    node_arch="x64"
    node_sha256="14b342e71204f811bde6153be8e04b62aef63c236fef92b55f9c83154b409647"
    ;;
  arm64)
    node_arch="arm64"
    node_sha256="01443c1e1a29e531ccad5a46fefa6df490d2189c49f7955904aecdbb0fe86fdc"
    ;;
  *)
    echo "unsupported TARGETARCH for Node.js: $target_arch" >&2
    exit 1
    ;;
esac

archive="node-v${node_version}-linux-${node_arch}.tar.xz"
url="https://nodejs.org/dist/v${node_version}/${archive}"
curl -fsSL "$url" -o "/tmp/${archive}"
printf '%s  %s\n' "$node_sha256" "/tmp/${archive}" | sha256sum -c -
tar -xJf "/tmp/${archive}" \
  -C /usr/local/bin \
  --strip-components=2 \
  "node-v${node_version}-linux-${node_arch}/bin/node"
mkdir -p /usr/share/doc/node
tar -xJf "/tmp/${archive}" \
  -C /usr/share/doc/node \
  --strip-components=1 \
  "node-v${node_version}-linux-${node_arch}/LICENSE"
rm -f "/tmp/${archive}"
node --version
