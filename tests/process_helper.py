
import subprocess
import select
import time
import os
import json
import signal

class ProcessHelper:
    def __init__(self):
        self.server_process = None
        self.client_process = None
        self.poll = None
        self.start_time = time.time()

    def run_server(self, params, capture_log = False):
        protocol = params.get("protocol", "grpc")
        server_args = ["python3", "server", "--protocol", protocol]
        server_args.extend(["--max-running-pipelines", str(params.get("max_running_pipelines", 10))])
        print(' '.join(server_args))

        if "ENABLE_RTSP" in os.environ:
            del os.environ["ENABLE_RTSP"]
        if params.get("enable_rtsp", None):
            os.environ["ENABLE_RTSP"] = "true"
            os.environ["RTSP_PORT"] = str(params.get("rtsp_port"))

        self.server_process = subprocess.Popen(server_args,
                                               bufsize=0,
                                               stdout=params.get("stdout",None),
                                               stderr=params.get("stderr", subprocess.PIPE if capture_log else None))
        time.sleep(params.get("sleep_period",0.25))
        if capture_log:
            self.poll = select.poll()
            self.poll.register(self.server_process.stderr, select.POLLIN)
        return self.server_process

    def get_server_log_message(self):
        if self.poll and self.poll.poll(0):
            try:
                line = self.server_process.stderr.readline()
                log_message = json.loads(line)
                if "levelname" in log_message and "message" in log_message:
                    return log_message["message"]
            except ValueError:
                pass
        return None

    def get_server_log_messages(self):
        lines = []
        line = self.get_server_log_message()
        while line is not None:
            lines.append(line)
            line = self.get_server_log_message()
        return lines

    def run_client(self, params, asynchronous=False):
        client_args = ["python3", "client",
                    "--protocol", params.get("protocol", "grpc"),
                    "-l", str(params.get("loop_count", 1)),
                    "-f", params["source"]]
        if params.get("pipeline"):
            extension_config = json.dumps({"pipeline":params["pipeline"]})
            client_args.extend(["--extension-config", extension_config])
        if params.get("shared_memory", False):
            client_args.append("-m")
        if params.get("output_location"):
            client_args.extend(["-o", params["output_location"]])
        if params.get("max_frames"):
            client_args.extend(["--max-frames", str(params["max_frames"])])
        if params.get("scale_factor"):
            client_args.extend(["--scale-factor", str(params["scale_factor"])])
        if params.get("stream_id"):
            client_args.extend(["--http-stream-id", params["stream_id"]])

        print(' '.join(client_args))
        self.client_process = subprocess.Popen(client_args,
                                               stdout=params.get("stdout",None),
                                               stderr=params.get("stderr",None))
        if not asynchronous:
            self.client_process.wait()
            assert self.client_process.returncode == params.get("expected_return_code", 0)
        return self.client_process

    def cleanup_processes(self):
        self.stop_process(self.server_process)
        self.server_process = None

    def stop_process(self, process, timeout = 10):
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGINT)
            print("Awaiting graceful exit")
            try:
                process.wait(timeout)
            except subprocess.TimeoutExpired:
                print("TimeoutExpired, killing process")
                process.kill()
