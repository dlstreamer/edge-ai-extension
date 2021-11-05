#!/bin/bash
IMAGE=video-analytics-serving-ava-tests
CURRENT_DIR=$(dirname $(readlink -f "$0"))
ROOT_DIR=$(dirname $CURRENT_DIR)
TESTS_DIR="$ROOT_DIR/tests"
docker stop $IMAGE
LOCAL_RESULTS_DIR="$CURRENT_DIR/results"
DOCKER_TEST_DIR="/home/edge-ai-extension/tests"
DOCKER_RESULTS_DIR="$DOCKER_TEST_DIR/results"
mkdir -p "$LOCAL_RESULTS_DIR"
PREPARE_GROUND_TRUTH=false
ENTRYPOINT_ARGS=
SELECTED="--pytest"
ENTRYPOINT=
ENVIRONMENT=

function show_help {
  echo "usage: run.sh (options are exclusive)"
  echo "  [ --pytest : Run tests ]"
  echo "  [ --pytest-generate : Generate new ground truth ]"
  echo "  [ --pylint : Run pylint scan ] "
  echo "  [ --pybandit: Run pybandit scan ] "
}

function recreate_shared_path() {
  SHARED_PATH=$1
  echo "recreating $SHARED_PATH"
  rm -Rf "$SHARED_PATH"
  mkdir -p "$SHARED_PATH"
}

ARGS=$@
while [[ "$#" -gt 0 ]]; do
  case $1 in
    -h | -\? | --help)
      show_help
      exit
      ;;
    --pytest)
      ;;
    --pylint)
      ENTRYPOINT="--entrypoint ./tests/entrypoint/pylint.sh"
      SELECTED="$1"
      ENVIRONMENT+=" -e PYLINTHOME=$DOCKER_RESULTS_DIR/pylint "
      ;;
    --pybandit)
      ENTRYPOINT="--entrypoint ./tests/entrypoint/pybandit.sh"
      SELECTED="$1"
      ;;
    --pytest-generate)
      ENTRYPOINT_ARGS+="--entrypoint-args --generate "
      VOLUME_MOUNT+="-v $TESTS_DIR/test_cases:$DOCKER_TESTS_DIR/test_cases "
      PREPARE_GROUND_TRUTH=true
      ;;
    *)
      break
      ;;
  esac
  shift
done

echo "running $SELECTED"

SELECTED="${SELECTED//-/}"

LOCAL_RESULTS_DIR="$LOCAL_RESULTS_DIR/$SELECTED"
DOCKER_RESULTS_DIR="$DOCKER_RESULTS_DIR/$SELECTED"
recreate_shared_path "$LOCAL_RESULTS_DIR"
VOLUME_MOUNT="-v $LOCAL_RESULTS_DIR:$DOCKER_RESULTS_DIR "

"$ROOT_DIR/docker/run_server.sh" --image $IMAGE -v /dev/shm:/dev/shm \
  $VOLUME_MOUNT -p 5001:5001 \
  $ENTRYPOINT \
  $ENVIRONMENT \
  $ENTRYPOINT_ARGS "$@"

if [ $PREPARE_GROUND_TRUTH == true ]; then
  echo "Renaming .json.generated files to .json in preparation to update ground truth."
  find $TESTS_DIR/test_cases -depth -name "*.json.generated" -exec sh -c 'mv "$1" "${1%.json.generated}.json"' _ {} \;
fi