#!/bin/sh
# Rust 安装脚本 - macOS & Linux
# 官方文档: https://rustup.rs/

set -e
echo "Installing Rust (macOS/Linux)..."
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
. "$HOME/.cargo/env"
echo ""
echo "Rust installed successfully!"
