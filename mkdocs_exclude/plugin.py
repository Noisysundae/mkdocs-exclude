import fnmatch
import re
import os
import subprocess
import mkdocs
import mkdocs.plugins
import mkdocs.structure.files
from mkdocs.config.config_options import Type

class ExcludeDecider:
    def __init__(self, globs, regexes, include_globs, include_regexes, gitignore):
        self.globs = globs
        self.regexes = regexes
        self.include_globs = include_globs
        self.include_regexes = include_regexes
        self.gitignore = gitignore

    def is_include(self, file, abs_file):
        if not self._is_include(file):
            return False
        if self.gitignore and git_ignores_path(abs_file):
            return False
        # Windows reports filenames as eg.  a\\b\\c instead of a/b/c.
        # To make the same globs/regexes match filenames on Windows and
        # other OSes, let's try matching against converted filenames.
        # On the other hand, Unix actually allows filenames to contain
        # literal \\ characters (although it is rare), so we won't
        # always convert them.  We only convert if os.sep reports
        # something unusual.  Conversely, some future mkdocs might
        # report Windows filenames using / separators regardless of
        # os.sep, so we *always* test with / above.
        if os.sep != '/':
            filefix = file.replace(os.sep, '/')
            if not self._is_include(filefix):
                return False
        return True

    def _is_include(self, file):
        for g in self.include_globs:
            if fnmatch.fnmatchcase(file, g):
                return True
        for r in self.include_regexes:
            if re.match(r, file):
                return True
        for g in self.globs:
            if fnmatch.fnmatchcase(file, g):
                return False
        for r in self.regexes:
            if re.match(r, file):
                return False
        return True

def get_list_from_config(name, config):
    """ Gets a list item from config. If it doesn't exist, gets empty list.
    If it is not a list, wrap it in a list """
    result = config[name] or []
    if not isinstance(result, list):
        result = [result]
    return result

class Exclude(mkdocs.plugins.BasePlugin):
    """A mkdocs plugin that removes all matching files from the input list."""

    config_scheme = (
        ('glob', Type((str, list), default=None)),
        ('regex', Type((str, list), default=None)),
        ('include-glob', Type((str, list), default=None)),
        ('include-regex', Type((str, list), default=None)),
        ('gitignore', Type((bool,), default=False)),

    )

    def on_files(self, files, config):
        for k in self.config:
            for scheme in self.config_scheme:
                if scheme[0] == k:
                    break
            else:
                raise Exception("Configuration '%s' not found for exclude-plugin" % k)

        globs = get_list_from_config('glob', self.config)
        regexes = get_list_from_config('regex', self.config)
        include_globs = get_list_from_config('include-glob', self.config)
        include_regexes = get_list_from_config('include-regex', self.config)
        gitignore = self.config['gitignore']
        exclude_decider = ExcludeDecider(globs, regexes, include_globs, include_regexes, gitignore)
        out = []
        for i in files:
            name = i.src_path
            abs_name = i.abs_src_path
            if exclude_decider.is_include(name, abs_name):
                print("include:",name)
                out.append(i)
        return mkdocs.structure.files.Files(out)

def git_ignores_path(abs_path):
    r"""
    This is adapted from `pytest-gitignore
    <https://github.com/tgs/pytest-gitignore/blob/7dc7087f16dbc467435e08f7faeac64d7ee0f0a1/pytest_gitignore.py#L18-L35>`_,
    which, as of the adaptation, was `signaled as being in the public domain
    <https://github.com/tgs/pytest-gitignore/blob/7dc7087f16dbc467435e08f7faeac64d7ee0f0a1/LICENSE>`_.
    """
    if os.path.basename(abs_path) == '.git':  # Ignore .git directory
        return True
    cmd = ['git', 'check-ignore', abs_path]
    result = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True)
    status = result.returncode
    # Possible return values: (via git help check-ignore)
    #    0: Yes, the file is ignored
    #    1: No, the file isn't ignored
    #  128: Fatal error, git can't tell us whether to ignore
    #
    # The latter happens a lot with python virtualenvs, since they have
    # symlinks and git gives up when you try to follow one.  But maybe you have
    # a test directory that you include with a symlink, who knows?  So we treat
    # the file as not-ignored.
    return status == 0
