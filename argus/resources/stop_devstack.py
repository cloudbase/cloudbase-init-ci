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

"""Stop nicely the devstack environment."""

import os
import shlex
import signal
import subprocess

import psutil


DEVSTACK_SCREEN = 'stack-screenrc'
SCREEN_KILL_COMMAND = "screen -S stack -X quit"


def _looks_like_devstack_screen(cmdline):
    return any(part.find(DEVSTACK_SCREEN) > -1
               for part in cmdline)


def _get_process_children(process):
    for child in process.get_children():
        yield child
        for subchild in child.get_children():
            yield subchild


def _get_devstack_screen():
    """Heuristic for retrieving the devstack screen."""
    for process in psutil.process_iter():
        if (process.name == 'screen'
                and _looks_like_devstack_screen(process.cmdline)):
            return process


def stop_devstack():
    """Stop the devstack environment

    Just sending the quit command to devstack screen is not
    enough, since the children will not be sent the proper
    termination signal (SIGTERM), leading to hanging processes
    over a couple of ports and so on. This approach sents
    explicitly SIGTERM to each child of the devstack screen,
    which will lead to a proper cleanup.
    """
    screen = _get_devstack_screen()
    if not screen:
        return

    for proc in _get_process_children(screen):
        try:
            os.kill(proc.pid, signal.SIGTERM)
        except OSError:
            pass
    subprocess.call(shlex.split(SCREEN_KILL_COMMAND))
