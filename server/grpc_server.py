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
from threading import Thread
from enum import Enum
from concurrent import futures
from queue import Empty
import grpc

from vaserving.gstreamer_app_source import GvaFrameData

from protocol_server import Server
from pipeline_processor import PipelineProcessor
from common.logging import get_logger
from common.grpc_autogen import media_pb2
from common.grpc_autogen import extension_pb2
from common.grpc_autogen import extension_pb2_grpc
from common.shared_memory import SharedMemoryManager
from common.exception_handler import log_exception


class TransferType(Enum):
    BYTES = 1  # Embedded Content
    REFERENCE = 2  # Shared Memory
    HANDLE = 3  # Reserved


class State:
    def __init__(self, media_stream_descriptor):
        try:
            # media descriptor holding input data format
            self.media_stream_descriptor = media_stream_descriptor

            # Get how data will be transferred
            if (
                    self.media_stream_descriptor.WhichOneof(
                        "data_transfer_properties")
                    is None
            ):
                self.content_transfer_type = TransferType.BYTES
            elif self.media_stream_descriptor.HasField(
                    "shared_memory_buffer_transfer_properties"
            ):
                self.content_transfer_type = TransferType.REFERENCE
            elif self.media_stream_descriptor.HasField(
                    "shared_memory_segments_transfer_properties"
            ):
                self.content_transfer_type = TransferType.HANDLE

            # Setup if shared mem used
            if self.content_transfer_type == TransferType.REFERENCE:
                # Create shared memory accessor specific to the client
                self.shared_memory_manager = SharedMemoryManager(
                    name=self.media_stream_descriptor.shared_memory_buffer_transfer_properties.handle_name,
                    size=self.media_stream_descriptor.shared_memory_buffer_transfer_properties.length_bytes,
                )
            else:
                self.shared_memory_manager = None

        except:
            log_exception(get_logger("State"))
            raise


