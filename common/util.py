'''
* Copyright (C) 2019 Intel Corporation.
*
* SPDX-License-Identifier: BSD-3-Clause
'''

import json
import jsonschema
from common import extension_schema, constants


def get_pipeline_config_value(extension_config, key):
    return extension_config.get(constants.PIPELINE).get(key, None)


def validate_extension_config(extension_config):
    try:
        validator = jsonschema.Draft4Validator(schema=extension_schema.extension_config,
                                               format_checker=jsonschema.draft4_format_checker)
        validator.validate(extension_config)
    except jsonschema.exceptions.ValidationError as err:
        raise Exception("Error validating pipeline request: {},: error: {}".format(
            extension_config, err.message)) from err


def get_typed_value(value):
    try:
        return json.loads(value)
    except ValueError:
        return value
