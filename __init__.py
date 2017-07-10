# -*- Mode: python; tab-width: 4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
#
# lazy_import --- https://github.com/mnmelo/lazy_import
# Copyright (c) 2017 Manuel Nuno Melo
#
# Released under the GNU Public Licence, v3 or any higher version
#
# This module was based on code from the importing module from the PEAK
# package (see http://peak.telecommunity.com/DevCenter/FrontPage). The PEAK
# package is released under the following license, reproduced here:
#
#  Copyright (C) 1996-2004 by Phillip J. Eby and Tyler C. Sarna.
#  All rights reserved.  This software may be used under the same terms
#  as Zope or Python.  THERE ARE ABSOLUTELY NO WARRANTIES OF ANY KIND.
#  Code quality varies between modules, from "beta" to "experimental
#  pre-alpha".  :)
#
# The following list summarizes the modifications to the importing code:
#  - a replacement of lazyModule (import_module, which defers most work to
#    _import_module) is implemented that uses an alternative LazyModule class;
#  - a different LazyModule class is created per instance, so that reverting
#    the __getattribute__ behavior can be done safely;
#  - a function to lazily import module functions was added.


"""
Lazy module loading
===================

Functions and classes for lazy module loading that also delay import errors.
Heavily borrowed from the `importing`_ module.

.. _`importing`: http://peak.telecommunity.com/DevCenter/Importing

Files and directories
---------------------

.. autofunction:: import_module
.. autofunction:: import_function

"""

__all__ = ['import_module', 'import_function']

from types import ModuleType
import sys
try:
    # imp is deprecated since python 3.4 but there's no clear alternative to
    # the lock mechanism, other than to import directly from _imp.
    from imp import acquire_lock, release_lock 
except ImportError:
    from _imp import acquire_lock, release_lock 

import six
from six.moves import reload_module


################################
# Module/function registration #
################################

#### Lazy classes ####

class LazyModule(ModuleType):
    """Class for lazily-loaded modules that triggers proper loading on access.

    Instantiation should be made from a subclass of :class:`LazyModule`, with
    one subclass per instantiated module. Regular attribute set/access can then
    be recovered by setting the subclass's :meth:`__getattribute__` and
    :meth:`__setattribute__` to those of :class:`types.ModuleType`.
    """
    # peak.util.imports sets __slots__ to (), but it seems pointless because
    # the base ModuleType doesn't itself set __slots__.
    def __init__(self, modname):
        super(ModuleType, self).__setattr__('__name__', modname)

    def __getattribute__(self, attr):
        # IPython tries to be too clever and constantly inspects, asking for
        #  modules' attrs, which causes premature module loading and unesthetic
        #  internal errors if the lazily-loaded module doesn't exist. Returning
        #  Nones seems to satisfy those needs:
        #caller_base = module_basename(_caller_name())
        #if (attr in ('__spec__', '__path__') or
        #    (run_from_ipython() and caller_base in ('inspect', 'IPython'))):
        #    return None
        try:
            modclass = type(self)
            return modclass._lazy_import_funcs[attr]
        except (AttributeError, KeyError):
            _load_module(self)
        return ModuleType.__getattribute__(self, attr)

    def __setattr__(self, attr, value):
        _load_module(self)
        return ModuleType.__setattr__(self, attr, value)


class LazyFunction(object):
    """Class for lazily-loaded functions that triggers module loading on access

    """
    def __init__(self, module, funcname):
        self.module = module
        self.modclass = type(self.module)
        self.funcname = funcname
        self.fn = None

    def __call__(self, *args, **kwargs):
        # No need to go through all the reloading more than once.
        if self.fn:
            return self.fn(*args, **kwargs)
        try:
            del self.modclass._lazy_import_funcs[self.funcname]
        except (AttributeError, KeyError):
            pass
        try:
            self.fn = getattr(self.module, self.funcname)
        except AttributeError:
            msg = modclass._lazy_import_error_msgs['msg_fn']
            raise AttributeError(msg.format(
                                 **self.modclass._lazy_import_error_strings))
        except ImportError:
            # Import failed. We reset the dict and re-raise the ImportError.
            try:
                self.modclass._lazy_import_funcs[self.funcname] = self
            except AttributeError:
                self.modclass._lazy_import_funcs = {self.funcname: self}
            raise
        else:
            return self.fn(*args, **kwargs)


