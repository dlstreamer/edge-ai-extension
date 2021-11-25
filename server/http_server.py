'''
* Copyright (C) 2019 Intel Corporation.
*
* SPDX-License-Identifier: BSD-3-Clause
'''

from wsgiref.simple_server import WSGIRequestHandler, make_server
import falcon
from google.protobuf.json_format import MessageToDict
from vaserving.gstreamer_app_source import GvaFrameData
from protocol_server import Server
from pipeline_processor import PipelineProcessor
from common import constants, util
from common.logging import get_logger


class LoggingWSGIRequestHandler(WSGIRequestHandler):

    def log_message(self, format, *args):  # pylint: disable=redefined-builtin
        logger = get_logger("HTTP Server")
        logger.debug("{} - - [{}] {}\n".format(
            self.address_string(),
            self.log_date_time_string(),
            format % args))


_HTTP_500 = falcon.HTTP_500  # pylint: disable=no-member
_HTTP_200 = falcon.HTTP_200  # pylint: disable=no-member
_HTTP_204 = falcon.HTTP_204  # pylint: disable=no-member
_HTTP_400 = falcon.HTTP_400  # pylint: disable=no-member


class HttpServer(Server):

    def __init__(self, args):
        self._port = args.http_port
        self._app = falcon.App()
        self._app.add_route(
            '/{pipeline_name}/{pipeline_version}', self, suffix='name_version')
        self._logger = get_logger("HTTP Server")
        self._pipelines = {}

    def start(self):
        self._logger.info(
            "Starting HTTP DL Streamer Edge AI Extension on port: %d", self._port)
        with make_server('', self._port, self._app, handler_class=LoggingWSGIRequestHandler) as server:
            server.serve_forever()

    def stop(self):
        pass

    def _stop_pipeline(self, stream_id):
        if stream_id in self._pipelines:
            pipeline_processor = self._pipelines[stream_id]
            if not pipeline_processor.stopped():
                pipeline_processor.stop()
            del self._pipelines[stream_id]

    def _start_pipeline(self, stream_id, extension_config):
        self._logger.info(
            "Starting  pipeline with stream identifier: {}".format(stream_id))
        self._pipelines[stream_id] = PipelineProcessor(extension_config)

    def _get_params(self, req_params):
        params = {}
        for key in req_params:
            if key != constants.STREAM_ID \
                    and not key.startswith(constants.FRAME_DESTINATION) \
                    and not key.startswith(constants.EXTENSIONS):
                params[key] = util.get_typed_value(req_params[key])

        return params

    def _get_config(self, req_params, prefix):
        params = {}
        prefix = "{}-".format(prefix)
        for key in req_params:
            if key.startswith(prefix):
                params[key[len(prefix):]] = req_params[key]

        return params

    def _create_extension_config(self, name, version, params):
        extension_config = {}
        pipeline_config = {
            constants.NAME: name,
            constants.VERSION: version
        }
        parameters = self._get_params(params)
        if parameters:
            pipeline_config[constants.PARAMETERS] = parameters

        frame_destination = self._get_config(
            params, constants.FRAME_DESTINATION)
        if frame_destination:
            pipeline_config[constants.FRAME_DESTINATION] = frame_destination

        extensions = self._get_config(params, constants.EXTENSIONS)
        if extensions:
            pipeline_config[constants.EXTENSIONS] = extensions

        extension_config.setdefault(constants.PIPELINE, pipeline_config)
        return extension_config

    def _compare_params(self, extension_config, stream_id):
        return self._pipelines[stream_id].compare_extension_config(extension_config)

    def _set_response(self, resp, status, content=None, error=False):
        resp.status = status
        if content:
            if error:
                content = {"Error": content}
                self._logger.error(content)
            resp.media = content

    def _verify_content_type(self, content_type):
        if not content_type or content_type not in constants.HTTP_SUPPORTED_CONTENT_TYPES:
            return False
        return True

    def on_post_name_version(self, req, resp, pipeline_name, pipeline_version):

        if not self._verify_content_type(req.content_type):
            response_message = " Only {} content-types supported ".format(
                constants.HTTP_SUPPORTED_CONTENT_TYPES)
            self._set_response(resp, _HTTP_400, response_message, error=True)
            return

        stream_id = req.params.get("stream-id", None)
        if req.params and stream_id is None:
            response_message = "Missing stream-id query params: When parameters set stream-id must be set"
            self._set_response(resp, _HTTP_400, response_message, error=True)
            return

        extension_config = self._create_extension_config(
            pipeline_name, pipeline_version, req.params)
        if stream_id is None:
            stream_id = "{}_{}".format(pipeline_name, pipeline_version)

        if stream_id not in self._pipelines:
            try:
                self._start_pipeline(stream_id, extension_config)
            except Exception as error:
                self._set_response(resp, _HTTP_400, str(error), error=True)
                return
        else:
            if not self._compare_params(extension_config, stream_id):
                response_message = "Pipeline with stream id {} and different params already running".format(
                    stream_id)
                self._set_response(
                    resp, _HTTP_400, response_message, error=True)
                return

        try:
            self._process_data(req.bounded_stream.read(),
                               stream_id, req.content_type, resp)
        except Exception as error:
            self._stop_pipeline(stream_id)
            response_message = "Pipeline Error: {} Pipeline with stream-id {} stopped".format(
                str(error), stream_id)
            self._set_response(resp, _HTTP_500, response_message, error=True)

    def _process_data(self, data, stream_id, content_type, resp):
        frame = None
        if data:
            frame = GvaFrameData(data, content_type)
        pipeline_processor = self._pipelines[stream_id]
        pipeline_processor.submit_frame(frame)
        if pipeline_processor.stopped():
            raise Exception("Pipeline not running")
        output = pipeline_processor.get_responses()[0]
        if output:
            if output.media_sample.inferences:
                response_message = MessageToDict(
                    output.media_sample, including_default_value_fields=True)
                self._set_response(resp, _HTTP_200, response_message)
            else:
                self._set_response(resp, _HTTP_204)
        else:
            response_message = "Received empty frame, stopping pipeline {}".format(
                stream_id)
            self._set_response(resp, _HTTP_400, response_message, error=True)
            if not pipeline_processor.stopped():
                self._logger.error("Failed to gracefully stop pipeline")
            self._stop_pipeline(stream_id)
            pipeline_processor.wait_for_completion()
