#!/bin/sh
set -eu
# Search resource allowances, not proof rules: 1,200 MiB virtual memory and
# 240 CPU seconds per process for the proof construction.
repo=${HEESCH_VERIFIER:-/tmp/yukon-home/heesch}
mkdir -p proof
cp best-finite.heesch proof/best.heesch
(
    ulimit -v 1228800
    ulimit -t 240
    python3 -u "$repo/tools/prove.py" proof/best.heesch
)
# The x86 checker under Rosetta needs a large virtual address reservation;
# the frozen verifier's minimum CakeML setting is 1024 MiB each for heap and
# stack. Their actual resident use is measured by this separate process.
HEESCH_CAKE_HEAP_MB=1024 python3 -u check_proof.py

