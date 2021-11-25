import os
import tempfile
import copy
import time
import utils

def test_pipeline_execution_one_client(helpers, test_case, test_filename, generate):
    #Create copy of test case to create the generated file
    _test_case = copy.deepcopy(test_case)
    helpers.run_server(_test_case["server_params"])

    #Create temporary directory for saving output
    workdir_path = tempfile.TemporaryDirectory()
    output_file = None

    if not "client" in _test_case:
        assert False, "Invalid test"

    # Start client
    client_params = _test_case["client"]["params"]
    output_file = os.path.join(workdir_path.name, "output_one_client.jsonl")
    client_params["output_location"] = output_file
    process = helpers.run_client(client_params, True)
    time.sleep(client_params["sleep_period"])
    expected_return_code = client_params.get("expected_return_code", 0)

    rtsp = client_params.get("rtsp", None)
    if rtsp:
        utils.test_rtsp(rtsp, client_params["pipeline"]["frame-destination"])

    if client_params["wait_to_complete"]:
        process.wait()
    else:
        helpers.stop_process(process)

    assert process.returncode == expected_return_code

    if output_file:
        utils.validate_output_against_schema(output_file)