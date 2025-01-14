#!/usr/bin/env python

"""
    Some path and shell utility methods.
"""

import os
import sys
import shutil
import string
import glob

import logging



#---- globals

log = logging.getLogger("sh")



#---- public interface

def isdir(dirname):
    r"""os.path.isdir() doesn't work for UNC mount points. Fake it.
    
    # For an existing mount point (want: isdir() == 1)
    os.path.ismount(r"\\netshare\apps") -> 1
    os.path.exists(r"\\netshare\apps") -> 0
    os.path.isdir(r"\\netshare\apps") -> 0
    os.listdir(r"\\netshare\apps") -> [...contents...]
    # For a non-existant mount point (want: isdir() == 0)
    os.path.ismount(r"\\netshare\foo") -> 1
    os.path.exists(r"\\netshare\foo") -> 0
    os.path.isdir(r"\\netshare\foo") -> 0
    os.listdir(r"\\netshare\foo") -> WindowsError
    # For an existing dir under a mount point (want: isdir() == 1)
    os.path.mount(r"\\netshare\apps\Komodo") -> 0
    os.path.exists(r"\\netshare\apps\Komodo") -> 1
    os.path.isdir(r"\\netshare\apps\Komodo") -> 1
    os.listdir(r"\\netshare\apps\Komodo") -> [...contents...]
    # For a non-existant dir/file under a mount point (want: isdir() == 0)
    os.path.ismount(r"\\netshare\apps\foo") -> 0
    os.path.exists(r"\\netshare\apps\foo") -> 0
    os.path.isdir(r"\\netshare\apps\foo") -> 0
    os.listdir(r"\\netshare\apps\foo") -> []  # as if empty contents
    # For an existing file under a mount point (want: isdir() == 0)
    os.path.ismount(r"\\netshare\apps\Komodo\latest.komodo-devel.txt") -> 0
    os.path.exists(r"\\netshare\apps\Komodo\latest.komodo-devel.txt") -> 1
    os.path.isdir(r"\\netshare\apps\Komodo\latest.komodo-devel.txt") -> 0
    os.listdir(r"\\netshare\apps\Komodo\latest.komodo-devel.txt") -> WindowsError
    """
    if sys.platform[:3] == 'win' and dirname[:2] == r'\\':
        if os.path.exists(dirname):
            return os.path.isdir(dirname)
        try:
            os.listdir(dirname)
        except WindowsError:
            return 0
        else:
            return os.path.ismount(dirname)
    else:
        return os.path.isdir(dirname)


def mkdir(newdir, mode=0777):
    """works the way a good mkdir should :)
        - already exists, silently complete
        - regular file in the way, raise an exception
        - parent directory(ies) does not exist, make them as well
    """
    if isdir(newdir):
        pass
    elif os.path.isfile(newdir):
        raise OSError("a file with the same name as the desired " \
                      "dir, '%s', already exists." % newdir)
    else:
        head, tail = os.path.split(newdir)
        if head and not isdir(head):
            mkdir(head, mode)
        if tail:
            log.debug('mkdir "%s"' % newdir)
            os.mkdir(newdir, mode)


def copy(src, dst):
    """works the way a good copy should :)
        - no source, raise an exception
        - destination directory, make a file in that dir named after src
        - source directory, recursively copy the directory to the destination
        - filename wildcarding allowed
    NOTE:
        - This copy CHANGES THE FILE ATTRIBUTES.
    """
    assert src != dst, "You are try to copy a file to itself. Bad you! "\
                       "src='%s' dst='%s'" % (src, dst)
    # determine if filename wildcarding is being used
    # (only raise error if non-wildcarded source file does not exist)
    if string.find(src, '*') != -1 or \
       string.find(src, '?') != -1 or \
       string.find(src, '[') != -1:
        usingWildcards = 1
        srcFiles = glob.glob(src)
    else:
        usingWildcards = 0
        srcFiles = [src]

    for srcFile in srcFiles:
        if os.path.isfile(srcFile):
            if usingWildcards:
                srcFileHead, srcFileTail = os.path.split(srcFile)
                srcHead, srcTail = os.path.split(src)
                dstHead, dstTail = os.path.split(dst)
                if dstTail == srcTail:
                    dstFile = os.path.join(dstHead, srcFileTail)
                else:
                    dstFile = os.path.join(dst, srcFileTail)
            else:
                dstFile = dst
            dstFileHead, dstFileTail = os.path.split(dstFile)
            if dstFileHead and not isdir(dstFileHead):
                mkdir(dstFileHead)
            if isdir(dstFile):
                dstFile = os.path.join(dstFile, os.path.basename(srcFile))
            if os.path.isfile(dstFile):
                # make sure 'dstFile' is writeable
                try:
                    os.chmod(dstFile, 0777)
                except OSError, ex:
                    log.warn(str(ex))
            log.debug('copy "%s" "%s"' % (srcFile, dstFile))
            try:
                shutil.copy(srcFile, dstFile)
            except OSError, ex:
                log.warn(str(ex))
            # make the new 'dstFile' writeable
            try:
                os.chmod(dstFile, 0777)
            except OSError, ex:
                log.warn(str(ex))
        elif isdir(srcFile):
            srcFiles = os.listdir(srcFile)
            if not os.path.exists(dst):
                mkdir(dst)
            for f in srcFiles:
                s = os.path.join(srcFile, f)
                d = os.path.join(dst, f)
                try:
                    copy(s, d)
                except (IOError, os.error), why:
                    raise OSError("Can't copy %s to %s: %s"\
                          % (repr(s), repr(d), str(why)))
        elif not usingWildcards:
            raise OSError("Source file %s does not exist" % repr(srcFile))


def _rmtreeOnError(rmFunction, filePath, excInfo):
    if excInfo[0] == OSError:
        # presuming because file is read-only
        os.chmod(filePath, 0777)
        rmFunction(filePath)

def rmtree(dirname):
    shutil.rmtree(dirname, 0, _rmtreeOnError)


def rm(path):
    """Remove the given path (be it a file or directory).
    
    Raises OSError if the given path does not exist. Can also raise an
    EnvironmentError if the path cannot be removed for some reason.
    """
    if path.find('*') != -1 or path.find('?') != -1 or path.find('[') != -1:
        paths = glob.glob(path)
        if not paths:
            raise OSError(2, "No such file or directory: '%s'" % path)
    else:
        paths = [path]    

    for path in paths:
        if os.path.isfile(path) or os.path.islink(path):
            try:
                os.remove(path)
            except OSError, ex:
                if ex.errno == 13: # OSError: [Errno 13] Permission denied
                    os.chmod(path, 0777)
                    os.remove(path)
                else:
                    raise
        elif os.path.isdir(path):
            for f in os.listdir(path):
                rm(os.path.join(path, f))
            os.rmdir(path)
        else:
            raise OSError(2, "No such file or directory", path)


