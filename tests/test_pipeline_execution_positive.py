
import os
import tempfile
import pytest
import time
import parse
import utils
from utils import ClientProcess


def get_num_running_clients(clients):
    count = 0
    for client in clients:
        if client.is_running():
            count += 1
    return count


@pytest.mark.timeout(300)
def test_pipeline_execution_positive(helpers, test_case, test_filename, generate):
    workdir_path = tempfile.TemporaryDirectory()
    clients = []
    is_max_frames_set = False
    num_of_concurrent_clients = 0
    for test in test_case["client"]:
        num_of_concurrent_clients += test.get("num_of_concurrent_clients", 1)
        if test["params"].get("max_frames"):
            is_max_frames_set = False

    if (len(test_case["client"]) > 1) and is_max_frames_set and test_case["golden_results"]:
        assert False, "Cannot limit number of video frames with multiple client test cases using ground truth"

    is_concurrent_test = num_of_concurrent_clients > 1
    helpers.run_server(test_case["server_params"], capture_log=is_concurrent_test)
    for test in test_case["client"]:
        for _ in range(test.get("num_of_concurrent_clients", 1)):
            output_file = "output{}.jsonl".format(len(clients))
            output_location = os.path.join(workdir_path.name, output_file)
            print("Spawning concurrent process with output location: {}".format(output_location))
            test["params"]["output_location"] = output_location
            client = ClientProcess(helpers, test["params"], is_concurrent_test)
            clients.append(client)

    if is_concurrent_test:
        sleep_duration = 0.25
        num_pipelines_running = 0
        num_pipelines_stopped = 0
        max_running_pipelines = 0
        while get_num_running_clients(clients) > 0 or num_pipelines_stopped != num_of_concurrent_clients:
            messages = helpers.get_server_log_messages()
            for message in messages:
                if parse.parse("Setting Pipeline {} State to RUNNING", message):
                    print("Test: " + message)
                    num_pipelines_running += 1

                if num_pipelines_running > max_running_pipelines:
                    max_running_pipelines = num_pipelines_running
                    print("Test: max_running_pipelines = {}".format(max_running_pipelines))

                if parse.parse("Pipeline {} Ended", message):
                    print("Test: " + message)
                    num_pipelines_running -= 1
                    num_pipelines_stopped += 1

            for client in clients:
                if not client.is_running():
                    assert client.has_correct_return_code(), "Incorrect return code"
            time.sleep(sleep_duration)

        if test_case["server_params"].get("max_running_pipelines", 0) > 1:
            assert max_running_pipelines == num_of_concurrent_clients, "Not all pipelines running in concurrent mode"
        else:
            assert max_running_pipelines == 1, "More than one concurrent pipeline running in serial mode"

    for client in clients:
        client.stop()
        utils.validate_output_against_schema(client.get_output_location())

    if test_case["golden_results"]:
        utils.golden_results(clients, test_case, generate, test_filename)