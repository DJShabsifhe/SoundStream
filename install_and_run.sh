#!/bin/bash

# SoundStream Install Dependencies and Run Script
# This script will install all required dependencies and then run sound_sender.py

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_header() {
    echo -e "${CYAN}======================================${NC}"
    echo -e "${CYAN}     SoundStream        ${NC}"
    echo -e "${CYAN}======================================${NC}"
}

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to pause and wait for user input
pause_for_user() {
    echo ""
    echo -e "${YELLOW}按任意键继续...${NC}"
    read -n 1 -s
    echo ""
}

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_header
echo "开始安装 SoundStream 依赖项..."
echo "脚本位置: $SCRIPT_DIR"
echo ""

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    print_error "此脚本仅支持 macOS 系统"
    pause_for_user
    exit 1
fi

print_status "检查系统要求..."

# Step 1: Install Homebrew if not present
if ! command_exists brew; then
    print_status "Homebrew 未安装，正在安装 Homebrew..."
    echo "这可能需要几分钟时间，请耐心等待..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for current session
    if [[ $(uname -m) == "arm64" ]]; then
        # Apple Silicon Mac
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
        export PATH="/opt/homebrew/bin:$PATH"
    else
        # Intel Mac
        echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/usr/local/bin/brew shellenv)"
        export PATH="/usr/local/bin:$PATH"
    fi
    
    print_success "Homebrew 安装完成"
else
    print_success "Homebrew 已安装"
    # Ensure Homebrew is in PATH
    if [[ $(uname -m) == "arm64" ]]; then
        export PATH="/opt/homebrew/bin:$PATH"
    else
        export PATH="/usr/local/bin:$PATH"
    fi
fi

# Update Homebrew
print_status "更新 Homebrew..."
brew update

# Step 2: Install PortAudio
print_status "检查 PortAudio..."
if brew list portaudio &> /dev/null; then
    print_success "PortAudio 已安装"
else
    print_status "正在安装 PortAudio..."
    brew install portaudio
    print_success "PortAudio 安装完成"
fi

# Step 3: Install Python 3.13
print_status "检查 Python 3.13..."
if brew list python@3.13 &> /dev/null; then
    print_success "Python 3.13 已安装"
else
    print_status "正在安装 Python 3.13..."
    brew install python@3.13
    print_success "Python 3.13 安装完成"
fi

# Step 4: Create virtual environment if it doesn't exist
print_status "设置 Python 虚拟环境..."
if [ ! -d ".venv" ]; then
    print_status "创建 Python 虚拟环境..."
    python3 -m venv .venv
    print_success "虚拟环境创建完成"
else
    print_success "虚拟环境已存在"
fi

# Step 5: Activate virtual environment and install requirements
print_status "激活虚拟环境并安装 Python 依赖..."
source .venv/bin/activate

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    print_error "未找到 requirements.txt 文件"
    print_status "创建默认的 requirements.txt..."
    cat > requirements.txt << EOF
numpy>=1.24
pyaudio>=0.2.13
pyinstaller>=6.0
EOF
fi

# Install Python requirements
print_status "安装 Python 依赖包..."
pip install --upgrade pip
pip install -r requirements.txt
print_success "Python 依赖安装完成"

echo ""
print_success "所有依赖项安装完成！"
echo ""

# Check if sound_sender.py exists
if [ ! -f "sound_sender.py" ]; then
    print_error "未找到 sound_sender.py 文件！"
    print_status "请确保 sound_sender.py 文件在当前目录中"
    pause_for_user
    exit 1
fi

print_status "准备启动 SoundStream..."
echo ""
echo -e "${CYAN}======================================${NC}"
echo -e "${CYAN}         启动 SoundStream            ${NC}"
echo -e "${CYAN}======================================${NC}"
echo ""
print_status "工作目录: $(pwd)"
print_status "Python 虚拟环境: $(which python3)"
echo ""

# Give user a chance to see the setup completion
print_warning "依赖安装完成，即将启动 SoundStream..."
print_warning "确保您的震动背心设备已正确配置并连接到同一 Wi-Fi 网络"
pause_for_user

# Run sound_sender.py
print_status "启动 sound_sender.py..."
echo -e "${YELLOW}按 Ctrl+C 停止程序${NC}"
echo ""

# Run the Python script
python3 sound_sender.py

echo ""
print_status "SoundStream 已退出"
pause_for_user