### Functions ###

def import_module(modname, error_strings=None, lazy_class=LazyModule,
                  level='leaf'):
    """Function allowing lazy importing of a module into the namespace.

    A lazy module object is created, registered in `sys.modules`, and
    returned. This is a hollow module; actual loading, and `ImportErrors` if
    not found, are delayed until an attempt is made to access attributes of the
    lazy module.

    A handy application is to use :func:`import_module` early in your own code
    (say, in `__init__.py`) to register all modulenames you want to be lazy.
    Because of registration in `sys.modules` later invocations of
    `import modulename` will also return the lazy object. This means that after
    initial registration the rest of your code can use regular pyhon import
    statements and retain the lazyness of the modules.

    Parameters
    ----------
    modname : str
         The module to import.
    error_strings : dict, optional
         A dictionary of strings to use when module-loading fails. Key 'msg'
         sets the message to use (defaults to :attr:`lazy_import._MSG`). The
         message is formatted using the remaining dictionary keys: the default
         message informs the user of which module is missing (key 'module'),
         what code loaded the module as lazy (key 'caller'), and which package
         should be installed to solve the dependency (key 'install_name').
         None of the keys is mandatory and all are given smart names by default.
    lazy_class: type, optional
         Which class to use when instantiating the lazy module, to allow
         deep customization. The default is :class:`LazyModule` and custom
         alternatives **must** be a subclass thereof.
    level : str, optional
         Which submodule reference to return. Either a reference to the 'leaf'
         module (the default) or to the 'base' module. This is useful if you'll
         be using the module functionality in the same place you're calling
         :func:`import_module` from, since then you don't need to run `import`
         again. Setting *level* does not affect which names/modules get
         registered in `sys.modules`.
         For *level* set to 'base' and *modulename* 'aaa.bbb.ccc'::

            aaa = import_module("aaa.bbb.ccc", level='base')
            # 'aaa' becomes defined in the current namespace, with
            #  (sub)attributes 'aaa.bbb' and 'aaa.bbb.ccc'.
            # It's the lazy equivalent to:
            import aaa.bbb.ccc

        For *level* set to 'leaf'::

            ccc = import_module("aaa.bbb.ccc", level='leaf')
            # Only 'ccc' becomes set in the current namespace.
            # Lazy equivalent to:
            from aaa.bbb import ccc

    Returns
    -------
    module
        The module specified by *modname*, or its base, depending on *level*.
        The module isn't immediately imported. Instead, an instance of
        *lazy_class* is returned. Upon access to any of its attributes, the
        module is finally loaded.

    See Also
    --------
    :func:`import_function`
    :class:`LazyModule`

    """
    if error_strings is None:
        error_strings = {}
    _set_default_errornames(modname, error_strings)

    mod = _import_module(modname, error_strings, lazy_class)
    if level == 'base':
        return sys.modules[module_basename(modname)]
    elif level == 'leaf':
        return mod
    else:
        raise ValueError("Parameter 'level' must be one of ('base', 'leaf')")


def _import_module(modname, error_strings, lazy_class):
    acquire_lock()
    try:
        fullmodname = modname
        fullsubmodname = None
        # ensure parent module/package is in sys.modules
        # and parent.modname=module, as soon as the parent is imported   
        while modname:
            try:
                mod = sys.modules[modname]
                # We reached a (base) module that's already loaded. Let's stop
                # the cycle.
                modname = ''
            except KeyError:
                err_s = error_strings.copy()
                class _LazyModule(lazy_class):
                    _lazy_import_error_msgs = {'msg': err_s.pop('msg')}
                    try:
                        _lazy_import_error_msgs['msg_fn'] = err_s.pop('msg_fn')
                    except KeyError:
                        pass
                    _lazy_import_error_strings = err_s
                    _lazy_import_funcs = {}
                mod = sys.modules[modname] = _LazyModule(modname)
            if fullsubmodname:
                ModuleType.__setattr__(mod, submodname,
                                       sys.modules[fullsubmodname])
            fullsubmodname = modname
            modname, _, submodname = modname.rpartition('.')
        return sys.modules[fullmodname]
    finally:
        release_lock()


