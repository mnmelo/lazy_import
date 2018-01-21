lazy_import
===========

|Build Status|

``lazy_import`` provides a set of functions that load modules, and related
attributes, in a lazy fashion. This allows deferring of ``ImportErrors`` to
actual module use-time. Likewise, actual module initialization only takes place
at use-time. This is useful when using optional dependencies with heavy loading
times and/or footprints, since that cost is only paid if the module is actually
used.

For minimal impact to other code running in the same session ``lazy_import``
functionality is implemented without the use of import hooks.

``lazy_import`` is compatible with Python ≥ 2.7 or ≥ 3.4.

Examples: lazy module loading
-----------------------------

.. code:: python

    import lazy_import
    np = lazy_import.lazy_module("numpy")
    # np is now available in the namespace and is listed in sys.modules under
    #  the 'numpy' key:
    import sys
    sys.modules['numpy']
    # The module is present as "Lazily-loaded module numpy"

    # Subsequent imports of the same module return the lazy version present
    #  in sys.modules
    import numpy # At this point numpy and np point to the same lazy module.
    # This is true for any import of 'numpy', even if from other modules!

    # Accessing attributes causes the full loading of the module ...
    np.pi
    # ... and the module is changed in place. np and numpy are now 
    #  "<module 'numpy' from '/usr/local/lib/python/site-packages/numpy/__init__.py'>"

    # Lazy-importing a module that's already fully loaded returns the full
    #  module instead (even if it was loaded elsewhere in the current session)
    #  because there's no point in being lazy in this case:
    os = lazy_import.lazy_module("os")
    # "<module 'os' from '/usr/lib/python/os.py'>"

In the above code it can be seen that issuing
``lazy_import.lazy_module("numpy")`` registers the lazy module in the
session-wide ``sys.modules`` registry. This means that *any* subsequent import
of ``numpy`` in the same session, while the module is still not fully loaded,
will get served a lazy version of the ``numpy`` module. This will happen also
outside the code that calls ``lazy_module``:

.. code:: python
   
    import lazy_import
    np = lazy_import.lazy_module("numpy")
    import module_that_uses_numpy # This module will get a lazy module upon
                                  # 'import numpy'

Normally this is ok because the lazy module will behave pretty much as the real
thing once fully-loaded. Still, it might be a good practice to document that
you're lazily importing modules so-and-so, so that users are warned.

Further uses are to delay ``ImportErrors``:

.. code:: python

    import lazy_import
    # The following succeeds even when asking for a module that's not available
    missing = lazy_import.lazy_module("missing_module")

    missing.some_attr # This causes the full loading of the module, which now fails.
    "ImportError: __main__ attempted to use a functionality that requires module
     missing_module, but it couldn't be loaded. Please install missing_module and retry."


Submodules work too:

.. code:: python

    import lazy_import
    mod = lazy_import.lazy_module("some.sub.module")
    # mod now points to the some.sub.module lazy module
    #  equivalent to "from some.sub import module as mod"

    # Alternatively the returned reference can be made to point to the
    #  base module:
    some = lazy_import.lazy_module("some.sub.module", level="base")

    # This is equivalent to "import some.sub.module" in that only the base
    #  module's name is added to the namespace. All submodules must be accessed
    #  via that:
    some.sub # Returns lazy module 'some.sub' without triggering full loading.
    some.sub.attr # Triggers full loading of 'some' and 'some.sub'.
    some.sub.module.function() # Triggers loading also of 'some.sub.module'.


Finally, if you want to mark some modules and submodules your package imports
as always being lazy, it is as simple as lazily importing them at the root
`__init__.py` level. Other files can then import all modules normally, and
those that have already been loaded as lazy in `__init__.py` will remain so:

