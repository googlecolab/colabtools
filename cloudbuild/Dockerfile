# Copyright 2017 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM ubuntu:17.10
MAINTAINER Google Colaboratory Team <colaboratory-team@google.com>

# Setup OS and core packages
RUN apt-get update && \
    apt-get install --no-install-recommends -y -q \
        build-essential \
        git \
        python \
        python-dev \
        python-pip \
        python-setuptools \
        python-zmq \
        python3 \
        python3-dev \
        python3-pip \
        python3-setuptools \
        python3-zmq \
        && \
    pip3 install wheel && \
    pip install wheel tox

# Fetch the colabtools source.
ADD . /colabtools

# Run tests and build a new wheel.
RUN cd /colabtools && \
    tox && \
    python setup.py bdist_wheel
