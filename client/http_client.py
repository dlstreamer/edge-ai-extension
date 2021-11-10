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
import requests
import cv2
from client import Client

class HttpClient(Client):
    def __init__(self, args, frame_size):
        super().__init__()
        if args.http_url:
            self._url = args.http_url
        else:
            self._url = "http://{}:{}/{}/{}".format(
                args.server_ip, args.server_port, args.pipeline_name, args.pipeline_version)

        self._encoding = '.{}'.format(args.encoding)
        content_type = "image/{}".format(args.encoding)
        self._headers = {
            "Content-Type": content_type,
            "Accept": "application/json",
            "Content-Length": str(frame_size)
        }
        self._index = 1

    def put_frame(self, image):
        data = None
        result_json = None
        if image is not None:
            _, encoded_image = cv2.imencode(self._encoding, image)
            data = encoded_image.tostring()
        else:
            self._headers = None

        response = requests.post(
            self._url, data=data, headers=self._headers)

        result_json = {"ackSequenceNumber": self._index}
        self._index += 1

        if response.status_code == 200:
            result_json["mediaSample"] = json.loads(response.text)
        elif response.status_code == 400:
            result_json = None
        elif response.status_code != 204:
            raise Exception("Server error {}".format(
                response.status_code))

        self._result_queue.put(result_json)

    def get_result(self):
        result = self._result_queue.get()
        return result

    def stop(self):
        pass
