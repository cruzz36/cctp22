import socket
from protocol import MissionLink,TelemetryStream
import os
import time
import json

def validateMission(mission_data):
    """
    Valida se um dicionário contém todos os campos obrigatórios de uma missão.
    
    Formato obrigatório de missão (conforme PDF):
    {
        "mission_id": string (obrigatório, identificador único),
        "rover_id": string (obrigatório),
        "geographic_area": dict (obrigatório),
        "task": string (obrigatório: capture_images|sample_collection|environmental_analysis|...),
        "duration_minutes": integer (obrigatório, > 0),
        "update_frequency_seconds": integer (obrigatório, > 0)
    }
    
    Campos opcionais:
    - "priority": string (low|medium|high)
    - "instructions": string
    
    Args:
        mission_data (dict or str): Dicionário ou string JSON com dados da missão
        
    Returns:
        tuple: (bool, str) - (True, "") se válido, (False, mensagem_erro) se inválido
    """
    # Se for string, fazer parse
    if isinstance(mission_data, str):
        try:
            mission_data = json.loads(mission_data)
        except json.JSONDecodeError:
            return False, "Formato JSON inválido"
    
    if not isinstance(mission_data, dict):
        return False, "Dados da missão devem ser um dicionário"
    
    # Campos obrigatórios
    required_fields = {
        "mission_id": str,
        "rover_id": str,
        "geographic_area": dict,
        "task": str,
        "duration_minutes": (int, float),
        "update_frequency_seconds": (int, float)
    }
    
    # Verificar presença e tipo dos campos obrigatórios
    for field, expected_type in required_fields.items():
        if field not in mission_data:
            return False, f"Campo obrigatório ausente: {field}"
        
        if not isinstance(mission_data[field], expected_type):
            return False, f"Campo {field} tem tipo incorreto. Esperado: {expected_type}"
    
    # Validações específicas
    if mission_data["duration_minutes"] <= 0:
        return False, "duration_minutes deve ser maior que 0"
    
    if mission_data["update_frequency_seconds"] <= 0:
        return False, "update_frequency_seconds deve ser maior que 0"
    
    # Validar geographic_area
    geo_area = mission_data["geographic_area"]
    if not isinstance(geo_area, dict):
        return False, "geographic_area deve ser um dicionário"
    
    # Verificar se tem coordenadas (formato rectangle com x1, y1, x2, y2)
    if "x1" in geo_area and "y1" in geo_area and "x2" in geo_area and "y2" in geo_area:
        try:
            x1, y1, x2, y2 = float(geo_area["x1"]), float(geo_area["y1"]), float(geo_area["x2"]), float(geo_area["y2"])
            if x1 >= x2 or y1 >= y2:
                return False, "Coordenadas inválidas: x1 < x2 e y1 < y2 são obrigatórios"
        except (ValueError, TypeError):
            return False, "Coordenadas devem ser números válidos"
    else:
        # Outros formatos podem ser adicionados aqui (polygon, circle, etc.)
        return False, "geographic_area deve conter coordenadas (x1, y1, x2, y2) ou outro formato válido"
    
    # Validar task (valores comuns)
    valid_tasks = ["capture_images", "sample_collection", "environmental_analysis"]
    if mission_data["task"] not in valid_tasks:
        # Aceitar outros valores mas avisar
        pass
    
    return True, ""


def validateTelemetryMessage(telemetry_data):
    """
    Valida se mensagem de telemetria cumpre requisitos mínimos do PDF.
    
    Requisitos obrigatórios conforme PDF:
    - rover_id (str): Identificação inequívoca do rover
    - position (dict): Localização com coordenadas (x, y, z)
    - operational_status (str): Estado operacional (em missão, a caminho, parado, erro)
    
    Args:
        telemetry_data (dict): Dicionário com dados de telemetria
        
    Returns:
        tuple: (bool, str) - (True, "") se válido, (False, mensagem_erro) se inválido
    """
    if not isinstance(telemetry_data, dict):
        return False, "Dados de telemetria devem ser um dicionário"
    
    # Campos obrigatórios
    required_fields = ["rover_id", "position", "operational_status"]
    
    for field in required_fields:
        if field not in telemetry_data:
            return False, f"Campo obrigatório ausente: {field}"
    
    # Validar rover_id
    if not isinstance(telemetry_data["rover_id"], str) or len(telemetry_data["rover_id"]) == 0:
        return False, "rover_id deve ser uma string não vazia"
    
    # Validar position
    position = telemetry_data["position"]
    if not isinstance(position, dict):
        return False, "position deve ser um dicionário"
    
    required_coords = ["x", "y", "z"]
    for coord in required_coords:
        if coord not in position:
            return False, f"Coordenada obrigatória ausente em position: {coord}"
        try:
            float(position[coord])  # Validar que é um número
        except (ValueError, TypeError):
            return False, f"Coordenada {coord} deve ser um número válido"
    
    # Validar operational_status
    valid_statuses = ["em missão", "a caminho", "parado", "erro"]
    if not isinstance(telemetry_data["operational_status"], str):
        return False, "operational_status deve ser uma string"
    
    # Aceitar outros valores mas avisar (não é erro crítico)
    if telemetry_data["operational_status"] not in valid_statuses:
        pass  # Aceitar mas poderia avisar
    
    return True, ""

