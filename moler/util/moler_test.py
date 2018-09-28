# -*- coding: utf-8 -*-
"""
Utility/common code of library.
"""

__author__ = 'Grzegorz Latuszek, Marcin Usielski, Michal Ernst'
__copyright__ = 'Copyright (C) 2018, Nokia'
__email__ = 'grzegorz.latuszek@nokia.com, marcin.usielski@nokia.com, michal.ernst@nokia.com'

import logging
import time
from functools import wraps
from types import FunctionType, MethodType

from moler.connection_observer import ConnectionObserver
from moler.exceptions import MolerException
from moler.exceptions import MolerStatusException


class MolerTest(object):
    _last_check_time = 0
    _was_error = False
    _was_steps_end = False
    _logger = logging.getLogger("moler")

    @staticmethod
    def steps_end():
        MolerTest._was_steps_end = True

    @staticmethod
    def log_error(msg, raise_exception=False):
        MolerTest._was_error = True
        MolerTest._logger.error(msg)
        if raise_exception:
            raise MolerException(msg)

    @staticmethod
    def log(msg):
        MolerTest._logger.info(msg)

    @staticmethod
    def _steps_start():
        MolerTest._was_steps_end = False

    @staticmethod
    def _final_check(caught_exception=None, check_steps_end=True):
        final_check_time = time.time()
        exceptions = ConnectionObserver.get_active_exceptions_in_time(MolerTest._last_check_time, time.time(), True)
        unhandled_exceptions = list()
        for exception in exceptions:
            unhandled_exceptions.append(exception)
            MolerTest.log_error("Unhandled exception: '{}'".format(exception))
        if caught_exception:
            unhandled_exceptions.append(caught_exception)
        MolerTest._last_check_time = final_check_time
        was_error_in_last_execution = MolerTest._was_error
        MolerTest._was_error = False
        err_msg = ""
        if check_steps_end and not MolerTest._was_steps_end:
            err_msg += "Method steps_end() was not called.\n"
        if was_error_in_last_execution:
            err_msg += "There were error messages in Moler execution. Please check Moler logs for details.\n"
        if len(unhandled_exceptions) > 0:
            err_msg += "There were unhandled exceptions in Moler.\n"
        if err_msg or len(unhandled_exceptions) > 0:
            raise MolerStatusException(err_msg, unhandled_exceptions)

    @staticmethod
    def moler_raise_background_exceptions():
        def decorate(obj):
            if obj.__dict__.items():
                for attributeName, attribute in obj.__dict__.items():
                    if attributeName.startswith("test"):
                        if isinstance(attribute, (FunctionType, MethodType)):
                            setattr(obj, attributeName, MolerTest.wrapper(attribute, False))
            else:
                obj = MolerTest.wrapper(obj, False)

            return obj

        return decorate

    @staticmethod
    def moler_raise_background_exceptions_steps_end():
        def decorate(obj):
            if obj.__dict__.items():
                for attributeName, attribute in obj.__dict__.items():
                    if attributeName.startswith("test"):
                        if isinstance(attribute, (FunctionType, MethodType)):
                            setattr(obj, attributeName, MolerTest.wrapper(attribute, True))
            else:
                obj = MolerTest.wrapper(obj, True)

            return obj

        return decorate

    @staticmethod
    def wrapper(method, check_steps_end):
        if hasattr(method, '_already_decorated') and method._already_decorated:
            return method

        @wraps(method)
        def wrapped(*args, **kwargs):
            MolerTest._steps_start()
            caught_exception = None
            try:
                result = method(*args, **kwargs)
            except Exception as exc:
                caught_exception = exc
            finally:
                MolerTest._final_check(caught_exception, check_steps_end)
            return result

        wrapped._already_decorated = True
        return wrapped
