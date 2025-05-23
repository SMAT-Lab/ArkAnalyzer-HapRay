set -x

WORKSPACE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
HapRayDep=$WORKSPACE/third-party/HapRayDep

python3 -m venv .venv
source .venv/bin/activate

cd third-party
git clone https://gitcode.com/sfoolish/HapRayDep.git
cd ${HapRayDep}
./setup.sh
cp pip.conf ../../.venv
cp npmrc ../../.npmrc

os_name=$(uname)
OS_ARCH_TYPE=Linux_X86_64
if [ "$os_name" = "Linux" ]; then
    OS_ARCH_TYPE=Linux_X86_64
    echo "OS type is: ${OS_ARCH_TYPE}"
elif [ "$os_name" = "Darwin" ]; then
    os_arch=$(uname -m)
    if [ "$os_arch" = "x86_64" ]; then
        OS_ARCH_TYPE=Darwin_X86_64
        echo "OS type is: macOS (x64)"
    elif [ "$os_arch" = "arm64" ]; then
            OS_ARCH_TYPE=Darwin_ARM64
        echo "OS type is: macOS (ARM/Apple Silicon)"
    else
        echo "OS type is: macOS (unknown $os_arch)"
    fi
else
    echo "Unknown OS type ($os_name)"
    exit
fi

if [ "$OS_ARCH_TYPE" = "Darwin_ARM64" ]; then
    cd ${HapRayDep}
    tar xf node-v22.15.0-darwin-arm64.tar.gz
    cd node-v22.15.0-darwin-arm64/bin
    echo "export PATH=$(pwd):\$PATH" >> ../../../../.venv/bin/activate
    cd ${HapRayDep}/sdk-toolchains-macos-arm
    echo "export PATH=$(pwd):\$PATH" >> ../../../.venv/bin/activate
elif [ "$OS_ARCH_TYPE" = "Darwin_X86_64" ]; then
    cd ${HapRayDep}
    tar xf node-v22.15.0-darwin-x64.tar.gz
    cd node-v22.15.0-darwin-x64/bin
    echo "export PATH=$(pwd):\$PATH" >> ../../../../.venv/bin/activate
    cd ${HapRayDep}/sdk-toolchains-macos-x64
    echo "export PATH=$(pwd):\$PATH" >> ../../../.venv/bin/activate
else
    cd ${HapRayDep}
    tar xf node-v22.14.0-linux-x64.tar.xz
    cd node-v22.14.0-linux-x64/bin
    echo "export PATH=$(pwd):\$PATH" >> ../../../../.venv/bin/activate
    cd ${HapRayDep}/sdk-toolchains
    echo "export PATH=$(pwd):\$PATH" >> ../../../.venv/bin/activate
fi

cd ${HapRayDep}
tar xf trace_streamer_binary.zip
chmod +x trace_streamer_binary/trace_streamer*
cd trace_streamer_binary
ln -s trace_streamer_mac trace_streamer
chmod +x trace_streamer_mac
cd ../
rm ../trace_streamer_binary
mv trace_streamer_binary ../

cd ${HapRayDep}/hypium-5.0.7.200
pip install xdevice-5.0.7.200.tar.gz
pip install xdevice-devicetest-5.0.7.200.tar.gz
pip install xdevice-ohos-5.0.7.200.tar.gz
pip install hypium-5.0.7.200.tar.gz

cd $WORKSPACE/perf_testing
pip install -r requirements.txt

cd ${WORKSPACE}
source .venv/bin/activate
npm install
npm run build
chmod +x toolbox/dist/third-party/trace_streamer_binary/trace_streamer*

