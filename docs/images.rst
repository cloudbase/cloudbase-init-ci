How to create images for Argus - a short recipe
===============================================


In order to work properly, Argus needs specialized images, tailored for its needs.

The current document tries to describe what steps are necessary for
creating a proper image.

It assumes that the images are created using this repository
https://github.com/PCManticore/windows-openstack-imaging-tools,
instead of the original one, https://github.com/cloudbase/windows-openstack-imaging-tools,
which I was unable to make it work for our scenarios.

For Microsoft Nano Server there are other steps, look at the bottom.


1. First, grab an ISO with the OS you want to create an image for.

2. You might want to configure Autounattend.xml to suit your needs
   and to be in a format acceptable for the operating system you're
   working with. Make sure to use a proper product key in the <ProductKey>
   section.

3. Run ``sudo ./create-autounattend-floppy.sh``, which will use
   the aforementioned Autounattend.xml in order to create an Autounattend.vfd,
   which will be used as a floppy device later on by another script.

4. Modify create_img.sh and add the ISO and the qcow2 paths.

5. Run ``sudo ./create_img.sh``

6. If the Autounattend.xml was in a format known by the said OS,
   the installation should be automatic, requiring no manual input.
   Jump to the ``glance`` step. Otherwise, the following steps should
   be done manually or by customizing the installation scripts.

7. Install Powershell 3.0 if it's not installed already.
   The following document describes how to install it on
   multiple Windows versions: https://technet.microsoft.com/en-us/library/hh847837.aspx

8. Clone https://github.com/cloudbase/windows-openstack-imaging-tools somewhere
   in the created image.

9. Create the `CiAdmin` user with the password `Passw0rd` and make it
   an Administrator.

10. Execute `Set-ExecutionPolicy Bypass` in an Administrator Powershell instance,
    in order to support running scripts from argus.

11. Activate RDP support:

     - run SystemPropertiesAdvanced
     - go to the Remote tab
     - Activate `Allow remote connections to this computer`

12. Run ``.\install_git.ps1`` from the cloned repository.

13. Run ``.\Specialize.ps1`` from the cloned repository.

14. Run ``.\FirstLogon.ps1`` from the cloned repository.
    Depending on how old your OS is, just doing this won't be enough.
    This script will try to detect what virtio drivers are needed,
    but it might not support installing the latest version of virtio.
    
    You might take a look at this compatibility table, taken from
    https://pve.proxmox.com/wiki/Windows_VirtIO_Drivers


   +----------------------+-----------------+---------------------------+-----------------+
   | OS                   | Numeric Version | dir for Storage / Balloon | dir for network |
   +======================+=================+===========================+=================+
   | W2008 R2 / Windows 7 | 6.1             | Win7 (32/64)              | Win7 (32/64)    |
   +----------------------+-----------------+---------------------------+-----------------+
   | W2008 / Vista        | 6.0             | Wlh (32/64)               | Vista (32/64)   |
   +----------------------+-----------------+---------------------------+-----------------+
   | W2003                | 5.2             | Wnet (32/64)              | XP (32/64)      |
   +----------------------+-----------------+---------------------------+-----------------+


In some situations though, just installing these particular versions of virtio
will still lead to BSODs when trying to boot the image through openstack and
these combinations were found to be useful during our attempts to create new argus
images:


  +----------------------+-------------------------------------+----------------------------+
  | OS                   | virtio version for Storage / Ballon | virtio version for network |
  +======================+=====================================+============================+
  | W2008                |           0.54                      |   0.102 or latest          |           
  +----------------------+-------------------------------------+----------------------------+
  | W8.1                 |           0.102 or latest           |   0.94                     |           
  +----------------------+-------------------------------------+----------------------------+


15. Run ``.\Logon.ps1``. This script will configure WinRM and will finalize the image,
    by running sysprep.

16. After the creation script finished preparing the image, you can add it
    to glance and use its id in argus.conf.


Microsoft Nano Server
==================

1. You need to create a new Nano Server image, you can follow these steps 
https://github.com/cloudbase/cloudbase-init-offline-install. Take care to specify
that you don't want to install cloudbase-init ``-AddCloudbaseInit:$false``. 
You need to do this on a Windows host

You also need to create an image for KVM (the script will install the proper VirtIO drivers)
``-Platform KVM``.

3. Allow ping , SMB and create the CiAdmin User
   Mount the vhd and create this folder:
   ``C:\Windows\Setup\Scripts``
   Add there the ``PostInstall.ps1`` and ``SetupComplete.cmd`` that you can find in docs/resources.

4. Install Git 

  You need to download in a Windows machine Git for Windows Portable from
  https://git-scm.com/download/win, install it on that machine.

  Copy ``PortableGit`` on the same vhd in ``C:\Program Files\PortableGit``.

5. Now you can upload it using glance.

