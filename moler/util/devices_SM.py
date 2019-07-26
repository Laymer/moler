# -*- coding: utf-8 -*-
"""
Perform devices SM autotest.
"""

__author__ = 'Michal Ernst'
__copyright__ = 'Copyright (C) 2019, Nokia'
__email__ = 'michal.ernst@nokia.com'

import os

from moler.device import DeviceFactory
from moler.exceptions import MolerException
from moler.config import load_config


def iterate_over_device_states(device):
    states = device.states

    states.remove("NOT_CONNECTED")

    for source_state in states:
        device.goto_state(source_state)
        for target_state in states:
            try:
                device.goto_state(target_state)
            except Exception as exc:
                raise MolerException(
                    "Cannot trigger change state: '{}' -> '{}'\n{}".format(source_state, target_state, exc))


def get_device(name, connection, device_output):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    load_config(os.path.join(dir_path, os.pardir, os.pardir, 'test', 'resources', 'device_config.yml'))

    device = DeviceFactory.get_device(name)
    device.io_connection = connection
    device.io_connection.name = device.name
    device.io_connection.moler_connection.name = device.name

    device.io_connection.remote_inject_response(device_output)
    device.io_connection.set_device(device)

    return device
