'''
* Copyright (C) 2019-2020 Intel Corporation.
*
* SPDX-License-Identifier: MIT License
*
*****
*
* MIT License
*
* Copyright (c) Microsoft Corporation.
*
* Permission is hereby granted, free of charge, to any person obtaining a copy
* of this software and associated documentation files (the "Software"), to deal
* in the Software without restriction, including without limitation the rights
* to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
* copies of the Software, and to permit persons to whom the Software is
* furnished to do so, subject to the following conditions:
*
* The above copyright notice and this permission notice shall be included in all
* copies or substantial portions of the Software.
*
* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
* IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
* FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
* AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
* LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
* OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
* SOFTWARE
'''

import os
import sys
import json
import argparse
from common.util import validate_extension_config
from common import constants

def parse_args(args=None, program_name="DL Streamer Edge AI Extension Client"):
    parser = argparse.ArgumentParser(
        prog=program_name,
        fromfile_prefix_chars="@",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--protocol",
        type=str.lower,
        choices=[constants.GRPC_PROTOCOL, constants.HTTP_PROTOCOL],
        help="Extension protocol (grpc or http)",
        default=os.getenv("PROTOCOL", "grpc").lower(),
    )

    parser.add_argument(
        "-s",
        metavar=("grpc_server_address"),
        dest="grpc_server_address",
        help="gRPC server address.",
        default=None,
    )
    parser.add_argument(
        "--server-ip",
        help="server ip.",
        default="localhost",
        type=str,
    )

    parser.add_argument(
        "--http-url",
        help="http Full URL.",
        type=str,
    )

    parser.add_argument(
        "--http-stream-id",
        help="stream id to assign pipeline to",
        dest="stream_id",
        type=str,
    )

    parser.add_argument(
        "--http-image-encoding",
        dest="encoding",
        help=" HTTP image encoding",
        default="jpeg",
        type=str,
        choices=["jpeg", "png", "bmp"],
    )

    parser.add_argument(
        "--grpc-port",
        help="grpc server port.",
        type=int,
        default=int(os.getenv("GRPC_PORT", constants.GRPC_PORT)),
    )

    parser.add_argument(
        "--http-port",
        help="http server port.",
        type=int,
        default=int(os.getenv("HTTP_PORT", constants.HTTP_PORT)),
    )

    parser.add_argument(
        "-f",
        "--sample-file-path",
        metavar=("sample_file"),
        dest="sample_file",
        help="Name of the sample video frame.",
        default="/home/edge-ai-extension/sampleframes/sample01.png",
    )
    parser.add_argument(
        "--max-frames",
        metavar=("max_frames"),
        help="How many frames to send from video.",
        type=int,
        default=sys.maxsize,
    )
    parser.add_argument(
        "-l",
        "--loop-count",
        metavar=("loop_count"),
        help="How many times to loop the source after it finishes.",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--fps-interval",
        help="How often to report FPS (every N seconds)",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--frame-rate",
        help="How many frames to send per second (-1 is no limit)",
        type=int,
        default=-1,
    )
    parser.add_argument(
        "--frame-queue-size",
        help="Max number of frames to buffer in client (0 is no limit)",
        type=int,
        default=200,
    )
    parser.add_argument(
        "-m",
        "--shared-memory",
        action="store_const",
        dest="use_shared_memory",
        const=True,
        default=False,
        help="set to use shared memory",
    )
    # nosec skips pybandit hits
    parser.add_argument(
        "-o",
        "--output-file-path",
        metavar=("output_file"),
        dest="output_file",
        help="Output file path",
        default="/tmp/results.jsonl",
    )  # nosec

    parser.add_argument(
        "--pipeline-name",
        action="store",
        help="name of the pipeline to run",
        type=str,
        default="object_detection",
    )

    parser.add_argument(
        "--pipeline-version",
        action="store",
        help="version of the pipeline to run",
        type=str,
        default="person_vehicle_bike_detection",
    )

    parser.add_argument(
        "--pipeline-parameters",
        action="store",
        type=str,
        default="",
    )

    parser.add_argument(
        "--pipeline-extensions",
        action="store",
        type=str,
        default="",
    )

    parser.add_argument(
        "--frame-destination",
        action="store",
        type=str,
        default="",
    )

    parser.add_argument(
        "--scale-factor",
        action="store",
        help="scale factor for decoded images",
        type=float,
        default=1.0,
    )

    parser.add_argument(
        "--extension-config",
        action="store",
        help="extension config in .json file path or as string",
        default="",
    )  # nosec

    parser.add_argument("--version", action="version", version="%(prog)s 1.0")
    if isinstance(args, dict):
        args = ["--{}={}".format(key, value) for key, value in args.items() if value]
    result = parser.parse_args(args)
    if not result.grpc_server_address:
        result.grpc_server_address = "{}:{}".format(
            result.server_ip, result.grpc_port
        )
    return result


def _create_extension_config(args):
    extension_config = {}
    pipeline_config = {}
    if args.pipeline_name:
        pipeline_config["name"] = args.pipeline_name
    if args.pipeline_version:
        pipeline_config["version"] = args.pipeline_version
    if args.pipeline_parameters:
        try:
            pipeline_config["parameters"] = json.loads(
                args.pipeline_parameters)
        except ValueError as err:
            raise Exception("Issue loading pipeline parameters: {}".format(
                args.pipeline_parameters)) from err
    if args.frame_destination:
        try:
            pipeline_config["frame-destination"] = json.loads(
                args.frame_destination)
        except ValueError as err:
            raise Exception("Issue loading frame destination: {}".format(
                args.frame_destination)) from err
    if args.pipeline_extensions:
        try:
            pipeline_config["extensions"] = json.loads(
                args.pipeline_extensions)
        except ValueError as err:
            raise Exception("Issue loading pipeline extensions: {}".format(
                args.pipeline_extensions)) from err

    if len(pipeline_config) > 0:
        extension_config.setdefault("pipeline", pipeline_config)

    return extension_config


def get_extension_config(args):
    extension_config = {}
    if args.extension_config:
        if args.extension_config.endswith(".json"):
            with open(args.extension_config, "r") as config:
                extension_config = json.loads(config.read())
        else:
            extension_config = json.loads(args.extension_config)
    else:
        extension_config = _create_extension_config(args)

    validate_extension_config(extension_config)

    return extension_config
