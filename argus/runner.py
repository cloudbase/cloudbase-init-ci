# Copyright 2014 Cloudbase Solutions Srl
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

import functools
import itertools
import json
import os
import sys
import time
import unittest

from argus import exceptions
from argus import util


CONF = util.get_config()
# Use this logger to log both to standard output and to argus log file.
LOG = util.get_logger(name=__name__, format_string='%(message)s')
LOG.propagate = False


class _WritelnDecorator(object):
    """Used to decorate file-like objects with a handy 'writeln' method."""
    def __init__(self, stream):
        self.stream = stream

    def __getattr__(self, attr):
        if attr in ('stream', '__getstate__'):
            raise AttributeError(attr)
        return getattr(self.stream, attr)

    def writeln(self, arg=None):
        if arg:
            self.write(arg)
        self.write('\n')  # text-mode streams translate to \r\n if needed


class _TestResult(unittest.TextTestResult):
    def printErrorList(self, flavour, errors):
        for test, err in errors:
            LOG.info(self.separator1)
            LOG.info("%s: %s", flavour, self.getDescription(test))
            LOG.info(self.separator2)
            LOG.info("%s", err)


class Runner(object):
    """Scenarios runner class.

    Given a list of scenarios, this class iterates through each
    one and calls its underlying tests.
    """

    def __init__(self, scenarios, stream=None):
        self._scenarios = scenarios
        self._stream = _WritelnDecorator(stream or sys.stderr)

    def run(self):
        start_time = time.time()
        tests_run = 0
        expected_failures = unexpected_successes = skipped = 0
        failures = errors = 0

        # pylint: disable=redefined-outer-name
        for scenario in self._scenarios:
            try:
                result = scenario.run()
            except Exception:
                # Something failed internally, report this scenario
                # as failed and continue to the other ones.
                tests = list(scenario.test_names())
                errors += len(tests)
                LOG.exception('Scenario %r failed', scenario.name)
            else:
                result.printErrors()
                tests_run += result.testsRun
                expected_failures += len(result.expectedFailures)
                unexpected_successes += len(result.unexpectedSuccesses)
                skipped += len(result.skipped)
                failures += len(result.failures)
                errors += len(result.errors)

        time_taken = time.time() - start_time

        LOG.info("\nRan %d test%s in %.3fs",
                 tests_run, tests_run != 1 and "s" or "", time_taken)

        if failures or errors:
            head = "FAILED"
        else:
            head = "OK"

        infos = []

        if failures or errors:
            if failures:
                infos.append("failures=%d" % failures)
            if errors:
                infos.append("errors=%d" % errors)

        if skipped:
            infos.append("skipped=%d" % skipped)
        if expected_failures:
            infos.append("expected failures=%d" % expected_failures)
        if unexpected_successes:
            infos.append("unexpected successes=%d" % unexpected_successes)

        if infos:
            LOG.info("%s (%s)", head, ", ".join(infos))
        else:
            LOG.info(head)

        return failures or errors


def _load_userdata(userdata):
    userdata, is_argus, part = userdata.partition("argus.")
    if is_argus:
        userdata = util.get_resource(part.replace(".", "/"))
    else:
        with open(userdata, 'rb') as stream:
            userdata = stream.read()
    return userdata


def _load_metadata(metadata):
    if os.path.isfile(metadata):
        with open(metadata) as stream:
            return json.load(stream)
    return json.loads(metadata)


def _build_scenarios_classes(scenario):
    """Return generic scenarios classes available for further customization."""
    opts = util.parse_cli()
    if opts.instance_output:
        try:
            os.makedirs(opts.instance_output)
        except OSError:
            pass

    test_result = _TestResult(_WritelnDecorator(sys.stdout), None, 0)

    if scenario.userdata:
        userdata = _load_userdata(scenario.userdata)
    else:
        userdata = None
    metadata = _load_metadata(scenario.metadata)
    test_classes = list(map(util.load_qualified_object,
                            scenario.test_classes))
    recipe = util.load_qualified_object(scenario.recipe)
    scenario_class = util.load_qualified_object(scenario.scenario)
    introspection = util.load_qualified_object(scenario.introspection)

    environment_preparer = None
    if scenario.environment:
        environment_preparer = util.load_qualified_object(
            scenario.environment.preparer)
        environment_preparer = environment_preparer(
            scenario.environment.config.config_file,
            scenario.environment.config.values,
            scenario.environment.start_commands,
            scenario.environment.stop_commands,
            scenario.environment.list_services_commands,
            scenario.environment.filter_services_regexes,
            scenario.environment.start_service_command,
            scenario.environment.stop_service_command)

    partial_scenario = functools.partial(
        scenario_class,
        name=scenario.name,
        test_classes=test_classes,
        recipe=recipe,
        metadata=metadata,
        userdata=userdata,
        service_type=scenario.service_type,
        introspection=introspection,
        result=test_result,
        output_directory=opts.instance_output,
        environment_preparer=environment_preparer)
    return [functools.partial(partial_scenario, image=image)
            for image in scenario.images]


def _cloud_scenarios_builder(partial_scenarios):
    """Build cloud specific custom scenarios objects."""
    opts = util.parse_cli()
    builds = set(opts.builds) if opts.builds else {util.BUILDS.Beta}
    arches = set(opts.arches) if opts.arches else {util.ARCHES.x64}
    scenarios = []
    for partial_scenario in partial_scenarios:
        for build in builds:
            for arch in arches:
                scenario = partial_scenario()
                scenario.build = build
                scenario.arch = arch
                scenarios.append(scenario)
    return scenarios


def _filter_scenarios(scenarios):
    """Filter the given scenarios according to some rules.

    The rules are passed at command line and the following
    rules are known:

      * os_type

          Use a scenario only if the image has this OS.
          Multiple OSes can be filtered.

      * test_type: Use a scenario only if it uses a particular test type.
    """
    opts = util.parse_cli()

    # Filter by OS type
    os_types = opts.test_os_types
    if os_types:
        scenarios = [scenario for scenario in scenarios
                     if scenario.image.os_type in os_types]

    # Filter by test_type
    scenario_type = opts.test_scenario_type
    if scenario_type:
        scenarios = [scenario for scenario in scenarios
                     if scenario.type and scenario.type == scenario_type]
    return scenarios


def run_scenarios():
    """Run all the defined scenarios in the configuration file.

    The function will filter all scenarios according to the requested OSes
    and test type. By default, all scenarios are executed.
    """
    opts = util.parse_cli()
    scenarios_builder = SCENARIOS_BUILDERS[opts.scenarios_builder]
    conf_scenarios = _filter_scenarios(CONF.scenarios)
    argus_scenarios = itertools.chain.from_iterable((
        scenarios_builder(_build_scenarios_classes(scenario))
        for scenario in conf_scenarios))
    return Runner(argus_scenarios).run()


SCENARIOS_BUILDERS = {
    "cloud": _cloud_scenarios_builder
}
