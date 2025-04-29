set -x

WORKSPACE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
HapRayDep=$WORKSPACE/third-party/HapRayDep

python3 -m venv HapRayVenv
source HapRayVenv/bin/activate

cd third-party
git clone https://gitcode.com/sfoolish/HapRayDep.git
cd ${HapRayDep}
./setup.sh
cp pip.conf ../../HapRayVenv
cp npmrc ../../.npmrc

cd ${HapRayDep}
tar xf node-v22.15.0-darwin-arm64.tar.gz
cd node-v22.15.0-darwin-arm64/bin
echo "export PATH=$(pwd):\$PATH" >> ../../../../HapRayVenv/bin/activate

cd ${HapRayDep}/sdk-toolchains-macos-arm
echo "export PATH=$(pwd):\$PATH" >> ../../../HapRayVenv/bin/activate

cd ${HapRayDep}
tar xf trace_streamer_binary.zip
chmod +x trace_streamer_binary/trace_streamer_mac
cd trace_streamer_binary
ln -s trace_streamer_mac trace_streamer
cd ../
mv trace_streamer_binary ../

cd ${HapRayDep}/hypium-5.0.7.200
pip install xdevice-5.0.7.200.tar.gz
pip install xdevice-devicetest-5.0.7.200.tar.gz
pip install xdevice-ohos-5.0.7.200.tar.gz
pip install hypium-5.0.7.200.tar.gz

cd ${HapRayDep}/hypium_perf-5.0.7.200 
./install.sh

cd ${WORKSPACE}
npm install
npm run build
chmod +x toolbox/dist/third-party/trace_streamer_binary/trace_streamer*
