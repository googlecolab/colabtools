# Copyright 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Configuration for the google.colab package."""

from setuptools import find_packages
from setuptools import setup

DEPENDENCIES = (
    # Note: these dependency versions should be kept in-sync with the versions
    # specified in the docker container requirements files.
    'astor~=0.8.1',
    'google-auth>=1.17.2',
    'ipykernel~=4.10',
    'ipython~=5.5.0',
    'notebook~=5.2.0; python_version < "3.0"',
    'notebook~=5.3.0; python_version >= "3.0"',
    'six~=1.15.0',
    'pandas~=0.24.0; python_version < "3.0"',
    'pandas~=1.1.0; python_version >= "3.0"',
    'portpicker~=1.3.1',
    'requests~=2.23.0',
    'tornado~=4.5.0; python_version < "3.0"',
    'tornado~=5.1.0; python_version >= "3.0"',
)

setup(
    name='google-colab',
    version='1.0.0',
    author='Google Colaboratory team',
    author_email='colaboratory-team@google.com',
    description='Google Colaboratory tools',
    long_description='Colaboratory-specific python libraries.',
    url='https://colaboratory.research.google.com/',
    packages=find_packages(exclude=('tests*',)),
    install_requires=DEPENDENCIES,
    namespace_packages=('google',),
    license='Apache 2.0',
    keywords='google colab ipython jupyter',
    classifiers=(
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: OS Independent',
        'Topic :: Internet :: WWW/HTTP',
    ),
    include_package_data=True,
)
