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

import json
import logging
import requests
import cv2
from protocol_client import Client
from arguments import get_extension_config
from common import constants
from common.util import get_pipeline_config_value


class HttpClient(Client):
    def __init__(self, args):
        super().__init__()
        self._params = {}

        if args.http_url:
            self._url = args.http_url
        else:
            self._build_url(args)

        self._encoding = '.{}'.format(args.encoding)
        content_type = "image/{}".format(args.encoding)
        self._headers = {
            "Content-Type": content_type,
            "Accept": "application/json"
        }

        self._index = 1

    def _build_url(self, args):
        stream_id = args.stream_id
        extension_config = get_extension_config(args)
        pipeline_name = get_pipeline_config_value(
            extension_config, constants.NAME)
        pipeline_version = get_pipeline_config_value(
            extension_config, constants.VERSION)
        parameters = get_pipeline_config_value(
            extension_config, constants.PARAMETERS)
        frame_destination = get_pipeline_config_value(
            extension_config, constants.FRAME_DESTINATION)
        extensions = get_pipeline_config_value(
            extension_config, constants.EXTENSIONS)
        if parameters:
            self._params = parameters
        if frame_destination:
            for key in frame_destination:
                new_key = "{}-{}".format(constants.FRAME_DESTINATION, key)
                self._params[new_key] = frame_destination[key]
        if extensions:
            for key in extensions:
                new_key = "{}-{}".format(constants.EXTENSIONS, key)
                self._params[new_key] = extensions[key]

        if self._params:
            if not stream_id:
                raise Exception(
                    "--stream-id must be specified when parameters are set")
            self._params["stream-id"] = stream_id

        self._url = "http://{}:{}/{}/{}".format(
            args.server_ip, args.http_port, pipeline_name, pipeline_version)

    def put_frame(self, image):
        data = None
        result_json = None
        encoded_image_size = 0
        if image is not None:
            _, encoded_image = cv2.imencode(self._encoding, image)
            encoded_image_size = encoded_image.size
            data = encoded_image.tostring()
        self._headers["Content-Length"] = str(encoded_image_size)
        response = requests.post(
            self._url, data=data, headers=self._headers, params=self._params)

        result_json = {"ackSequenceNumber": self._index}
        self._index += 1

        if response.status_code == 200:
            result_json["mediaSample"] = json.loads(response.text)
        elif response.status_code != 204:
            result_json = None
            error_text = " Response code: {}, Message: {}".format(response.status_code, response.text)
            logging.error(error_text)
            if data:
                raise Exception(error_text)

        self._result_queue.put(result_json)

    def get_result(self):
        result = self._result_queue.get()
        return result

    def stop(self):
        pass
