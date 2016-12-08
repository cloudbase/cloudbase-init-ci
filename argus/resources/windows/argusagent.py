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
import base64
import sys
import zipfile


def initialize_parser_args():
    """Returns a prepared argument parser."""
    parser = argparse.ArgumentParser(description="Utilities needed by Argus")
    parser.add_argument("--encode", type=str, nargs="*",
                        help="return an encoded base64 string")
    parser.add_argument("--archive", type=str, nargs="*",
                        help="archive given file")
    parser_args = parser.parse_args()
    return parser_args


def base64_read_file(filepath):
    """Reads the given filepath and writes the content as a base64 string."""
    with open(filepath, 'rb') as stream:
        data = stream.read()
    file_64_encode = base64.standard_b64encode(data)
    sys.stdout.write(file_64_encode.decode('utf-8'))
    sys.stdout.flush()


def archive_file(filepath, archivepath):
    """Archives and compresses a given file path."""
    with zipfile.ZipFile(archivepath, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(filepath)


if __name__ == "__main__":
    args = initialize_parser_args()
    if args.encode:
        base64_read_file(args.encode[0])
    if args.archive:
        archive_file(args.archive[0], args.archive[1])
