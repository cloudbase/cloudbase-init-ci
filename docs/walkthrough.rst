Getting started
===============

Before explaining how to use argus, first we must describe a
couple of concepts that argus uses.


Concepts
--------

First, *argus* is based on a concept of a **scenario**, which describes
what and how something should be tested. As a parallel with the unittest
module, you can view a scenario as a test case, composed of multiple
test methods. The scenario itself is composed of a couple of other
concepts, as well:

   * first, we have the concept of a **backend**, the underlying
     component which provides **virtual machine instances** to the scenario.
     An instance in this case can be anything: it can be an
     OpenStack instance, created with nova, it can be a
     docker container or a virtual machine created with Vagrant.

   * the second concept is the **introspection**, which provides
     a way for working with the instances created by the backend.

   * the instance can be prepared before running the tests
     by using a **recipe**, which describes the steps that
     are executed before running the actual tests.

   * finally, the scenario is composed of the tests themselves,
     which verifies that the expected things to test actually
     occurred into the instance.


Testing cloudbase-init
----------------------

Before writing our integration tests, we need to think a little
about what technologies we're planning to use. The current stack
that argus provides is tailored for interacting with Windows platforms,
but since the code is decoupled, other platforms can be easily
added by writing a couple of classes. The same can be said about
the backends that argus is currently exported, they can be easily
replaced with anything else, as long as the established API is used
for the new ones.

Let's take a simple example in order to see how a test scenario looks like.


::

    from argus.scenarios import base
    from argus.backends.tempest import tempest_backend
    from argus.introspection.cloud import windows as introspection
    from argus.recipe.cloud import recipe


    class BaseWindowsScenario(base.BaseScenario):

        backend_type = tempest_backend.BaseWindowsTempestBackend
        introspection_type = introspection.InstanceIntrospection
        recipe_type = recipe.CloudbaseinitRecipe
        service_type = 'http'
        userdata = None
        metadata = {}

Each of the scenarios we're planning to write must inherit from
the one provided in ``argus.scenarios.base``.
