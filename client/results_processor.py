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
import json
from types import SimpleNamespace


class ResultsProcessor:
    def __init__(self):
        self._results_received = 0

    def process(self, result, output):
        self._results_received += 1
        if isinstance(result, Exception):
            raise result
        self._log_result(result, output)

    def results_received(self):
        return self._results_received

    def _get_inference_details(self, inference):
        attributes = []
        if inference.get("inferenceId", None):
            attribute_string = "{}: {}".format(
                'inferenceId', inference["inferenceId"])
            attributes.append(attribute_string)
        if inference.get("subtype", None):
            attribute_string = "{}: {}".format('subtype', inference["subtype"])
            attributes.append(attribute_string)
        if inference.get("related_inferences", None):
            attribute_string = "{}: {}".format(
                'relatedInferences', inference["related_inferences"])
            attributes.append(attribute_string)
        return attributes

    def _log_entity(self, inference):
        entity = inference["entity"]
        tag = SimpleNamespace(**entity["tag"])
        box = SimpleNamespace(**entity["box"])
        attributes = self._get_inference_details(inference)

        if entity.get("id", None):
            attribute_string = "{}: {}".format('id', entity["id"])
            attributes.append(attribute_string)
        if entity.get("attributes", None):
            for attribute in entity["attributes"]:
                attribute_string = "{}: {}".format(attribute["name"], attribute["value"])
                attributes.append(attribute_string)
        logging.info(
            "ENTITY - {} ({:.2f}) [{:.2f}, {:.2f}, {:.2f}, {:.2f}] {}".format(
                tag.value, tag.confidence, box.l, box.t, box.w, box.h, attributes
            )
        )

    def _log_event(self, inference):
        event = inference["event"]
        attributes = self._get_inference_details(inference)

        for attribute in event["properties"]:
            attribute_string = "{}: {}".format(attribute, event["properties"][attribute])
            attributes.append(attribute_string)
        logging.info(
            "EVENT - {}: {}".format(event["name"], attributes)
        )

    def _log_classification(self, inference):
        tag = SimpleNamespace(**inference["classification"]["tag"])
        logging.info(
            "CLASSIFICATION - {} ({:.2f})".format(tag.value, tag.confidence))

    def _log_result(self, result_json, output, log_result=True):
        if not log_result:
            return
        if not result_json:
            return
        logging.debug("Inference result {}".format(result_json["ackSequenceNumber"]))
        inferences = []
        media_sample = result_json.get("mediaSample", None)
        if media_sample:
            inferences = media_sample.get("inferences", None)
        for inference in inferences:
            if inference["type"].upper() == "ENTITY":
                self._log_entity(inference)
            elif inference["type"].upper() == "EVENT":
                self._log_event(inference)
            elif inference["type"].upper() == "CLASSIFICATION":
                self._log_classification(inference)
            else:
                logging.error(
                    "Bad inference type {}".format(inference["type"]))

        if media_sample:
            json_str = json.dumps(media_sample, default=str)
            output.write("{}\n".format(json_str))
