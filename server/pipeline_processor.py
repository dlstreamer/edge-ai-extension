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

import json
import uuid
import copy
from queue import Queue

from vaserving.vaserving import VAServing
from vaserving.pipeline import Pipeline

from common.logging import get_logger
from common.grpc_autogen import inferencing_pb2
from common.grpc_autogen import extension_pb2
from common.exception_handler import log_exception
from common.util import validate_extension_config


class PipelineProcessor:
    def __init__(self, extension_config, input_queue_size=1):
        self._input_queue_size = input_queue_size
        self._logger = get_logger("PipelineProcessor")
        self._extension_config = copy.deepcopy(extension_config)
        pipeline_config = self._set_pipeline_properties(extension_config)
        pipeline_name = pipeline_config["name"]
        pipeline_version = pipeline_config["version"]
        pipeline_parameters = pipeline_config.get("parameters")
        self._extensions = pipeline_config.get("extensions")
        frame_destination = pipeline_config.get("frame-destination")

        self._logger.info("Pipeline Name : {}".format(pipeline_name))
        self._logger.info("Pipeline Version : {}".format(pipeline_version))
        self._logger.info(
            "Pipeline Parameters : {}".format(pipeline_parameters))
        self._logger.info("Frame Destination : {}".format(frame_destination))
        self._input_frame = Queue(maxsize=self._input_queue_size)
        self._output_frame = Queue()

        destination = {
            "metadata": {
                "type": "application",
                "class": "GStreamerAppDestination",
                "output": self._output_frame,
                "mode": "frames",
            }
        }

        if frame_destination:
            destination["frame"] = frame_destination

        try:
            self._pipeline = VAServing.pipeline(pipeline_name, pipeline_version)
            self._pipeline.start(
                source={
                    "type": "application",
                    "class": "GStreamerAppSource",
                    "input": self._input_frame,
                    "mode": "push",
                },
                destination=destination,
                parameters=pipeline_parameters,
            )
        except Exception as error:
            raise error
        self._frames_received = 0
        self._responses_sent = 0
        self._error = False

    def get_pipeline(self):
        return self._pipeline

    def compare_extension_config(self, extention_config):
        return self._extension_config == extention_config

    def stopped(self):
        return self._pipeline.status().state.stopped()

    def get_responses(self, timeout=40):
        output_messages = []
        samples = []
        samples.append(self._output_frame.get(timeout=timeout))
        while not self._output_frame.empty():
            samples.append(self._output_frame.get())

        for sample in samples:
            if sample is None:
                output_messages.append(None)
            else:
                output_messages.append(
                    self._generate_media_stream_message(sample))
        return output_messages

    def submit_frame(self, input_gva_frame):
        self._input_frame.put(input_gva_frame)
        if input_gva_frame:
            self._frames_received += 1

    def set_as_error(self):
        self._error = True

    def aborted_or_error(self):
        state = self._pipeline.status().state
        return state in (Pipeline.State.ERROR, Pipeline.State.ABORTED) or self._error

    def wait_for_completion(self, wait=10):
        # One final check on the pipeline to ensure it worked properly
        status = self._pipeline.wait(wait)
        self._logger.info("Pipeline Ended Status: {}".format(status))
        if (not status) or (status.state == Pipeline.State.ERROR):
            raise Exception("Pipeline did not complete successfully")

        self._logger.info(
            "Done processing messages: Received: {}, Sent: {}".format(
                self._frames_received, self._responses_sent
            )
        )

    def _generate_media_stream_message(self, gva_sample):
        self._responses_sent += 1
        if gva_sample is None:
            return None
        msg = extension_pb2.MediaStreamMessage()
        messages = list(gva_sample.video_frame.messages())
        if messages:
            message = json.loads(messages[0])
            if message.get("sequence_number", None):
                msg.ack_sequence_number = message["sequence_number"]
            if message.get("timestamp", None):
                msg.media_sample.timestamp = message["timestamp"]
        inferences = msg.media_sample.inferences
        events = self._get_events(gva_sample)
        # gvaactionrecognitionbin element has no video frame regions
        if not list(gva_sample.video_frame.regions()):
            for tensor in gva_sample.video_frame.tensors():
                if tensor.name() == "action":
                    try:
                        label = tensor.label()
                        confidence = tensor.confidence()
                        classification = inferencing_pb2.Classification(
                            tag=inferencing_pb2.Tag(
                                value=label, confidence=confidence
                            )
                        )
                    except:
                        log_exception(self._logger)
                        raise
                    inference = inferences.add()
                    inference.type = (
                        # pylint: disable=no-member
                        inferencing_pb2.Inference.InferenceType.CLASSIFICATION
                    )
                    inference.classification.CopyFrom(classification)

        for region_index, region in enumerate(gva_sample.video_frame.regions()):

            attributes = []
            obj_id = None
            obj_label = None
            obj_confidence = 0
            obj_left = 0
            obj_width = 0
            obj_top = 0
            obj_height = 0

            for tensor in region.tensors():
                if tensor.is_detection():
                    obj_confidence = region.confidence()
                    obj_label = region.label()

                    obj_left, obj_top, obj_width, obj_height = region.normalized_rect()
                    if region.object_id():  # Tracking
                        obj_id = str(region.object_id())
                elif tensor["label"]:  # Classification
                    attr_name = tensor.name()
                    attr_label = tensor["label"]
                    attr_confidence = region.confidence()
                    attributes.append([attr_name, attr_label, attr_confidence])

            if obj_label is not None:
                try:
                    entity = inferencing_pb2.Entity(
                        tag=inferencing_pb2.Tag(
                            value=obj_label, confidence=obj_confidence
                        ),
                        box=inferencing_pb2.Rectangle(
                            l=obj_left, t=obj_top, w=obj_width, h=obj_height
                        ),
                    )
                    for attr in attributes:
                        attribute = inferencing_pb2.Attribute(
                            name=attr[0], value=attr[1], confidence=attr[2]
                        )
                        entity.attributes.append(attribute)
                    if obj_id:
                        entity.id = obj_id
                except:
                    log_exception(self._logger)
                    raise
                inference = inferences.add()
                inference.type = (
                    # pylint: disable=no-member
                    inferencing_pb2.Inference.InferenceType.ENTITY
                )
                if self._extensions:
                    for key in self._extensions:
                        inference.extensions[key] = self._extensions[key]
                inference.entity.CopyFrom(entity)
                self._update_inference_ids(events, inference, region_index)
        self._process_events(events, inferences)
        return msg

    def _get_events(self, gva_sample):
        events = []
        for message in gva_sample.video_frame.messages():
            message_obj = json.loads(message)
            if "events" in message_obj.keys():
                events = message_obj["events"]
                break
        return events

    def _update_inference_ids(self, events, inference, region_index):
        for event in events:
            for i in range(len(event['related-objects'])):
                if region_index == event['related-objects'][i]:
                    if not inference.inference_id:
                        inference.inference_id = uuid.uuid4().hex
                        inference.subtype = "objectDetection"
                    event['related-objects'][i] = inference.inference_id

    def _process_events(self, events, inferences):
        for event in events:
            self._add_event(inferences, event)

    def _add_event(self, inferences, event):
        event_name = ""
        event_properties = {}
        inference_event = inferences.add()
        inference_event.type = (
            # pylint: disable=no-member
            inferencing_pb2.Inference.InferenceType.EVENT
        )
        inference_event.inference_id = uuid.uuid4().hex
        inference_event.subtype = event["event-type"]

        for inference_id in event['related-objects']:
            inference_event.related_inferences.append(inference_id)

        for key, value in event.items():
            if key in ('event-type', 'related-objects'):
                continue
            if "name" in key:
                event_name = value
            else:
                event_properties[key] = str(value)

        inference_event.event.CopyFrom(inferencing_pb2.Event(
            name=event_name,
            properties=event_properties,
        ))

    def _set_pipeline_properties(self, extension_configuration):
        # Set deployment pipeline name, version, and args if set

        pipeline_config = {
            "name": "",
            "version": "",
            "parameters": {},
            "frame-destination": {},
            "extensions": {}
        }

        # Validate the extension_config against the schema
        validate_extension_config(extension_configuration)

        # If extension_config has pipeline values, set the properties
        if "pipeline" in extension_configuration:
            pipeline_config.update(extension_configuration["pipeline"])

        return pipeline_config
