# Copyright 2016 Cloudbase Solutions Srl
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

from __future__ import print_function

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import requests
import six
from six.moves import urllib_parse as urlparse

from argus.backends.tempest import manager
from argus import config as argus_config
from argus.config import ci
from argus import exceptions
from os_testr import subunit2html

CONFIG = argus_config.CONFIG


def _download_resource(url, location):
    """Download a file from a remote url.

    :param url: The URL that points to the resource
    :param location: Where to save the resource
    """
    for _ in range(CONFIG.argus.retry_count):
        try:
            response = requests.get(url)
            response.raise_for_status()
        except (requests.RequestException, requests.HTTPError) as ex:
            raise exceptions.ArgusEnvironmentError(
                "Download failed from %s to %s with %s .", url, location, ex)

    with open(location, 'wb') as file_handle:
        file_handle.write(response.text)


def download_argus_resource(resource_path, location, resources_link):
    """Download an Argus Resource.

    :param resource_path: Path of the resource relative to the
                         Argus `resources` directory
    :param location: Where to save the resource
    """
    base_url = resources_link.rsplit("/", 1)[0]

    url_resource = urlparse.urljoin(base_url, resource_path)
    _download_resource(url_resource, location)


def _get_image_name(image_ref):
    """Return the image name.

    :param image_ref: The id of the image.
    """
    image_name = None
    try:
        mng = manager.APIManager()
        images = mng.image_client.list_images()["images"]
        for img_ref in images:
            if img_ref["id"].lower() == image_ref.lower():
                image_name = img_ref["name"]
    finally:
        mng.cleanup_credentials()

    return image_name


def _get_base_directory(directory, image_name, image_ref):
    """Return the path to the root directory for this run."""
    if directory:
        if not os.path.isdir(directory):
            os.mkdir(directory)
    else:
        directory = tempfile.mkdtemp(prefix="argus-", dir="/tmp")

    base_directory = os.path.abspath(directory)
    image_ref_directory = os.path.join(base_directory, image_ref)
    image_name_link = os.path.join(base_directory, image_name)

    if not os.path.isdir(image_ref_directory):
        os.mkdir(image_ref_directory)
    os.symlink(image_ref_directory, image_name_link)

    return image_ref_directory


def _prepare_argument_parser():
    """Prepare the argument parser."""
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--directory",
                        help="Directory that will hold the required files.")
    parser.add_argument("-i", "--image_ref",
                        help="Glance image-id to use for this run.")
    parser.add_argument("-f", "--flavor_ref",
                        help="The flavor id.")
    parser.add_argument("-t", "--tests", default="",
                        help="The tests you want to run.")
    parser.add_argument("-r", "--resources", default=ci.RESOURCES_LINK,
                        help="URL to Argus resources.")
    parser.add_argument("-p", "--parallel", type=int,
                        help="many processes to use in parallel.")
    parser.add_argument("-l", "--local",
                        help="Local git repository with all the Argus files.")
    parser.add_argument("-s", "--separate", action="store_true",
                        help="Make sepatate log files for each scenario.")
    parser.add_argument("-g", "--git_command", default="",
                        help="The git command that will test the "
                             "Cloudbase-Init patch.")
    parser.add_argument("-z", "--zip_patch", default="",
                        help="The zip patch to use when testing.")
    parser.add_argument("-c", "--config_file", default=None,
                        help="A config file that will be used when running"
                             " a scenario.")
    parser.add_argument("-a", "--architecture", default="x64",
                        help="The OS architecture.")
    parser.add_argument("--use_arestor", dest="use_arestor",
                        action='store_true',
                        help="Use arestor metadata.")
    return parser


def _prepare_environment(local, directory, resources_link, config_file):
    """Prepare the temp environment."""
    os.mkdir(os.path.join(directory, "ci"))

    testr_conf = os.path.join(directory, ".testr.conf")
    tests = os.path.join(directory, "ci", "tests.py")

    # Create the etc/argus directory structure
    config_file_directory = os.path.join(directory, "etc", "argus")
    os.makedirs(config_file_directory)
    config_file_path = os.path.join(config_file_directory, "argus.conf")

    if local:
        local = os.path.abspath(local)
        os.link(os.path.join(local, ".testr.conf"), testr_conf)
        os.link(os.path.join(local, "ci", "tests.py"), tests)
    else:
        # Download the necessary items
        download_argus_resource(".testr.conf", testr_conf, resources_link)
        download_argus_resource("ci/tests.py", tests, resources_link)

    if config_file:
        if not os.path.isabs(config_file):
            config_file = os.path.abspath(config_file)
        shutil.copyfile(config_file, config_file_path)

    # Create a new repository
    subprocess.Popen(["testr", "init"], cwd=directory, close_fds=True).wait()


def _prepare_config(separate, resources, flavor_ref,
                    git_command, zip_patch,
                    directory, image_ref, architecture, use_arestor):
    """Prepare the Argus config file."""

    conf = six.moves.configparser.SafeConfigParser()
    conf.add_section("argus")
    conf.add_section("openstack")

    conf.set("argus", "output_directory", os.path.join(directory, "output"))
    conf.set("argus", "argus_log_file", os.path.join(directory, "argus.log"))
    conf.set("argus", "git_command", str(git_command))
    conf.set("argus", "patch_install", str(zip_patch))
    conf.set("argus", "log_each_scenario", str(separate))
    conf.set("argus", "arch", str(architecture))
    conf.set("argus", "use_arestor", str(use_arestor))
    conf.set("openstack", "image_ref", str(image_ref))

    if resources:
        conf.set("argus", "resources", str(resources))

    if flavor_ref:
        conf.set("openstack", "flavor_ref", str(flavor_ref))

    config_path = os.path.join(directory, "argus.conf")
    with open(config_path, 'w') as file_handle:
        conf.write(file_handle)

    return config_path


def _start_testr(parallel, tests, directory):
    """Start running the tests."""

    cmd = ["testr", "run", str(tests)]
    if parallel:
        args = ["--parallel", "--concurrency={}".format(parallel)]
        cmd.extend(args)

    process = subprocess.Popen(cmd, cwd=directory, close_fds=True)
    return process


def main():
    """The main entry point."""
    parser = _prepare_argument_parser()
    args = parser.parse_args(sys.argv[1:])
    image_name = _get_image_name(args.image_ref)

    base_directory = _get_base_directory(args.directory, image_name,
                                         args.image_ref)

    print("Starting at {}".format(base_directory))

    _prepare_environment(args.local, base_directory, args.resources,
                         args.config_file)

    _prepare_config(args.separate, args.resources,
                    args.flavor_ref, args.git_command,
                    args.zip_patch, base_directory,
                    args.image_ref, args.architecture,
                    args.use_arestor)

    process = _start_testr(args.parallel, args.tests, base_directory)
    exit_code = process.wait()

    # generate subunit
    stream = os.path.join(base_directory,
                          ".testrepository", "0")
    output = os.path.join(base_directory,
                          "argus-results-{}.html".format(image_name))
    sys.argv[1] = stream
    sys.argv[2] = output

    subunit2html.main()

    return exit_code


if __name__ == "__main__":
    exit(main())
