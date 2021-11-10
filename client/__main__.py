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
import os
import sys
import time
import cv2

from arguments import parse_args
from grpc_client import GrpcClient
from http_client import HttpClient
from results_processor import ResultsProcessor
from common.exception_handler import log_exception
from common.ava_api import AvaApi, get_ava_api


class VideoSource:
    def __init__(self, filename, loop_count, scale_factor = 1.0):
        self._loop_count = loop_count
        self._filename = filename
        self._scale_factor = scale_factor
        self._open_video_source()

    def _open_video_source(self):
        self._vid_cap = cv2.VideoCapture(self._filename, cv2.CAP_GSTREAMER)
        if self._vid_cap is None or not self._vid_cap.isOpened():
            raise Exception("Error opening video source: {}".format(self._filename))

    def get_frame(self):
        ret, frame = self._vid_cap.read()
        if ret:
            width = int(self._vid_cap.get(cv2.CAP_PROP_FRAME_WIDTH) * self._scale_factor)
            height = int(self._vid_cap.get(cv2.CAP_PROP_FRAME_HEIGHT) * self._scale_factor)
            dsize = (width, height)
            frame = cv2.resize(frame, dsize)
            return frame
        self._loop_count -= 1
        if self._loop_count > 0:
            self._open_video_source()
            ret, frame = self._vid_cap.read()
            if ret:
                width = int(self._vid_cap.get(cv2.CAP_PROP_FRAME_WIDTH) * self._scale_factor)
                height = int(self._vid_cap.get(cv2.CAP_PROP_FRAME_HEIGHT) * self._scale_factor)
                dsize = (width, height)
                frame = cv2.resize(frame, dsize)
                return frame
        return None

    def close(self):
        self._vid_cap.release()


def _log_options(args):
    heading = "Options for {}".format(os.path.basename(__file__))
    banner = "=" * len(heading)
    logging.info(banner)
    logging.info(heading)
    logging.info(banner)
    for arg in vars(args):
        logging.info("{} == {}".format(arg, getattr(args, arg)))
        logging.info(banner)


def _log_fps(start_time, frames_received, prev_fps_delta, fps_interval):
    delta = int(time.time() - start_time)
    if (fps_interval > 0) and (delta != prev_fps_delta) and (delta % fps_interval == 0):
        logging.info(
            "FPS: {} Frames Recieved: {}".format(
                (frames_received / delta), frames_received
            )
        )
        return delta
    return prev_fps_delta


def main():
    frame_source = None
    client = None
    args = parse_args()
    _log_options(args)
    try:
        frame_delay = 1 / args.frame_rate if args.frame_rate > 0 else 0
        frames_sent = 0
        prev_fps_delta = 0
        start_time = None
        frame_source = VideoSource(args.sample_file, args.loop_count, args.scale_factor)

        image = frame_source.get_frame()

        if image is None:
            raise Exception("Error getting frame from video source: {}".format(args.sample_file))

        height, width, _ = image.shape

        if get_ava_api(args.api) == AvaApi.GRPC:
            client = GrpcClient(args, width, height, image.size)
        else:
            client = HttpClient(args, image.size)
        result_processor = ResultsProcessor()
        with open(args.output_file, "w") as output:
            start_time = time.time()
            while image is not None and frames_sent < args.max_frames:
                client.put_frame(image)
                frames_sent += 1
                while client.have_result():
                    result_processor.process(client.get_result(), output)
                prev_fps_delta = _log_fps(
                    start_time, result_processor.results_received(), prev_fps_delta, args.fps_interval
                )
                image = frame_source.get_frame()
                time.sleep(frame_delay)

            client.put_frame(None)
            result = client.get_result()
            while result:
                result_processor.process(result, output)
                result = client.get_result()
                prev_fps_delta = _log_fps(
                    start_time, result_processor.results_received(), prev_fps_delta, args.fps_interval
                )

        results_received = result_processor.results_received()
        delta = time.time() - start_time
        logging.info(
            "Start Time: {} End Time: {} Frames: Tx {} Rx {} FPS: {}".format(
                start_time,
                start_time + delta,
                frames_sent,
                results_received,
                (results_received / delta) if delta > 0 else None,
            )
        )

        if frames_sent != results_received:
            raise Exception("Sent {} requests, received {} responses".format(
                frames_sent, results_received))

        return True
    except (KeyboardInterrupt, SystemExit, Exception):
        log_exception()
        return False
    finally:
        if client is not None:
            client.stop()
        if frame_source:
            frame_source.close()


if __name__ == "__main__":
    # Set logging parameters
    logging.basicConfig(
        level=logging.INFO,
        format="[AIXC] [%(asctime)-15s] [%(threadName)-12.12s] [%(levelname)s]: %(message)s",
        handlers=[
            # logging.FileHandler(LOG_FILE_NAME),    # write in a log file
            logging.StreamHandler(sys.stdout)  # write in stdout
        ],
    )

    # Call Main logic
    if not main():
        sys.exit(1)
    logging.info("Client finished execution")
