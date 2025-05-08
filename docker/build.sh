#!/bin/bash
set -x

git clone git@gitcode.com:sfoolish/HapRayDep.git
cd HapRayDep
./setup.sh
cd ../

docker pull ubuntu:22.04
docker build -t hapray -f Dockerfile .
