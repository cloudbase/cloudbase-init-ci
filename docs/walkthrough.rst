Getting started
===============

Before explaining how to use argus, first we must describe a
couple of concepts that argus uses.


Concepts
^^^^^^^^

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
     a way for interactiong with the instances created by the backend.
     This usually means establishing a communication channel
     from the host to the instance.

   * the instance can be prepared before running the tests
     by using a **recipe**, which describes the steps that
     are executed before running the actual tests.

   * finally, the scenario is composed of the tests themselves,
     which verifies that the expected things to test actually
     occurred into the instance.

In the next section, we'll see how one can write a scenario
with a couple of tests.



Writing integration tests
^^^^^^^^^^^^^^^^^^^^^^^^^

Before writing our integration tests, we need to think a little
about what technologies we're planning to use. The current stack
that argus provides is tailored for interacting with Windows platforms,
but since the code is decoupled, other platforms can be easily
added by writing a couple of classes. The same can be said about
the backends that argus is currently exported, they can be easily
replaced with anything else, as long as the established API is used
for the new ones.


The backend
-----------

We were saying in the previous section that a backend
is used in order to spin up new VMs, which will be used to run
our application code and the tests were writing will be verifying
that what happened in them was actually what we were expecting
to be happening. In other words, the tests will run on the host,
while the application code will run in the VM, which means that we
can do almost anything in those VMs.


The base backend class in argus in :class:`argus.backends.base.BaseBackend`,
which provides only three public methods,
:meth:`argus.backends.base.BaseBackend.setup_instance` for creating an
instance, :meth:`argus.backends.base.BaseBackend.cleanup` for
destroying it and :meth:`argus.backends.base.BaseBackend.get_remote_client`
for obtaining a client that can *talk* with our instances.

There is no requirement about how the client needs to look,
only that it needs to implement a method through which a command
can be executed on the instance. This means that we can use any protocol
we want as long as it is supported by the instance's OS (SSH for instance
can work great for Unix based systems, while WinRM can be used for Windows).

Let's take an example where we're using OpenStack and its **nova**
component as our VMs provider.

Finding what images we have available is as easy as running this command:

.. code-block:: sh


  $ nova image-list
  +--------------------------------------+-----------+--------+--------+
  |                  ID                  |    Name   | Status | Server |
  +--------------------------------------+-----------+--------+--------+
  | 17a34b8e-c573-48d6-920c-b4b450172b41 | Windows 8 | ACTIVE |        |
  +--------------------------------------+-----------+--------+--------+

Creating a new instance will look like this:

.. code-block:: sh


  $ nova boot --flavor 2 --image 17a34b8e-c573-48d6-920c-b4b450172b41 windows-10
  +------------------------+--------------------------------------+
  |        Property        |                Value                 |
  +------------------------+--------------------------------------+
  | id                     | 0e4011a4-3128-4674-ab16-dd1b7ecc126e |
  | ...                    |                ....                  |
  +------------------------+--------------------------------------+

While destroying a new instance usually is as simple as:

.. code-block:: sh

  $ nova delete 0e4011a4-3128-4674-ab16-dd1b7ecc126e


Knowing this, our nova backend can look like this:

::

  import subprocess

  from argus.backends.base import BaseBackend
  from argus.client.windows import WinRemoteClient


  class NovaBackend(BaseBackend):

      def prepare_instance(self):
          flavor_id = self._conf.openstack.flavor_ref
          image_id = self._conf.openstack.image_ref
          command = ["nova", "boot", "--flavor", flavor_ref,
                     "--image", image_ref, self._name]
          popen = subprocess.call(command, out=subprocess.PIPE)
          self._instance_id = _get_the_instance_id(popen)
          

      def cleanup(self):
          subprocess.call(["nova", "delete", self._instance_id])

      def get_remote_client(self, username, password, **kwargs):
          """Get a client to the underlying instance using username and password."""
          return WinRemoteClient(self._instance_floating_ip,
                                 username, password)


The recipe
----------

Now that our backend is capable of spinning up new VMs, let's see
how can we prepare them in order to test our application code.

Preparing an instance is the duty of a *recipe*, argus providing
a base class for them in :class:`argus.recipes.base.BaseRecipe`.
This class provides only one public method, 
:meth:`argus.recipes.base.BaseRecipe.prepare`, which will be called
when the scenario wants to prepare an instance. The recipe itself
will be initialized with a configuration object (where argus will
hold all its settings) and the backend we specified in the scenario.

The recipe will use backend's underlying remote client in order to talk
with the instance.

Let's see how can we write a very simple recipe, that does nothing
but to create a file before running our application code.

::

  from argus.recipe.base import BaseRecipe

  class MyBasicRecipe(BaseRecipe):

      def prepare(self, **kwargs):
          install_python = "..."
          self._backend.remote_client.run_remote_cmd(install_python)

That's all really. Now of course you can do almost anything with the
recipe, by running commands into the underlying instance. This really
means that when our application code runs, our environment can be
fully prepared to accomodate its needs.


The tests
---------

This will be the simplest part when writing integration tests using
argus. As mentioned earlier, the tests are nothing more than
unittest-like tests on steroids, so they should be pretty familiar
to anyone who wrote unittests in their career. As a note, the tests
themselves will run on the host where argus is installed, not in
the VM instances spinned up by the backend and they are used for
testing that something occurred, as expected, in those instances.


Let's write a test which verifies for instance that our
application created a bunch of expected files on the root drive
of the operating system.

::

  from argus.tests import base


  class MyTest(base.BaseTestCase):

      def test_files_created(self):
           list_files_cmd = "..."
           files = self._backend.remote_client.run_remote_cmd(list_files_cmd)
           self.assertIn(some_file, files)


Just with this code, we now have all the required components that can be
used to form a very simple argus integration tests workflow.


The scenario
------------

The final step is to write the scenario, which will use all the
other components we mentioned so far.

::

  from argus.scenarios.base import BaseScenario

  class MyScenario(BaseScenario):

      backend_type = NovaBackend
      recipe_type = MyBasicRecipe
      test_classes = (MyTest, )


That's it! Point your favorite Python test runner to a file which contains
this setup for your integration tests to run.
