import socket
from otherEntities import Limit
import time
import threading


# [flag,idMission,seq,ack,size,missionType,message]
#   0       1      2   3   4        5           6
# NOTA: No handshake, idMission contém temporariamente o ID do rover
#       Após handshake, idMission contém o ID da missão
flagPos = 0
idMissionPos = 1
seqPos = 2
ackPos = 3
sizePos = 4
missionTypePos = 5
messagePos = 6


class MissionLink:
    """
    Protocolo MissionLink (ML) - Protocolo aplicacional sobre UDP para comunicação crítica
    entre a Nave-Mãe e os rovers. Implementa mecanismos de fiabilidade a nível aplicacional
    incluindo handshake, números de sequência, acknowledgments e retransmissão.
    """
    def __init__(self,serverAddress,storeFolder = "."):
        """
        Inicializa o protocolo MissionLink.
        
        Args:
            serverAddress (str): Endereço IP do servidor
            storeFolder (str, optional): Pasta onde armazenar ficheiros recebidos. Defaults to "."
        """
        self.serverAddress = serverAddress
        self.port = 8080
        self.sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.server()
        self.limit = Limit.Limit()
        self.sock.settimeout(self.limit.timeout)
        # Lock para proteger operações críticas do socket (evitar race conditions entre startConnection e acceptConnection)
        self.sock_lock = threading.Lock()
        if storeFolder.endswith("/"):
            self.storeFolder = storeFolder
        else:
            self.storeFolder = storeFolder + "/"
        # ============================================================
        # TIPOS DE OPERAÇÃO DO PROTOCOLO (missionType)
        # ============================================================
        # NOTA IMPORTANTE: Estes valores (R, T, M, Q, P) são diferentes dos tipos de tarefa
        #                  que aparecem dentro do JSON da missão (capture_images, sample_collection, environmental_analysis).
        #
        # missionType indica o TIPO DE OPERAÇÃO do protocolo:
        #   - Como processar a mensagem recebida
        #   - Que handler chamar no servidor/cliente
        #   - Qual o propósito da comunicação
        #
        # task (dentro do JSON) indica o TIPO DE TAREFA da missão:
        #   - O que o rover deve executar fisicamente
        #   - Apenas aparece quando missionType="T" (Task)
        #   - Valores possíveis: "capture_images", "sample_collection", "environmental_analysis"
        # ============================================================
        self.registerAgent = "R"      # Register: Rover regista-se na Nave-Mãe
        self.taskRequest = "T"        # Task: Nave-Mãe envia missão ao rover (JSON contém campo "task")
        # self.sendMetrics = "M"       # Metrics: Rover envia métricas à Nave-Mãe
        self.requestMission = "Q"    # Request/Query: Rover solicita uma missão à Nave-Mãe
        self.reportProgress = "P"      # Progress: Rover reporta progresso de uma missão em execução
        self.noneType = "N"           # None: ACK/FIN sem tipo de operação específico (codificado quando missionType=None)
        
        # ============================================================
        # FLAGS DE CONTROLO DO PROTOCOLO
        # ============================================================
        # Flags para controlo de conexão e fiabilidade sobre UDP
        self.datakey = "D"           # Data: Mensagem de dados normal
        self.synkey = "S"            # SYN: Inicia handshake (3-way)
        self.ackkey = "A"            # ACK: Confirmação de receção
        self.finkey = "F"            # FIN: Fecha conexão
        self.synackkey = "Z"         # SYN-ACK: Resposta ao SYN no handshake
        # Constante para fim de mensagem - melhora manutenibilidade
        self.eofkey = '\0'

    
    def server(self):
        """
        Liga o socket UDP ao endereço e porta especificados.
        Prepara o socket para receber mensagens.
        
        COMO FUNCIONA:
        - Usa o método bind() do socket para associar o socket ao endereço IP e porta
        - Após bind, o socket está pronto para receber mensagens UDP na porta 8080
        - Este método deve ser chamado antes de qualquer operação de receção
        
        PORQUÊ:
        - UDP não tem conexão, então precisamos de "ligar" o socket a um endereço/porta
        - Sem bind, não podemos receber mensagens - o sistema não sabe onde enviar os dados
        - O bind associa o socket ao endereço local, permitindo receber pacotes UDP
        
        NOTA: Este método é chamado automaticamente no __init__, não precisa ser chamado manualmente
        """
        # Liga o socket UDP ao endereço IP e porta especificados
        # Após esta linha, o socket está pronto para receber mensagens UDP
        self.sock.bind((self.serverAddress,self.port))


    def getHeaderSize(self):
        """
        Calcula o tamanho do cabeçalho da mensagem do protocolo.
        
        COMO FUNCIONA:
        - Soma o tamanho de todos os campos do cabeçalho do protocolo
        - Formato: flag|idMission|seq|ack|size|missionType|message
        - Cada campo tem tamanho fixo, separados por "|" (1 byte cada)
        
        PORQUÊ:
        - Necessário para calcular quanto espaço sobra para dados úteis
        - Quando enviamos mensagens grandes, precisamos saber quantos bytes podemos enviar por chunk
        - Tamanho útil = buffersize - headerSize
        
        Returns:
            int: Tamanho do cabeçalho em bytes (flag + separadores + idMission + seq + ack + size + missionType)
        
        Cálculo detalhado:
            flag: 1 byte (S, Z, A, F, D)
            |: 1 byte (separador)
            idMission: 3 bytes (ex: "M01")
            |: 1 byte
            seq: 4 bytes (número de sequência)
            |: 1 byte
            ack: 4 bytes (acknowledgment)
            |: 1 byte
            size: 4 bytes (tamanho da mensagem)
            |: 1 byte
            missionType: 1 byte (R, T, M, Q, P, N)
            |: 1 byte
            Total: 1+1+3+1+4+1+4+1+4+1+1+1 = 23 bytes
        """
        # flag + | + idMission + | + seq + | + ack + | + size + | + missionType + |
        return 1 + 1 + 3 + 1 + 4 + 1 + 4 + 1 + 4 + 1 + 1 + 1
    
    def formatMessage(self,missionType,flag,idMission,seqNum,ackNum,message):
        """
        Formata uma mensagem segundo o protocolo MissionLink.
        Formato: flag|idMission|seq|ack|size|missionType|message
        
        NOTA: No handshake, idMission contém temporariamente o ID do rover.
              Nas mensagens de dados, idMission contém o ID da missão.
        
        ============================================================
        DIFERENÇA ENTRE missionType E task:
        ============================================================
        - missionType (campo do protocolo): Tipo de OPERAÇÃO (R, T, M, Q, P)
          * R = Register: Rover regista-se
          * T = Task: Nave-Mãe envia missão
          * M = Metrics: Rover envia métricas
          * Q = Request: Rover solicita missão
          * P = Progress: Rover reporta progresso
        
        - task (campo dentro do JSON): Tipo de TAREFA física (quando missionType="T")
          * "capture_images": Capturar imagens
          * "sample_collection": Recolher amostras
          * "environmental_analysis": Análise ambiental
        ============================================================
        
        Formato de mensagem de missão (quando missionType="T"):
        O campo 'message' deve conter um JSON com os seguintes campos obrigatórios:
        {
            "mission_id": string (obrigatório, identificador único da missão),
            "rover_id": string (obrigatório, ID do rover destinatário),
            "geographic_area": {
                "x1": float, "y1": float, "x2": float, "y2": float
            } (obrigatório, área geográfica a explorar),
            "task": string (obrigatório, tipo de tarefa: capture_images|sample_collection|environmental_analysis),
            "duration_minutes": integer (obrigatório, > 0, tempo máximo para execução)
        }
        
        Campos opcionais:
        - "priority": string (low|medium|high)
        - "instructions": string (instruções adicionais)
        
        Exemplo de mensagem de missão:
        {
            "mission_id": "M-001",
            "rover_id": "r1",
            "geographic_area": {"x1": 10.0, "y1": 20.0, "x2": 50.0, "y2": 60.0},
            "task": "capture_images",  ← Tipo de tarefa (um dos 3 possíveis)
            "duration_minutes": 30
        }
        
        Args:
            missionType (str or None): Tipo de operação do protocolo (R=Register, T=Task, M=Metrics, Q=Request, P=Progress) ou None
            flag (str): Flag de controlo (S=SYN, A=ACK, F=FIN, Z=SYN-ACK, D=Data)
            idMission (str): Identificador da missão (3 caracteres) ou ID do rover no handshake
            seqNum (int): Número de sequência
            ackNum (int): Número de acknowledgment
            message (str): Conteúdo da mensagem (JSON string quando missionType="T", onde o JSON contém o campo "task")
            
        Returns:
            bytes: Mensagem formatada e codificada em bytes
        """
        # Bug fix: Quando missionType=None, codificar como "N" apenas para ACKs/FINs
        #          Para mensagens de dados, preservar o missionType original passado ao send()
        #          Isto garante que quando o servidor envia missões com taskRequest ("T"),
        #          o rover recebe "T" em vez de "N", permitindo roteamento correto do protocolo
        if missionType != None: 
            return f"{flag}|{idMission}|{seqNum}|{ackNum}|{len(message)}|{missionType}|{message}".encode()
        # missionType=None é usado apenas para ACKs/FINs, codificar como "N"
        return f"{flag}|{idMission}|{seqNum}|{ackNum}|{len(message)}|N|{message}".encode()
        

    def splitMessage(self,message):
        """
        Divide uma mensagem em chunks se exceder o tamanho máximo do buffer.
        
        COMO FUNCIONA:
        - Calcula o tamanho máximo útil (buffersize - headerSize)
        - Se a mensagem for maior, divide em pedaços (chunks) desse tamanho
        - Se couber num pacote, retorna a mensagem original como string
        - Se não couber, retorna uma lista de strings (chunks)
        
        PORQUÊ:
        - UDP tem limite de tamanho de pacote (geralmente 65507 bytes, mas usamos 1024)
        - Mensagens grandes precisam ser fragmentadas em múltiplos pacotes
        - Cada chunk será enviado separadamente e reconstruído no destino
        
        Exemplo:
            Mensagem de 2500 bytes, buffer útil = 1000 bytes
            Retorna: ["bytes 0-999", "bytes 1000-1999", "bytes 2000-2499"]
        
        Args:
            message (str): Mensagem a dividir
            
        Returns:
            str or list: Mensagem original se couber num pacote, ou lista de chunks
        """
        # Calcula tamanho máximo útil (tamanho total do buffer menos o cabeçalho)
        max_useful_size = self.limit.buffersize - self.getHeaderSize()
        
        # Se a mensagem for maior que o tamanho útil, divide em chunks
        if len(message) > max_useful_size:
            # Cria lista de chunks, cada um com tamanho máximo útil
            # range(0, len(message), max_useful_size) cria índices: 0, max_useful_size, 2*max_useful_size, ...
            # message[i:i+max_useful_size] extrai o chunk da posição i até i+max_useful_size
            return [message[i:i+max_useful_size] for i in range(0, len(message), max_useful_size)]
        else:
            # Se couber num pacote, retorna a mensagem original
            return message


    def startConnection(self, idAgent, destAddress, destPort, retryLimit=5):
        """
        Inicia uma conexão com handshake de 3 vias (SYN, SYN-ACK, ACK).
        Implementa mecanismo de fiabilidade sobre UDP.
        
        NOTA: No handshake, o campo idMission é usado temporariamente para enviar o ID do rover.
              A Nave-Mãe guarda o mapeamento (IP, porta) -> ID do rover.
        
        Args:
            idAgent (str): Identificador do agente/rover (3 caracteres)
            destAddress (str): Endereço IP do destino
            destPort (int): Porta do destino
            retryLimit (int, optional): Número máximo de tentativas. Defaults to 5
            
        Returns:
            tuple: ((destAddress, destPort), idAgent, seq, ack) - Informação da conexão estabelecida
            
        Raises:
            TimeoutError: Se não conseguir estabelecer conexão após múltiplas tentativas
        """
        seqinicial = 100
        retries = 0
        print(f"[DEBUG] startConnection: Iniciando handshake com {destAddress}:{destPort}, idAgent={idAgent}, retryLimit={retryLimit}")
        
        while retries < retryLimit:
            try:
                # Send SYN - no handshake, idMission contém o ID do rover
                print(f"[DEBUG] startConnection: Enviando SYN (tentativa {retries + 1}/{retryLimit})")
                self.sock.sendto(
                    f"{self.synkey}|{idAgent}|{seqinicial}|0|_|0|-.-".encode(),
                    (destAddress, destPort)
                )
                try:
                    # Aguardar um pouco antes de receber para dar tempo ao servidor enviar SYN-ACK
                    time.sleep(0.1)  # Reduzido de 0.3s para 0.1s
                    # Usar lock para evitar que acceptConnection() consuma o SYN-ACK
                    synack_received = False
                    synack_retries = 0
                    max_synack_retries = 5  # Reduzido de 10 para 5 - suficiente para 1% packet loss
                    
                    while not synack_received and synack_retries < max_synack_retries:
                        try:
                            with self.sock_lock:
                                # Timeout aumentado para dar mais oportunidade de receber SYN-ACK
                                # mesmo que acceptConnection() tenha consumido o anterior
                                original_timeout_inner = self.sock.gettimeout()
                                self.sock.settimeout(2.0)  # Timeout de 2s para receber SYN-ACK (aumentado para compensar acceptConnection)
                                try:
                                    message, (recv_ip, recv_port) = self.sock.recvfrom(self.limit.buffersize)
                                finally:
                                    self.sock.settimeout(original_timeout_inner)
                            
                            lista = message.decode().split("|")
                            if len(lista) < 7:
                                synack_retries += 1
                                # Reenviar SYN se não recebeu resposta válida
                                if synack_retries % 2 == 0:  # Reenviar a cada 2 tentativas (reduzido de 3)
                                    self.sock.sendto(
                                        f"{self.synkey}|{idAgent}|{seqinicial}|0|_|0|-.-".encode(),
                                        (destAddress, destPort)
                                    )
                                time.sleep(0.1)  # Reduzido de 0.5s para 0.1s
                                continue
                            
                            # Verificar se o pacote veio do destino correto
                            if recv_ip != destAddress or recv_port != destPort:
                                synack_retries += 1
                                time.sleep(0.05)  # Reduzido de 0.2s para 0.05s
                                continue  # Continuar a aguardar sem incrementar retries principais
                            
                            # Verificar se recebeu SYN-ACK válido
                            if lista[flagPos] == self.synackkey:
                                print(f"[DEBUG] startConnection: SYN-ACK recebido de {destAddress}:{destPort}")
                                synack_received = True
                                break
                            else:
                                # Recebeu outro tipo de pacote, continuar a aguardar
                                synack_retries += 1
                                time.sleep(0.05)  # Reduzido de 0.2s para 0.05s
                                continue
                                
                        except socket.timeout:
                            synack_retries += 1
                            print(f"[PACKET LOSS] Timeout ao aguardar SYN-ACK de {destAddress}:{destPort} (tentativa {synack_retries}/{max_synack_retries})")
                            # Reenviar SYN periodicamente
                            if synack_retries % 2 == 0:  # Reenviar a cada 2 timeouts
                                print(f"[RETRANSMISSÃO] Reenviando SYN para {destAddress}:{destPort}")
                                self.sock.sendto(
                                    f"{self.synkey}|{idAgent}|{seqinicial}|0|_|0|-.-".encode(),
                                    (destAddress, destPort)
                                )
                            time.sleep(0.1)  # Reduzido de 0.3s para 0.1s
                            continue
                        except Exception:
                            synack_retries += 1
                            time.sleep(0.1)  # Reduzido de 0.3s para 0.1s
                            continue
                    
                    # Se não recebeu SYN-ACK após múltiplas tentativas, incrementar retry principal
                    if not synack_received:
                        retries += 1
                        if retries >= retryLimit:
                            break
                        continue

                except socket.timeout:
                    retries += 1
                    if retries >= retryLimit:
                        break
                    continue
                except Exception:
                    retries += 1
                    if retries >= retryLimit:
                        break
                    continue

                # Send ACK
                print(f"[DEBUG] startConnection: Enviando ACK para completar handshake")
                self.sock.sendto(
                    f"{self.ackkey}|{idAgent}|{seqinicial}|{seqinicial}|_|0|-.-".encode(),
                    (destAddress, destPort)
                )
                print(f"[DEBUG] startConnection: Handshake concluído com sucesso - seq={seqinicial + 1}")
                return  (destAddress,destPort),idAgent,seqinicial + 1,seqinicial + 1 # Handshake successful

            
        
            except socket.timeout:
                retries += 1
            except Exception:
                retries += 1
        
        error_msg = f"Falha ao estabelecer conexão com {destAddress}:{destPort} após {retryLimit} tentativas"
        raise TimeoutError(error_msg)


    def acceptConnection(self):
        """
        Aceita uma conexão recebendo um pedido SYN e respondendo com handshake de 3 vias.
        Deve ser executado pelo servidor (Nave-Mãe).
        
        NOTA: No handshake, o campo idMission contém temporariamente o ID do rover.
              O servidor deve guardar o mapeamento (IP, porta) -> ID do rover.
        
        Returns:
            tuple: ((ip, port), idAgent, seq, ack) - Informação da conexão estabelecida
                - ip (str): Endereço IP do cliente
                - port (int): Porta do cliente
                - idAgent (str): Identificador do agente/rover (extraído de idMission no handshake)
                - seq (int): Número de sequência inicial
                - ack (int): Número de acknowledgment inicial (igual a seq)
        """
        print(f"[DEBUG] acceptConnection: Aguardando SYN...")
        # RECEBER O SYN
        # CRÍTICO: acceptConnection() só deve consumir pacotes SYN quando está à espera de SYN
        #           Se consumir pacotes D (dados), SYN-ACK, ou ACK, impede que recv() e startConnection() os recebam
        #           Como UDP não permite peek, usamos timeout muito curto e só processamos SYN
        original_timeout = self.sock.gettimeout()
        # Timeout MUITO curto (10ms) para não bloquear recv() e startConnection() - apenas verificar se há SYN
        self.sock.settimeout(0.01)  # 10ms - extremamente curto para não interferir com outras operações
        
        while True:
            try:
                # Usar lock APENAS durante recvfrom(), não durante todo o processamento
                with self.sock_lock:
                    message,(ip,port) = self.sock.recvfrom(self.limit.buffersize)
                # Lock libertado aqui - recv() e startConnection() podem agora receber pacotes
                
                lista = message.decode().split("|")
                if len(lista) < 7:
                    # Mensagem malformada - ignorar e continuar
                    continue
                flag = lista[flagPos]
                
                # CRÍTICO: Só processar SYN. Todos os outros pacotes (D, SYN-ACK, ACK, FIN) devem ser ignorados
                #          porque são destinados a recv() ou startConnection()
                if flag == self.synkey:
                    print(f"[DEBUG] acceptConnection: SYN recebido de {ip}:{port}, idAgent={lista[idMissionPos]}")
                    # Restaurar timeout original antes de continuar
                    self.sock.settimeout(original_timeout)
                    print(f"[DEBUG] acceptConnection: SYN válido processado")
                    break
                else:
                    # NÃO É SYN - não processar, não fazer nada, simplesmente continuar
                    # Este pacote foi consumido mas não é para nós - recv() ou startConnection() vão receber o próximo
                    # Não fazer print para não poluir logs - apenas continuar
                    continue
            except socket.timeout:
                # Timeout é normal e esperado - lock já foi libertado, então recv() e startConnection() podem receber pacotes
                # Não fazer sleep - deixar outras operações terem oportunidade imediata
                continue
        
        # Restaurar timeout original
        self.sock.settimeout(original_timeout)
        # No handshake, idMission contém o ID do rover
        idAgent = lista[idMissionPos]
        print(f"[DEBUG] acceptConnection: Enviando SYN-ACK para {ip}:{port}, idAgent={idAgent}")
        # ENVIAR SYNACK 
        lista[flagPos] = self.synackkey
        prevLista = lista.copy()
        self.sock.sendto("|".join(lista).encode(),(ip,port))
        print(f"[DEBUG] acceptConnection: SYN-ACK enviado, aguardando ACK")
        # RECEBER ACK
        ack_retries = 0
        max_ack_retries = 5  # Reduzido de 10 para 5 - suficiente para 1% packet loss
        while ack_retries < max_ack_retries:
            try:
                # Usar lock para evitar race conditions
                with self.sock_lock:
                    message, (recv_ip, recv_port) = self.sock.recvfrom(self.limit.buffersize)
                # Verificar se o pacote veio do cliente correto
                if recv_ip != ip or recv_port != port:
                    # Pacote de origem diferente - não é para nós, continuar a aguardar
                    # Não incrementar retries porque pode ser outro cliente
                    time.sleep(0.01)  # Reduzido para não bloquear
                    continue
                lista = message.decode().split("|")
                if len(lista) < 7:
                    # Mensagem malformada - reenviar SYN-ACK
                    print(f"[RETRANSMISSÃO] Reenviando SYN-ACK para {ip}:{port} (mensagem malformada)")
                    self.sock.sendto("|".join(prevLista).encode(),(ip,port))
                    ack_retries += 1
                    time.sleep(0.05)  # Reduzido de 0.1s para 0.05s
                    continue
                if (lista[flagPos] == self.ackkey and 
                lista[idMissionPos] == idAgent and 
                lista[ackPos] == lista[seqPos]):
                    print(f"[DEBUG] acceptConnection: ACK recebido, handshake concluído - seq={lista[seqPos]}, ack={lista[ackPos]}")
                    return (ip,port),idAgent,int(lista[seqPos]),int(lista[ackPos])
                else:
                    # Pacote recebido mas não é ACK válido - reenviar SYN-ACK
                    print(f"[RETRANSMISSÃO] Reenviando SYN-ACK para {ip}:{port} (ACK inválido)")
                    self.sock.sendto("|".join(prevLista).encode(),(ip,port))
                    ack_retries += 1
                    time.sleep(0.05)  # Reduzido de 0.1s para 0.05s
                    continue
            except socket.timeout:
                # Timeout ao aguardar ACK - reenviar SYN-ACK mais agressivamente
                print(f"[PACKET LOSS] Timeout ao aguardar ACK do handshake de {ip}:{port} (tentativa {ack_retries+1}/{max_ack_retries})")
                print(f"[RETRANSMISSÃO] Reenviando SYN-ACK para {ip}:{port}")
                self.sock.sendto("|".join(prevLista).encode(),(ip,port))
                ack_retries += 1
                time.sleep(0.05)  # Reduzido - reenvio mais rápido
                continue
            except Exception:
                print(f"[RETRANSMISSÃO] Reenviando SYN-ACK para {ip}:{port} (erro)")
                self.sock.sendto("|".join(prevLista).encode(),(ip,port))
                ack_retries += 1
                time.sleep(0.05)
                continue

        
        
    def send(self,ip,port,missionType,idAgent,idMission,message):
        """
        Envia uma mensagem ou ficheiro através do protocolo MissionLink.
        Estabelece conexão, envia dados com confirmação e fecha conexão.
        
        Args:
            ip (str): Endereço IP do destinatário
            port (int): Porta do destinatário
            missionType (str): Tipo de missão/operação (R=Register, T=Task, M=Metrics, Q=Request, P=Progress)
            idAgent (str): Identificador do agente/rover (usado apenas no handshake)
            idMission (str): Identificador da missão (3 caracteres, "000" se não aplicável)
            message (str): Mensagem ou caminho do ficheiro a enviar
            
        Returns:
            bool: True se a mensagem foi enviada com sucesso
        """
        # Bug fix: Garantir que message é string antes de chamar métodos de string
        if not isinstance(message, str):
            message = str(message)
        
        print(f"[DEBUG] send: Iniciando envio - missionType={missionType}, idAgent={idAgent}, idMission={idMission}, tamanho={len(message)} bytes, destino={ip}:{port}")
        
        # The connection starts with an handshake to assure it has a somewhat reliable 
        # transfers between the client and the server 
        print(f"[DEBUG] send: Iniciando handshake com {ip}:{port}")
        _,idAgent,seq,ack = self.startConnection(idAgent,ip,port)
        print(f"[DEBUG] send: Handshake concluído - seq={seq}, ack={ack}")

        if message.endswith(".json"):
            # First cycle is to send the filename
            print(f"[DEBUG] send: Enviando ficheiro: {message}")
            while True:
                print(f"[DEBUG] send: Enviando nome do ficheiro (seq={seq})")
                self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,message),(ip,port))
                try:
                    text,(responseIp,responsePort) = self.sock.recvfrom(self.limit.buffersize)
                    lista = text.decode().split("|")
                    # Validar formato da mensagem
                    if len(lista) < 7:
                        # Mensagem malformada - retransmitir nome do ficheiro
                        continue
                    if(
                        responseIp == ip and
                        responsePort == port and
                        lista[flagPos] == self.ackkey and
                        lista[ackPos] == str(seq) and
                        lista[idMissionPos] == idMission  # Validação de segurança: verifica idMission
                    ):
                        seq += 1
                        ack = seq
                        print(f"[DEBUG] send: Nome do ficheiro confirmado (ACK recebido, seq={seq})")
                        break
                except socket.timeout:
                    # Timeout ao aguardar ACK - retransmitir nome do ficheiro
                    print(f"[PACKET LOSS] Timeout ao aguardar ACK do nome do ficheiro de {ip}:{port}")
                    print(f"[RETRANSMISSÃO] Reenviando nome do ficheiro para {ip}:{port}")
                    continue
                except Exception as e:
                    print(f"Erro ao aguardar ACK do nome do ficheiro: {e}")
                    continue

            with open(message,"r") as file:
                buffer = file.read(self.limit.buffersize-self.getHeaderSize())
                i = 1
                while buffer:
                    i+=1
                    self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,buffer),(ip,port))
                    try:
                        text,(responseIp,responsePort) = self.sock.recvfrom(self.limit.buffersize)
                        lista = text.decode().split("|")
                        # Bug fix: Validar formato da mensagem antes de aceder a índices
                        if len(lista) < 7:
                            # Mensagem malformada - retransmitir chunk
                            self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,buffer),(ip,port))
                            continue
                        if(
                            responseIp == ip and
                            responsePort == port and
                            lista[flagPos] == self.ackkey and
                            lista[ackPos] == str(seq) and
                            lista[idMissionPos] == idMission  # Validação de segurança: verifica idMission
                        ):
                            seq += 1
                            ack = seq
                            buffer = file.read(self.limit.buffersize - self.getHeaderSize())
                    except socket.timeout:
                        # Retransmitir chunk em caso de timeout
                        print(f"[PACKET LOSS] Timeout ao aguardar ACK do chunk {i} de {ip}:{port}")
                        print(f"[RETRANSMISSÃO] Reenviando chunk {i} para {ip}:{port}")
                        self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,buffer),(ip,port))
                        continue
            # Incrementar seq antes de enviar FIN para garantir número de sequência diferente
            # Evita ambiguidade entre último chunk e FIN
            seq += 1
            ack = seq
            self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
            while True:
                try:
                    text,(responseIp,responsePort) = self.sock.recvfrom(self.limit.buffersize)
                    lista = text.decode().split("|")
                    # Validação do pacote FIN recebido
                    if(
                        len(lista) == 7 and
                        responseIp == ip and
                        responsePort == port and
                        lista[ackPos] == str(seq) and
                        lista[flagPos] == self.finkey and
                        lista[idMissionPos] == idMission  # Validação de segurança: verifica idMission
                    ):
                        seq += 1
                        ack = seq
                        # Confirmação FIN recebida corretamente
                        self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
                        return True
                except socket.timeout:
                    print(f"[PACKET LOSS] Timeout ao aguardar FIN-ACK de {ip}:{port} (ficheiro)")
                    print(f"[RETRANSMISSÃO] Reenviando FIN para {ip}:{port}")
                    self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
                    

        else:
            chunks = self.splitMessage(message)

            # If chunks is a string, only a packet with data is sent
            # The next one is a connection closing one
            if isinstance(chunks,str):
                print(f"[DEBUG] send: Mensagem cabe num único pacote ({len(chunks)} bytes)")
                print(f"[DEBUG] send: Enviando mensagem completa (seq={seq})")
                self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,chunks),(ip,port))
                while True: 
                    try:
                        # Usar lock para evitar que acceptConnection() consuma o ACK
                        with self.sock_lock:
                            text,(responseIp,responsePort) = self.sock.recvfrom(self.limit.buffersize)
                        lista = text.decode().split("|")
                        # Bug fix: Validar formato da mensagem antes de aceder a índices
                        if len(lista) < 7:
                            # Mensagem malformada - retransmitir mensagem
                            self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,chunks),(ip,port))
                            continue
                        if (responseIp == ip and
                            responsePort == port and
                            lista[ackPos] == str(seq) and 
                            lista[flagPos] == self.ackkey and
                            lista[idMissionPos] == idMission  # Validação de segurança: verifica idMission
                            ):
                            seq += 1
                            ack = seq
                            print(f"[DEBUG] send: ACK da mensagem recebido (seq={seq}), iniciando fechamento de conexão")
                            self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
                            print(f"[DEBUG] send: FIN enviado (seq={seq}), aguardando FIN-ACK")
                            # Fechamento bidirecional completo (4-way handshake)
                            # Aguarda ACK do FIN enviado OU FIN do outro lado
                            while True:
                                try:
                                    # Usar lock para evitar que acceptConnection() consuma pacotes
                                    with self.sock_lock:
                                        text,(responseIp,responsePort) = self.sock.recvfrom(self.limit.buffersize)
                                    lista = text.decode().split("|")
                                    # Validar formato da mensagem
                                    if len(lista) < 7:
                                        # Mensagem malformada - reenviar FIN
                                        self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
                                        continue
                                    if (
                                        responseIp == ip and
                                        responsePort == port and
                                        len(lista) == 7 and
                                        lista[idMissionPos] == idMission
                                    ):
                                        if lista[flagPos] == self.finkey:
                                            # Recebeu FIN do outro lado - responder com ACK
                                            # Bug fix: Deve reconhecer o número de sequência do FIN recebido (lista[seqPos])
                                            #          e incrementar o nosso próprio seq para o próximo pacote
                                            seq += 1
                                            ack = int(lista[seqPos])  # Reconhecer o seq do FIN recebido
                                            print(f"[DEBUG] send: FIN recebido do outro lado, enviando ACK (seq={seq}, ack={ack})")
                                            self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
                                            # Aguardar ACK do FIN que enviamos anteriormente para completar o handshake
                                            print(f"[DEBUG] send: Aguardando ACK do FIN enviado anteriormente...")
                                            ack_retries = 0
                                            max_ack_retries = 5  # Reduzido de 10 para 5 - suficiente para 1% packet loss
                                            while ack_retries < max_ack_retries:
                                                try:
                                                    with self.sock_lock:
                                                        ack_response, (ack_ip, ack_port) = self.sock.recvfrom(self.limit.buffersize)
                                                    ack_lista = ack_response.decode().split("|")
                                                    if (len(ack_lista) == 7 and
                                                        ack_ip == ip and
                                                        ack_port == port and
                                                        ack_lista[flagPos] == self.ackkey and
                                                        ack_lista[idMissionPos] == idMission and
                                                        ack_lista[ackPos] == str(seq - 1)):  # ACK do nosso FIN (seq anterior)
                                                        print(f"[DEBUG] send: ACK do FIN recebido, conexão fechada com sucesso")
                                                        return True
                                                except socket.timeout:
                                                    ack_retries += 1
                                                    if ack_retries % 3 == 0:
                                                        print(f"[PACKET LOSS] Timeout ao aguardar ACK do FIN enviado (tentativa {ack_retries}/{max_ack_retries})")
                                                        print(f"[RETRANSMISSÃO] Reenviando FIN para {ip}:{port}")
                                                        self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq-1,ack,self.eofkey),(ip,port))
                                                    continue
                                                except Exception as e:
                                                    print(f"[DEBUG] send: Erro ao aguardar ACK do FIN: {e}")
                                                    ack_retries += 1
                                                    if ack_retries >= max_ack_retries:
                                                        break
                                                    continue
                                            # Se chegou aqui, não recebeu ACK mas já enviou ACK do FIN recebido, conexão considerada fechada
                                            print(f"[DEBUG] send: Não recebeu ACK do FIN após {max_ack_retries} tentativas, mas já enviou ACK do FIN recebido - conexão fechada")
                                            return True
                                        elif (lista[flagPos] == self.ackkey and 
                                              lista[ackPos] == str(seq) and
                                              lista[idMissionPos] == idMission):  # Validação de segurança: verifica idMission
                                            # Recebeu ACK do FIN enviado - agora esperar FIN do outro lado
                                            # Continuar loop para aguardar FIN
                                            continue
                                except socket.timeout:
                                    # Reenvia FIN se timeout (pode ser que o outro lado ainda não recebeu)
                                    print(f"[PACKET LOSS] Timeout ao aguardar FIN/ACK de {ip}:{port}")
                                    print(f"[RETRANSMISSÃO] Reenviando FIN para {ip}:{port}")
                                    self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
                                    continue
                                except Exception as e:
                                    print(f"Erro ao aguardar resposta FIN: {e}")
                                    # Reenviar FIN
                                    self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
                                    continue
                        continue
                    except socket.timeout:
                        # Timeout ao aguardar ACK - retransmitir mensagem
                        print(f"[PACKET LOSS] Timeout ao aguardar ACK da mensagem de {ip}:{port}")
                        print(f"[RETRANSMISSÃO] Reenviando mensagem para {ip}:{port}")
                        self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,chunks),(ip,port))
                        continue
                    except Exception as e:
                        print(f"Erro ao aguardar ACK: {e}")
                        # Retransmitir mensagem
                        print(f"[RETRANSMISSÃO] Reenviando mensagem após erro para {ip}:{port}")
                        self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,chunks),(ip,port))
                        continue
            # In case the message is big enough, 
            # we must send each element of the list
            print(f"[DEBUG] send: Mensagem dividida em {len(chunks)} chunks")
            i = 0
            while i != len(chunks):
                print(f"[DEBUG] send: Enviando chunk {i+1}/{len(chunks)} (seq={seq}, tamanho={len(chunks[i])} bytes)")
                self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,chunks[i]),(ip,port))
                try:
                    response,(responseIp,responsePort) = self.sock.recvfrom(self.limit.buffersize)
                    lista = response.decode().split("|")
                    if(
                        len(lista) == 7 and
                        responseIp == ip and
                        responsePort == port and
                        lista[ackPos] == str(seq) and 
                        lista[flagPos] == self.ackkey and
                        lista[idMissionPos] == idMission  # Validação de segurança: verifica idMission
                    ):
                        seq += 1
                        ack = seq
                        print(f"[DEBUG] send: Chunk {i+1}/{len(chunks)} confirmado (ACK recebido, seq={seq})")
                        i += 1
                        continue
                    else:
                        print(f"[DEBUG] send: ACK inválido recebido - IP={responseIp} (esperado {ip}), Port={responsePort} (esperado {port}), ack={lista[ackPos] if len(lista) > ackPos else 'N/A'} (esperado {seq}), flag={lista[flagPos] if len(lista) > flagPos else 'N/A'}")
                except socket.timeout:
                    # Timeout ao aguardar ACK - retransmitir chunk
                    print(f"[PACKET LOSS] Timeout ao aguardar ACK do chunk {i+1}/{len(chunks)} de {ip}:{port}")
                    print(f"[RETRANSMISSÃO] Reenviando chunk {i+1}/{len(chunks)} para {ip}:{port}")
                    self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,chunks[i]),(ip,port))
                    continue
                except Exception as e:
                    print(f"Erro ao receber ACK do chunk: {e}")
                    # Retransmitir chunk
                    print(f"[RETRANSMISSÃO] Reenviando chunk {i+1}/{len(chunks)} após erro para {ip}:{port}")
                    self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,chunks[i]),(ip,port))
                    continue
            self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
            while True:
                try:
                    text,(responseIp,responsePort) = self.sock.recvfrom(self.limit.buffersize)
                    lista = text.decode().split("|")
                    # Validar formato da mensagem
                    if len(lista) < 7:
                        # Mensagem malformada - reenviar FIN
                        self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
                        continue
                    if(
                        responseIp == ip and
                        responsePort == port and
                        lista[ackPos] == str(seq) and
                        lista[flagPos] == self.finkey and
                        lista[idMissionPos] == idMission  # Validação de segurança: verifica idMission
                    ):
                        print(f"[DEBUG] send: FIN-ACK recebido, conexão fechada com sucesso")
                        return True                  
                # Bug fix: Socket operations raise socket.timeout, not TimeoutError
                #          Todos os outros timeout handlers neste ficheiro usam socket.timeout corretamente
                #          (linhas 238, 257, 325, 383, etc.). Esta inconsistência significa que timeouts
                #          durante a troca de FIN não serão tratados, causando exceções não tratadas
                #          e falhas de conexão em vez de retransmitir o pacote FIN
                except socket.timeout:
                    print(f"[PACKET LOSS] Timeout ao aguardar FIN-ACK de {ip}:{port} (mensagem longa)")
                    print(f"[RETRANSMISSÃO] Reenviando FIN para {ip}:{port}")
                    self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
                    
                



    # Method to receive messages/files
    # Will either return the message or the name of the transfered file
    # along with the agent ID 
    def recv(self):
        """
        Returns a list with 5 items by order
            - 0 - idAgent (ID do rover)
            - 1 - idMission (ID da missão)
            - 2 - missionType (tipo de missão/operação)
            - 3 - file name or the message in string
            - 4 - ip address
        """
        message = ""
        # Establish connection, com timeout total de ~10s para não ficar infinito
        print(f"[DEBUG] recv: Iniciando receção - aguardando handshake")
        start_wait = time.time()
        while True:
            try:
                (ipDest,portDest),idAgent,seq,ack = self.acceptConnection()
                print(f"[DEBUG] recv: Handshake concluído - idAgent={idAgent}, seq={seq}, ack={ack}, origem={ipDest}:{portDest}")
                break
            except socket.timeout:
                elapsed = time.time() - start_wait
                if elapsed >= 10:
                    raise TimeoutError("MissionLink: sem ligação após 10s à espera de SYN")
                continue
            except Exception as e:
                elapsed = time.time() - start_wait
                if elapsed >= 10:
                    raise TimeoutError(f"MissionLink: sem ligação após 10s ({e})")
                continue
        idMission = None  # Será extraído da primeira mensagem

        fileName = None
        missionType = ""

        # We get the first message with data to know if it is a message or a file 
        firstMessage = None
        print(f"[DEBUG] recv: Aguardando primeira mensagem...")
        while firstMessage == None:
            try:
                # Usar lock para evitar race conditions com send()
                with self.sock_lock:
                    firstMessage,(ip,port) = self.sock.recvfrom(self.limit.buffersize)
                print(f"[DEBUG] recv: Primeira mensagem recebida de {ip}:{port}, tamanho={len(firstMessage)} bytes")
                lista = firstMessage.decode().split("|")
                print(f"[DEBUG] recv: Mensagem parseada - flag={lista[0] if len(lista) > 0 else 'N/A'}, idMission={lista[1] if len(lista) > 1 else 'N/A'}, seq={lista[2] if len(lista) > 2 else 'N/A'}, missionType={lista[5] if len(lista) > 5 else 'N/A'}")
                # Validar formato da mensagem
                if len(lista) < 7:
                    # Mensagem malformada - ignorar e continuar
                    print(f"[DEBUG] recv: Mensagem malformada (apenas {len(lista)} campos, esperado 7), ignorando")
                    firstMessage = None
                    continue
                # Bug fix: Extrair idMission apenas quando a validação de IP/porta/seq passar
                #          Se extrairmos idMission de uma mensagem com formato válido mas IP/porta/seq incorretos,
                #          podemos extrair o idMission errado de um emissor diferente, causando rejeição de mensagens válidas
                #          Solução: Extrair idMission apenas quando a validação completa passar (IP/porta/seq corretos)
                #          Isto garante que idMission seja sempre do emissor correto
                print(f"[DEBUG] recv: Validando primeira mensagem - IP esperado={ipDest}, recebido={ip}, Porta esperada={portDest}, recebida={port}, Seq esperado={seq+1}, recebido={lista[seqPos]}")
                if (
                    ip == ipDest and 
                    port == portDest and
                    lista[seqPos] == str(seq + 1)
                ):
                    print(f"[DEBUG] recv: Validação passou!")
                    # Extrair idMission apenas quando validação completa passar
                    if idMission is None:
                        idMission = lista[idMissionPos]  # Extrai idMission da primeira mensagem válida
                        print(f"[DEBUG] recv: idMission extraído: {idMission}")
                    # Bug fix: missionType deve ser atualizado sempre que uma mensagem válida é recebida
                    #          Se a primeira mensagem falhar na validação (linhas 615-619), missionType permanece ""
                    #          e quando o método retorna (linha 727 ou 816), passa "" em vez do tipo de mensagem real
                    #          causando identificação incorreta do tipo de mensagem no código de chamada
                    #          (ex: if lista[2] == self.missionLink.taskRequest falhará mesmo que uma mensagem tenha sido recebida)
                    #          Solução: missionType é atualizado aqui quando uma mensagem válida é finalmente recebida
                    missionType = lista[missionTypePos]
                    seq += 1
                    ack = seq
                    print(f"[DEBUG] recv: Primeira mensagem válida - missionType={missionType}, idMission={idMission}, seq={seq}")
                    if lista[messagePos].endswith(".json"):
                        # É um ficheiro
                        fileName = lista[messagePos]
                        print(f"[DEBUG] recv: É um ficheiro: {fileName}")
                    else:
                        # É uma mensagem
                        firstMessage = lista[messagePos]
                        print(f"[DEBUG] recv: É uma mensagem, tamanho={len(firstMessage)} bytes")
                    self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
                    print(f"[DEBUG] recv: ACK da primeira mensagem enviado")
                    break
                else:
                    # Bug fix: Se validação falhar, resetar firstMessage para None
                    #          mas NÃO resetar missionType - ele será atualizado quando uma mensagem válida for recebida
                    #          O problema é que missionType permanece "" se a primeira mensagem falhar,
                    #          mas isso é correto porque ainda não recebemos uma mensagem válida
                    print(f"[DEBUG] recv: Validação falhou - IP/porta/seq não correspondem, ignorando mensagem")
                    firstMessage = None
            except socket.timeout:
                firstMessage = None
                continue
            except Exception as e:
                print(f"Erro ao receber primeira mensagem: {e}")
                firstMessage = None
                continue

        # firstMessage pode ser string (mensagem), None (ficheiro), ou bytes (se validação falhou)
        # Bug fix: Garantir que prevMessage é sempre string ou None, nunca bytes
        # Se for string, usar como prevMessage; se for None ou bytes, prevMessage será None
        # NOTA: Se fileName foi definido, firstMessage será None (é ficheiro, não mensagem)
        if isinstance(firstMessage, str) and fileName is None:
            prevMessage = firstMessage
        else:
            prevMessage = None

        if fileName == None:
            # Bug fix: Se firstMessage contém o primeiro chunk, concatená-lo imediatamente
            #          para evitar perder o primeiro chunk em mensagens multi-chunk
            if prevMessage is not None:
                message = prevMessage
                prevMessage = None  # Reset para usar estratégia de escrita atrasada
            else:
                message = ""
            
            # Catch packets until the fin packet arrives
            print(f"[DEBUG] recv: Aguardando chunks adicionais ou FIN...")
            chunk_count = 0
            while True:
                # Try to receive a packet until timeout
                try:
                    chunks, (ip,port) = self.sock.recvfrom(self.limit.buffersize)
                    chunk_count += 1
                    print(f"[DEBUG] recv: Chunk {chunk_count} recebido de {ip}:{port}, tamanho={len(chunks)} bytes")
                    lista = chunks.decode().split("|")
                    print(f"[DEBUG] recv: Chunk parseado - flag={lista[0] if len(lista) > 0 else 'N/A'}, seq={lista[2] if len(lista) > 2 else 'N/A'}, esperado seq={seq+1}")
                    # When receiving a packet, the packet is accepted if:
                    # the length of the list is 7
                    # the mission id matches the connection's mission (se idMission já foi extraído)
                    # the seq is greater 1 unit the whats stored on receiver side
                    # the IP address and Port must be the same (identifica o rover)
                    # Bug fix: Verificar se idMission não é None antes de comparar
                    #          Se a primeira mensagem falhar na validação, idMission permanece None
                    #          e a comparação lista[idMissionPos] == idMission falhará para mensagens válidas
                    if(
                        len(lista) == 7 and
                        (idMission is None or lista[idMissionPos] == idMission) and
                        lista[seqPos] == str(seq + 1) and
                        ipDest == ip and
                        port == portDest
                    ):
                        # Se idMission ainda não foi extraído, extrair agora (primeira mensagem válida)
                        if idMission is None:
                            idMission = lista[idMissionPos]
                            print(f"[DEBUG] recv: idMission extraído do chunk: {idMission}")
                        print(f"[DEBUG] recv: Chunk válido recebido (seq={lista[seqPos]}, tamanho mensagem={len(lista[messagePos]) if len(lista) > messagePos else 0} bytes)")
                        # Estratégia anti-duplicação: escrever chunk anterior quando próximo chega
                        # Previne duplicação em caso de retransmissão
                        if prevMessage is not None:
                            message += prevMessage
                            print(f"[DEBUG] recv: Chunk anterior adicionado à mensagem (tamanho total agora: {len(message)} bytes)")
                        prevMessage = lista[messagePos]

                        # Increase the seq num to the new value (+1)
                        seq += 1
                        # The acknowledge number becomnes the same as the new sequence number
                        ack = seq
                        # The new acknowledge number is put in the list of fields
                        lista[ackPos] = str(ack)

                        #Check if the client send a connection closing message
                        if lista[flagPos] == self.finkey:
                            print(f"[DEBUG] recv: FIN recebido! Mensagem completa tem {len(message)} bytes")
                            # Bug fix: Concatenar último chunk (prevMessage) antes de fechar conexão
                            #          para evitar perder o último chunk da mensagem
                            if prevMessage is not None:
                                message += prevMessage
                                print(f"[DEBUG] recv: Último chunk adicionado (tamanho final: {len(message)} bytes)")
                            
                            # Handshake de 4 vias correto:
                            # 1. Servidor envia FIN -> rover recebe
                            # 2. Rover envia ACK do FIN recebido
                            # 3. Rover envia seu próprio FIN
                            # 4. Servidor envia ACK do FIN do rover
                            
                            # Passo 2: Enviar ACK do FIN recebido primeiro
                            fin_seq_received = int(lista[seqPos])
                            fin_ack_seq = seq  # ACK do nosso lado
                            fin_ack = fin_seq_received  # Reconhecer o seq do FIN recebido
                            print(f"[DEBUG] recv: Enviando ACK do FIN recebido (seq={fin_ack_seq}, ack={fin_ack})")
                            self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,fin_ack_seq,fin_ack,self.eofkey),(ip,port))
                            
                            # Passo 3: Enviar nosso próprio FIN
                            seq += 1
                            ack = seq
                            print(f"[DEBUG] recv: Enviando nosso próprio FIN (seq={seq})")
                            self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
                            
                            # Passo 4: Aguardar ACK do nosso FIN
                            print(f"[DEBUG] recv: Aguardando ACK do nosso FIN enviado")
                            fin_ack_retries = 0
                            max_fin_ack_retries = 5  # Reduzido de 10 para 5 - suficiente para 1% packet loss
                            while fin_ack_retries < max_fin_ack_retries:
                                try:
                                    ack_response, (ack_ip, ack_port) = self.sock.recvfrom(self.limit.buffersize)
                                    ack_lista = ack_response.decode().split("|")
                                    if (
                                        ack_ip == ipDest and
                                        ack_port == portDest and
                                        len(ack_lista) == 7 and
                                        ack_lista[flagPos] == self.ackkey and
                                        ack_lista[idMissionPos] == idMission and
                                        ack_lista[ackPos] == str(seq)  # ACK do nosso FIN
                                    ):
                                        # Recebeu ACK do nosso FIN - conexão fechada corretamente
                                        # Bug fix: Remover \x00 (EOF) do final da mensagem se existir
                                        #          O eofkey é usado apenas em ACKs/FINs, não deve aparecer no conteúdo da mensagem
                                        #          Mas pode aparecer incorretamente devido a bugs anteriores ou retransmissões
                                        if message and message.endswith(self.eofkey):
                                            message = message[:-1]
                                        print(f"[DEBUG] recv: ACK do nosso FIN recebido, conexão fechada. Retornando mensagem completa (tamanho: {len(message)} bytes)")
                                        return [idAgent,idMission,missionType,message,ip]
                                except socket.timeout:
                                    # Reenvia FIN se não receber ACK
                                    fin_ack_retries += 1
                                    if fin_ack_retries % 3 == 0:
                                        print(f"[PACKET LOSS] Timeout ao aguardar ACK do nosso FIN de {ip}:{port} (recv) (tentativa {fin_ack_retries}/{max_fin_ack_retries})")
                                        print(f"[RETRANSMISSÃO] Reenviando nosso FIN para {ip}:{port}")
                                        self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
                                    continue
                                except Exception as e:
                                    print(f"Erro ao aguardar ACK do nosso FIN: {e}")
                                    fin_ack_retries += 1
                                    if fin_ack_retries >= max_fin_ack_retries:
                                        break
                                    # Reenviar FIN
                                    self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
                                    continue
                            
                            # Se chegou aqui, não recebeu ACK mas já enviou ACK do FIN recebido e nosso próprio FIN
                            print(f"[DEBUG] recv: Não recebeu ACK do nosso FIN após {max_fin_ack_retries} tentativas, mas já enviou ACK do FIN recebido - retornando mensagem")
                            if message and message.endswith(self.eofkey):
                                message = message[:-1]
                            return [idAgent,idMission,missionType,message,ip]
                        # Enviar ACK do chunk recebido
                        # Bug fix: ACK deve ter missionType=None, não o missionType do chunk recebido
                        #          Todos os outros ACKs no código usam None corretamente
                        print(f"[DEBUG] recv: Enviando ACK do chunk (seq={seq})")
                        self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
                    



                # In case of a timeout, it means the
                # either the message did not reach the destination
                # or the message do not correspond to the expected sequence
                # So, to make sure, we sent the previous message that was supposed to be sent
                except socket.timeout:
                    # Reenviar último ACK para solicitar retransmissão
                    print(f"[PACKET LOSS] Timeout ao aguardar próximo chunk de {ip}:{port} (chunk {chunk_count+1})")
                    print(f"[DEBUG] recv: Timeout - último seq recebido={seq}, último ack enviado={ack}")
                    print(f"[RETRANSMISSÃO] Reenviando último ACK para solicitar retransmissão para {ip}:{port}")
                    self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
                    continue
                except Exception as e:
                    print(f"Erro ao receber chunk: {e}")
                    # Reenviar último ACK
                    print(f"[RETRANSMISSÃO] Reenviando último ACK após erro para {ip}:{port}")
                    self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
                    continue


        ## Comentário explicativo sobre estratégia de escrita de ficheiros
        # Com retransmissão, há probabilidade de escrever o mesmo texto 2 vezes
        # Portanto, quando os chunks chegam, guardamos a mensagem antes de escrever
        # assim só quando o próximo chunk chega, guardamos o próximo e escrevemos o anterior
        # Esta estratégia previne duplicação de dados em caso de retransmissão
        else:
            # Usar with para garantir fechamento do ficheiro mesmo em caso de erro
            with open(self.storeFolder + fileName,"w") as file:
                previous = None
                while True:
                    try:
                        text,(ip,port) = self.sock.recvfrom(self.limit.buffersize)
                        lista = text.decode().split("|")
                        # Validar formato da mensagem
                        if len(lista) < 7:
                            # Mensagem malformada - reenviar ACK e continuar
                            self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
                            continue
                        if(
                            len(lista) == 7 and
                            lista[idMissionPos] == idMission and
                            ip == ipDest and
                            port == portDest and
                            lista[seqPos] == str(seq + 1) 
                        ):
                            seq += 1
                            ack = seq
                            # Estratégia anti-duplicação: escrever chunk anterior quando próximo chega
                            # Previne duplicação em caso de retransmissão
                            if previous != None:
                                file.write(previous)
                            
                            if lista[flagPos] == self.finkey:
                                # Bug fix: Escrever último chunk que está em lista[messagePos] quando recebe FIN
                                #          O chunk final nunca era escrito, apenas previous (penúltimo chunk)
                                if lista[messagePos] != self.eofkey:
                                    file.write(lista[messagePos])
                                # Ficheiro será fechado automaticamente pelo with
                                self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
                                while True:
                                    try:
                                        text,(ip,port) = self.sock.recvfrom(self.limit.buffersize)
                                        lista = text.decode().split("|")
                                        # Validação do pacote FIN recebido
                                        # Bug fix: Deve verificar lista[ackPos] == str(seq) para validar que o FIN recebido
                                        #          está a reconhecer o nosso número de sequência FIN (consistente com linha 701 e 419)
                                        if(
                                            len(lista) == 7 and
                                            ip == ipDest and
                                            port == portDest and 
                                            lista[idMissionPos] == idMission and
                                            lista[ackPos] == str(seq) and
                                            lista[flagPos] == self.finkey
                                        ):
                                            # Ficheiro recebido e conexão fechada
                                            return [idAgent,idMission,missionType,fileName,ip]
                                    except socket.timeout:
                                        # Reenviar FIN se timeout
                                        print(f"[PACKET LOSS] Timeout ao aguardar confirmação FIN de {ip}:{port} (ficheiro)")
                                        print(f"[RETRANSMISSÃO] Reenviando FIN para {ip}:{port}")
                                        self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
                                        continue
                                    except Exception as e:
                                        print(f"Erro ao aguardar confirmação FIN: {e}")
                                        # Reenviar FIN
                                        print(f"[RETRANSMISSÃO] Reenviando FIN após erro para {ip}:{port}")
                                        self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
                                        continue
                            else:
                                # Atualizar previous para o próximo chunk (estratégia anti-duplicação)
                                previous = lista[messagePos]
                                # Enviar ACK do chunk recebido
                                self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))

                    except socket.timeout:
                        # Reenviar último ACK para solicitar retransmissão
                        print(f"[PACKET LOSS] Timeout ao aguardar próximo chunk de ficheiro de {ip}:{port}")
                        print(f"[RETRANSMISSÃO] Reenviando último ACK para solicitar retransmissão para {ip}:{port}")
                        self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
                        continue
                    except Exception as e:
                        print(f"Erro ao receber chunk de ficheiro: {e}")
                        # Reenviar último ACK
                        print(f"[RETRANSMISSÃO] Reenviando último ACK após erro para {ip}:{port}")
                        self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
                        continue


