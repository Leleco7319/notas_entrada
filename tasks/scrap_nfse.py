import os
import subprocess
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import base64
import capsolver
import time
import shutil
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import boto3
from botocore.exceptions import ClientError
import logging
from datetime import datetime
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import json

# Configuração do logging
def setup_logging():
    """Configura os loggers para notas canceladas e erros"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    # Log para notas canceladas
    canceled_logger = logging.getLogger('canceled_notes')
    if not canceled_logger.handlers:  # Só adiciona handler se não existir nenhum
        canceled_logger.setLevel(logging.INFO)
        canceled_handler = logging.FileHandler(os.path.join(log_dir, 'notas_canceladas.log'), encoding='utf-8')
        canceled_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        canceled_logger.addHandler(canceled_handler)
    
    # Log para erros
    error_logger = logging.getLogger('error_notes')
    if not error_logger.handlers:  # Só adiciona handler se não existir nenhum
        error_logger.setLevel(logging.ERROR)
        error_handler = logging.FileHandler(os.path.join(log_dir, 'erros_processamento.log'), encoding='utf-8')
        error_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        error_logger.addHandler(error_handler)
    
    return canceled_logger, error_logger

class ScrapNotaFiscal:
    """
    Classe para automação de download de Notas Fiscais de Serviço Eletrônicas (NFS-e).
    
    Esta classe automatiza o processo de:
    - Login no sistema de NFS-e
    - Seleção de meses específicos
    - Download das notas fiscais
    - Organização dos arquivos por mês
    """
    
    def __init__(self):
        """Inicializa a classe carregando configurações e preparando diretórios."""
        try:
            load_dotenv()
            self._carregar_configuracoes()
            self._preparar_diretorios()
                
        except Exception as e:
            print(f"Erro ao inicializar ScrapNotaFiscal: {e}")
            raise e
    
    def _carregar_configuracoes(self):
        """Carrega as configurações do arquivo .env."""
        self.url = os.getenv("URL_CNPJ")
        self.captcha_key = os.getenv("API_KEY")
        
        if not self.url or not self.captcha_key:
            raise ValueError("URL_CNPJ e API_KEY devem estar definidas no arquivo .env")
    
    def _preparar_diretorios(self):
        """Prepara os diretórios necessários para download das notas fiscais."""
        # Diretório base para notas fiscais (relativo ao script)
        self.download_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            "notas_fiscais"
        )
        os.makedirs(self.download_dir, exist_ok=True)
        print(f"Diretório de notas fiscais: {self.download_dir}")
        
        # Limpa arquivos antigos do diretório
        self._limpar_diretorio_download()
    
    def _limpar_diretorio_download(self):
        """Remove todos os arquivos do diretório de download para evitar conflitos."""
        if os.path.exists(self.download_dir):
            for item in os.listdir(self.download_dir):
                item_path = os.path.join(self.download_dir, item)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                        print(f"Arquivo removido: {item_path}")
                except Exception as e:
                    print(f"Erro ao remover {item_path}: {e}")

    def sanitize_filename(self, filename):
        """
        Remove caracteres inválidos do nome do arquivo.
        
        Args:
            filename (str): Nome do arquivo a ser sanitizado
            
        Returns:
            str: Nome do arquivo sanitizado
        """
        # Lista de caracteres inválidos no Windows + caracteres problemáticos
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '$', '%', '#', '@', '!', '&']
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove espaços duplos e espaços no início/fim
        filename = ' '.join(filename.split())
        
        # Limita o tamanho do nome do arquivo (Windows tem limite de 255 caracteres)
        if len(filename) > 200:
            name_part = filename.rsplit('.', 1)[0][:190]
            ext_part = filename.rsplit('.', 1)[1] if '.' in filename else 'pdf'
            filename = f"{name_part}.{ext_part}"
        
        return filename

    def preencher_input(self, driver, selector, texto, timeout=5):
        """
        Preenche um campo de input simulando digitação humana.
        
        Args:
            driver: WebDriver do Selenium
            selector (str): Seletor CSS do elemento
            texto (str): Texto a ser digitado
            timeout (int): Tempo limite para encontrar o elemento
            
        Returns:
            WebElement: Elemento que foi preenchido
        """
        input_element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        # Simula digitação humana com pequenos intervalos
        for caractere in texto:
            input_element.send_keys(caractere)
            time.sleep(0.05)
        return input_element

    def fazer_login(self, driver, login, password, max_tentativas=3):
        """
        Realiza login no sistema com tratamento de captcha e múltiplas tentativas.
        
        Args:
            driver: WebDriver do Selenium
            login (str): Login/CNPJ do usuário
            password (str): Senha do usuário
            max_tentativas (int): Número máximo de tentativas de login
            
        Returns:
            bool: True se login bem-sucedido, False caso contrário
            
        Raises:
            Exception: Se todas as tentativas falharem
        """
        print(f"Iniciando login para: {login}")
        self.preencher_input(driver, "#txtLogin", login)
        
        for tentativa in range(max_tentativas):
            try:
                print(f"Tentativa de login {tentativa + 1}/{max_tentativas}")
                
                # Limpar senha em tentativas subsequentes
                if tentativa > 0:
                    senha_field = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "#txtSenha"))
                    )
                    senha_field.clear()
                
                # Preencher senha
                self.preencher_input(driver, "#txtSenha", password)
                
                # Resolver captcha
                img = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#imgNewCaptcha"))
                )
                captcha_text = self.solve_captcha(img)
                # Remove caractere 't' específico que causa problemas
                formatted_captcha = captcha_text.replace("t", "")
                
                # Limpar captcha em tentativas subsequentes
                if tentativa > 0:
                    captcha_field = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "#txtCodeTextBox"))
                    )
                    captcha_field.clear()
                
                # Preencher captcha
                self.preencher_input(driver, "#txtCodeTextBox", formatted_captcha)
                
                # Clicar no botão de login
                btn_login = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "#btnLogar"))
                )
                btn_login.click()
                time.sleep(3)
                
                # Verificar se houve erro de login
                if self._verificar_erro_login(driver):
                    if tentativa < max_tentativas - 1:
                        print("Erro detectado, tentando novamente...")
                        continue
                    else:
                        raise Exception(f"Falha no login após {max_tentativas} tentativas")
                
                print("Login realizado com sucesso!")
                return True
                
            except Exception as e:
                if tentativa < max_tentativas - 1:
                    print(f"Erro na tentativa {tentativa+1}: {e}")
                    continue
                else:
                    raise Exception(f"Falha nas {max_tentativas} tentativas: {e}")
        
        return False
    
    def _verificar_erro_login(self, driver):
        """
        Verifica se há mensagens de erro após tentativa de login.
        
        Args:
            driver: WebDriver do Selenium
            
        Returns:
            bool: True se houver erro, False caso contrário
        """
        try:
            msg_element = WebDriverWait(driver, 2).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#lblMsg"))
            )
            if msg_element.text.strip():
                print(f"Mensagem de erro detectada: {msg_element.text}")
                return True
        except:
            # Se não encontrar elemento de erro, assume sucesso
            pass
        return False

    def _navegar_para_nfse(self, driver):
        """
        Navega pelos menus até chegar na página de pesquisa de NFS-e.
        
        Args:
            driver: WebDriver do Selenium
        """
        print("Navegando para a página de NFS-e...")
        
        # Acessar menu principal
        frame_menu = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "fraMenu"))
        )
        driver.switch_to.frame(frame_menu)
        
        elemento_menu = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#td1_div5 > b > span"))
        )
        elemento_menu.click()
        time.sleep(2)
        driver.switch_to.default_content()

        # Acessar área de Nota Fiscal
        frame_main = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "fraMain"))
        )
        driver.switch_to.frame(frame_main)
        
        iframe_menu = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "iFrameMenu"))
        )
        driver.switch_to.frame(iframe_menu)
        
        link_nfse = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Pesquisar NFS-e Recebidas (IFRAME)"))
        )
        link_nfse.click()
        driver.switch_to.default_content()

    def _processar_mes(self, driver, month):
        """
        Processa todas as notas fiscais de um mês específico.
        
        Args:
            driver: WebDriver do Selenium
            month (str): Nome do mês a ser processado
        """
        print(f"Processando mês: {month}")
        
        # Selecionar o mês
        select_mes = Select(driver.find_element(By.ID, "Mes"))
        select_mes.select_by_visible_text(month)
        
        # Executar pesquisa
        btn_pesquisar = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "btnPesquisar"))
        )
        btn_pesquisar.click()
        time.sleep(2)
        
        # Processar todas as páginas de resultados
        self._processar_todas_paginas(driver, month)

    def _processar_todas_paginas(self, driver, month):
        """
        Processa todas as páginas de resultados para um mês.
        
        Args:
            driver: WebDriver do Selenium
            month (str): Nome do mês sendo processado
        """
        pagina_atual = 1
        
        while True:
            print(f"Processando página {pagina_atual} do mês {month}")
            
            # Processar notas da página atual
            self._processar_notas_pagina_atual(driver, month)
            
            # Verificar se há próxima página
            if not self._ir_para_proxima_pagina(driver):
                print(f"Todas as páginas do mês {month} foram processadas")
                break
                
            pagina_atual += 1

    def _processar_notas_pagina_atual(self, driver, month):
        """
        Processa todas as notas fiscais da página atual.
        
        Args:
            driver: WebDriver do Selenium
            month (str): Nome do mês sendo processado
        """
        canceled_logger, error_logger = setup_logging()
        
        try:
            # Localizar tabela de notas
            tabela = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "tblNfse"))
            )
            
            tbody = WebDriverWait(tabela, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "tbody"))
            )
            
            rows = WebDriverWait(tbody, 5).until(
                EC.presence_of_all_elements_located((By.TAG_NAME, "tr"))
            )
            
            print(f"Encontradas {len(rows)} notas na página atual")
            
            for i, row in enumerate(rows):
                try:
                    # Pular linhas canceladas
                    if "canceled" in row.get_attribute("class"):

                        print(f"Nota cancelada encontrada, registrando...")
                        colunas = row.find_elements(By.TAG_NAME, "td")
                        numero_nota = colunas[1].text.strip()
                        data_emissao = colunas[4].text.strip().split()[0]
                        valor_nota = colunas[5].text.strip().replace(".", "").replace(",", "_")
                        
                        # Registrar no log de notas canceladas
                        canceled_logger.info(f"Nota {numero_nota} do mês {month} está cancelada - Data: {data_emissao}, Valor: {valor_nota}")
                    
                    print(f"Processando nota {i+1}/{len(rows)}")
                    self._processar_nota_individual(driver, row, month)
                    
                except Exception as e:
                    colunas = row.find_elements(By.TAG_NAME, "td")
                    numero_nota = colunas[1].text.strip()
                    data_emissao = colunas[4].text.strip().split()[0]
                    valor_nota = colunas[5].text.strip()
                    error_msg = f"Erro ao processar nota {numero_nota} - Data: {data_emissao}, Valor: {valor_nota} Motivo: {str(e)}"
                    print(error_msg)
                    error_logger.error(error_msg)
                    continue
                    
        except Exception as e:
            error_msg = f"Erro ao processar notas da página: {str(e)}"
            print(error_msg)
            error_logger.error(error_msg)

    def _processar_nota_individual(self, driver, row, month):
        """
        Processa uma nota fiscal individual (download e renomeação).
        
        Args:
            driver: WebDriver do Selenium
            row: Elemento da linha da tabela
            month (str): Nome do mês sendo processado
        """
        canceled_logger, error_logger = setup_logging()
        
        try:
            # Extrair dados da nota
            colunas = row.find_elements(By.TAG_NAME, "td")
            if len(colunas) < 6:
                error_msg = "Linha sem dados suficientes, pulando..."
                print(error_msg)
                error_logger.error(error_msg)
                return
            
            numero_nota = colunas[1].text.strip()
            data_emissao = colunas[4].text.strip().split()[0]
            valor_nota = colunas[5].text.strip().replace(".", "").replace(",", "_")
            
            print(f"Processando nota: {numero_nota}")
            
            # Fazer download da nota
            self._fazer_download_nota(driver, row)
            
            # Renomear e organizar arquivo
            self._organizar_arquivo_baixado(month, data_emissao, numero_nota, valor_nota)
            
        except Exception as e:
            error_msg = f"Erro ao processar nota individual {numero_nota if 'numero_nota' in locals() else 'desconhecida'}: {str(e)}"
            print(error_msg)
            error_logger.error(error_msg)
            raise

    def _fazer_download_nota(self, driver, row):
        """
        Executa o download de uma nota fiscal específica.
        
        Args:
            driver: WebDriver do Selenium
            row: Elemento da linha da tabela contendo o botão de download
        """
        # Clicar no botão de imprimir
        botao_imprimir = row.find_element(
            By.CSS_SELECTOR, 
            "td.action-column button[data-action='imprimir']"
        )
        botao_imprimir.click()
        
        # Confirmar impressão no modal
        botao_confirmar = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".modal-footer button.btn-success"))
        )
        botao_confirmar.click()
        time.sleep(1)
        
        # Fechar modal
        botao_fechar = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".modal-footer button.btn-secondary"))
        )
        botao_fechar.click()
        
        # Aguardar download completar
        time.sleep(2)

    def _organizar_arquivo_baixado(self, month, data_emissao, numero_nota, valor_nota):
        """
        Organiza o arquivo baixado renomeando e movendo para pasta correta.
        
        Args:
            month (str): Nome do mês
            data_emissao (str): Data de emissão da nota
            numero_nota (str): Número da nota fiscal
            valor_nota (str): Valor da nota fiscal
        """
        try:
            # Criar pasta do mês se não existir
            pasta_mes = os.path.join(self.download_dir, month)
            os.makedirs(pasta_mes, exist_ok=True)
            print(f"Pasta do mês verificada: {pasta_mes}")
            
            # Encontrar arquivos PDF no diretório principal (não nas subpastas)
            arquivos_pdf = []
            for item in os.listdir(self.download_dir):
                item_path = os.path.join(self.download_dir, item)
                # Só considera arquivos PDF que estão diretamente no diretório principal
                if os.path.isfile(item_path) and item.lower().endswith('.pdf'):
                    arquivos_pdf.append(item_path)
            
            if not arquivos_pdf:
                print("Nenhum arquivo PDF encontrado no diretório principal para organizar")
                return
            
            # Encontrar o arquivo mais recente
            arquivo_mais_recente = max(arquivos_pdf, key=os.path.getctime)
            print(f"Arquivo mais recente detectado: {arquivo_mais_recente}")
            
            # Verificar se o arquivo ainda existe (pode ter sido movido por processo anterior)
            if not os.path.exists(arquivo_mais_recente):
                print(f"Arquivo {arquivo_mais_recente} não existe mais, pulando...")
                return
            
            # Criar nome sanitizado
            nome_arquivo = f"{data_emissao}_{numero_nota}_{valor_nota}.pdf"
            nome_sanitizado = self.sanitize_filename(nome_arquivo)
            
            # Caminho final do arquivo
            caminho_final = os.path.join(pasta_mes, nome_sanitizado)
            
            # Verificar se arquivo com mesmo nome já existe
            if os.path.exists(caminho_final):
                print(f"Arquivo já existe: {caminho_final}")
                # Remove o arquivo baixado pois já temos uma cópia
                try:
                    os.remove(arquivo_mais_recente)
                    print(f"Arquivo duplicado removido: {arquivo_mais_recente}")
                except Exception as e:
                    print(f"Erro ao remover arquivo duplicado: {e}")
            else:
                # Mover e renomear o arquivo
                try:
                    shutil.move(arquivo_mais_recente, caminho_final)
                    print(f"Arquivo organizado com sucesso: {caminho_final}")
                except Exception as e:
                    print(f"Erro ao mover arquivo com shutil.move: {e}")
                    # Fallback: tentar com copy + remove
                    try:
                        shutil.copy2(arquivo_mais_recente, caminho_final)
                        os.remove(arquivo_mais_recente)
                        print(f"Arquivo copiado e original removido: {caminho_final}")
                    except Exception as e2:
                        print(f"Erro no fallback copy+remove: {e2}")
                
        except Exception as e:
            print(f"Erro geral ao organizar arquivo: {e}")
            # Em caso de erro, pelo menos tenta listar o que está no diretório
            try:
                print("Conteúdo do diretório de download:")
                for item in os.listdir(self.download_dir):
                    item_path = os.path.join(self.download_dir, item)
                    tipo = "PASTA" if os.path.isdir(item_path) else "ARQUIVO"
                    print(f"  {tipo}: {item}")
            except:
                pass

    def _ir_para_proxima_pagina(self, driver):
        """
        Tenta navegar para a próxima página de resultados.
        
        Args:
            driver: WebDriver do Selenium
            
        Returns:
            bool: True se conseguiu ir para próxima página, False se não há mais páginas
        """
        try:
            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "li.paginate_button.page-item.next"))
            )
            
            if "disabled" in next_button.get_attribute("class"):
                return False
            
            next_button.click()
            time.sleep(2)
            return True
            
        except Exception as e:
            print(f"Erro ao navegar para próxima página: {e}")
            return True

    def get_info(self, driver, login, password, months):
        """
        Método principal para extrair informações de notas fiscais.
        
        Args:
            driver: WebDriver do Selenium
            login (str): Login/CNPJ do usuário
            password (str): Senha do usuário
            months (list): Lista de meses para processar
        """
        try:
            print(f"Iniciando extração para os meses: {months}")
            
            # Acessar sistema
            driver.get(self.url)
            
            # Fazer login
            self.fazer_login(driver, login, password)
            
            # Navegar para área de NFS-e
            self._navegar_para_nfse(driver)
            
            # Obter referência do frame principal
            frame_main = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "fraMain"))
            )
            # Navegar para o frame de filtros
            driver.switch_to.frame(frame_main)
            iframe_notas = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_frmObras"))
            )
            driver.switch_to.frame(iframe_notas)
            # Processar cada mês
            for month in months:
                try:
                    print(f"\n=== Iniciando processamento do mês: {month} ===")
                    self._processar_mes(driver, month)
                    print(f"=== Mês {month} processado com sucesso ===\n")
                except Exception as e:
                    print(f"Erro ao processar mês {month}: {e}")
                    continue
            
            print("Extração concluída para todos os meses!")
            
        except Exception as e:
            print(f"Erro durante extração: {e}")
            raise

    def solve_captcha(self, img_element):
        """
        Resolve captcha usando serviço CapSolver.
        
        Args:
            img_element: Elemento da imagem do captcha
            
        Returns:
            str: Texto do captcha resolvido
        """
        try:
            # Criar pasta temporária
            os.makedirs("temp", exist_ok=True)
            
            # Capturar screenshot do captcha
            image_path = "temp/captcha.jpeg"
            img_element.screenshot(image_path)
            
            # Converter para base64
            base64_string = self.image_to_base64(image_path)
            
            # Resolver captcha
            capsolver.api_key = self.captcha_key
            solution = capsolver.solve({
                "type": "ImageToTextTask",
                "body": base64_string,
                "module": "common",
                "borderless": True,
                "mediaSize": {
                    "height_microns": 297000,   # A4
                    "width_microns": 210000,
                    "name": "ISO_A4",
                    "custom_display_name": "A4"
                }
            })
            
            print(f"Captcha resolvido: {solution['text']}")
            return solution["text"]

        except Exception as e:
            raise Exception(f"Erro ao resolver captcha: {e}")
        
    def image_to_base64(self, image_path):
        """
        Converte uma imagem para string Base64.

        Args:
            image_path (str): Caminho para o arquivo de imagem

        Returns:
            str: String Base64 da imagem ou None se erro
        """
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
                return encoded_string
        except FileNotFoundError:
            print(f"Erro: Arquivo não encontrado: {image_path}")
            return None
        except Exception as e:
            print(f"Erro ao converter imagem: {e}")
            return None
        
    def abrir_navegador(self, profile_dir):
        """
        Configura e abre o navegador Chrome com configurações otimizadas.
        
        Args:
            profile_dir (str): Diretório do perfil do Chrome
            
        Returns:
            WebDriver: Instância do driver do Chrome configurado
        """
        try:
            os.makedirs(profile_dir, exist_ok=True)
            print(f"Usando perfil do Chrome: {profile_dir}")

            options = Options()
            options.add_argument(f"user-data-dir={os.path.abspath(profile_dir)}")
            options.add_argument("--disable-download-notification")
            options.add_argument("--kiosk-printing")
            
            # Configurações para download automático de PDFs
            prefs = {
                "download.default_directory": self.download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "plugins.always_open_pdf_externally": True,
                "print.always_print_silent": True,
                "printing.default_destination_selection_rules": {
                    "kind": "local",
                    "namePattern": "Save as PDF",
                },
                "savefile.default_directory": self.download_dir,
                "browser.download.manager.showWhenStarting": False,
                "browser.helperApps.neverAsk.saveToDisk": "application/pdf",
                "print_printer_pdf_printer_settings": {
                    "dpi": 300,
                    "use_system_print_dialog": False,
                },
                "print.default_destination_selection_rules": {
                    "kind": "local",
                    "namePattern": "Save as PDF",
                },
                "print.print_preview_sticky_settings.appState": json.dumps({
                    "recentDestinations": [{
                        "id": "Save as PDF",
                        "origin": "local",
                        "account": "",
                    }],
                    "selectedDestinationId": "Save as PDF",
                    "version": 2,
                    "isHeaderFooterEnabled": False,
                    "isLandscapeEnabled": False,
                    "marginsType": 2,  # 0=default, 1=minimum, 2=custom
                    "customMargins": {
                        "top": 0,
                        "bottom": 0,
                        "left": 0,
                        "right": 0
                    },
                    "scaling": 100,  # 100% da página
                    "scalingType": 3,  # 3=fit to page
                    "scalingPdf": 100,
                    "isScalingDisabled": False,
                    "isColorEnabled": False,
                    "isDuplexEnabled": False,
                    "duplex": 0,
                    "isLandscapeEnabled": False,
                    "pagesPerSheet": 1,
                    "copies": 1,
                    "defaultPrinter": "Save as PDF",
                    "borderless": True,
                    "mediaSize": {
                        "height_microns": 297000,   # A4
                        "width_microns": 210000,
                        "name": "ISO_A4",
                        "custom_display_name": "A4"
                    }
                })
            }
            options.add_experimental_option("prefs", prefs)
            
            driver = webdriver.Chrome(options=options)
            print("Navegador Chrome iniciado com sucesso!")
            return driver

        except Exception as e:
            raise Exception(f"Erro ao abrir navegador: {e}")
    
    def kill_chrome_instances(self):
        """Encerra todas as instâncias do Chrome em execução."""
        try:
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], check=True)
            print("Instâncias do Chrome encerradas com sucesso.")
        except subprocess.CalledProcessError as e:
            print(f"Erro ao encerrar Chrome: {e}")
            
    def upload_to_s3(self, file_path, s3_key):
        """
        Faz upload de um arquivo para o bucket S3 (funcionalidade desabilitada).
        
        Args:
            file_path (str): Caminho local do arquivo
            s3_key (str): Chave do arquivo no S3
            
        Returns:
            bool: Sempre False (funcionalidade desabilitada)
        """
        print("Upload para S3 está desabilitado nesta versão")
        return False

    def process_month(self, month):
        """Processa todas as notas de um mês específico"""
        print(f"\n=== Iniciando processamento do mês: {month} ===")
        print(f"Processando mês: {month}")
        
        # Configuração dos loggers
        canceled_logger, error_logger = setup_logging()
        
        try:
            # Clica no mês
            month_element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f"//div[contains(@class, 'month') and contains(text(), '{month}')]"))
            )
            month_element.click()
            time.sleep(2)

            # Processa cada página
            page = 1
            while True:
                try:
                    print(f"Processando página {page} do mês {month}")
                    
                    # Encontra todas as linhas da tabela
                    rows = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "tr.ng-scope"))
                    )
                    
                    # Filtra apenas as linhas que contêm notas (exclui cabeçalhos)
                    note_rows = [row for row in rows if row.get_attribute("ng-repeat") is not None]
                    
                    if not note_rows:
                        print(f"Nenhuma nota encontrada na página {page}")
                        break
                    
                    print(f"Encontradas {len(note_rows)} notas na página atual")
                    
                    # Processa cada nota
                    for i, row in enumerate(note_rows, 1):
                        try:
                            print(f"Processando nota {i}/{len(note_rows)}")
                            
                            # Verifica se a nota está cancelada
                            status_element = row.find_element(By.CSS_SELECTOR, "td:nth-child(4)")
                            if "Cancelada" in status_element.text:
                                nota_num = row.find_element(By.CSS_SELECTOR, "td:nth-child(1)").text
                                canceled_logger.info(f"Nota {nota_num} do mês {month} está cancelada")
                                continue
                            
                            # Clica na linha para abrir os detalhes
                            row.click()
                            time.sleep(1)
                            
                            # Processa a nota
                            self.process_note(month)
                            
                        except Exception as e:
                            error_logger.error(f"Erro ao processar nota na página {page}: {str(e)}")
                            print(f"Erro ao processar nota: {str(e)}")
                            continue
                    
                    # Tenta ir para a próxima página
                    try:
                        next_button = self.driver.find_element(By.CSS_SELECTOR, "button[ng-click='selectPage(page + 1, $event)']")
                        if "disabled" in next_button.get_attribute("class"):
                            print("Última página alcançada")
                            break
                        next_button.click()
                        time.sleep(2)
                        page += 1
                    except NoSuchElementException:
                        print("Botão de próxima página não encontrado")
                        break
                        
                except TimeoutException:
                    print(f"Timeout ao processar página {page}")
                    break
                except Exception as e:
                    error_logger.error(f"Erro ao processar página {page}: {str(e)}")
                    print(f"Erro ao processar página {page}: {str(e)}")
                    break
                    
            print(f"Todas as páginas do mês {month} foram processadas")
            print(f"=== Mês {month} processado com sucesso ===\n")
            
        except Exception as e:
            error_logger.error(f"Erro ao processar mês {month}: {str(e)}")
            print(f"Erro ao processar mês {month}: {str(e)}")

    def process_note(self, month):
        """Processa uma nota fiscal individual"""
        try:
            # Obtém o número da nota
            nota_num = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[ng-show='nfse.numero']"))
            ).text.split(": ")[1]
            
            print(f"Processando nota: {nota_num}")
            
            # Obtém o valor da nota
            valor_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[ng-show='nfse.valor']"))
            )
            valor = valor_element.text.split(": ")[1].replace("R$ ", "").replace(".", "").replace(",", ".")
            
            # Obtém a data da nota
            data_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[ng-show='nfse.data']"))
            )
            data = data_element.text.split(": ")[1]
            
            # Organiza o arquivo
            self._organizar_arquivo_baixado(month, data, nota_num, valor)
            
        except Exception as e:
            _, error_logger = setup_logging()
            error_logger.error(f"Erro ao processar nota {nota_num if 'nota_num' in locals() else 'desconhecida'}: {str(e)}")
            print(f"Erro ao processar nota: {str(e)}")


# Exemplo de uso da classe
if __name__ == "__main__":
    """
    Exemplo de como usar a classe ScrapNotaFiscal.
    Substitua os valores pelos dados reais antes de executar.
    """
    scraper = ScrapNotaFiscal()
    driver = None
    
    try:
        # Configurações
        CNPJ_LOGIN = "50417374000185"  # Substitua pelo CNPJ real
        SENHA = "sua_senha_aqui"       # Substitua pela senha real
        MESES_PROCESSAR = ["Janeiro", "Fevereiro", "Março"]  # Meses desejados
        
        # Iniciar navegador
        driver = scraper.abrir_navegador("chrome_profile")
        
        # Executar extração
        scraper.get_info(driver, CNPJ_LOGIN, SENHA, MESES_PROCESSAR)
        
    except Exception as e:
        print(f"Erro durante execução: {e}")
    finally:
        # Limpeza
        if driver:
            driver.quit()
        scraper.kill_chrome_instances()
        print("Processo finalizado!")

                

