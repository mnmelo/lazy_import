#!/bin/bash -e
basedir=$(pwd)
cd
pip3 install --force-reinstall --user $basedir
pip2 install --force-reinstall --user $basedir
python3 -m pytest --boxed -n 4 -v --pyargs lazy_import
python2 -m pytest --boxed -n 4 -v --pyargs lazy_import
cd $basedir
