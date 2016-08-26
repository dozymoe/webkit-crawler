#!/bin/bash

PYTHON_VERSION=${1:-3.4}

# system package requirements:
#   - dev-lang/python (appropriate version)
#   - dev-python/virtualenv


fatal() {
  message="$1";

  echo "ERROR: $message"
  exit 1
}

[[ ! -x /usr/bin/python${PYTHON_VERSION} ]] && fatal "Please install python${PYTHON_VERSION} or use ./configure VERSION"
[[ ! -x /usr/bin/Xvfb ]] && fatal 'Please install xvfb (ubuntu) or xorg-x11-server-Xvfb (centos)'

# setup python modules
[[ ! -x /usr/bin/virtualenv ]] && fatal 'Please install python-virtualenv'
if [[ ! -d .virtualenv ]]
then
    virtualenv --python=python${PYTHON_VERSION} .virtualenv || fatal 'Failed to create virtualenv'
fi

if [[ ! -h python_modules ]]
then
    ln -s .virtualenv/lib/python${PYTHON_VERSION}/site-packages python_modules || fatal 'Failed to create symlink "python_modules"'
fi

[[ ! -r .virtualenv/bin/activate ]] && fatal 'Cannot activate virtualenv'
if [[ -r .virtualenv/bin/activate ]]
then
    . .virtualenv/bin/activate
fi

pip install --upgrade pip || fatal 'Cannot upgrade pip'

if [[ ! -h python_modules/PyQt4 ]]
then
    if [[ -d /usr/lib/python${PYTHON_VERSION}/site-packages/PyQt4 ]]
    then
        [[ ! -r /usr/lib/python${PYTHON_VERSION}/site-packages/PyQt4/QtWebKit.so ]] && fatal 'Please install PyQt4-webkit'
        ln -s /usr/lib/python${PYTHON_VERSION}/site-packages/PyQt4 python_modules/
    else
        if [[ -d /usr/lib64/python${PYTHON_VERSION}/site-packages/PyQt4 ]]
        then
            [[ ! -r /usr/lib64/python${PYTHON_VERSION}/site-packages/PyQt4/QtWebKit.so ]] && fatal 'Please install PyQt4-webkit'
            ln -s /usr/lib64/python${PYTHON_VERSION}/site-packages/PyQt4 python_modules/
        else
            fatal 'Please install PyQt4'
        fi
    fi
fi

if [[ ! -h python_modules/sip.so ]]
then
    if [[ -r /usr/lib/python${PYTHON_VERSION}/site-packages/sip.so ]]
    then
        ln -s /usr/lib/python${PYTHON_VERSION}/site-packages/sip* python_modules/
    else
        if [[ -r /usr/lib64/python${PYTHON_VERSION}/site-packages/sip.so ]]
        then
            ln -s /usr/lib64/python${PYTHON_VERSION}/site-packages/sip* python_modules/
        else
            fatal 'Please install python-sip'
        fi
    fi
fi

if [[ "$PYTHON_VERSION" == '2.6' ]]
then
    pip install --upgrade simplejson
fi

pip install --upgrade pyvirtualdisplay
#pip install -r requirements.txt || fatal  'Cannot install python modules'
