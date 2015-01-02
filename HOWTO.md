#Prerequisites and installation steps
-------------------------------------

Installing and running argus should follow the next steps:


* First, argus needs a clean Windows image, without cloudbaseinit installed.
  Preferrably, it should be created with the following scripts:

  https://github.com/PCManticore/windows-openstack-imaging-tools

  The scripts creates a testing user, configures WinRM and so forth.
  It's not mandatory, but it is preferred to configure only WinRM for
  the HTTP transport, since we'll want to test that cloudbaseinit
  configures properly the HTTPS transport.
  
  Creating the image is as simple as:
  ```sh
  sudo ./create-autounattend-floppy.sh
  sudo ./create_img.sh
  ```
  Then, upload the image to glance and set the new image id
  in `argus.conf`.

* tempest should be installed, on the node where argus is executed.
  A modern version of tempest is required (must have resource_cleanup and
  resource_setup hooks in scenario.manager.BaseScenario).

* argus doesn't require any modification in tempest, except setting the
  public network id (it's not required to set the `image_ref` or `flavor_ref`,
  since they are provided in argus's own configuration).

* next, argus will require an `argus.conf` file. There is an example for it
  in `argus/etc`. The most important bits are `image_ref`, `flavor_ref` and
  `path_to_private_key`.

* to run the tests, simply run the following command:
  ```sh
  argus --conf=<path to argus.conf>
  ```
  A test run will take usually up to 15 minutes.

* if needed, you can test other patches, not just the installer, by executing the
  following command:
  ```sh 
  argus --conf=<path to argus.conf> --git-command=<git command>
  ```
  It's very important that `--git-command` should go after `--conf`.

  An example:
  ```sh
  argus --conf argus.conf --git-command "git fetch https://review.openstack.org/stackforge/cloudbase-init refs/changes/77/143277/1 && git checkout FETCH_HEAD"
  ```
  This will work only if you set `replace_code` option in `argus.conf` to `True`.
