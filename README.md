argus-ci [![build status](https://api.travis-ci.org/PCManticore/argus-ci.svg?branch=master)](https://travis-ci.org/PCManticore/argus-ci)
========

Tempest integration gate for CloudbaseInit

#Prerequisites and installation steps
-------------------------------------

Installing and running argus should follow the next steps:

1. First, argus needs a clean Windows image, without cloudbaseinit installed.
  Preferrably, it should be created with the following [scripts](https://github.com/PCManticore/windows-openstack-imaging-tools).

  The scripts create a testing user, configures WinRM and so forth.
  It's not mandatory, but it is preferred to configure only WinRM for
  the HTTP transport, since we'll want to test if cloudbaseinit
  configures properly the HTTPS transport.
  
  Creating the image is as simple as:
  ```sh
  sudo ./create-autounattend-floppy.sh
  sudo ./create_img.sh
  ```
  Then, upload the image to glance and set the new image id
  in **argus.conf**.

2. tempest should be installed, on the node where argus is executed.
  A modern version of tempest is required (must have resource_cleanup and
  resource_setup hooks in `scenario.manager.BaseScenario`).

3. Don't forget to configure your **tempest.conf**; argus doesn't require any modification in tempest, except setting the
  public network id (it's not required to set the `image_ref` or `flavor_ref`,
  since they are provided in argus's own configuration).

4. Next, argus will require an **argus.conf** file. There is an example for it
  in *argus/etc*. The most important bits are `image_ref`, `flavor_ref` and
  `path_to_private_key`.

5. To run the tests, simply run the following command:
  ```sh
  argus --conf=<path to argus.conf>
  ```
  A test run will take usually up to 15 minutes.

6. If needed, you can test other patches, not just the installer, by executing the
  following command:
  ```sh 
  argus --conf=<path to argus.conf> --git-command=<git command>
  ```
  It's very important that `--git-command` should go after `--conf`.

  An example:
  ```sh
  argus --conf argus.conf --git-command "git fetch https://review.openstack.org/stackforge/cloudbase-init refs/changes/77/143277/1 && git checkout FETCH_HEAD"
  ```


Troubleshooting
---------------

* If the test fails with an error "Multiple possible networks found, use a Network ID to be more precise", that means
  that the used network is shared. Disable this by using the following command:
  ```sh
  neutron net-update <network id> --shared=false
  ```

* If it fails with an error like "No valid host was found", check the **screen-n-cpu.log** under */opt/stack/logs/screen*; maybe you ran out of disk space or you're having trouble with the AppArmor rights.

* Make sure you provide sufficient time for instance making in **tempest.conf** under */opt/stack/tempest/etc*, at least for the first build.
