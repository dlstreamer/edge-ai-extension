#!/bin/bash
ENTRYPOINT_DIR=$(dirname "$(readlink -f "$0")")
TESTS_DIR=$(dirname $ENTRYPOINT_DIR)
SOURCE_DIR=$(dirname $TESTS_DIR)

RESULTS_DIR=${RESULTS_DIR:-"$TESTS_DIR/results/clamav"}
OUTPUT_FILE="$RESULTS_DIR/report.txt"
SCAN_DIR=${SCAN_DIR:-"/home"}
CLAMAV_ARGS=${CLAMAV_ARGS:-"$@"}

# TODO: Add negative test confirming eicar is detected
# wget -O /tmp/eicar.com http://www.eicar.org/download/eicar.com

mkdir -p "$RESULTS_DIR"

clamscan --version

# Squelch error since daemon is not running so
# won't be connecting to notify
sed -i 's/NotifyClamd/#NotifyClamd/g' /etc/clamav/freshclam.conf
# Update to latest virus definitions
freshclam

clamscan --version > ${OUTPUT_FILE}
clamscan -r --bell -i ${SCAN_DIR} $CLAMAV_ARGS >> ${OUTPUT_FILE}