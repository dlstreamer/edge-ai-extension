
import os
import json
import pytest
from process_helper import ProcessHelper

@pytest.fixture
def helpers():
    process_helper = ProcessHelper()
    yield process_helper
    process_helper.cleanup_processes()

def pytest_addoption(parser):
    parser.addoption("--generate", action="store_true", help="generate expected results",
                     default=False)
    parser.addoption("--cpu", action="store_true", help="Run CPU tests",
                     default=True)
    parser.addoption("--no-cpu", action="store_false", dest='cpu', help="Disable CPU tests")
    parser.addoption("--gpu", action="store_true", help="Run GPU tests",
                     default=False)
    parser.addoption("--myriad", action="store_true", help="Run MYRIAD tests",
                     default=False)


#Parse the test_cases folder to load config files for parameterizing tests and checking results
def load_test_cases(metafunc, directory):
    dir_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_cases", directory)
    list_of_dir_paths = [dir_path]

    filenames = []
    if metafunc.config.getoption("cpu"):
        cpu_path = os.path.join(dir_path, "cpu")
        if os.path.isdir(cpu_path):
            list_of_dir_paths.append(cpu_path)
    if metafunc.config.getoption("gpu"):
        gpu_path = os.path.join(dir_path, "gpu")
        if os.path.isdir(gpu_path):
            list_of_dir_paths.append(gpu_path)

    if metafunc.config.getoption("myriad"):
        gpu_path = os.path.join(dir_path, "myriad")
        if os.path.isdir(gpu_path):
            list_of_dir_paths.append(gpu_path)

    for path in list_of_dir_paths:
        dir_filenames = [(os.path.abspath(os.path.join(path, fn)),
                           os.path.splitext(fn)[0]) for fn in os.listdir(path)
                           if os.path.isfile(os.path.join(path, fn)) and
                           os.path.splitext(fn)[1] == '.json']
        filenames.extend(dir_filenames)
    test_cases = []
    test_names = []
    generate = metafunc.config.getoption("generate")
    for filepath, testname in filenames:
        try:
            with open(filepath) as json_file:
                test_cases.append((json.load(json_file), filepath, generate))
                test_names.append(testname)
        except Exception as error:
            print(error)
            assert False, "Error Reading Test Case"
    return (test_cases, test_names)

def pytest_generate_tests(metafunc):
    if "pipeline_execution_positive" in metafunc.function.__name__:
        test_cases, test_names = load_test_cases(metafunc, "pipeline_execution_positive")
        metafunc.parametrize("test_case,test_filename,generate", test_cases, ids=test_names)

    if "pipeline_execution_one_client" in metafunc.function.__name__:
        test_cases, test_names = load_test_cases(metafunc, "pipeline_execution_one_client")
        metafunc.parametrize("test_case,test_filename,generate", test_cases, ids=test_names)

    if "algorithm" in metafunc.function.__name__:
        test_cases, test_names = load_test_cases(metafunc, "algorithm")
        metafunc.parametrize("test_case,test_filename,generate", test_cases, ids=test_names)

    if "http_execution" in metafunc.function.__name__:
        test_cases, test_names = load_test_cases(metafunc, "http_execution")
        metafunc.parametrize("test_case,test_filename,generate", test_cases, ids=test_names)
