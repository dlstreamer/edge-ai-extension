#!/bin/bash -e
CURRENT_DIR=$(dirname $(readlink -f "$0"))
ROOT_DIR=$(dirname $CURRENT_DIR)
EXTENSION_IMAGE_TAG="dlstreamer-edge-ai-extension:0.7.0"
TEST_IMAGE_TAG="dlstreamer-edge-ai-extension-tests"
SAMPLE_BUILD_ARGS=$(env | cut -f1 -d= | grep -E '_(proxy|REPO|VER)$' | sed 's/^/--build-arg / ' | tr '\n' ' ')

function launch { $@
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo "ERROR: error with $1" >&2
        exit $exit_code
    fi
    return $exit_code
}

#Get options passed into script
function get_options {
  while :; do
    case $1 in
      -h | -\? | --help)
        show_help
        exit
        ;;
      --ava-image)
        if [ "$2" ]; then
          AVA_IMAGE=$2
          SAMPLE_BUILD_ARGS+=" --build-arg BASE=$AVA_IMAGE"
          shift
        else
          error 'ERROR: "--ava-image" requires an argument.'
        fi
        ;;
      --docker-cache)
        if [ "$2" ]; then
          CACHE_PREFIX=$2
          shift
        else
          error 'ERROR: "--docker-cache" requires an argument.'
        fi
        ;;
      # For backwards compatbility with scripts that took cache prefix as $1
      *cache*)
        CACHE_PREFIX=$1
        ;;
      *)
        break
        ;;
    esac
    shift
  done
}

function show_help {
  echo "usage: ./build.sh"
  echo "  [ --ava-image : AVA extension image to base test image on ] "
  echo "  [ --docker-cache : Docker cache prefix ] "
}

get_options "$@"

# Build AVA image if not specified
if [ -z "$AVA_IMAGE" ]; then
    echo Building $EXTENSION_IMAGE_TAG
    launch "$ROOT_DIR/docker/build.sh"
fi

# Add tests layer
echo "docker build -f $CURRENT_DIR/Dockerfile $SAMPLE_BUILD_ARGS -t $TEST_IMAGE_TAG $CURRENT_DIR"
launch "docker build -f $CURRENT_DIR/Dockerfile $SAMPLE_BUILD_ARGS -t $TEST_IMAGE_TAG $CURRENT_DIR"
