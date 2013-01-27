#!/usr/bin/env python

import os
import subprocess
import sys


KNOWN_LIVE_SUITES = [
    'client',
    'glance',
    'identity',
    'nova',
    'swift',
]


def ensure_tarmac_log_dir():
    """Hack-around tarmac not creating its own log directory."""
    try:
        os.makedirs(os.path.expanduser("~/logs/"))
    except OSError:
        # Could be already exists, or cannot create, either way, just continue
        pass


def create_tarmac_repository():
    """Try to ensure a shared repository for the code."""
    try:
        import bzrlib.branch
    except ImportError, e:
        sys.stderr.write('Could not import bzrlib to ensure a repository\n')
    try:
        b, _ = bzrlib.branch.Branch.open_containing('.')
    except:
        sys.stderr.write('Could not open local branch\n')
        return
    # By the time we get here, we've already branched everything from
    # launchpad. So if we aren't in a shared repository, we create one, and
    # fetch all the data into it, so it doesn't have to be fetched again.
    if b.repository.is_shared():
        return
    pwd = os.getcwd()
    expected_dir = 'src/launchpad.net/'
    offset = pwd.rfind(expected_dir)
    if offset == -1:
        sys.stderr.write('Could not find %r to create a shared repo\n')
        return
    path = pwd[:offset+len(expected_dir)]
    from bzrlib import controldir, transport, reconfigure
    repo_fmt = controldir.format_registry.make_bzrdir('default')
    trans = transport.get_transport(path)
    info = repo_fmt.initialize_on_transport_ex(trans, create_prefix=False,
        make_working_trees=True, shared_repo=True, force_new_repo=True,
        use_existing_dir=True,
        repo_format_name=repo_fmt.repository_format.get_format_string())
    repo = info[0]
    sys.stderr.write('Reconfiguring to use a shared repository\n')
    reconfiguration = reconfigure.Reconfigure.to_use_shared(b.bzrdir)
    reconfiguration.apply(False)


def ensure_juju_core_dependencies():
    """Ensure that juju-core and all dependencies have been installed."""
    # Note: This potentially overwrites goose while it is updating the world.
    # However, if we are targetting the trunk branch of goose, that should have
    # already been updated to the latest version by tarmac.
    # I don't quite see a way to reconcile that we want the latest juju-core
    # and all of the other dependencies, but we don't want to touch goose
    # itself. One option would be to have a split GOPATH. One installs the
    # latest juju-core and everything else. The other is where the
    # goose-under-test resides. So we don't add the goose-under-test to GOPATH,
    # call "go get", then add it to the GOPATH for the rest of the testing.
    cmd = ['go', 'get', '-u', 'launchpad.net/juju-core/...']
    sys.stderr.write('Running: %s\n' % (' '.join(cmd),))
    retcode = subprocess.call(cmd)
    if retcode != 0:
        sys.stderr.write('WARN: Failed to update launchpad.net/juju-core\n')


def tarmac_setup(opts):
    """Do all the bits of setup that need to happen for the tarmac bot."""
    ensure_tarmac_log_dir()
    create_tarmac_repository()
    ensure_juju_core_dependencies()


def setup_gopath():
    pwd = os.getcwd()
    offset = pwd.rfind('src/launchpad.net/goose')
    if offset == -1:
        sys.stderr.write('Could not find "src/launchpad.net/goose" in cwd: %s\n'
                         % (cwd,))
        sys.stderr.write('Unable to automatically set GOPATH\n')
        return
    add_gopath = pwd[:offset].rstrip('/')
    gopath = os.environ.get("GOPATH")
    if gopath:
        if add_gopath in gopath:
            return
        # Put this path first, so we know we are running these tests
        gopath = add_gopath + os.pathsep + gopath
    else:
        gopath = add_gopath
    sys.stderr.write('Setting GOPATH to: %s\n' % (gopath,))
    os.environ['GOPATH'] = gopath


def run_go_build(opts):
    go_build_cmd = ['go', 'build']
    sys.stderr.write('Running: %s\n' % (' '.join(go_build_cmd,)))
    retcode = subprocess.call(go_build_cmd)
    if retcode != 0:
        sys.stderr.write('FAIL: failed running go build\n')
    return retcode


def run_go_test(opts):
    go_test_cmd = ['go', 'test', './...']
    sys.stderr.write('Running: %s\n' % (' '.join(go_test_cmd,)))
    retcode = subprocess.call(go_test_cmd)
    if retcode != 0:
        sys.stderr.write('FAIL: failed running go build\n')
    return retcode


def run_live_tests(opts):
    """Run all of the live tests."""
    orig_wd = os.getcwd()
    final_retcode = 0
    for d in KNOWN_LIVE_SUITES:
        try:
            cmd = ['go', 'test', '-live', '-gocheck.v']
            sys.stderr.write('Running: %s in %s\n' % (' '.join(cmd), d))
            os.chdir(d)
            retcode = subprocess.call(cmd)
            if retcode != 0:
                sys.stderr.write('FAIL: Running live tests in %s\n' % (d,))
                final_retcode = retcode
        finally:
            os.chdir(orig_wd)


def main(args):
    import argparse
    p = argparse.ArgumentParser(description='Run the goose test suite')
    p.add_argument('--verbose', action='store_true', help='Be chatty')
    p.add_argument('--version', action='version', version='%(prog)s 0.1')
    p.add_argument('--tarmac', action='store_true',
        help="Pass this if the script is running as the tarmac bot."
             " This is used for stuff like ensuring repositories and"
             " logging directories are initialized.")
    p.add_argument('--live', action='store_true',
        help="Run tests against a live service.")

    opts = p.parse_args(args)
    setup_gopath()
    if opts.tarmac:
        tarmac_setup(opts)
    retcode = run_go_build(opts)
    if retcode != 0:
        return retcode
    retcode = run_go_test(opts)
    if retcode != 0:
        return retcode
    if opts.live:
        retcode = run_live_tests(opts)
        if retcode != 0:
            return retcode


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
