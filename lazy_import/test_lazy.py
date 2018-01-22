# -*- Mode: python; tab-width: 4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
#
# Testing for lazy_import --- https://github.com/mnmelo/lazy_import
# Copyright (C) 2017-2018 Manuel Nuno Melo
#
# This file is part of lazy_import.
#
#  lazy_import is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  lazy_import is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with lazy_import.  If not, see <http://www.gnu.org/licenses/>.
#

import pytest
import importlib
import sys
import six
from six.moves import range
import itertools
import string
import random
random.seed(42) # For consistency when parallel-testing

import lazy_import

# Shortcut to allow direct testing from within python

def run(np=None):
    if np is None:
        import multiprocessing
        np = multiprocessing.cpu_count()
    import os
    path = os.path.dirname(__file__)
    if np > 1:
        pytest.main(['-n', str(np), '--boxed', path])
    else:
        pytest.main(['--boxed', path])
###############################################################################
# Constants and util functions

RANDOM_PREFIX = "_lazy_test_"
RANDOM_ALPHABET = string.ascii_letters + string.digits
def random_str(size=5):
    # We make it start with a letter
    return "m" + ''.join(random.choice(RANDOM_ALPHABET) for _ in range(size))

def random_modname(submodules=0):
    while True:
        subname = ".".join(random_str() for _ in range(submodules + 1))
        modname = RANDOM_PREFIX + subname
        if modname in _GENERATED_NAMES or modname in sys.modules:
            continue
        _GENERATED_NAMES.append(modname)
        return modname 

class _TestLazyModule(lazy_import.LazyModule):
    pass

_GENERATED_NAMES = []
# Modules not usually loaded on startup. Must include at least one with
#  submodule
NAMES_EXISTING = ("sched", "distutils.core")

LEVELS = ("leaf", "base")
CLASSES = (_TestLazyModule, lazy_import.LazyModule)
CALLABLE_NAMES =("fn1", ("fn1"), ("fn1", "fn2"), ("fn1", "fn2", "fn3"))
ERROR_MSGS = (None, {"msg":"Module: {module}\n"
                           "Caller: {caller}\n"
                           "Install Name: {install_name}\n",
                     "msg_callable":"Module: {module}\n"
                           "Caller: {caller}\n"
                           "Install Name: {install_name}\n"
                           "Callable: {callable}\n",
                     "module":"error_modname",
                     "caller":"error_callername",
                     "install_name":"error_installname"})
CALLABLE_ALIASES = (lazy_import.lazy_callable,
        lazy_import.lazy_function, lazy_import.lazy_class)

###############################################################################
# Fixtures

@pytest.fixture(params=itertools.product(LEVELS, CLASSES, ERROR_MSGS))
def lazy_opts(request):
    return request.param

###############################################################################
# Re-usable tests

def _check_reuse(modname):
    curr_module_id = id(sys.modules[modname])
    newmod = importlib.import_module(modname)
    assert id(newmod) == curr_module_id

def _check_lazy_loading(modname):
    names = modname.split(".")
    _check_not_loaded(modname)
    basename = lazy_import.module_basename(modname)
    mod = lazy_import.lazy_module(modname, level="leaf")
    assert sys.modules[modname] is mod
    assert str(mod) == "Lazily-loaded module " + modname
    base = lazy_import.lazy_module(modname, level="base")
    assert sys.modules[basename] is base
    assert str(base) == "Lazily-loaded module " + basename

    # A subtle bug only rears its head if an actual import statement is done.
    # Can only test that for the module names we know of
    # (meaning, no random ones)
    if modname in NAMES_EXISTING:
        if modname == 'sched':
            import sched as newmod
        elif modname == 'distutils.core':
            import distutils.core as newmod
        assert str(newmod) == "Lazily-loaded module " + modname

    # Check that all submodules are in and that submodule access works
    curr_name = basename
    curr_mod = base
    for submod in names[1:]:
        curr_name += "." + submod
        curr_mod = getattr(curr_mod, submod)
        assert curr_name in sys.modules
        assert str(curr_mod) == "Lazily-loaded module " + curr_name
        assert isinstance(curr_mod, lazy_import.LazyModule)
        _check_reuse(curr_name)
        # Check that missing modules raise errors
        if modname in _GENERATED_NAMES:
            _check_module_missing(curr_mod)

