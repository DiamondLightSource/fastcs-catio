#!/bin/bash

# podman launcher for phoebus container

rootdir=$(realpath $(dirname ${BASH_SOURCE[0]/})/..)

args=${args}"
-it
-e DISPLAY
--net host
--security-opt=label=type:container_runtime_t
"

mounts="
-v=/tmp:/tmp
-v=${rootdir}:/workspace
"

settings="
-resource /workspace/screens/catio.bob
"

set -x
podman run ${mounts} ${args} ghcr.io/epics-containers/ec-phoebus:latest ${settings} "${@}"
