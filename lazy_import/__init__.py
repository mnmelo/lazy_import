# -*- coding: utf-8 -*-

from .lazy_import import *

# It is sometime useful to have access to the version number of a library.
# This is usually done through the __version__ special attribute.
# To make sure the version number is consistent between setup.py and the
# library, we read the version number from the file called VERSION that stays
# in the module directory.
import os
VERSION_FILE = os.path.join(os.path.dirname(__file__), 'VERSION')
with open(VERSION_FILE) as infile:
    __version__ = infile.read().strip()
del os
del VERSION_FILE
