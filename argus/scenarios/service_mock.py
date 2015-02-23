# Copyright 2015 Cloudbase Solutions Srl
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


import contextlib
import threading

import cherrypy
from six.moves import urllib


class BaseServiceMock(object):

    script_name = None
    host = "0.0.0.0"
    port = 8080


@contextlib.contextmanager
def create_service(*service_classes):
    """Context manager used for mocking metadata services.
    
    Create and start a custom server based on the
    provided class. Kill it when leaving the context.
    """
    # start the service(s) in different thread(s)
    threads = []
    for service_class in service_classes:
        kwargs = {
            "root": service_class,
            "script_name": service_class.script_name,
            "config": {
                "server.socket_host": service_class.host,
                "server.socket_port": service_class.port
            }
        }
        thread = threading.Thread(target=cherrypy.quickstart,
                                  kwargs=kwargs)
        thread.start()
        threads.append(thread)

    yield

    # send the shutdown "signal"
    for service_class in service_classes:
        urllib.request.urlopen(link)
    while threads:
        thread = threads.pop()
        thread.join()