def import_function(modname, *funcnames, **kwargs):
    """Performs lazy importing of one or more functions into the namespace.

    Parameters
    ----------
    modname : str
         The base module from where to import the function(s) in *funcnames*,
         or a full 'module_name.function_name' string.
    funcnames : str (optional)
         The function name(s) to import from the module specified by *modname*.
         If left empty, *modname* is assumed to also include the function name
         to import.
    error_strings : dict, optional
         A dictionary of strings to use when reporting loading errors (either a
         missing module, or a missing function name in the loaded module).
         *error_string* follows the same usage as described under
         :func:`import_module`, with the exceptions that 1) a further key,
         'msg_fn', can be supplied to be used as the error when a module is
         successfully loaded but the target function can't be found therein
         (defaulting to :attr:`lazy_import._MSG_FN`); 2) a key 'function' is
         always added with the function name being loaded.
    lazy_class : type, optional
         See definition under :func:`import_module`.
    lazy_fn_class : type, optional
         Analogously to *lazy_class*, allows setting a custom class to handle
         lazy functions, other than the default :class:`LazyFunction`.

    Returns
    -------
    function or list of functions
        If *funcnames* is passed, returns a list of imported functions, one for
        each element in *funcnames*.
        If only *modname* is passed it is assumed to be a full
        'module_name.function_name' string, in which case the imported function
        is returned directly, and not in a list.
        The module specified by *modname* is always imported lazily, via the
        same mechanism as :func:`import_module`.
        
    See Also
    --------
    :func:`import_module`
    :class:`LazyFunction`
    :class:`LazyModule`

    """
    if not funcnames:
        modname, _, funcname = modname.rpartition(".")
    lazy_class = _setdef(kwargs, 'lazy_class', LazyModule)
    lazy_fn_class = _setdef(kwargs, 'lazy_fn_class', LazyFunction)
    error_strings = _setdef(kwargs, 'error_strings', {})
    _set_default_errornames(modname, error_strings, fn=True)

    if not funcnames:
        # We allow passing a single string as 'modname.funcname',
        # in which case the function is returned directly and not as a list.
        return _import_function(modname, funcname, error_strings.copy(),
                                lazy_class, lazy_fn_class)
    return [_import_function(modname, fn, error_strings.copy(),
                             lazy_class, lazy_fn_class) for fn in funcnames]


def _import_function(modname, funcname, error_strings,
                     lazy_class, lazy_fn_class):
    # We could do most of this in the LazyFunction __init__, but here we can
    # pre-check whether to actually be lazy or not.
    error_strings['function'] = funcname
    module = _import_module(modname, error_strings, lazy_class)
    modclass = type(module)
    if (issubclass(modclass, LazyModule) and
        hasattr(modclass, '_lazy_import_funcs')):
        modclass._lazy_import_funcs.setdefault(
            funcname, lazy_fn_class(module, funcname))
    return getattr(module, funcname)


#######################
# Real module loading #
#######################

