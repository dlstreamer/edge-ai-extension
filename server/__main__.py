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

import argparse
import os
import sys
from vaserving.vaserving import VAServing
from grpc_server import GrpcServer
from http_server import HttpServer
from common import logging, constants
from common.exception_handler import log_exception



PROGRAM_NAME = "DL Streamer Edge AI Extension"


def parse_args(args=None, program_name=PROGRAM_NAME):

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
        "--grpc-port",
        action="store",
        help="Port number to serve gRPC server",
        type=int,
        default=int(os.getenv("GRPC_PORT", constants.GRPC_PORT)),
    )

    parser.add_argument(
        "--http-port",
        action="store",
        help="Port number to serve HTTP server",
        type=int,
        default=int(os.getenv("HTTP_PORT", constants.HTTP_PORT)),
    )

    parser.add_argument(
        "--max-running-pipelines",
        action="store",
        type=int,
        default=int(os.getenv("MAX_RUNNING_PIPELINES", "10")),
    )
    parser.add_argument(
        "--log-level",
        action="store",
        choices=['INFO', 'DEBUG'],
        default=os.getenv('EXTENSION_LOG_LEVEL', 'INFO'))

    if isinstance(args, dict):
        args = ["--{}={}".format(key, value)
                for key, value in args.items() if value]

    return parser.parse_known_args(args)


def append_default_server_args(va_serving_args, max_running_pipelines):
    va_serving_args.append("--max_running_pipelines")
    va_serving_args.append(str(max_running_pipelines))
    return va_serving_args


if __name__ == "__main__":

    args, va_serving_args = parse_args()
    logging.set_default_log_level(args.log_level)
    logger = logging.get_logger("Main")
    server = None
    try:
        server_args = append_default_server_args(
            va_serving_args, args.max_running_pipelines
        )
        try:
            VAServing.start(server_args)
        except Exception as error:
            logger.error(error)
            logger.error("Exception encountered during VAServing start")
            raise

        if args.protocol == constants.GRPC_PROTOCOL:
            server = GrpcServer(args)
        else:
            server = HttpServer(args)

        server.start()
    except (KeyboardInterrupt, SystemExit, Exception):
        log_exception()
        sys.exit(-1)
    finally:
        if server:
            server.stop()
        VAServing.stop()