def _check_module_missing(obj, msg=None, call=False):
    with pytest.raises(ImportError) as excinfo:
        if call:
            obj()
        else:
            obj.modattr
    if msg is not None:
        assert str(excinfo.value) == msg

def _check_callable_missing(obj, msg=None):
    with pytest.raises(AttributeError) as excinfo:
        obj()
    if msg is not None:
        assert str(excinfo.value) == msg

def _check_not_loaded(modname):
    assert modname not in sys.modules, \
        modname + " already loaded. Maybe use with pytest's xdist's '--boxed'?"

###############################################################################
# TESTS                              TESTS                              TESTS #
###############################################################################

@pytest.mark.parametrize("modname", tuple(random_modname(i) for i in range(3))
                                    + NAMES_EXISTING)
def test_lazyload(modname):
    _check_lazy_loading(modname)

def test_presentload():
    import os.path
    mod = lazy_import.lazy_module("os")
    assert mod is os
    mod = lazy_import.lazy_module("os.path")
    assert mod is os.path
    mod = lazy_import.lazy_module("os.path", level="base")
    assert mod is os
    assert not isinstance(mod, lazy_import.LazyModule)

@pytest.mark.parametrize("nsub", range(3))
def test_opts(nsub, lazy_opts):
    modname = random_modname(nsub)
    level, modclass, errors = lazy_opts
    mod = lazy_import.lazy_module(modname, error_strings=errors,
            lazy_mod_class=modclass, level=level)
    names = modname.split(".")
    basename = lazy_import.module_basename(modname)
    if level == "leaf":
        assert sys.modules[modname] is mod
        err_modname = modname
    elif level == "base":
        assert sys.modules[basename] is mod
        err_modname = basename
    else:
        raise ValueError("Unexpected value {} for 'level'".format(level))
    # Test the exception err msg
    assert isinstance(mod, modclass)
    if errors is None:
        expected_err = lazy_import._MSG.format(module=err_modname,
                                               caller=__name__,
                                               install_name=basename)
    else:
        expected_err = errors["msg"].format(**errors)
    _check_module_missing(mod, msg=expected_err)


@pytest.mark.parametrize("nsub, errors, cnames, fn",
        itertools.product(range(3), ERROR_MSGS, CALLABLE_NAMES,
            CALLABLE_ALIASES))
def test_callable_missing_module(nsub, errors, cnames, fn):
    modname = random_modname(nsub)
    basename = lazy_import.module_basename(modname)
    if isinstance(cnames, six.string_types):
        lazys = (fn(modname+"."+cnames, error_strings=errors),)
        cnames = (cnames, )
    else:
        lazys = fn(modname, *cnames, error_strings=errors)
    for lazy in lazys:
        if errors is None:
            expected_err = lazy_import._MSG.format(module=modname,
                                                   caller=__name__,
                                                   install_name=basename)
        else:
            expected_err = errors["msg"].format(**errors)
        _check_module_missing(lazy, msg=expected_err, call=True)
    
@pytest.mark.parametrize("modname, errors, cnames, fn",
        itertools.product(NAMES_EXISTING, ERROR_MSGS, CALLABLE_NAMES,
            CALLABLE_ALIASES))
def test_callable_missing(modname, errors, cnames, fn):
    _check_not_loaded(modname)
    basename = lazy_import.module_basename(modname)
    if isinstance(cnames, six.string_types):
        lazys = (fn(modname+"."+cnames, error_strings=errors),)
        cnames = (cnames, )
    else:
        lazys = fn(modname, *cnames, error_strings=errors)
    for lazy, cname in zip(lazys, cnames):
        if errors is None:
            expected_err = lazy_import._MSG_CALLABLE.format(module=modname,
                                                   caller=__name__,
                                                   install_name=basename,
                                                   callable=cname)
        else:
            errors['callable'] = cname
            expected_err = errors["msg_callable"].format(**errors)
        _check_callable_missing(lazy, msg=expected_err)
    

@pytest.mark.parametrize("modname",
                [modname for modname in NAMES_EXISTING if '.' in modname])
def test_load_lazysub_on_fullmodule(modname, lazy_opts):
    level, modclass, errors = lazy_opts
    base = modname.split('.')[0]
    # A fully loaded base...
    importlib.import_module(base)
    # and a lazy sub...
    mod = lazy_import.lazy_module(modname, error_strings=errors,
                                   lazy_mod_class=modclass, level=level)
    if level == 'base':
        assert not isinstance(mod, modclass)
    else:
        assert isinstance(mod, modclass)