def _load_module(module):
    """Ensures that a module, and its parents, are properly loaded

    """
    modclass = type(module)
    # We only take care of our own LazyModule instances
    if not issubclass(modclass, LazyModule):
        return
    acquire_lock()
    try:
        # We first identify whether this is a loadable LazyModule, then we
        # strip as much of lazy_import behavior as possible (keeping it cached,
        # in case loading fails and we need to reset the lazy state).
        if not hasattr(modclass, '_lazy_import_error_msgs'):
            # Alreay loaded (no _lazy_import_error_msgs attr). Not reloading.
            return
        cached_data = _clean_lazymodule(modclass)

        # First, ensure the parent is loaded (using recursion; *very* unlikely
        # we'll ever hit a stack limit in this case).
        parent, _, modname = module.__name__.rpartition('.')
        try:
            if parent:
                _load_module(sys.modules[parent])
                setattr(sys.modules[parent], modname, module)
            # Get Python to do the real import!
            reload_module(module)           
        except:
            # Loading failed. We reset our lazy state.
            _reset_lazymodule(modclass, cached_data)
            raise
    except (AttributeError, ImportError) as err:
        # Under Python 3 reloading our dummy LazyModule instances causes an
        # AttributeError if the module can't be found. Would be preferrable if
        # we could always rely on an ImportError. As it is we vet the
        # AttributeError as thoroughly as possible.
        if not (six.PY3 and isinstance(err, AttributeError) and
                 err.args[0] == "'NoneType' object has no attribute 'name'"):
            # Not the AttributeError we were looking for.
            raise
        msg = modclass._lazy_import_error_msgs['msg']
        # Way to silence context tracebacks in Python3 but with a syntax
        # compatible with Python2. This would normally be:
        #  raise ImportError(...) from None
        exc = ImportError(msg.format(**modclass._lazy_import_error_strings))
        exc.__suppress_context__ = True
        raise exc
    finally:
        release_lock()


##############################
# Helper functions/constants #
##############################

_MSG = ("{caller} attempted to use a functionality that requires module "
        "{module}, but it couldn't be loaded. Please install {install_name} "
        "and retry.")

_MSG_FN = ("{caller} attempted to use a functionality that requires function "
           "{function} of module {module}, but it couldn't be found in that "
           "module. Please install a version of {install_name} that has "
           "{module}.{function} and retry.")

_CLS_ATTRS = ("_lazy_import_error_strings", "_lazy_import_error_msgs",
              "_lazy_import_funcs")

def _setdef(argdict, name, defaultvalue):
    """Like dict.setdefault but sets the default value also if None is present.

    """
    if not name in argdict or argdict['name'] is None:
        argdict[name] = defaultvalue
    return argdict[name]


def module_basename(modname):
    return modname.partition('.')[0]


def _set_default_errornames(modname, error_strings, fn=False):
    error_strings.setdefault('module', modname)
    error_strings.setdefault('caller', _caller_name(3, default='Python'))
    error_strings.setdefault('install_name', module_basename(modname))
    error_strings.setdefault('msg', _MSG)
    if fn:
        error_strings.setdefault('msg_fn', _MSG_FN)


def _caller_name(depth=2, default=''):
    """Returns the name of the calling namespace.

    """
    # the presence of sys._getframe might be implementation-dependent.
    # It isn't that serious if we can't get the caller's name.
    try:
        return sys._getframe(depth).f_globals['__name__']
    except AttributeError:
        return default


def _clean_lazymodule(modclass):
    """Removes all lazy behavior from a module's class, for loading.

    Returns
    -------
    dict
        A dictionary of deleted class attributes, that can be used to reset the
        lazy state using :func:`_reset_lazymodule`.
    """
    modclass.__getattribute__ = ModuleType.__getattribute__
    modclass.__setattr__ = ModuleType.__setattr__
    cls_attrs = {}
    for cls_attr in _CLS_ATTRS:
        try:
            cls_attrs[cls_attr] = getattr(modclass, cls_attr)
            delattr(modclass, cls_attr)
        except AttributeError:
            pass
    return cls_attrs


def _reset_lazymodule(modclass, cls_attrs):
    """Resets a module's lazy state from cached data.

    """
    del modclass.__getattribute__
    del modclass.__setattr__
    for cls_attr in _CLS_ATTRS:
        try:
            setattr(modclass, cls_attr, cls_attrs[cls_attr])
        except KeyError:
            pass


def run_from_ipython():
    # Taken from https://stackoverflow.com/questions/5376837
    try:
        __IPYTHON__
        return True
    except NameError:
        return False