def removeNulls(text):
    """
    Remove todas as strings vazias de uma lista.
    
    COMO FUNCIONA:
    - Tenta remover strings vazias ("") da lista repetidamente
    - Continua até não haver mais strings vazias (quando remove() lança exceção)
    - Usa try-except para detectar quando não há mais strings vazias
    
    PORQUÊ:
    - Comandos do sistema (como 'ip') podem retornar linhas vazias
    - Estas linhas vazias causam problemas no processamento
    - Remove todas de uma vez para limpar a lista
    
    Args:
        text (list): Lista de strings (será modificada in-place)
        
    Returns:
        list: Lista sem strings vazias (mesma referência, modificada)
    
    NOTA: Modifica a lista original (não cria cópia)
    """
    # Loop infinito até não haver mais strings vazias
    while True:
        try:
            # Tenta remover uma string vazia da lista
            # remove() modifica a lista in-place e retorna None
            text.remove("")
        except ValueError:
            # Quando não há mais strings vazias, remove() lança ValueError
            # Sai do loop e retorna a lista limpa
            break
    return text

class NMS_Agent:
    """
    Classe que representa um agente/rover no sistema.
    Responsável por medir métricas, comunicar com a Nave-Mãe e executar missões.
    """
    def __init__(self,serverAddress,frequency = 1,storeFolder = "."):
        """
        Inicializa o agente NMS.
        
        Args:
            serverAddress (str): Endereço IP da Nave-Mãe (servidor)
            frequency (int, optional): Frequência de operação. Defaults to 1
            storeFolder (str, optional): Pasta para armazenar ficheiros. Defaults to "."
        """
        self.id = socket.gethostname()
        self.ipAddress = self.getinterfaces()[0].split(" ")[1]
        self.serverAddress = serverAddress
        self.missionLink = MissionLink.MissionLink(self.ipAddress,storeFolder)
        self.telemetryStream = TelemetryStream.TelemetryStream(self.ipAddress,storeFolder)
        self.tasks = dict()
        self.frequency = frequency
        
        # Estado do rover para telemetria (conforme requisitos do PDF)
        self.position = {"x": 0.0, "y": 0.0, "z": 0.0}  # Posição inicial
        self.operational_status = "parado"  # Estado inicial: parado, em missão, a caminho, erro
        self.battery = 100.0  # Nível de bateria (0-100%)
        self.velocity = 0.0  # Velocidade atual (m/s)
        self.direction = 0.0  # Direção em graus (0-360, onde 0 = Norte)
        self.temperature = 20.0  # Temperatura interna (°C)
        self.system_health = "operacional"  # Estado de saúde do sistema
        
        # Estado de monitorização contínua
        self.telemetry_thread = None  # Thread para monitorização contínua
        self.telemetry_running = False  # Flag para controlar loop
        self.telemetry_interval = 30  # Intervalo padrão em segundos

    # def sendMetrics(self,ip,filename:str):
    #     """
    #     Envia um ficheiro de métricas para a Nave-Mãe através do MissionLink.
    #     Retransmite até receber confirmação válida.
    #     
    #     Args:
    #         ip (str): Endereço IP da Nave-Mãe
    #         filename (str): Nome do ficheiro de métricas a enviar (formato: alert_idMission_task-XXX_iter.json)
    #     """
    #     try:
    #         lista = filename.split("_")
    #         if len(lista) >= 4:
    #             iter = lista[3].split(".")[0]
    #             idMission = lista[1]
    #         else:
    #             print(f"Erro: Formato de nome de ficheiro inválido: {filename}. Esperado: alert_idMission_task-XXX_iter.json")
    #             iter = "unknown"
    #             idMission = "000"
    #     except (IndexError, AttributeError) as e:
    #         print(f"Erro ao processar nome de ficheiro de métricas: {e}")
    #         iter = "error"
    #         idMission = "000"
    #     self.missionLink.send(ip,self.missionLink.port,self.missionLink.sendMetrics,self.id,idMission,filename)
    #     reply = self.missionLink.recv()
    #     retries = 0
    #     max_retries = 10
    #     while (reply[3] != iter or reply[4] != ip) and retries < max_retries:
    #         retries += 1
    #         self.missionLink.send(ip,self.missionLink.port,self.missionLink.sendMetrics,self.id,idMission,filename)
    #         reply = self.missionLink.recv()
    #     
    #     if retries >= max_retries:
    #         print(f"Aviso: Máximo de tentativas ({max_retries}) atingido ao enviar métricas")
            
    def register(self,ip):
        """
        Regista o agente na Nave-Mãe através do MissionLink.
        Retransmite o pedido até receber confirmação válida.
        
        Args:
            ip (str): Endereço IP da Nave-Mãe
        """
        print(f"[DEBUG] register: Iniciando registo na Nave-Mãe {ip} (rover_id={self.id})")
        # No registo, idMission = "000" porque ainda não há missão atribuída
        print(f"[DEBUG] register: Enviando pedido de registo...")
        self.missionLink.send(ip,self.missionLink.port,self.missionLink.registerAgent,self.id,"000","\0")
        print(f"[DEBUG] register: Aguardando confirmação de registo...")
        lista = self.missionLink.recv()
        print(f"[DEBUG] register: Resposta recebida: idAgent={lista[0]}, ip={lista[4]}, message={lista[3]}")
        # Bug fix: lista[2] é missionType (não flag), lista[0] é idAgent
        # Quando servidor envia confirmação de registo, missionType será None ou vazio
        # Validação correta: verificar se idAgent corresponde e se recebemos resposta do servidor correto
        # Bug fix: Usar 'or' está correto - retransmitir se QUALQUER validação falhar
        #          Mas vamos adicionar um limite de retries para evitar loops infinitos
        retries = 0
        max_retries = 10
        while (lista[0] != self.id or lista[4] != ip) and retries < max_retries:
            retries += 1
            print(f"[DEBUG] register: Resposta inválida (esperado idAgent={self.id}, ip={ip}, recebido idAgent={lista[0]}, ip={lista[4]}). Retry {retries}/{max_retries}")
            self.missionLink.send(ip,self.missionLink.port,self.missionLink.registerAgent,self.id,"000","\0")
            lista = self.missionLink.recv()
            print(f"[DEBUG] register: Nova resposta recebida: idAgent={lista[0]}, ip={lista[4]}, message={lista[3]}")
        
        if retries >= max_retries:
            print(f"[ERRO] Máximo de tentativas ({max_retries}) atingido ao registar")
        else:
            print(f"[OK] Registado com sucesso na Nave-Mãe {ip} (resposta: {lista[3]})")
    
    def registerAgent(self, ip):
        """
        Alias para register() para compatibilidade com código existente.
        
        Args:
            ip (str): Endereço IP da Nave-Mãe
        """
        return self.register(ip)


    def requestMission(self, ip):
        """
        Solicita uma missão à Nave-Mãe através do MissionLink.
        Implementa o requisito: "O rover deve ser capaz de solicitar uma missão à Nave-Mãe."
        
        Args:
            ip (str): Endereço IP da Nave-Mãe
            
        Returns:
            dict or None: Dicionário com dados da missão recebida, ou None se não houver missão disponível
        """
        print(f"[DEBUG] requestMission: Solicitando missão à Nave-Mãe {ip} (rover_id={self.id})")
        # Enviar solicitação de missão
        self.missionLink.send(ip, self.missionLink.port, self.missionLink.requestMission, self.id, "000", "request")
        print(f"[DEBUG] requestMission: Solicitação enviada, aguardando resposta...")
        
        # Aguardar resposta (pode ser missão ou mensagem de "sem missão disponível")
        try:
            response = self.missionLink.recv()
            print(f"[DEBUG] requestMission: Resposta recebida: idAgent={response[0]}, idMission={response[1]}, missionType={response[2]}, message={response[3][:50] if len(response[3]) > 50 else response[3]}..., ip={response[4]}")
            # response tem: [idAgent, idMission, missionType, message, ip]
            if response[2] == self.missionLink.taskRequest:
                # Bug fix: Missão já está na primeira resposta (response[3])
                #          Não fazer recv() novamente - extrair e validar diretamente
                mission_message = response[3]
                mission_id = response[1]  # idMission do protocolo
                
                # Validar formato da missão
                is_valid, error_msg = validateMission(mission_message)
                
                if not is_valid:
                    print(f"Erro: Missão recebida é inválida: {error_msg}")
                    # Enviar ACK mesmo assim para não bloquear o servidor
                    self.missionLink.send(response[4], self.missionLink.port, None, self.id, mission_id, "invalid")
                    return None
                
                # Parse do JSON da missão
                try:
                    if isinstance(mission_message, str):
                        mission_data = json.loads(mission_message)
                    else:
                        mission_data = mission_message
                except json.JSONDecodeError as e:
                    print(f"Erro: Não foi possível fazer parse do JSON da missão: {e}")
                    self.missionLink.send(response[4], self.missionLink.port, None, self.id, mission_id, "parse_error")
                    return None
                
                # Verificar se o rover_id corresponde
                if mission_data.get("rover_id") != self.id:
                    print(f"Aviso: Missão {mission_id} destinada a outro rover ({mission_data.get('rover_id')})")
                    # Continuar mesmo assim - pode ser útil para debug
                
                # Armazenar missão validada
                self.tasks[mission_id] = mission_data
                print(f"[DEBUG] requestMission: Missão {mission_id} armazenada em self.tasks")
                
                # Enviar ACK de confirmação
                print(f"[DEBUG] requestMission: Enviando ACK de confirmação para missão {mission_id}")
                self.missionLink.send(response[4], self.missionLink.port, None, self.id, mission_id, mission_id)
                print(f"[OK] requestMission: Missão {mission_id} recebida e confirmada")
                
                return mission_data
            elif response[2] == self.missionLink.noneType:
                # Bug fix: Quando servidor envia com missionType=None, é codificado como "N" no protocolo
                #          O recv() extrai isto como a string "N", não Python None
                #          Verificar response[2] == "N" em vez de response[2] is None
                # Sem missão disponível (mensagem será "no_mission")
                if response[3] == "no_mission":
                    print(f"[INFO] requestMission: Nave-Mãe respondeu: sem missão disponível no momento")
                else:
                    print(f"[DEBUG] requestMission: Resposta inesperada com missionType=None: {response[3]}")
                return None
        except Exception as e:
            print(f"[ERRO] requestMission: Erro ao solicitar missão: {e}")
            import traceback
            traceback.print_exc()
            return None

    def recvMissionLink(self):
        """
        Recebe uma mensagem através do MissionLink.
        Se for um pedido de tarefa (taskRequest), valida o formato da missão,
        armazena a missão e envia confirmação.
        
        Formato esperado da missão (conforme PDF):
        {
            "mission_id": string (obrigatório),
            "rover_id": string (obrigatório),
            "geographic_area": {"x1": float, "y1": float, "x2": float, "y2": float},
            "task": string (obrigatório),
            "duration_minutes": integer (obrigatório, > 0),
            "update_frequency_seconds": integer (obrigatório, > 0)
        }
        
        NOTA: O idAgent é usado apenas no handshake. Nas mensagens de dados,
              apenas idMission é enviado no protocolo.
        
        Returns:
            dict or None: Dicionário com dados da missão validada, ou None se não for missão válida
        """
        print(f"[DEBUG] recvMissionLink: Aguardando mensagem do MissionLink...")
        lista = self.missionLink.recv()
        print(f"[DEBUG] recvMissionLink: Mensagem recebida: idAgent={lista[0]}, idMission={lista[1]}, missionType={lista[2]}, ip={lista[4]}")
        # lista tem: [idAgent, idMission, missionType, message, ip]
        # idAgent é identificado pelo IP/porta do handshake
        
        # missionType = tipo de operação do protocolo (R, T, M, Q, P)
        # Quando missionType="T" (taskRequest), o campo 'message' contém um JSON
        # que inclui o campo "task" com um dos 3 valores: capture_images, sample_collection, environmental_analysis
        if lista[2] == self.missionLink.taskRequest:
            mission_message = lista[3]
            mission_id = lista[1]  # idMission do protocolo
            print(f"[DEBUG] recvMissionLink: Recebida missão {mission_id}, validando formato...")
            
            # Validar formato da missão
            is_valid, error_msg = validateMission(mission_message)
            
            if not is_valid:
                print(f"[ERRO] recvMissionLink: Missão recebida é inválida: {error_msg}")
                # Enviar ACK mesmo assim para não bloquear o servidor
                # Bug fix: ackkey é uma flag, não um missionType. Usar None como missionType
                print(f"[DEBUG] recvMissionLink: Enviando ACK 'invalid' para {lista[4]}")
                self.missionLink.send(lista[4], self.missionLink.port, None, self.id, mission_id, "invalid")
                return None
            
            print(f"[DEBUG] recvMissionLink: Missão validada, fazendo parse do JSON...")
            # Parse do JSON da missão
            try:
                if isinstance(mission_message, str):
                    mission_data = json.loads(mission_message)
                else:
                    mission_data = mission_message
                print(f"[DEBUG] recvMissionLink: JSON parseado com sucesso")
            except json.JSONDecodeError as e:
                print(f"[ERRO] recvMissionLink: Não foi possível fazer parse do JSON da missão: {e}")
                # Bug fix: ackkey é uma flag, não um missionType. Usar None como missionType
                print(f"[DEBUG] recvMissionLink: Enviando ACK 'parse_error' para {lista[4]}")
                self.missionLink.send(lista[4], self.missionLink.port, None, self.id, mission_id, "parse_error")
                return None
            
            # Verificar se o rover_id corresponde
            if mission_data.get("rover_id") != self.id:
                print(f"[AVISO] recvMissionLink: Missão {mission_id} destinada a outro rover ({mission_data.get('rover_id')}), mas continuando...")
                # Continuar mesmo assim - pode ser útil para debug
            
            # Armazenar missão validada
            self.tasks[mission_id] = mission_data
            print(f"[DEBUG] recvMissionLink: Missão {mission_id} armazenada em self.tasks")
            
            # Extrair informações da missão para processamento
            print(f"[OK] Missão recebida e validada:")
            print(f"  ID: {mission_data.get('mission_id')}")
            print(f"  Tarefa: {mission_data.get('task')}")
            print(f"  Duração: {mission_data.get('duration_minutes')} minutos")
            print(f"  Frequência de atualização: {mission_data.get('update_frequency_seconds')} segundos")
            print(f"  Área geográfica: ({mission_data['geographic_area'].get('x1')}, {mission_data['geographic_area'].get('y1')}) a ({mission_data['geographic_area'].get('x2')}, {mission_data['geographic_area'].get('y2')})")
            
            # Enviar ACK de confirmação
            print(f"[DEBUG] recvMissionLink: Enviando ACK de confirmação para {lista[4]}")
            # Bug fix: ackkey é uma flag, não um missionType. Usar None como missionType
            self.missionLink.send(lista[4], self.missionLink.port, None, self.id, mission_id, mission_id)
            print(f"[DEBUG] recvMissionLink: ACK enviado")
            
            return mission_data
        
        print(f"[DEBUG] recvMissionLink: Mensagem recebida não é uma missão (missionType={lista[2]}), retornando None")
        return None

    def reportMissionProgress(self, ip, mission_id, progress_data):
        """
        Reporta o progresso de uma missão à Nave-Mãe.
        Implementa o requisito: "O rover deve reportar o progresso da missão de acordo 
        com parâmetros definidos na própria missão."
        
        Formato de progress_data:
        {
            "mission_id": string (obrigatório),
            "progress_percent": integer (0-100, obrigatório),
            "status": string (obrigatório: "in_progress"|"completed"|"failed"|"paused"),
            "current_position": {"x": float, "y": float} (opcional),
            "events": list (opcional, lista de eventos ocorridos),
            "samples_collected": integer (opcional, para tarefas de coleta),
            "images_captured": integer (opcional, para tarefas de captura),
            "time_elapsed_minutes": float (opcional),
            "estimated_completion_minutes": float (opcional)
        }
        
        Args:
            ip (str): Endereço IP da Nave-Mãe
            mission_id (str): Identificador da missão
            progress_data (dict): Dicionário com dados de progresso
            
        Returns:
            bool: True se progresso foi reportado com sucesso, False caso contrário
        """
        # Validar campos obrigatórios
        if "mission_id" not in progress_data:
            progress_data["mission_id"] = mission_id
        
        if "progress_percent" not in progress_data:
            print("Erro: progress_percent é obrigatório")
            return False
        
        if "status" not in progress_data:
            print("Erro: status é obrigatório")
            return False
        
        # Converter para JSON
        progress_json = json.dumps(progress_data)
        
        # Enviar reporte de progresso
        try:
            self.missionLink.send(ip, self.missionLink.port, self.missionLink.reportProgress, self.id, mission_id, progress_json)
            
            # Aguardar confirmação
            response = self.missionLink.recv()
            # Bug fix: Quando servidor envia com missionType=None, é codificado como "N" no protocolo
            #          O recv() extrai isto como a string "N", não Python None
            #          Verificar response[2] == "N" em vez de response[2] is None
            if response[2] == self.missionLink.noneType and response[3] in ["progress_received", "Registered", "Already registered"]:
                print(f"Progresso da missão {mission_id} reportado com sucesso")
                return True
            else:
                print(f"Falha ao reportar progresso: resposta inesperada (missionType={response[2]}, message={response[3]})")
                return False
        except Exception as e:
            print(f"Erro ao reportar progresso: {e}")
            return False
        

    def sendTelemetry(self,ip,message):
        """
        Envia dados de telemetria para a Nave-Mãe através do TelemetryStream (TCP).
        
        Args:
            ip (str): Endereço IP da Nave-Mãe
            message (str): Caminho do ficheiro de telemetria a enviar
        
        Returns:
            bool: True se telemetria foi enviada com sucesso, False em caso de erro
        """
        return self.telemetryStream.send(ip,message)
    
    def createTelemetryMessage(self, metrics=None):
        """
        Cria mensagem de telemetria completa conforme requisitos do PDF.
        
        Requisitos mínimos obrigatórios:
        - rover_id: Identificação do rover
        - position: Coordenadas (x, y, z)
        - operational_status: Estado operacional
        
        Campos opcionais adicionados:
        - battery: Nível de bateria
        - velocity: Velocidade atual
        - temperature: Temperatura interna
        - system_health: Estado de saúde do sistema
        - Métricas técnicas recolhidas (CPU, RAM, bandwidth, etc.)
        
        COMO FUNCIONA:
        - Combina campos obrigatórios (rover_id, position, operational_status)
        - Adiciona campos opcionais (battery, velocity, temperature, etc.)
        - Valida estrutura antes de retornar
        
        PORQUÊ:
        - Garante que todas as mensagens de telemetria cumprem requisitos do PDF
        - Centraliza criação de mensagens de telemetria
        - Facilita manutenção e extensão
        
        Args:
            metrics (dict, optional): Dicionário com métricas técnicas recolhidas (CPU, RAM, etc.)
                                      Se None, apenas campos obrigatórios são incluídos
        
        Returns:
            dict: Dicionário com mensagem de telemetria completa e validada
        """
        # Criar estrutura base com campos obrigatórios
        telemetry = {
            "rover_id": self.id,
            "position": self.position.copy(),  # Cópia para não modificar original
            "operational_status": self.operational_status
        }
        
        # Adicionar campos opcionais
        telemetry["battery"] = self.battery
        telemetry["velocity"] = self.velocity
        telemetry["direction"] = self.direction
        telemetry["temperature"] = self.temperature
        telemetry["system_health"] = self.system_health
        
        # Adicionar métricas técnicas se fornecidas
        if metrics is not None and isinstance(metrics, dict):
            # Adicionar métricas técnicas ao dicionário de telemetria
            for key, value in metrics.items():
                # Não sobrescrever campos obrigatórios
                if key not in ["rover_id", "position", "operational_status"]:
                    telemetry[key] = value
        
        # Validar estrutura antes de retornar
        is_valid, error_msg = validateTelemetryMessage(telemetry)
        if not is_valid:
            print(f"Aviso: Mensagem de telemetria inválida: {error_msg}")
            # Retornar mesmo assim, mas com aviso
        
        return telemetry
    
    def createAndSendTelemetry(self, server_ip, metrics=None, filename=None):
        """
        Cria ficheiro de telemetria conforme requisitos do PDF e envia via TelemetryStream.
        
        COMO FUNCIONA:
        - Cria mensagem de telemetria completa usando createTelemetryMessage()
        - Salva em ficheiro JSON
        - Envia via TelemetryStream (TCP)
        - Remove ficheiro temporário após envio
        
        PORQUÊ:
        - Automatiza processo completo de criação e envio de telemetria
        - Garante que estrutura cumpre requisitos do PDF
        - Facilita uso em loops de monitorização contínua
        
        Args:
            server_ip (str): Endereço IP da Nave-Mãe
            metrics (dict, optional): Dicionário com métricas técnicas recolhidas
            filename (str, optional): Nome do ficheiro. Se None, gera automaticamente
        
        Returns:
            bool: True se telemetria foi criada e enviada com sucesso, False em caso de erro
        """
        print(f"[DEBUG] createAndSendTelemetry: Criando telemetria para {server_ip} (rover_id={self.id})")
        try:
            # Criar mensagem de telemetria
            telemetry = self.createTelemetryMessage(metrics)
            print(f"[DEBUG] createAndSendTelemetry: Mensagem de telemetria criada (rover_id={telemetry.get('rover_id')}, status={telemetry.get('operational_status')})")
            
            # Gerar nome do ficheiro se não fornecido
            if filename is None:
                timestamp = int(time.time())
                filename = f"telemetry_{self.id}_{timestamp}.json"
            
            # Garantir que filename está na pasta correta
            if not os.path.dirname(filename):
                filename = os.path.join(".", filename)
            
            # Salvar em ficheiro JSON
            print(f"[DEBUG] createAndSendTelemetry: Salvando telemetria em {filename}")
            with open(filename, "w") as f:
                json.dump(telemetry, f, indent=2)
            print(f"[DEBUG] createAndSendTelemetry: Ficheiro salvo, enviando via TelemetryStream...")
            
            # Enviar via TelemetryStream
            success = self.sendTelemetry(server_ip, filename)
            
            if success:
                print(f"[DEBUG] createAndSendTelemetry: Telemetria enviada com sucesso, removendo ficheiro temporário...")
                # Opcional: remover ficheiro após envio bem-sucedido
                try:
                    os.remove(filename)
                    print(f"[DEBUG] createAndSendTelemetry: Ficheiro {filename} removido")
                except:
                    pass  # Ignorar erro ao remover
            
            return success
            
        except Exception as e:
            print(f"[ERRO] createAndSendTelemetry: Erro ao criar e enviar telemetria: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def updatePosition(self, x, y, z=0.0):
        """
        Atualiza a posição do rover.
        
        Args:
            x (float): Coordenada X
            y (float): Coordenada Y
            z (float, optional): Coordenada Z. Defaults to 0.0
        """
        self.position = {"x": float(x), "y": float(y), "z": float(z)}
    
    def updateOperationalStatus(self, status):
        """
        Atualiza o estado operacional do rover.
        
        Args:
            status (str): Estado operacional ("em missão", "a caminho", "parado", "erro")
        """
        valid_statuses = ["em missão", "a caminho", "parado", "erro"]
        if status in valid_statuses:
            self.operational_status = status
        else:
            print(f"Aviso: Estado operacional '{status}' não é válido. Estados válidos: {valid_statuses}")
            self.operational_status = status  # Aceitar mesmo assim
    
    def updateBattery(self, level):
        """
        Atualiza o nível de bateria do rover.
        
        Args:
            level (float): Nível de bateria (0-100%)
        """
        self.battery = max(0.0, min(100.0, float(level)))
    
    def updateVelocity(self, velocity):
        """
        Atualiza a velocidade do rover.
        
        Args:
            velocity (float): Velocidade em m/s
        """
        self.velocity = max(0.0, float(velocity))
    
    def updateTemperature(self, temp):
        """
        Atualiza a temperatura interna do rover.
        
        Args:
            temp (float): Temperatura em °C
        """
        self.temperature = float(temp)
    
    def updateSystemHealth(self, health):
        """
        Atualiza o estado de saúde do sistema.
        
        Args:
            health (str): Estado de saúde ("operacional", "degradado", "crítico")
        """
        self.system_health = health
    
    def updateDirection(self, direction):
        """
        Atualiza a direção do rover.
        
        Args:
            direction (float): Direção em graus (0-360, onde 0 = Norte)
        """
        # Normalizar para 0-360
        self.direction = float(direction) % 360.0
    
    def startContinuousTelemetry(self, server_ip, interval_seconds=30):
        """
        Inicia monitorização contínua de telemetria.
        Envia telemetria periodicamente em thread separada.
        
        COMO FUNCIONA:
        - Cria thread separada para não bloquear execução principal
        - Em loop, cria e envia telemetria com frequência definida
        - Continua até ser parado com stopContinuousTelemetry()
        
        PORQUÊ:
        - Implementa requisito do PDF: "reportar dados de monitorização continuamente"
        - Permite monitorização em background sem bloquear outras operações
        - Facilita integração com sistema de missões
        
        Args:
            server_ip (str): Endereço IP da Nave-Mãe
            interval_seconds (int, optional): Intervalo entre envios em segundos. Defaults to 30
        
        Returns:
            bool: True se monitorização foi iniciada, False se já estava em execução
        """
        import threading
        
        if self.telemetry_running:
            print("[AVISO] Monitorização contínua já está em execução")
            return False
        
        print(f"[DEBUG] startContinuousTelemetry: Iniciando telemetria contínua (intervalo={interval_seconds}s, server_ip={server_ip})")
        self.telemetry_interval = interval_seconds
        self.telemetry_running = True
        
        def telemetry_loop():
            """Loop interno para envio periódico de telemetria."""
            iteration = 0
            print(f"[DEBUG] telemetry_loop: Thread iniciada, aguardando {self.telemetry_interval}s antes do primeiro envio...")
            time.sleep(self.telemetry_interval)  # Aguardar intervalo antes do primeiro envio
            while self.telemetry_running:
                try:
                    iteration += 1
                    filename = f"telemetry_{self.id}_{int(time.time())}.json"
                    print(f"[DEBUG] telemetry_loop: Iteração {iteration}, criando e enviando telemetria...")
                    success = self.createAndSendTelemetry(server_ip, None, filename)
                    
                    if success:
                        print(f"[OK] [Telemetria {iteration}] Enviada com sucesso para {server_ip}")
                    else:
                        print(f"[ERRO] [Telemetria {iteration}] Falha ao enviar para {server_ip} (verificar conectividade)")
                    
                    # Aguardar intervalo antes do próximo envio
                    print(f"[DEBUG] telemetry_loop: Aguardando {self.telemetry_interval}s até próximo envio...")
                    time.sleep(self.telemetry_interval)
                    
                except Exception as e:
                    print(f"[ERRO] telemetry_loop: Erro no loop de telemetria (iteração {iteration}): {e}")
                    import traceback
                    traceback.print_exc()
                    # Continuar mesmo em caso de erro
                    time.sleep(self.telemetry_interval)
        
        # Criar e iniciar thread
        self.telemetry_thread = threading.Thread(target=telemetry_loop, daemon=True)
        self.telemetry_thread.start()
        
        print(f"Monitorização contínua de telemetria iniciada (intervalo: {interval_seconds}s)")
        return True
    
    def stopContinuousTelemetry(self):
        """
        Para a monitorização contínua de telemetria.
        
        COMO FUNCIONA:
        - Define flag para False, fazendo o loop terminar
        - Aguarda thread terminar (até 5 segundos)
        
        PORQUÊ:
        - Permite parar monitorização de forma controlada
        - Útil para cleanup ou reinicialização
        
        Returns:
            bool: True se foi parada, False se já estava parada
        """
        if not self.telemetry_running:
            print("Aviso: Monitorização contínua não está em execução")
            return False
        
        self.telemetry_running = False
        
        # Aguardar thread terminar (com timeout)
        if self.telemetry_thread is not None:
            self.telemetry_thread.join(timeout=5.0)
            if self.telemetry_thread.is_alive():
                print("Aviso: Thread de telemetria não terminou no tempo esperado")
            else:
                print("Monitorização contínua de telemetria parada")
        
        return True
    
    def isTelemetryRunning(self):
        """
        Verifica se a monitorização contínua está em execução.
        
        Returns:
            bool: True se está em execução, False caso contrário
        """
        return self.telemetry_running
    
    def getinterfaces(self):
        """
        Obtém a lista de interfaces de rede do sistema usando o comando ip.
        
        Returns:
            list: Lista de strings com informações das interfaces (formato: "interface ip")
        """
        text = os.popen("ip -o -4 route show | awk '{print $3,$9}'").read()
        text = text.split("\n")
        removeNulls(text)
        return text[1:]

    