# -*- coding: utf-8 -*-
"""
asyncio_runner_with_only_async_functions.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A fully-functional connection-observer using configured concurrency variant.

This is Layer_3 example:
- shows configuration phase and usage phase
  - configure named connections via config file
- uses Moler provided TCP connection implementation
- usage hides implementation variant via factories
- variant is known only during backend configuration phase
- uses connection observer with asyncio runner

This example demonstrates multiple connection observers working
on multiple connections.

Shows following concepts:
- multiple observers may observe single connection
- each one is focused on different data (processing decomposition)
- client code may run observers on different connections
- client code may "start" observers in sequence

Shows how to use connection observers inside code that uses only
'async def xxx()' functions (no threads/processes).
"""

__author__ = 'Grzegorz Latuszek'
__copyright__ = 'Copyright (C) 2018, Nokia'
__email__ = 'grzegorz.latuszek@nokia.com'

import logging
import sys
import os
import time
import asyncio

from moler.connection import get_connection
from moler.asyncio_runner import AsyncioRunner

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # allow finding modules in examples/

from network_toggle_observers import NetworkDownDetector, NetworkUpDetector


# ===================== Moler's connection-observer usage ======================


@asyncio.coroutine
def ping_observing_task(ext_io_connection, ping_ip):
    """
    Here external-IO connection is abstract - we don't know its type.
    What we know is just that it has .moler_connection attribute.
    """

    logger = logging.getLogger('moler.user.app-code')
    conn_addr = str(ext_io_connection)

    # Layer 2 of Moler's usage (ext_io_connection + runner):
    # 3. create observers on Moler's connection
    net_down_detector = NetworkDownDetector(ping_ip,
                                            connection=ext_io_connection.moler_connection,
                                            runner=AsyncioRunner())
    net_up_detector = NetworkUpDetector(ping_ip,
                                        connection=ext_io_connection.moler_connection,
                                        runner=AsyncioRunner())

    info = '{} on {} using {}'.format(ping_ip, conn_addr, net_down_detector)
    logger.debug('observe ' + info)

    # 4. start observer (nonblocking, using as future)
    net_down_detector.start()  # should be started before we open connection
    # to not loose first data on connection

    with ext_io_connection:
        # 5. await that observer to complete
        net_down_time = yield from net_down_detector
        # net_down_time = await net_down_detector
        timestamp = time.strftime("%H:%M:%S", time.localtime(net_down_time))
        logger.debug('Network {} is down from {}'.format(ping_ip, timestamp))

        # 6. call next observer (blocking till completes)
        info = '{} on {} using {}'.format(ping_ip, conn_addr, net_up_detector)
        logger.debug('observe ' + info)
        # using as synchronous function (so we want verb to express action)
        detect_network_up = net_up_detector
        net_up_time = yield from detect_network_up
        timestamp = time.strftime("%H:%M:%S", time.localtime(net_up_time))
        logger.debug('Network {} is back "up" from {}'.format(ping_ip, timestamp))
    logger.debug('exiting ping_observing_task')


# ==============================================================================
async def main(connections2observe4ip):
    logger = logging.getLogger('asyncio.main')
    event_loop = asyncio.get_event_loop()

    # Starting the clients
    connections = []
    for _, connection_name, ping_ip in connections2observe4ip:
        # ------------------------------------------------------------------
        # This front-end code hides all details of connection.
        # We just use its name - such name should be meaningful for user.
        # like: "main_dns_server", "backup_ntp_server", ...
        # Another words, all we want here is stg like:
        # "give me connection to main_dns_server"
        # ------------------------------------------------------------------
        con_logger = logging.getLogger('tcp-thrd-io.{}'.format(connection_name))
        tcp_connection = get_connection(name=connection_name, logger=con_logger)
        tcp_connection.moler_connection.name = connection_name
        # client_task= asyncio.ensure_future(ping_observing_task(tcp_connection, ping_ip))
        connections.append(ping_observing_task(tcp_connection, ping_ip))
    # await observers job to be done
    completed, pending = await asyncio.wait(connections)


