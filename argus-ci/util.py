import base64
import subprocess

import six

from argus import remote_client
from tempest.openstack.common import log as logging

__all__ = (
    'WinRemoteClient',
    'decrypt_password',
    'run_once',
)


LOG = logging.getLogger('cbinit')


class WinRemoteClient(remote_client.WinRemoteClient):
    def run_verbose_wsman(self, cmd):
        """Run the given command and log anything it returns."""

        LOG.info("Running command", cmd)
        stdout, stderr, exit_code = self.run_wsman_cmd(cmd)

        LOG.info("The command returned the output %s", stdout)
        LOG.info("The stderr of the command was %s", stderr)
        LOG.info("The exit code of the command was %s", exit_code)
        return stdout


def decrypt_password(private_key, password):
    """Decode password and unencrypts it with private key.

    Requires openssl binary available in the path.
    """
    unencoded = base64.b64decode(password)
    cmd = ['openssl', 'rsautl', '-decrypt', '-inkey', private_key]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    out, err = proc.communicate(unencoded)
    proc.stdin.close()
    if proc.returncode:
        raise Exception("Failed calling openssl with error: {!r}"
                        .format(err))
    return out

# pylint: disable=dangerous-default-value
def run_once(func, state={}):
    """A memoization decorator, whose purpose is to cache calls."""
    @six.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return state[func]
        except KeyError:
            state[func] = result = func(*args, **kwargs)
            return result
    return wrapper


def trap_failure(func):
    """Call pdb.set_trace when an exception occurs."""
    @six.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BaseException:
            import pdb
            pdb.set_trace()
    return wrapper
