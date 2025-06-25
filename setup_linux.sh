#!/bin/bash

echo "=== Configuração do ambiente Linux para o bot de notas fiscais ==="

# Verificar se o Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "Python3 não encontrado. Instalando..."
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv
fi

# Verificar se o Chrome está instalado
if ! command -v google-chrome &> /dev/null; then
    echo "Google Chrome não encontrado. Instalando..."
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
    sudo apt update
    sudo apt install -y google-chrome-stable
fi

# Criar ambiente virtual
echo "Criando ambiente virtual..."
python3 -m venv venv

# Ativar ambiente virtual
echo "Ativando ambiente virtual..."
source venv/bin/activate

# Instalar dependências Python
echo "Instalando dependências Python..."
pip install --upgrade pip
pip install -r requirements.txt

# Instalar dependências do sistema para o Chrome
echo "Instalando dependências do sistema para o Chrome..."
sudo apt install -y xvfb libgconf-2-4

echo "=== Configuração concluída! ==="
echo ""
echo "Para ativar o ambiente virtual:"
echo "source venv/bin/activate"
echo ""
echo "Para executar o bot:"
echo "python main.py"
echo ""
echo "Para executar em modo headless (sem interface gráfica):"
echo "O código já está configurado para rodar em modo headless no Linux" 