.. code:: python

    # in __init__.py:

    import lazy_import
    lazy_import.lazy_module("numpy")
    lazy_import.lazy_module("scipy.stats")


    # then, in any other file in the package just use the imports normally:

    import requests # This one is not lazy.
    import numpy # This one is lazy, as long as no other code caused its
                 #  loading in the meantime.
    import scipy # This one is also lazy. It was lazily loaded as part of the
                 #  lazy loading of scipy.stats.
    import scipy.stats # Also lazy.
    import scipy.linalg # Uh-oh, we didn't lazily import the 'linalg' submodule
                        #  earlier, and importing it like this here will cause
                        #  both scipy and scipy.linalg (but not scipy.stats) to
                        #  immediately become fully loaded.


Examples: lazy callable loading
-------------------------------

To emulate the ``from some.module import function`` syntax ``lazy_module``
provides ``lazy_callable``. It returns a wrapper function. Only upon being
called will it trigger the loading of the target module and the calling of the
target callable (function, class, etc.).

.. code:: python

    import lazy_import
    fn = lazy_import.lazy_callable("numpy.arange")
    # 'numpy' is now in sys.modules and is 'Lazily-loaded module numpy'

    fn(10)
    # array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])

``lazy_callable`` is only useful when the target callable is going to be called:

.. code:: python

    import lazy_import
    cl = lazy_import.lazy_callable("numpy.ndarray") # a class

    obj = cl([1, 2]) # This works OK (and also triggers the loading of numpy)

    class MySubclass(cl): # This fails because cl is just a wrapper,
        pass              #  not an actual class.


Installation
------------

.. code:: bash

    pip install lazy_import

Or, to include dependencies needed to run regression tests:

.. code:: bash

    pip install lazy_import[test]

Tests
-----

The ``lazy_module`` module comes with a series of tests. If you install with
test dependencies (see above), just run

.. code:: python

    import lazy_import.test_lazy
    lazy_import.test_lazy.run()
    # This will automatically parallelize over the available number of cores

Alternatively, tests can be run from the command line:

.. code:: bash

    pytest -n 4 --boxed -v --pyargs lazy_import
    # (replace '4' with the number of cores in your machine, or set to 1 if
    #  you'd rather test in serial)

Tests depend only on |pytest|_ and |pytest-xdist|_, so if you didn't install
them along ``lazy_import`` (as described under `Installation`_) just run

.. code:: bash

    pip install pytest pytest-xdist

Note that ``pytest-xdist`` is required even for serial testing because of its
``--boxed`` functionality.

License
-------

``lazy_import`` is released under GPL v3. It was based on code from the
|importing|_ module from the PEAK_ package. The licenses for both
``lazy_import`` and the PEAK package are included in the ``LICENSE`` file. The
respective license notices are reproduced here:

  lazy_import — a module to allow lazy importing of python modules

  Copyright (C) 2017-2018 Manuel Nuno Melo 

  lazy_import is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  lazy_import is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with lazy_import.  If not, see <http://www.gnu.org/licenses/>.


The PEAK ``importing`` code is

  Copyright (C) 1996-2004 by Phillip J. Eby and Tyler C. Sarna.
  All rights reserved.  This software may be used under the same terms
  as Zope or Python.  THERE ARE ABSOLUTELY NO WARRANTIES OF ANY KIND.
  Code quality varies between modules, from "beta" to "experimental
  pre-alpha".  :)
  
Code pertaining to lazy loading from PEAK ``importing`` was included in
``lazy_import``, modified in a number of ways. These are detailed in the
``CHANGELOG`` file of ``lazy_import``. Changes mainly involved Python 3
compatibility, extension to allow customizable behavior, and added
functionality (lazy importing of callable objects).


.. |Build Status| image:: https://api.travis-ci.org/mnmelo/lazy_import.svg
   :target: https://travis-ci.org/mnmelo/lazy_import

.. |importing| replace:: ``importing``
.. |pytest| replace:: ``pytest``
.. |pytest-xdist| replace:: ``pytest-xdist``

.. _importing: http://peak.telecommunity.com/DevCenter/Importing
.. _PEAK: http://peak.telecommunity.com/DevCenter/FrontPage
.. _pytest: https://docs.pytest.org/en/latest/
.. _pytest-xdist: https://pypi.python.org/pypi/pytest-xdist