class GrpcServer(extension_pb2_grpc.MediaGraphExtensionServicer, Server):
    def __init__(self, args):
        self._server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=args.max_running_pipelines) # pylint: disable=consider-using-with
            )
        extension_pb2_grpc.add_MediaGraphExtensionServicer_to_server(
            self,
            self._server,
        )
        self._logger = get_logger("gRPC Server")
        self._port = args.grpc_port
        self._stopped = True

    def start(self):
        self._stopped = False
        self._logger.info(
            "Starting GRPC DL Streamer Edge AI Extension on port: %d", self._port)
        self._server.add_insecure_port(f"[::]:{self._port}")
        self._server.start()
        self._server.wait_for_termination()

    def stop(self):
        self._server.stop(None)
        self._stopped = True

    def _generate_gva_sample(self, client_state, request):

        new_sample = None

        try:
            # Get reference to raw bytes
            if client_state.content_transfer_type == TransferType.BYTES:
                raw_bytes = memoryview(
                    request.media_sample.content_bytes.bytes)
            elif client_state.content_transfer_type == TransferType.REFERENCE:
                # Data sent over shared memory buffer
                address_offset = request.media_sample.content_reference.address_offset
                length_bytes = request.media_sample.content_reference.length_bytes

                # Get memory reference to (in readonly mode) data sent over shared memory
                raw_bytes = client_state.shared_memory_manager.read_bytes(
                    address_offset, length_bytes
                )

            # Get encoding details of the media sent by client
            encoding = (
                client_state.media_stream_descriptor.media_descriptor.video_frame_sample_format.encoding
            )

            # Handle RAW content (Just place holder for the user to handle each variation...)
            if (
                    encoding
                    == client_state.media_stream_descriptor.media_descriptor.video_frame_sample_format.Encoding.RAW
            ):
                pixel_format = (
                    client_state.media_stream_descriptor.media_descriptor.video_frame_sample_format.pixel_format
                )
                caps_format = None

                caps_formats = {
                    media_pb2.VideoFrameSampleFormat.PixelFormat.RGBA: "RGBA",
                    media_pb2.VideoFrameSampleFormat.PixelFormat.RGB24: "RGB",
                    media_pb2.VideoFrameSampleFormat.PixelFormat.BGR24: "BGR"
                }
                if pixel_format in caps_formats:
                    caps_format = caps_formats.get(pixel_format, None)

                if caps_format is not None:
                    caps = "".join(
                        (
                            "video/x-raw,format=",
                            caps_format,
                            ",width=",
                            str(
                                client_state.media_stream_descriptor.
                                media_descriptor.video_frame_sample_format.dimensions.width
                            ),
                            ",height=",
                            str(
                                client_state.media_stream_descriptor.
                                media_descriptor.video_frame_sample_format.dimensions.height
                            ),
                        )
                    )
                    new_sample = GvaFrameData(
                        bytes(raw_bytes),
                        caps,
                        message={
                            "sequence_number": request.sequence_number,
                            "timestamp": request.media_sample.timestamp,
                        },
                    )
            else:
                self._logger.info("Sample format is not RAW")
        except:
            log_exception(self._logger)
            raise
        return new_sample

    # gRPC stubbed function
    # client/gRPC will call this function to send frames/descriptions

    def ProcessMediaStream(self, request_iterator, context):
        # First message from the client is (must be) MediaStreamDescriptor
        request = next(request_iterator)
        # Extract message IDs
        request_seq_num = request.sequence_number
        request_ack_seq_num = request.ack_sequence_number
        # State object per client
        client_state = State(request.media_stream_descriptor)
        self._logger.info(
            "[Received] SeqNum: {0:07d} | "
            "AckNum: {1}\nMediaStreamDescriptor:\n{2}".format(
                request_seq_num,
                request_ack_seq_num,
                client_state.media_stream_descriptor,
            )
        )
        # First message response ...
        media_stream_message = extension_pb2.MediaStreamMessage(
            sequence_number=1,
            ack_sequence_number=request_seq_num,
            media_stream_descriptor=extension_pb2.MediaStreamDescriptor(
                media_descriptor=media_pb2.MediaDescriptor(
                    timescale=client_state.media_stream_descriptor.media_descriptor.timescale
                )
            ),
        )

        yield media_stream_message

        extension_configuration = None
        if request.media_stream_descriptor.extension_configuration:
            # Load the extension_config
            try:
                extension_configuration = json.loads(
                    request.media_stream_descriptor.extension_configuration)
            except ValueError:
                self._logger.error("Decoding extension_configuration field has failed: {}".format(
                    request.media_stream_descriptor.extension_configuration))
                raise

        try:
            pipeline_processor = PipelineProcessor(extension_configuration)
        except:
            log_exception(self._logger)
            raise

        incoming_request_thread = Thread(target=self._process_input_request, args=(
            request_iterator, pipeline_processor, client_state, context))

        incoming_request_thread.start()
        last_frame = False
        while not self._stopped and not pipeline_processor.aborted_or_error() and not last_frame:
            responses = []
            try:
                responses = pipeline_processor.get_responses()
            except Empty:
                self._logger.debug("Timeout occured on getting responses")
                if pipeline_processor.stopped():
                    break
            for media_stream_message in responses:
                if media_stream_message:
                    self._logger.debug("[Sent] AckSeqNum: {0:07d}".format(
                        media_stream_message.ack_sequence_number)
                    )
                    if context.is_active():
                        yield media_stream_message
                else:
                    last_frame = True
                    break

        if pipeline_processor.aborted_or_error():
            try:
                raise Exception("Pipeline encountered an issue, pipeline state: {}".format(
                    pipeline_processor.get_pipeline().status().state))
            except:
                log_exception(self._logger)
                raise
        pipeline_processor.wait_for_completion()
        incoming_request_thread.join()

        self._logger.debug("MediaStreamDescriptor:\n{0}".format(
            client_state.media_stream_descriptor))

    def _process_input_request(self, request_iterator, pipeline_processor, client_state, context):
        for request in request_iterator:
            # Read request id, sent by client
            request_seq_num = request.sequence_number
            self._logger.debug(
                "[Received] SeqNum: {0:07d}".format(request_seq_num))
            input_sample = self._generate_gva_sample(client_state, request)
            pipeline_processor.submit_frame(input_sample)
            if self._stopped or not context.is_active() or pipeline_processor.stopped():
                break

        if not pipeline_processor.stopped():
            # After the server has finished processing all the request iterator objects
            # Push a None object into the input queue.
            # When the None object comes out of the output queue, we know we've finished
            # processing all requests
            pipeline_processor.submit_frame(None)
        else:
            pipeline_processor.set_as_error()