# ==============================================================================
if __name__ == '__main__':
    from threaded_ping_server import start_ping_servers, stop_ping_servers
    from asyncio_common import run_via_asyncio
    import os
    from moler.config import load_config
    # -------------------------------------------------------------------
    # Configure moler connections (backend code)
    # 1) configure variant by YAML config file
    # 2) ver.2 - configure named connections by YAML config file
    load_config(config=os.path.join(os.path.dirname(__file__), "..", "named_connections.yml"))

    # 3) take default class used to realize tcp-threaded-connection
    # -------------------------------------------------------------------

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s |%(name)-45s |%(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,
    )

    connections2serve = [(('localhost', 5671), '10.0.2.15'),
                         (('localhost', 5672), '10.0.2.16')]
    connections2observe4ip = [(('localhost', 5671), 'net_1', '10.0.2.15'),
                              (('localhost', 5672), 'net_2', '10.0.2.16')]
    servers = start_ping_servers(connections2serve)

    try:
        run_via_asyncio(main(connections2observe4ip))

    finally:
        stop_ping_servers(servers)

'''
LOG OUTPUT

18:23:25 |asyncio                                  |Using selector: SelectSelector
18:23:25 |asyncio.ping.tcp-server(5671)            |Ping Sim started at tcp://localhost:5671
18:23:25 |asyncio.ping.tcp-server(5671)            |WARNING - I'll be tired too much just after first client!
18:23:25 |asyncio.ping.tcp-server(5672)            |Ping Sim started at tcp://localhost:5672
18:23:25 |asyncio.ping.tcp-server(5672)            |WARNING - I'll be tired too much just after first client!
18:23:25 |moler.runner.asyncio                     |created
18:23:25 |moler.runner.asyncio                     |created
18:23:25 |moler.user.app-code                      |observe 10.0.2.15 on tcp://localhost:5671 using NetworkDownDetector(id:30c4278)
18:23:25 |moler.runner.asyncio                     |go background: NetworkDownDetector(id:30c4278, using ObservableConnection(id:3096358)-->[<bound method Tcp.send of <moler.io.raw.tcp.ThreadedTcp object at 0x00000000030C4048>>])
18:23:25 |moler.runner.asyncio                     |subscribing for data NetworkDownDetector(id:30c4278, using ObservableConnection(id:3096358)-->[<bound method Tcp.send of <moler.io.raw.tcp.ThreadedTcp object at 0x00000000030C4048>>])
18:23:25 |tcp-thrd-io.net_1                        |connecting to tcp://localhost:5671
18:23:25 |tcp-thrd-io.net_1                        |connection tcp://localhost:5671 is open
18:23:25 |moler.runner.asyncio                     |go foreground: NetworkDownDetector(id:30c4278, using ObservableConnection(id:3096358)-->[<bound method Tcp.send of <moler.io.raw.tcp.ThreadedTcp object at 0x00000000030C4048>>])
18:23:25 |moler.runner.asyncio                     |created
18:23:25 |moler.runner.asyncio                     |created
18:23:25 |moler.user.app-code                      |observe 10.0.2.16 on tcp://localhost:5672 using NetworkDownDetector(id:30c4588)
18:23:25 |moler.runner.asyncio                     |go background: NetworkDownDetector(id:30c4588, using ObservableConnection(id:30c40b8)-->[<bound method Tcp.send of <moler.io.raw.tcp.ThreadedTcp object at 0x00000000030C4128>>])
18:23:25 |moler.runner.asyncio                     |subscribing for data NetworkDownDetector(id:30c4588, using ObservableConnection(id:30c40b8)-->[<bound method Tcp.send of <moler.io.raw.tcp.ThreadedTcp object at 0x00000000030C4128>>])
18:23:25 |tcp-thrd-io.net_2                        |connecting to tcp://localhost:5672
18:23:25 |tcp-thrd-io.net_2                        |connection tcp://localhost:5672 is open
18:23:25 |moler.runner.asyncio                     |go foreground: NetworkDownDetector(id:30c4588, using ObservableConnection(id:30c40b8)-->[<bound method Tcp.send of <moler.io.raw.tcp.ThreadedTcp object at 0x00000000030C4128>>])
18:23:25 |moler.runner.asyncio                     |START OF feed(NetworkDownDetector(id:30c4278))
18:23:25 |moler.runner.asyncio                     |START OF feed(NetworkDownDetector(id:30c4588))
18:23:25 |asyncio.ping.tcp-server(5672 -> 53079)   |connection accepted - client at tcp://127.0.0.1:53079
18:23:25 |asyncio.ping.tcp-server(5671 -> 53078)   |connection accepted - client at tcp://127.0.0.1:53078
18:23:25 |tcp-thrd-io.net_2                        |< b'\n'
18:23:25 |moler.connection.net_2                   |b'\n'
18:23:25 |tcp-thrd-io.net_1                        |< b'\n'
18:23:25 |moler.connection.net_1                   |b'\n'
18:23:26 |tcp-thrd-io.net_2                        |< b'greg@debian:~$ ping 10.0.2.16\n'
18:23:26 |tcp-thrd-io.net_1                        |< b'greg@debian:~$ ping 10.0.2.15\n'
18:23:26 |moler.connection.net_2                   |b'greg@debian:~$ ping 10.0.2.16\n'
18:23:26 |moler.connection.net_1                   |b'greg@debian:~$ ping 10.0.2.15\n'
18:23:27 |tcp-thrd-io.net_1                        |< b'PING 10.0.2.15 (10.0.2.15) 56(84) bytes of data.\n'
18:23:27 |moler.connection.net_1                   |b'PING 10.0.2.15 (10.0.2.15) 56(84) bytes of data.\n'
18:23:27 |tcp-thrd-io.net_2                        |< b'PING 10.0.2.16 (10.0.2.16) 56(84) bytes of data.\n'
18:23:27 |moler.connection.net_2                   |b'PING 10.0.2.16 (10.0.2.16) 56(84) bytes of data.\n'
18:23:28 |tcp-thrd-io.net_2                        |< b'64 bytes from 10.0.2.16: icmp_req=1 ttl=64 time=0.080 ms\n'
18:23:28 |moler.connection.net_2                   |b'64 bytes from 10.0.2.16: icmp_req=1 ttl=64 time=0.080 ms\n'
18:23:28 |tcp-thrd-io.net_1                        |< b'64 bytes from 10.0.2.15: icmp_req=1 ttl=64 time=0.080 ms\n'
18:23:28 |moler.connection.net_1                   |b'64 bytes from 10.0.2.15: icmp_req=1 ttl=64 time=0.080 ms\n'
18:23:29 |tcp-thrd-io.net_1                        |< b'64 bytes from 10.0.2.15: icmp_req=2 ttl=64 time=0.037 ms\n'
18:23:29 |moler.connection.net_1                   |b'64 bytes from 10.0.2.15: icmp_req=2 ttl=64 time=0.037 ms\n'
18:23:29 |tcp-thrd-io.net_2                        |< b'64 bytes from 10.0.2.16: icmp_req=2 ttl=64 time=0.037 ms\n'
18:23:29 |moler.connection.net_2                   |b'64 bytes from 10.0.2.16: icmp_req=2 ttl=64 time=0.037 ms\n'
18:23:30 |tcp-thrd-io.net_2                        |< b'64 bytes from 10.0.2.16: icmp_req=3 ttl=64 time=0.045 ms\n'
18:23:30 |moler.connection.net_2                   |b'64 bytes from 10.0.2.16: icmp_req=3 ttl=64 time=0.045 ms\n'
18:23:30 |tcp-thrd-io.net_1                        |< b'64 bytes from 10.0.2.15: icmp_req=3 ttl=64 time=0.045 ms\n'
18:23:30 |moler.connection.net_1                   |b'64 bytes from 10.0.2.15: icmp_req=3 ttl=64 time=0.045 ms\n'
18:23:31 |tcp-thrd-io.net_1                        |< b'ping: sendmsg: Network is unreachable\n'
18:23:31 |tcp-thrd-io.net_2                        |< b'ping: sendmsg: Network is unreachable\n'
18:23:31 |moler.connection.net_1                   |b'ping: sendmsg: Network is unreachable\n'
18:23:31 |moler.connection.net_2                   |b'ping: sendmsg: Network is unreachable\n'
18:23:31 |moler.NetworkDownDetector(id:30c4278)    |Network 10.0.2.15 is down!
18:23:31 |moler.NetworkDownDetector(id:30c4588)    |Network 10.0.2.16 is down!
18:23:31 |moler.runner.asyncio                     |done & unsubscribing NetworkDownDetector(id:30c4278, using ObservableConnection(id:3096358)-->[<bound method Tcp.send of <moler.io.raw.tcp.ThreadedTcp object at 0x00000000030C4048>>])
18:23:31 |moler.runner.asyncio                     |returning result NetworkDownDetector(id:30c4278)
18:23:31 |moler.runner.asyncio                     |END   OF feed(NetworkDownDetector(id:30c4278))
18:23:31 |moler.runner.asyncio                     |done & unsubscribing NetworkDownDetector(id:30c4588, using ObservableConnection(id:30c40b8)-->[<bound method Tcp.send of <moler.io.raw.tcp.ThreadedTcp object at 0x00000000030C4128>>])
18:23:31 |moler.runner.asyncio                     |returning result NetworkDownDetector(id:30c4588)
18:23:31 |moler.runner.asyncio                     |END   OF feed(NetworkDownDetector(id:30c4588))
18:23:31 |moler.user.app-code                      |Network 10.0.2.15 is down from 18:23:31
18:23:31 |moler.user.app-code                      |observe 10.0.2.15 on tcp://localhost:5671 using NetworkUpDetector(id:30c4358)
18:23:31 |moler.runner.asyncio                     |go background: NetworkUpDetector(id:30c4358, using ObservableConnection(id:3096358)-->[<bound method Tcp.send of <moler.io.raw.tcp.ThreadedTcp object at 0x00000000030C4048>>])
18:23:31 |moler.runner.asyncio                     |subscribing for data NetworkUpDetector(id:30c4358, using ObservableConnection(id:3096358)-->[<bound method Tcp.send of <moler.io.raw.tcp.ThreadedTcp object at 0x00000000030C4048>>])
called from async code
called from async code
18:23:31 |moler.runner.asyncio                     |go foreground: NetworkUpDetector(id:30c4358, using ObservableConnection(id:3096358)-->[<bound method Tcp.send of <moler.io.raw.tcp.ThreadedTcp object at 0x00000000030C4048>>])
18:23:31 |moler.user.app-code                      |Network 10.0.2.16 is down from 18:23:31
18:23:31 |moler.user.app-code                      |observe 10.0.2.16 on tcp://localhost:5672 using NetworkUpDetector(id:30c45f8)
18:23:31 |moler.runner.asyncio                     |go background: NetworkUpDetector(id:30c45f8, using ObservableConnection(id:30c40b8)-->[<bound method Tcp.send of <moler.io.raw.tcp.ThreadedTcp object at 0x00000000030C4128>>])
18:23:31 |moler.runner.asyncio                     |subscribing for data NetworkUpDetector(id:30c45f8, using ObservableConnection(id:30c40b8)-->[<bound method Tcp.send of <moler.io.raw.tcp.ThreadedTcp object at 0x00000000030C4128>>])
18:23:31 |moler.runner.asyncio                     |go foreground: NetworkUpDetector(id:30c45f8, using ObservableConnection(id:30c40b8)-->[<bound method Tcp.send of <moler.io.raw.tcp.ThreadedTcp object at 0x00000000030C4128>>])
18:23:31 |moler.runner.asyncio                     |START OF feed(NetworkUpDetector(id:30c4358))
18:23:31 |moler.runner.asyncio                     |START OF feed(NetworkUpDetector(id:30c45f8))
18:23:32 |tcp-thrd-io.net_1                        |< b'ping: sendmsg: Network is unreachable\n'
18:23:32 |moler.connection.net_1                   |b'ping: sendmsg: Network is unreachable\n'
18:23:32 |tcp-thrd-io.net_2                        |< b'ping: sendmsg: Network is unreachable\n'
18:23:32 |moler.connection.net_2                   |b'ping: sendmsg: Network is unreachable\n'
18:23:33 |tcp-thrd-io.net_2                        |< b'ping: sendmsg: Network is unreachable\n'
18:23:33 |moler.connection.net_2                   |b'ping: sendmsg: Network is unreachable\n'
18:23:33 |tcp-thrd-io.net_1                        |< b'ping: sendmsg: Network is unreachable\n'
18:23:33 |moler.connection.net_1                   |b'ping: sendmsg: Network is unreachable\n'
18:23:34 |tcp-thrd-io.net_1                        |< b'64 bytes from 10.0.2.15: icmp_req=7 ttl=64 time=0.123 ms\n'
18:23:34 |tcp-thrd-io.net_2                        |< b'64 bytes from 10.0.2.16: icmp_req=7 ttl=64 time=0.123 ms\n'
18:23:34 |moler.connection.net_1                   |b'64 bytes from 10.0.2.15: icmp_req=7 ttl=64 time=0.123 ms\n'
18:23:34 |moler.connection.net_2                   |b'64 bytes from 10.0.2.16: icmp_req=7 ttl=64 time=0.123 ms\n'
18:23:34 |moler.NetworkUpDetector(id:30c4358)      |Network 10.0.2.15 is up!
18:23:34 |moler.NetworkUpDetector(id:30c45f8)      |Network 10.0.2.16 is up!
18:23:34 |moler.runner.asyncio                     |done & unsubscribing NetworkUpDetector(id:30c4358, using ObservableConnection(id:3096358)-->[<bound method Tcp.send of <moler.io.raw.tcp.ThreadedTcp object at 0x00000000030C4048>>])
18:23:34 |moler.runner.asyncio                     |returning result NetworkUpDetector(id:30c4358)
18:23:34 |moler.runner.asyncio                     |END   OF feed(NetworkUpDetector(id:30c4358))
18:23:34 |moler.runner.asyncio                     |done & unsubscribing NetworkUpDetector(id:30c45f8, using ObservableConnection(id:30c40b8)-->[<bound method Tcp.send of <moler.io.raw.tcp.ThreadedTcp object at 0x00000000030C4128>>])
18:23:34 |moler.runner.asyncio                     |returning result NetworkUpDetector(id:30c45f8)
18:23:34 |moler.runner.asyncio                     |END   OF feed(NetworkUpDetector(id:30c45f8))
18:23:34 |moler.user.app-code                      |Network 10.0.2.15 is back "up" from 18:23:34
18:23:34 |tcp-thrd-io.net_1                        |connection tcp://localhost:5671 is closed
18:23:34 |moler.user.app-code                      |exiting ping_observing_task
18:23:34 |moler.user.app-code                      |Network 10.0.2.16 is back "up" from 18:23:34
18:23:34 |tcp-thrd-io.net_2                        |connection tcp://localhost:5672 is closed
18:23:34 |moler.user.app-code                      |exiting ping_observing_task
18:23:36 |asyncio.ping.tcp-server(5672 -> 53079)   |Connection tcp://127.0.0.1:53079 closed
18:23:36 |asyncio.ping.tcp-server(5671 -> 53078)   |Connection tcp://127.0.0.1:53078 closed
18:23:36 |asyncio.ping.tcp-server(5672)            |Ping Sim: I'm tired after this client ... will do sepuku
18:23:36 |asyncio.ping.tcp-server(5671)            |Ping Sim: I'm tired after this client ... will do sepuku
18:23:36 |asyncio.main                             |exiting main
18:23:36 |asyncio.main                             |cancelling all remaining tasks
18:23:36 |asyncio.main                             |closing events loop ...
18:23:36 |asyncio.main                             |... events loop closed
18:23:36 |moler.runner.asyncio                     |shutting down
18:23:36 |moler.runner.asyncio                     |shutting down
18:23:36 |moler.runner.asyncio                     |shutting down
18:23:36 |moler.runner.asyncio                     |shutting down
'''
