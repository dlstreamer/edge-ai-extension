'''
* Copyright (C) 2019-2020 Intel Corporation.
*
* SPDX-License-Identifier: MIT License
'''

def test_ava_nonexistant_source(helpers, sleep_period=0.25, port=5001):
    client_params = {
        "source": "/home/edge-ai-extension/sampleframes/nonexistantimage.png",
        "sleep_period": sleep_period,
        "port": port,
        "shared_memory": False,
        "expected_return_code": 1
    }

    helpers.run_client(client_params)
