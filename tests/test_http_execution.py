import os
import tempfile
import copy
import time
import utils
from utils import ClientProcess


def test_http_execution(helpers, test_case, test_filename, generate):
    #Create copy of test case to create the generated file
    _test_case = copy.deepcopy(test_case)
    helpers.run_server(_test_case["server_params"])

    if not "client" in _test_case:
        assert False, "Invalid test"

    workdir_path = tempfile.TemporaryDirectory()
    client_processes = []
    counter =1
    for client in _test_case["client"]:
        client_params = client["params"]
        file_name = "{}_{}".format(test_filename.split("/")[-1],counter)
        counter +=1
        client_params["output_location"] = os.path.join(workdir_path.name, file_name)
        client_process = ClientProcess(helpers, client_params, True)
        client_processes.append(client_process)
        time.sleep(client_params["sleep_period"])
        rtsp_params = client_params.get("rtsp",None)

        if rtsp_params:
            utils.test_rtsp(
                rtsp_params, client_params["pipeline"]["frame-destination"])


    for client_process in client_processes:
        client_process.wait()
        assert client_process.has_correct_return_code()
        utils.validate_output_against_schema(client_process.get_output_location())

    if test_case.get("golden_results",None):
        utils.golden_results(client_processes, test_case, generate, test_filename)
