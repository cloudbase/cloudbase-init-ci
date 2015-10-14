.. argus documentation master file, created by
   sphinx-quickstart on Fri Oct  9 15:30:46 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to argus's documentation!
=================================

**argus** is a framework for writing complex integration tests,
for code that needs to run under various different operating systems.
The tests themselves are running on a host, while the code that
is tested runs into virtual machine instances. The underlying technology
for spinning up new machines can be anything, as long as a wrapper
is written for it. We're using for now `OpenStack`_ based backends.

The project is actually used to test `cloudbase-init`_, a portable
multi-cloud initialization service, targeted to Windows platforms.


Contents:

.. toctree::
   :maxdepth: 2

   walkthrough.rst
   api.rst
   images.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


.. _cloudbase-init: https://github.com/stackforge/cloudbase-init
.. _OpenStack: http://www.openstack.org/