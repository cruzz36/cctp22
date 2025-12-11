import socket
import os
import threading
import json
from otherEntities import Limit

lenMessageSize = 4

class TelemetryStream:
    """
    Protocolo TelemetryStream (TS) - Protocolo aplicacional sobre TCP para transmissão
    contínua de dados de monitorização dos rovers para a Nave-Mãe.
    
    Formato de mensagem: tamanho_nome(4 bytes) + nome_ficheiro + conteúdo_ficheiro
    """
    def __init__(self,ip,storefolder = ".",limit = 1024):
        """
        Inicializa o protocolo TelemetryStream.
        
        Args:
            ip (str): Endereço IP do servidor
            storefolder (str, optional): Pasta onde armazenar ficheiros recebidos. Defaults to "."
            limit (int, optional): Tamanho do buffer em bytes. Defaults to 1024
        """
        self.ip = ip
        self.port = 8081
        # Criar socket para servidor (bind) - será usado apenas no modo servidor
        # Para envios (send()), criamos novo socket para cada conexão
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Tentar fazer bind - pode falhar se porta já estiver em uso (normal em testes)
            self.socket.bind((self.ip, self.port))
        except OSError:
            # Porta já em uso - normal se múltiplas instâncias ou socket já ligado
            # O socket ainda pode ser usado para accept() se já estiver ligado
            pass
        if storefolder.endswith("/"): 
            self.storefolder = storefolder
        else: 
            self.storefolder = f"{storefolder}/"
        self.limit = Limit.Limit(limit)

    def _handle_client(self, clientSocket, ip, port):
        """
        Processa uma conexão de cliente em thread separada.
        Permite processamento paralelo de múltiplos rovers.
        
        COMO FUNCIONA:
        - Recebe dados de telemetria do cliente
        - Organiza ficheiros por rover_id (se possível)
        - Fecha conexão após processamento
        
        PORQUÊ:
        - Permite processar múltiplas conexões simultaneamente
        - Não bloqueia outras conexões
        - Melhora capacidade de lidar com múltiplos rovers em paralelo
        
        Args:
            clientSocket (socket.socket): Socket do cliente
            ip (str): Endereço IP do cliente
            port (int): Porta do cliente
        """
        try:
            filename = self.recv(clientSocket, ip, port)
            filename_str = filename.decode()
            
            # Tentar organizar por rover_id se o ficheiro contém telemetria JSON
            rover_id = "unknown"
            try:
                file_path = os.path.join(self.storefolder, filename_str)
                if os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        telemetry_data = json.load(f)
                        rover_id = telemetry_data.get("rover_id", "unknown")
                        rover_folder = os.path.join(self.storefolder, rover_id)
                        os.makedirs(rover_folder, exist_ok=True)
                        new_path = os.path.join(rover_folder, filename_str)
                        if os.path.exists(file_path) and file_path != new_path:
                            os.rename(file_path, new_path)
            except (json.JSONDecodeError, KeyError, OSError):
                pass
            
            print(f"[INFO] Telemetria recebida de {rover_id} ({ip}): {filename_str}")
            
        except Exception:
            pass
        finally:
            clientSocket.close()
    
    def server(self):
        """
        Inicia o servidor TelemetryStream em modo loop infinito.
        Aceita conexões TCP de múltiplos rovers e processa em paralelo.
        
        COMO FUNCIONA:
        - Coloca o socket em modo listening
        - Aceita conexões TCP de clientes (rovers) em loop infinito
        - Para cada conexão, cria thread separada para processamento paralelo
        - Threads processam dados de telemetria sem bloquear outras conexões
        
        PORQUÊ:
        - TCP permite conexões confiáveis para transmissão de telemetria
        - Threads permitem processar múltiplos rovers simultaneamente
        - Melhora capacidade de lidar com múltiplos rovers em paralelo
        - Organiza dados por rover_id automaticamente
        
        NOTA: Este método bloqueia indefinidamente - deve ser executado em thread separada
        """
        print(f"[INFO] Servidor TelemetryStream iniciado em {self.ip}:{self.port}")
        self.socket.listen()
        
        while True:
            try:
                clientSocket, (ip, _) = self.socket.accept()
                print(f"[INFO] Conexão TelemetryStream estabelecida com {ip}")
                # Criar thread para processar conexão em paralelo
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(clientSocket, ip, self.port),
                    daemon=True
                )
                client_thread.start()
            except Exception:
                continue

    def formatInteger(self,num):
        """
        Formata um número inteiro como string com 4 dígitos, preenchendo com zeros à esquerda.
        
        Args:
            num (int): Número a formatar
            
        Returns:
            str: String com 4 dígitos
        """
        line = str(num)
        displacement = 4 - len(line)
        for i in range(displacement):
            line = "0" + line
        return line

    def recv(self,clientSock:socket.socket,ip,port):
        """
        Recebe dados de telemetria de um cliente através de uma conexão TCP.
        Primeiro recebe o tamanho do nome do ficheiro (4 bytes), depois o nome do ficheiro,
        e finalmente o conteúdo do ficheiro.
        
        COMO FUNCIONA:
        - Recebe 4 bytes que indicam o tamanho do nome do ficheiro
        - Recebe o nome do ficheiro (número de bytes indicado)
        - Recebe o conteúdo do ficheiro em chunks até receber dados vazios
        - Escreve o ficheiro na pasta storefolder
        
        PORQUÊ:
        - TCP é stream-oriented, então precisamos saber o tamanho do nome antes de receber
        - Receção em chunks permite lidar com ficheiros grandes
        - Validação previne ataques (tamanho excessivo)
        
        Args:
            clientSock (socket.socket): Socket TCP do cliente conectado
            ip (str): Endereço IP do cliente
            port (int): Porta do cliente
            
        Returns:
            bytes: Nome do ficheiro recebido
            
        Raises:
            ValueError: Se o tamanho do nome do ficheiro for inválido
            OSError: Se houver erro ao escrever o ficheiro
        """ 
        try:
            # Receber tamanho do nome do ficheiro (4 bytes)
            message = clientSock.recv(lenMessageSize)
            if len(message) != lenMessageSize:
                raise ValueError(f"Tamanho do nome do ficheiro inválido: recebidos {len(message)} bytes, esperados {lenMessageSize}")
            
            fileNameLen = int(message.decode())
            
            # Validar tamanho do nome do ficheiro (prevenir ataques)
            if fileNameLen < 1 or fileNameLen > 255:
                raise ValueError(f"Tamanho do nome do ficheiro inválido: {fileNameLen} (deve estar entre 1 e 255)")
            
            # Receber nome do ficheiro
            filename = clientSock.recv(fileNameLen)
            if len(filename) != fileNameLen:
                raise ValueError(f"Nome do ficheiro incompleto: recebidos {len(filename)} bytes, esperados {fileNameLen}")
            
            filename_str = filename.decode()
            
            # Criar pasta se não existir
            os.makedirs(self.storefolder, exist_ok=True)
            
            # Receber e escrever conteúdo do ficheiro
            file_path = os.path.join(self.storefolder, filename_str)
            with open(file_path, "w") as file:
                message = clientSock.recv(self.limit.buffersize)
                while message != b"":
                    file.write(message.decode())
                    message = clientSock.recv(self.limit.buffersize)
            
            return filename
            
        except ValueError as e:
            print(f"Erro de validação ao receber telemetria: {e}")
            raise
        except OSError as e:
            print(f"Erro ao escrever ficheiro de telemetria: {e}")
            raise
        except Exception as e:
            print(f"Erro ao receber telemetria: {e}")
            raise
                


    def send(self,ip,message:str):
        """
        Envia um ficheiro de telemetria para o servidor através de TCP.
        Primeiro envia o tamanho do nome do ficheiro, depois o nome, e finalmente o conteúdo.
        
        COMO FUNCIONA:
        - Cria um novo socket TCP para cada envio (evita conflito com socket do servidor)
        - Conecta ao servidor, envia tamanho do nome (4 bytes), nome do ficheiro, e conteúdo
        - Fecha a conexão após envio completo
        
        PORQUÊ:
        - O socket criado no __init__ pode estar ligado ao servidor (bind)
        - Tentar fazer connect() num socket já ligado causa OSError
        - Criar novo socket para cada envio garante que funciona tanto como cliente quanto servidor
        
        Args:
            ip (str): Endereço IP do servidor destinatário
            message (str): Caminho do ficheiro a enviar
            
        Returns:
            bool: True se o ficheiro foi enviado com sucesso, False em caso de erro
        """
        # Criar novo socket para cada envio (evita conflito com socket do servidor)
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        try:
            # Verificar se ficheiro existe antes de tentar enviar
            if not os.path.exists(message):
                return False
            
            # Extrair apenas o nome do ficheiro (sem caminho completo)
            filename = os.path.basename(message)
            
            # Conectar ao servidor
            client_socket.connect((ip, self.port))
            
            # Enviar tamanho do nome do ficheiro (4 bytes)
            length = self.formatInteger(len(filename))
            client_socket.sendall(length.encode())
            
            # Enviar nome do ficheiro
            client_socket.sendall(filename.encode())
            
            # Enviar conteúdo do ficheiro em chunks
            with open(message, "r") as file:
                buffer = file.read(self.limit.buffersize)
                while buffer != "":
                    client_socket.sendall(buffer.encode())
                    buffer = file.read(self.limit.buffersize)
            
            # Fechar conexão
            client_socket.close()
            return True
            
        except Exception:
            try:
                client_socket.close()
            except:
                pass
            return False

    def endConnection(self):
        """
        Fecha a conexão TCP do socket principal.
        
        NOTA: Este método fecha o socket do servidor (self.socket).
        Para envios (send()), um novo socket é criado e fechado automaticamente.
        Este método é útil apenas se precisar fechar o servidor explicitamente.
        
        COMO FUNCIONA:
        - Verifica se o socket existe e está aberto
        - Fecha o socket
        - Imprime mensagem de confirmação
        
        PORQUÊ:
        - Permite fechar o servidor explicitamente se necessário
        - Útil para cleanup ou reinicialização
        """
        if self.socket is not None:
            try:
                self.socket.close()
                print("Connection closed.")
            except Exception as e:
                print(f"Erro ao fechar conexão: {e}")