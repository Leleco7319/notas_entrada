# Bot de Notas Fiscais - Configuração para Linux

Este documento contém instruções específicas para executar o bot de notas fiscais em ambiente Linux.

## Pré-requisitos

- Ubuntu/Debian ou distribuição Linux baseada em Debian
- Python 3.7 ou superior
- Google Chrome
- Acesso à internet

## Instalação Automática

Execute o script de configuração:

```bash
chmod +x setup_linux.sh
./setup_linux.sh
```

## Instalação Manual

### 1. Instalar Python e pip

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

### 2. Instalar Google Chrome

```bash
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update
sudo apt install -y google-chrome-stable
```

### 3. Instalar dependências do sistema

```bash
sudo apt install -y xvfb libgconf-2-4
```

### 4. Criar e ativar ambiente virtual

```bash
python3 -m venv venv
source venv/bin/activate
```

### 5. Instalar dependências Python

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Configuração

### 1. Criar arquivo .env

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```env
URL_CNPJ=sua_url_aqui
API_KEY=sua_chave_capsolver_aqui
```

### 2. Configurar diretórios

O script criará automaticamente os diretórios necessários:
- `notas_fiscais/` - Para armazenar os PDFs baixados
- `logs/` - Para logs de erros e notas canceladas
- `temp/` - Para arquivos temporários

## Execução

### 1. Ativar ambiente virtual

```bash
source venv/bin/activate
```

### 2. Executar o bot

```bash
python main.py
```

### 3. Usar a API

O bot estará disponível em `http://localhost:8000`

**Endpoint para baixar notas:**
```bash
curl -X POST "http://localhost:8000/baixar-notas-fiscais" \
     -H "Content-Type: application/json" \
     -d '{
       "login": "seu_cnpj",
       "password": "sua_senha",
       "chrome_profile": "chrome_profile_linux"
     }'
```

## Modo Headless

O bot está configurado para rodar em modo headless no Linux (sem interface gráfica). Se você quiser ver a interface do navegador, remova a linha:

```python
options.add_argument("--headless")
```

do arquivo `tasks/scrap_nfse.py`.

## Solução de Problemas

### Erro: "ChromeDriver not found"

O `webdriver-manager` deve baixar automaticamente o ChromeDriver. Se houver problemas:

```bash
# Verificar versão do Chrome
google-chrome --version

# Limpar cache do webdriver-manager
rm -rf ~/.wdm/
```

### Erro: "Permission denied"

```bash
# Dar permissão de execução ao script
chmod +x setup_linux.sh

# Se necessário, dar permissões ao diretório
chmod -R 755 .
```

### Erro: "No display found"

Para servidores sem interface gráfica, o modo headless já está habilitado. Se ainda houver problemas:

```bash
# Instalar xvfb se não estiver instalado
sudo apt install -y xvfb

# Executar com xvfb
xvfb-run python main.py
```

### Erro: "Chrome crashed"

```bash
# Limpar perfis do Chrome
rm -rf chrome_profile_*

# Verificar se há processos do Chrome rodando
ps aux | grep chrome
pkill -f chrome
```

## Logs

Os logs são salvos em:
- `logs/erros_processamento.log` - Erros durante o processamento
- `logs/notas_canceladas.log` - Notas que foram canceladas

## Estrutura de Arquivos

```
nota_de_entrada/
├── main.py                 # API principal
├── tasks/
│   └── scrap_nfse.py      # Lógica de scraping
├── requirements.txt        # Dependências Python
├── setup_linux.sh         # Script de instalação
├── README_LINUX.md        # Este arquivo
├── notas_fiscais/         # PDFs baixados
├── logs/                  # Logs do sistema
└── temp/                  # Arquivos temporários
```

## Suporte

Se encontrar problemas, verifique:
1. Se todas as dependências estão instaladas
2. Se o arquivo `.env` está configurado corretamente
3. Se o Chrome está instalado e funcionando
4. Os logs em `logs/` para detalhes dos erros 