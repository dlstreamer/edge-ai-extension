"""
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
"""
import logging
import queue
import json
import jsonschema

from google.protobuf.json_format import MessageToDict
from media_stream_processor import MediaStreamProcessor
from common import extension_schema
from client import Client


def validate_extension_config(extension_config):
    try:
        validator = jsonschema.Draft4Validator(schema=extension_schema.extension_config,
                                                format_checker=jsonschema.draft4_format_checker)
        validator.validate(extension_config)
    except jsonschema.exceptions.ValidationError as err:
        raise Exception("Error validating pipeline request: {},: error: {}".format(
            extension_config, err.message)) from err

def create_extension_config(args):
    extension_config = {}
    pipeline_config = {}
    if args.pipeline_name:
        pipeline_config["name"] = args.pipeline_name
    if args.pipeline_version:
        pipeline_config["version"] = args.pipeline_version
    if args.pipeline_parameters:
        try:
            pipeline_config["parameters"] = json.loads(args.pipeline_parameters)
        except ValueError as err:
            raise Exception("Issue loading pipeline parameters: {}".format(args.pipeline_parameters)) from err
    if args.frame_destination:
        try:
            pipeline_config["frame-destination"] = json.loads(args.frame_destination)
        except ValueError as err:
            raise Exception("Issue loading frame destination: {}".format(args.frame_destination)) from err
    if args.pipeline_extensions:
        try:
            pipeline_config["pipeline_extensions"] = json.loads(args.pipeline_extensions)
        except ValueError as err:
            raise Exception("Issue loading pipeline extensions: {}".format(args.pipeline_extensions)) from err

    if len(pipeline_config) > 0:
        extension_config.setdefault("pipeline", pipeline_config)

    return extension_config

class GrpcClient(Client):
    def __init__(self, args, width, height, frame_size):
        super().__init__()
        self._frame_queue = queue.Queue(args.frame_queue_size)

        extension_config = {}
        if args.extension_config:
            if args.extension_config.endswith(".json"):
                with open(args.extension_config, "r") as config:
                    extension_config = json.loads(config.read())
            else:
                extension_config = json.loads(args.extension_config)
        else:
            extension_config = create_extension_config(args)

        validate_extension_config(extension_config)
        logging.info("Extension Configuration: {}".format(extension_config))

        self._msp = MediaStreamProcessor(
            args.grpc_server_address,
            args.use_shared_memory,
            args.frame_queue_size,
            frame_size,
        )

        self._msp.start(width, height, self._frame_queue,
                       self._result_queue, json.dumps(extension_config))

    def put_frame(self, image):
        if image is None:
            frame = None
        else:
            frame = image.tobytes()
        self._frame_queue.put(frame)

    def get_result(self):
        result = self._result_queue.get()
        if result:
            return MessageToDict(result, including_default_value_fields=True)
        return None

    def stop(self):
        self._msp.stop()
