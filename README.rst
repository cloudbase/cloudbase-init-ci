argus-ci
========

.. image:: https://travis-ci.org/PCManticore/argus-ci.svg?branch=develop
    :target: https://travis-ci.org/PCManticore/argus-ci


argus-ci is a continuous integration framework, built atop of `Tempest`_
and `OpenStack`_. It's original purpose is to be a CI for the
`cloudbaseinit`_ project, but it's pretty decoupled and can be used
for other testing purposes.



Architecture
------------

argus uses the concept of **scenario**, which tests that certain behaviour
occurred in an instance.

A **scenario** is composed of the following things:

   - a **recipee**. A recipee is a class which knows how to prepare
     an instance, by installing required stuff, enabling privileges
     and so on. In the project, in ``argus.recipees.cloud`` there are
     recipees used in production for testing cloudbaseinit. Similar
     recipees can be provided.

   - an **image**, which is uploaded in glance.

   - **userdata**, which is passed in the instance, available
     for whatever cloud initialization service is running
     inside it.

   - **metadata**, which is information regarding configuration
     in OpenStack.

   - **service type**, which is the transport of the metadata
     in the instance.

   - **test classes**, which validates what happened in the instance.


argus will spin a new VM, using the provided image and then will
provision the new VM with the given recipee. After the recipee is
finished executing, the test classes are invoked, to validate what
happened in the instance. The test classes are nothing but
``unittest.TestCase`` classes, which uses a remote introspection mechanism
for working with the instance.

argus is driven by a config file, which describes what scenarios,
images and recipees are used. An example of such configuration file can be
seen in the ``etc`` folder. This is actually a configuration used in
production for testing cloudbaseinit.


Prerequisites and installation steps
------------------------------------



Installing and running argus should follow the next steps:

1. First, argus needs a configuration file. See the one provided
   in ``etc`` folder for an example. There should be at least
   one image defined and used and the image must be uploaded in glance.
   The image section has a couple of options which needs to be completed:

      * **default_ci_username**

        With what name argus should connect in the instance.
        For Windows images, argus will use the `WinRM`_ protocol,
        so make sure that the image has activated the HTTP port
        for this protocol.

      * **default_ci_password**

        The password for the default_ci_username.

      * **flavor_ref**

        A flavor which will be used as a template for the instance.

      * **os_type**

        The type of the OS that this image represents.

     Other options are used for testing cloudbaseinit.


  For testing cloudbaseinit, the image must be a clean Windows image,
  without cloudbaseinit installed.
  Preferrably, it should be created with the following
  `scripts`_.

  These scripts creates the default_ci_username, configures WinRM and so forth.
  It's not mandatory, but it is preferred to configure only WinRM for
  the HTTP transport, since we'll want to test if cloudbaseinit
  configures properly the HTTPS transport.

  Creating the image is as simple as:

  .. code-block:: sh

      $ sudo ./create-autounattend-floppy.sh
      $ sudo ./create_img.sh

  Then, upload the image to glance and set the new image id
  in **argus.conf**.

2. tempest should be installed, on the node where argus is executed.

3. Don't forget to configure your **tempest.conf**.
   argus doesn't require any modification in tempest, except setting the
   public network id (it's not required to set the `image_ref` or `flavor_ref`,
   since they are provided in argus's own configuration).

4. Next, argus will require an **argus.conf** file. There is an example for it
   in *argus/etc*.

5. To run the tests, simply run the following command:

   .. code-block:: sh

      $ argus --conf=<path to argus.conf>


6. If needed, you can test other patches, not just the installer,
   by executing the following command:

   .. code-block:: sh

      $ argus --conf=<path to argus.conf> --git-command=<git command>

   An example:

   .. code-block:: sh

      $ argus --conf argus.conf --git-command "git fetch https://review.openstack.org/stackforge/cloudbase-init refs/changes/77/143277/1 && git checkout FETCH_HEAD"


Troubleshooting
---------------

* If argus fails with an error "Multiple possible networks found, use a Network ID to be more precise",
  that means that the used network is shared.
  Disable this by using the following command:

  .. code-block:: sh

     $ neutron net-update <network id> --shared=false

* If it fails with an error like "No valid host was found", check the
  **screen-n-cpu.log** under */opt/stack/logs/screen*; maybe you ran out
  of disk space or you're having trouble with the AppArmor rights.

* Make sure you provide sufficient time for instance making in
  **tempest.conf** under */opt/stack/tempest/etc*, at least for
  the first build.



 .. _Tempest: http://git.openstack.org/cgit/openstack/tempest/
 .. _cloudbaseinit: https://github.com/stackforge/cloudbase-init
 .. _OpenStack: http://www.openstack.org/
 .. _WinRM: https://msdn.microsoft.com/en-us/library/aa384426%28v=vs.85%29.aspx
 .. _scripts: https://github.com/PCManticore/windows-openstack-imaging-tools
