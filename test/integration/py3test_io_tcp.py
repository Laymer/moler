# -*- coding: utf-8 -*-
"""
Testing external-IO TCP connection

- open/close
- send/receive (naming may differ)
"""

__author__ = 'Grzegorz Latuszek'
__copyright__ = 'Copyright (C) 2018, Nokia'
__email__ = 'grzegorz.latuszek@nokia.com'

import time
import importlib
import asyncio
import pytest


@pytest.mark.asyncio
async def test_can_open_and_close_connection(tcp_connection_class,
                                             integration_tcp_server_and_pipe):
    """
    Not so atomic test (checks 2 things) but:
    - it is integration tests
    - anyway open needs close as cleanup to not have resources leaking in tests
    """
    from moler.connection import ObservableConnection
    (tcp_server, tcp_server_pipe) = integration_tcp_server_and_pipe

    moler_conn = ObservableConnection()
    connection = tcp_connection_class(moler_connection=moler_conn, port=tcp_server.port, host=tcp_server.host)
    await connection.open()
    await connection.close()
    time.sleep(0.1)  # otherwise we have race between server's pipe and from-client-connection
    tcp_server_pipe.send(("get history", {}))
    dialog_with_server = tcp_server_pipe.recv()
    assert 'Client connected' in dialog_with_server
    assert 'Client disconnected' in dialog_with_server


@pytest.mark.asyncio
async def test_can_open_and_close_connection_as_context_manager(tcp_connection_class,
                                                                integration_tcp_server_and_pipe):
    from moler.connection import ObservableConnection
    (tcp_server, tcp_server_pipe) = integration_tcp_server_and_pipe

    moler_conn = ObservableConnection()
    connection = tcp_connection_class(moler_connection=moler_conn, port=tcp_server.port, host=tcp_server.host)
    async with connection:
        pass
    time.sleep(0.1)  # otherwise we have race between server's pipe and from-client-connection
    tcp_server_pipe.send(("get history", {}))
    dialog_with_server = tcp_server_pipe.recv()
    assert 'Client connected' in dialog_with_server
    assert 'Client disconnected' in dialog_with_server


# Note: external-IO 'send' method works on bytes; moler_connection performs encoding
@pytest.mark.asyncio
async def test_can_send_binary_data_over_connection(tcp_connection_class,
                                                    integration_tcp_server_and_pipe):
    from moler.connection import ObservableConnection
    (tcp_server, tcp_server_pipe) = integration_tcp_server_and_pipe

    moler_conn = ObservableConnection()
    connection = tcp_connection_class(moler_connection=moler_conn, port=tcp_server.port, host=tcp_server.host)
    async with connection:
        await connection.send(data=b'raw data to be send')
        time.sleep(0.1)  # otherwise we have race between server's pipe and from-client-connection
        tcp_server_pipe.send(("get history", {}))
        dialog_with_server = tcp_server_pipe.recv()
        assert ['Received data:', b'raw data to be send'] == dialog_with_server[-1]


# Note: different external-IO connection may have different naming for their 'send' method
# however, they are uniformed via glueing with moler_connection.send()
# external-IO 'send' method works on bytes; moler_connection performs encoding
@pytest.mark.asyncio
async def test_can_send_data_over_connection(tcp_connection_class,
                                             integration_tcp_server_and_pipe):
    from moler.connection import ObservableConnection
    (tcp_server, tcp_server_pipe) = integration_tcp_server_and_pipe

    moler_conn = ObservableConnection(encoder=lambda data: data.encode("utf-8"))
    connection = tcp_connection_class(moler_connection=moler_conn, port=tcp_server.port, host=tcp_server.host)
    async with connection:
        moler_conn.send(data='data to be send')
        time.sleep(0.1)  # otherwise we have race between server's pipe and from-client-connection
        tcp_server_pipe.send(("get history", {}))
        dialog_with_server = tcp_server_pipe.recv()
        assert ['Received data:', b'data to be send'] == dialog_with_server[-1]


# Note: external-IO 'receive' method works on bytes; moler_connection performs decoding
@pytest.mark.asyncio
async def test_can_receive_binary_data_from_connection(tcp_connection_class,
                                                       integration_tcp_server_and_pipe):
    from moler.connection import ObservableConnection
    (tcp_server, tcp_server_pipe) = integration_tcp_server_and_pipe
    received_data = bytearray()
    receiver_called = asyncio.Event()

    def receiver(data):
        received_data.extend(data)
        receiver_called.set()

    moler_conn = ObservableConnection()  # no decoder, just pass bytes 1:1
    moler_conn.subscribe(receiver)
    connection = tcp_connection_class(moler_connection=moler_conn, port=tcp_server.port, host=tcp_server.host)
    async with connection:
        time.sleep(0.1)  # otherwise we have race between server's pipe and from-client-connection
        tcp_server_pipe.send(("send async msg", {'msg': b'data to read'}))
        await asyncio.wait_for(receiver_called.wait(), timeout=0.5)

    assert b'data to read' == received_data


# Note: external-IO 'receive' method works on bytes; moler_connection performs decoding
@pytest.mark.asyncio
async def test_can_receive_data_from_connection(tcp_connection_class,
                                                integration_tcp_server_and_pipe):
    from moler.connection import ObservableConnection
    (tcp_server, tcp_server_pipe) = integration_tcp_server_and_pipe
    received_data = []
    receiver_called = asyncio.Event()

    def receiver(data):
        received_data.append(data)
        receiver_called.set()

    moler_conn = ObservableConnection(decoder=lambda data: data.decode("utf-8"))
    moler_conn.subscribe(receiver)
    connection = tcp_connection_class(moler_connection=moler_conn, port=tcp_server.port, host=tcp_server.host)
    async with connection:
        time.sleep(0.1)  # otherwise we have race between server's pipe and from-client-connection
        tcp_server_pipe.send(("send async msg", {'msg': b'data to read'}))
        await asyncio.wait_for(receiver_called.wait(), timeout=0.5)

    assert 'data to read' == received_data[0]


# TODO: tests for error cases raising Exceptions

# --------------------------- resources ---------------------------


@pytest.fixture(params=['io.asyncio.tcp.AsyncioTcp'])
def tcp_connection_class(request):
    module_name, class_name = request.param.rsplit('.', 1)
    module = importlib.import_module('moler.{}'.format(module_name))
    connection_class = getattr(module, class_name)
    return connection_class


@pytest.yield_fixture()
def integration_tcp_server_and_pipe():
    from moler.io.raw.tcpserverpiped import tcp_server_piped
    with tcp_server_piped(use_stderr_logger=True) as server_and_pipe:
        (server, svr_ctrl_pipe) = server_and_pipe
        yield (server, svr_ctrl_pipe)