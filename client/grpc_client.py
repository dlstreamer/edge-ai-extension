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

from google.protobuf.json_format import MessageToDict
from media_stream_processor import MediaStreamProcessor

from protocol_client import Client
from arguments import get_extension_config


class GrpcClient(Client):
    def __init__(self, args, width, height, frame_size):
        super().__init__()
        self._frame_queue = queue.Queue(args.frame_queue_size)

        extension_config = get_extension_config(args)

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
