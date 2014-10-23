#!/usr/bin/python -u

""" git threading hammer test """

import os
from multiprocessing import Pool, log_to_stderr
import logging
import tempfile
from shutil import rmtree
import subprocess
from time import sleep
from random import random
import itertools
import traceback
import sys
import logging

LOGGER = log_to_stderr()
LOGGER.setLevel(logging.WARN)
logging.basicConfig(level=logging.INFO)

# --- CONFIG START ---
REPO_SSH = "ssh://git@gitlab.citrite.net/craigem/testing.git"
REPO_HTTP = "http://gitlab.citrite.net/craigem/testing.git"
PROCS = 10
# --- CONFIG END ---
REPOS = [REPO_HTTP]

SSH_ERROR_CODE = 128
SSH_ERROR = "ssh_exchange_identification: Connection closed by remote host"

def ssh_safe_clone(repo, dname):
    """ catch ssh errors """
    tried = 0
    while True:
        proc = subprocess.Popen(["git", "clone", repo, dname], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=open(os.devnull))
        out = proc.communicate()[0]
        ret = proc.returncode
        tried += 1
        if ret != SSH_ERROR_CODE or SSH_ERROR not in out or tried == 100:
            return (ret, out)
        sleep(0.5)


def clone(repo, remove=True):
    """ clone something """
    dname = tempfile.mkdtemp(dir=os.path.join(tempfile.gettempdir(),'loadtest'))
    delay = 3.0 * random() # 0-3 seconds random delay
    #LOGGER.warn("In %0.3f seconds I'll clone %s into %s", delay, repo, dname)
    sleep(delay)
    (ret, out) = ssh_safe_clone(repo, dname)
    present = os.path.isdir(dname)
    if ret == 0:
        if present:
            msg = "worked"
        else:
            msg = "missing"
    else:
        msg = "failed (ret = %s)\n%s" % (ret, out)
    #LOGGER.warn("Cloning %s into %s %s", repo, dname, msg)
    if remove and present:
        rmtree(dname)
    return (ret, out, dname)


def clone_and_push_in_loop(repo):
    (ret,out,dpath) = clone(repo, remove=False)
    logging.info("Starting writable repo %s in %s ..." % (repo, dpath))
    if ret != 0:
       raise Exception("Fatal error on writable thread %s => %s: %s" % (repo, dpath, out))
    while True:
        # appending one line to a text file
        f = open(os.path.join(dpath, 'sample.txt'), "a")
        f.write("bla bla made from %s \n" % dpath)
        f.close
        sleep(1)

        proc = subprocess.Popen(["ls","-l"], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=open(os.devnull), cwd=dpath)
        (out,outerr) = proc.communicate()
        ret = proc.returncode
        print(ret, out, outerr)

        proc = subprocess.Popen(["git", "commit", "-a", "-m", "some-change"], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=open(os.devnull), cwd=dpath)
        (out,outerr) = proc.communicate()
        ret = proc.returncode
        print(ret, out, outerr)
        if ret:
           raise Exception("commit failed!: %s" % out)
        # pushing
        proc = subprocess.Popen(["git", "push"], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=open(os.devnull), cwd=dpath)
        (out,outerr) = proc.communicate()
        ret = proc.returncode
        print(ret, out, outerr)
        if ret:
           raise Exception("push failed: %s" % out)
        sleep(2)
    rmtree(dpath)

def main():
    """ main """

    logging.info("Starting writing thread...")
    testdir = os.path.join(tempfile.gettempdir(),'loadtest')
    wp = Pool(1)
    result = wp.map_async(clone_and_push_in_loop, [REPO_SSH] * 1)
    sleep(5)
    logging.info("Starting the load test on %s threads..." % PROCS)
    try:
        os.mkdir(testdir)
    except:
        pass

    try:
        for repo in REPOS:
            p = Pool(PROCS)
            result = p.map_async(clone, [repo] * PROCS) 
            failed = len(list(itertools.ifilter(lambda r: r[0] != 0, result.get(999999)))) # see http://stackoverflow.com/a/1408476/99834
            print "%s / %s failed" % (failed, PROCS)
            p.close()
            p.join()
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback,
                              limit=2, file=sys.stdout)
        #traceback.print_tb(e)
        #logging.error(e)
        print e
        try:
            os.removedirs(testdir)
        except:
            pass

    wp.close
    wp.join

if __name__ == "__main__":
    main()
