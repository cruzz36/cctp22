import socket
from protocol import MissionLink,TelemetryStream
import threading
from otherEntities import Limit
import os
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

class NMS_Server: 
    """
    Classe que representa a Nave-Mãe (servidor) no sistema.
    Responsável por coordenar rovers, receber telemetria e enviar missões.
    """
    def __init__(self):
        """
        Inicializa o servidor NMS.
        Cria diretórios necessários e inicializa os protocolos MissionLink e TelemetryStream.
        """
        self.id = socket.gethostname()
        # Preferir a interface da rede dos rovers (10.0.1.x). Se não existir, usar a primeira.
        interfaces = self.getinterfaces()
        rover_ip = next((i.split(" ")[1] for i in interfaces if i.split(" ")[1].startswith("10.0.1.")), None)
        self.IPADDRESS = rover_ip if rover_ip else interfaces[0].split(" ")[1]
        dir = f"../{self.id}/"
        try:
            os.mkdir(dir)
        except FileExistsError:
            None
        netDir = f"{dir}net/"
        try:
            os.mkdir(netDir)
        except FileExistsError:
            None
        self.missionLink = MissionLink.MissionLink(self.IPADDRESS,netDir)
        alertDir = f"{dir}alerts/"
        try:
            os.mkdir(alertDir)
        except FileExistsError:
            None
        self.telemetryStream = TelemetryStream.TelemetryStream(self.IPADDRESS,alertDir,1024)
        self.agents =  dict() # (agentId,ip)
        self.tasks = dict()
        self.pendingMissions = []  # Missões pendentes para atribuir quando rover solicitar
        self.missionProgress = dict()  # {mission_id: {rover_id: progress_data}}
        
        # Inicializar API de Observação
        try:
            from API.ObservationAPI import ObservationAPI
            self.observation_api = ObservationAPI(self, host='0.0.0.0', port=8082)
            print(f"[INFO] API de Observação inicializada (host=0.0.0.0, port=8082)")
        except ImportError as e:
            print(f"[AVISO] API de Observação não disponível: {e}")
            print("[AVISO] Instale Flask com: pip install flask")
            self.observation_api = None
        except Exception as e:
            print(f"[ERRO] Erro ao inicializar API de Observação: {e}")
            import traceback
            traceback.print_exc()
            self.observation_api = None


    def recvTelemetry(self):
        """
        Inicia o servidor TelemetryStream para receber dados de telemetria dos rovers.
        Executa em loop infinito.
        """
        print("[DEBUG] recvTelemetry: Iniciando servidor TelemetryStream...")
        self.telemetryStream.server()
    
    def startObservationAPI(self):
        """
        Inicia a API de Observação em thread separada.
        Disponibiliza endpoints REST para consulta de estado do sistema.
        """
        if self.observation_api is not None:
            try:
                self.observation_api.start()
                # Pequeno delay para garantir que a API está pronta
                import time
                time.sleep(0.5)
            except Exception as e:
                print(f"[ERRO] Erro ao iniciar API de Observação: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("[AVISO] API de Observação não disponível (Flask não instalado)")

    def recvMissionLink(self):
        """
        Recebe e processa mensagens através do MissionLink.
        Processa registos de agentes, envio de métricas, solicitações de missão e reportes de progresso.
        
        NOTA: O idAgent é extraído do handshake e identificado pelo IP/porta.
              O protocolo de dados não inclui idAgent, apenas idMission.
        """
        print("[DEBUG] recvMissionLink: Thread iniciada, aguardando mensagens de rovers...")
        while True:
            try:
                print("[DEBUG] recvMissionLink: Aguardando próxima mensagem...")
                lista = self.missionLink.recv()
                print(f"[DEBUG] recvMissionLink: Mensagem recebida: idAgent={lista[0]}, idMission={lista[1]}, missionType={lista[2]}, ip={lista[4]}")
            except TimeoutError as e:
                print(f"[AVISO] MissionLink timeout à espera de rover: {e}")
                continue
            except Exception as e:
                print(f"[AVISO] Erro inesperado no MissionLink: {e}")
                import traceback
                traceback.print_exc()
                continue

            # lista tem: [idAgent, idMission, missionType, message, ip]
            # idAgent é identificado pelo IP/porta do handshake
            idAgent = lista[0]
            idMission = lista[1]
            missionType = lista[2]  # Tipo de operação: R, T, M, Q, P (NÃO confundir com "task" do JSON)
            message = lista[3]
            ip = lista[4]

            # ============================================================
            # PROCESSAMENTO POR TIPO DE OPERAÇÃO (missionType)
            # ============================================================
            # NOTA: missionType indica o tipo de OPERAÇÃO do protocolo,
            #       não o tipo de tarefa física (capture_images, etc.)
            #       O tipo de tarefa física está dentro do JSON quando missionType="T"
            # ============================================================
            
            if missionType == self.missionLink.registerAgent:  # "R"
                # Rover regista-se na Nave-Mãe
                print(f"[DEBUG] recvMissionLink: Processando registo de rover (idAgent={idAgent}, ip={ip})")
                self.registerAgent(idAgent,ip) # It already sends the confirmation reply
                continue

            # if missionType == self.missionLink.sendMetrics:  # "M"
            #     # Rover envia métricas (nome de ficheiro JSON)
            #     try:
            #         parts = message.split("_")
            #         if len(parts) >= 4:
            #             iter = parts[3].split(".")[0]
            #         else:
            #             iter = "unknown"
            #             print(f"Aviso: Formato de nome de ficheiro inválido: {message}")
            #     except (IndexError, AttributeError) as e:
            #         print(f"Erro ao processar nome de ficheiro de métricas: {e}")
            #         iter = "error"
            #     self.missionLink.send(ip,self.missionLink.port,None,idAgent,idMission,iter)
            #     continue

            if missionType == self.missionLink.requestMission:  # "Q"
                # Rover solicita uma missão à Nave-Mãe
                print(f"[DEBUG] recvMissionLink: Processando solicitação de missão (idAgent={idAgent}, ip={ip})")
                self.handleMissionRequest(idAgent, ip)
                continue

            if missionType == self.missionLink.reportProgress:  # "P"
                # Rover reporta progresso de uma missão em execução
                # O campo 'message' contém dados de progresso (JSON)
                print(f"[DEBUG] recvMissionLink: Processando reporte de progresso (idAgent={idAgent}, idMission={idMission}, ip={ip})")
                self.handleMissionProgress(idAgent, idMission, message, ip)
                continue

    def sendTask(self,ip,idAgent,idMission,task):
        """
        Envia uma tarefa/missão para um rover através do MissionLink.
        Retransmite até receber confirmação válida.
        
        NOTA: Este método mantém compatibilidade com código antigo.
              Para enviar missões validadas, use sendMission().
        
        Args:
            ip (str): Endereço IP do rover
            idAgent (str): Identificador do rover
            idMission (str): Identificador da missão
            task: Objeto ou string com a definição da tarefa
        """
        print(f"[DEBUG] sendTask: Enviando tarefa para {idAgent} ({ip}), idMission={idMission}")
        self.missionLink.send(ip,self.missionLink.port,self.missionLink.taskRequest,idAgent,idMission,task)
        print(f"[DEBUG] sendTask: Aguardando confirmação de {idAgent}...")
        lista = self.missionLink.recv()
        print(f"[DEBUG] sendTask: Resposta recebida de {idAgent}: idAgent={lista[0]}, missionType={lista[2]}, ip={lista[4]}")
        # lista agora tem: [idAgent, idMission, missionType, message, ip]
        # Bug fix: usar 'or' em vez de 'and' - retransmitir se QUALQUER validação falhar
        # Bug fix: Removido loop interno redundante que comparava lista[3] != task incorretamente
        #          lista[3] é a mensagem recebida (string), task pode ser dict/string, comparação não faz sentido
        # Bug fix: lista[2] é missionType, não flag. Quando cliente envia ACK, missionType será None
        #          Verificar se missionType é None (confirmação) ou verificar mensagem de confirmação
        # Bug fix: Adicionar limite de retries para evitar loops infinitos (consistente com sendMission, sendMetrics, register)
        retries = 0
        max_retries = 10
        while (
            (lista[0] != idAgent or
            lista[2] is not None or  # missionType deve ser None para ACK de confirmação
            lista[4] != ip) and
            retries < max_retries
        ):
            retries += 1
            print(f"[DEBUG] sendTask: Confirmação inválida, retry {retries}/{max_retries} (esperado idAgent={idAgent}, ip={ip}, recebido idAgent={lista[0]}, missionType={lista[2]}, ip={lista[4]})")
            self.missionLink.send(ip,self.missionLink.port,self.missionLink.taskRequest,idAgent,idMission,task)
            lista = self.missionLink.recv()
            print(f"[DEBUG] sendTask: Nova resposta recebida: idAgent={lista[0]}, missionType={lista[2]}, ip={lista[4]}")
        
        if retries >= max_retries:
            print(f"[ERRO] sendTask: Máximo de tentativas ({max_retries}) atingido ao enviar tarefa para {idAgent}")
        else:
            print(f"[OK] sendTask: Tarefa {idMission} confirmada por {idAgent}")

    def sendMission(self, ip, idAgent, mission_data):
        """
        Envia uma missão completa e validada para um rover através do MissionLink.
        Valida o formato da missão antes de enviar e retransmite até receber confirmação.
        
        Formato obrigatório da missão (conforme PDF):
        {
            "mission_id": string (obrigatório, identificador único),
            "rover_id": string (obrigatório),
            "geographic_area": {
                "x1": float, "y1": float, "x2": float, "y2": float
            },
            "task": string (obrigatório: capture_images|sample_collection|environmental_analysis|...),
            "duration_minutes": integer (obrigatório, > 0),
            "update_frequency_seconds": integer (obrigatório, > 0),
            "priority": string (opcional: low|medium|high),
            "instructions": string (opcional)
        }
        
        Args:
            ip (str): Endereço IP do rover
            idAgent (str): Identificador do rover
            mission_data (dict or str): Dicionário ou string JSON com dados da missão
            
        Returns:
            bool: True se missão foi enviada e confirmada com sucesso, False caso contrário
            
        Raises:
            ValueError: Se o formato da missão for inválido
        """
        print(f"[DEBUG] sendMission: Preparando envio de missão para {idAgent} ({ip})")
        # Validar formato da missão
        is_valid, error_msg = validateMission(mission_data)
        if not is_valid:
            print(f"[ERRO] sendMission: Formato de missão inválido: {error_msg}")
            raise ValueError(f"Formato de missão inválido: {error_msg}")
        
        print(f"[DEBUG] sendMission: Missão validada com sucesso")
        # Converter para string JSON se for dicionário
        if isinstance(mission_data, dict):
            mission_json = json.dumps(mission_data)
        else:
            mission_json = mission_data
        
        # Extrair mission_id do JSON para usar como idMission no protocolo
        if isinstance(mission_data, dict):
            mission_id = mission_data["mission_id"]
        else:
            mission_dict = json.loads(mission_json)
            mission_id = mission_dict["mission_id"]
        
        print(f"[DEBUG] sendMission: Enviando missão {mission_id} para {idAgent} ({ip})")
        # Enviar missão via MissionLink
        # missionType="T" (taskRequest) indica que é uma operação de envio de tarefa
        # O mission_json contém o JSON completo da missão, incluindo o campo "task"
        # que pode ser: "capture_images", "sample_collection", ou "environmental_analysis"
        self.missionLink.send(ip, self.missionLink.port, self.missionLink.taskRequest, idAgent, mission_id, mission_json)
        
        # Aguardar confirmação
        print(f"[DEBUG] sendMission: Aguardando confirmação de {idAgent}...")
        lista = self.missionLink.recv()
        print(f"[DEBUG] sendMission: Resposta recebida: idAgent={lista[0]}, missionType={lista[2]}, message={lista[3]}, ip={lista[4]}")
        retries = 0
        max_retries = 5
        
        while retries < max_retries:
            # Bug fix: lista[2] é missionType, não flag. Quando cliente envia com missionType=None, é codificado como "N"
            #          O recv() extrai isto como a string "N", não Python None
            #          Verificar lista[2] == "N" em vez de lista[2] is None
            if (
                lista[0] == idAgent and
                lista[2] == self.missionLink.noneType and  # missionType deve ser "N" para ACK de confirmação
                lista[4] == ip
            ):
                # Confirmação recebida
                print(f"[OK] sendMission: Missão {mission_id} confirmada por {idAgent}")
                return True
            
            # Retransmitir
            retries += 1
            print(f"[DEBUG] sendMission: Confirmação inválida, retry {retries}/{max_retries} (esperado idAgent={idAgent}, missionType={self.missionLink.noneType}, ip={ip}, recebido idAgent={lista[0]}, missionType={lista[2]}, ip={lista[4]})")
            self.missionLink.send(ip, self.missionLink.port, self.missionLink.taskRequest, idAgent, mission_id, mission_json)
            lista = self.missionLink.recv()
            print(f"[DEBUG] sendMission: Nova resposta recebida: idAgent={lista[0]}, missionType={lista[2]}, ip={lista[4]}")
        
        print(f"[ERRO] sendMission: Falha ao enviar missão {mission_id} para {idAgent} após {max_retries} tentativas")
        return False



    def registerAgent(self,idAgent,ip):
        """
        Regista um agente/rover no sistema.
        Envia confirmação de registo através do MissionLink.
        
        Args:
            idAgent (str): Identificador único do agente
            ip (str): Endereço IP do agente
        """
        print(f"[DEBUG] registerAgent: Processando registo de {idAgent} de {ip}")
        if self.agents.get(idAgent) == None:
            self.agents[idAgent] = ip
            print(f"[OK] Rover {idAgent} registado com sucesso (IP: {ip})")
            print(f"[DEBUG] registerAgent: Enviando confirmação 'Registered' para {ip}")
            # No registo, idMission = "000" porque ainda não há missão atribuída
            # Bug fix: ackkey é uma flag, não um missionType. Usar None como missionType
            self.missionLink.send(ip,self.missionLink.port,None,idAgent,"000","Registered")
            print(f"[DEBUG] registerAgent: Confirmação enviada para {idAgent}")
            return
        print(f"[AVISO] Rover {idAgent} já estava registado (IP: {ip})")
        # Bug fix: ackkey é uma flag, não um missionType. Usar None como missionType
        self.missionLink.send(ip,self.missionLink.port,None,idAgent,"000","Already registered")
        print(f"[DEBUG] registerAgent: Resposta 'Already registered' enviada para {idAgent}")


    def parseConfig(self,filename):
        """
        Faz parse de um ficheiro de configuração JSON e envia tarefas para os rovers.
        
        NOTA: Este método é usado para configurações de métricas (template.json).
              Para enviar missões completas, use parseMissionFile() ou sendMission().
        
        Args:
            filename (str): Caminho do ficheiro de configuração JSON
        """
        file = open(filename)
        config = json.load(file)
        #print(config)
        i = 0
        for a in config:
            taskid = a["task_id"]
            self.tasks[taskid] = json.dumps(a)
            agentsToSend = a["devices"]
            for agent in agentsToSend:
                # Bug fix: Verificar se agente está registado antes de enviar
                agent_ip = self.agents.get(agent["device_id"])
                if agent_ip is None:
                    print(f"Aviso: Agente {agent['device_id']} não está registado. Ignorando envio de tarefa.")
                    continue
                
                # Bug fix: Converter dict para JSON string antes de enviar
                #          send() espera string e chama message.endswith(".json")
                agent_json = json.dumps(agent)
                # Envia tarefa com idAgent=agent["device_id"] e idMission=taskid
                self.missionLink.send(agent_ip,self.missionLink.port,self.missionLink.taskRequest,agent["device_id"],taskid,agent_json)
                #print(f"Agent {agent['device_id']} Parsed and sent")
        print("File Parsed")

    def parseMissionFile(self, filename):
        """
        Faz parse de um ficheiro de missão JSON e envia missões completas para os rovers.
        Valida o formato de cada missão antes de enviar.
        
        Formato esperado: Array de objetos de missão ou objeto único de missão.
        Cada missão deve conter todos os campos obrigatórios (ver validateMission()).
        
        Exemplo de ficheiro:
        [
            {
                "mission_id": "M-001",
                "rover_id": "r1",
                "geographic_area": {"x1": 10.0, "y1": 20.0, "x2": 50.0, "y2": 60.0},
                "task": "capture_images",
                "duration_minutes": 30,
                "update_frequency_seconds": 120
            },
            ...
        ]
        
        Args:
            filename (str): Caminho do ficheiro de missão JSON
            
        Returns:
            dict: Dicionário com estatísticas: {"sent": int, "failed": int, "errors": list}
        """
        print(f"[DEBUG] parseMissionFile: Iniciando parse do ficheiro {filename}")
        try:
            file = open(filename, 'r')
            missions_data = json.load(file)
            file.close()
            print(f"[DEBUG] parseMissionFile: Ficheiro lido com sucesso")
        except FileNotFoundError:
            print(f"[ERRO] parseMissionFile: Ficheiro {filename} não encontrado")
            return {"sent": 0, "failed": 0, "errors": [f"Ficheiro não encontrado: {filename}"]}
        except json.JSONDecodeError as e:
            print(f"[ERRO] parseMissionFile: JSON inválido em {filename}: {e}")
            return {"sent": 0, "failed": 0, "errors": [f"JSON inválido: {e}"]}
        
        # Se for um único objeto, converter para lista
        if isinstance(missions_data, dict):
            missions_data = [missions_data]
            print(f"[DEBUG] parseMissionFile: Convertido objeto único para lista")
        
        print(f"[DEBUG] parseMissionFile: Processando {len(missions_data)} missão(ões)")
        stats = {"sent": 0, "failed": 0, "errors": []}
        
        for mission in missions_data:
            mission_id = mission.get('mission_id', 'desconhecida')
            print(f"[DEBUG] parseMissionFile: Processando missão {mission_id}")
            # Validar missão
            is_valid, error_msg = validateMission(mission)
            if not is_valid:
                print(f"[ERRO] parseMissionFile: Missão {mission_id} inválida: {error_msg}")
                stats["failed"] += 1
                stats["errors"].append(f"Missão {mission_id}: {error_msg}")
                continue
            
            print(f"[DEBUG] parseMissionFile: Missão {mission_id} validada")
            # Obter IP do rover
            rover_id = mission["rover_id"]
            rover_ip = self.agents.get(rover_id)
            
            if rover_ip is None:
                print(f"[ERRO] parseMissionFile: Rover {rover_id} não está registado (agentes registados: {list(self.agents.keys())})")
                stats["failed"] += 1
                stats["errors"].append(f"Rover {rover_id} não está registado")
                continue
            
            print(f"[DEBUG] parseMissionFile: Rover {rover_id} encontrado (IP: {rover_ip}), enviando missão...")
            # Enviar missão
            try:
                success = self.sendMission(rover_ip, rover_id, mission)
                if success:
                    stats["sent"] += 1
                    print(f"[OK] parseMissionFile: Missão {mission_id} enviada para rover {rover_id}")
                else:
                    stats["failed"] += 1
                    stats["errors"].append(f"Falha ao enviar missão {mission_id} para rover {rover_id}")
                    print(f"[ERRO] parseMissionFile: Falha ao enviar missão {mission_id} para rover {rover_id}")
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"Erro ao enviar missão {mission_id}: {e}")
                print(f"[ERRO] parseMissionFile: Exceção ao enviar missão {mission_id}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"[OK] parseMissionFile: Parse concluído: {stats['sent']} enviadas, {stats['failed']} falhadas")
        if stats['errors']:
            print(f"[DEBUG] parseMissionFile: Erros encontrados: {stats['errors']}")
        return stats

    def handleMissionRequest(self, idAgent, ip):
        """
        Processa solicitação de missão de um rover.
        Implementa o requisito: "O rover deve ser capaz de solicitar uma missão à Nave-Mãe."
        
        Se houver missão disponível para o rover, envia-a. Caso contrário, responde que não há missão.
        
        Args:
            idAgent (str): Identificador do rover
            ip (str): Endereço IP do rover
        """
        print(f"[DEBUG] handleMissionRequest: Processando solicitação de missão de {idAgent} ({ip})")
        print(f"[DEBUG] handleMissionRequest: Missões pendentes: {len(self.pendingMissions)}")
        # Procurar missão disponível para este rover
        # (pode ser implementada lógica mais sofisticada de atribuição)
        if self.pendingMissions:
            # Enviar primeira missão disponível
            mission = self.pendingMissions.pop(0)
            mission_id = mission.get('mission_id', 'desconhecida')
            print(f"[DEBUG] handleMissionRequest: Enviando missão {mission_id} para {idAgent}")
            try:
                success = self.sendMission(ip, idAgent, mission)
                if success:
                    print(f"[OK] handleMissionRequest: Missão {mission_id} atribuída ao rover {idAgent}")
                else:
                    # Recolocar missão na fila se falhou
                    print(f"[AVISO] handleMissionRequest: Falha ao enviar missão {mission_id}, recolocando na fila")
                    self.pendingMissions.insert(0, mission)
            except Exception as e:
                print(f"[ERRO] handleMissionRequest: Erro ao enviar missão solicitada: {e}")
                import traceback
                traceback.print_exc()
                self.pendingMissions.insert(0, mission)
        else:
            # Sem missão disponível - enviar ACK indicando isso
            print(f"[DEBUG] handleMissionRequest: Sem missões disponíveis, enviando resposta 'no_mission' para {idAgent}")
            # Bug fix: ackkey é uma flag, não um missionType. Usar None como missionType
            self.missionLink.send(ip, self.missionLink.port, None, idAgent, "000", "no_mission")
            print(f"[INFO] handleMissionRequest: Rover {idAgent} solicitou missão, mas não há missões disponíveis")

    def handleMissionProgress(self, idAgent, idMission, progress_json, ip):
        """
        Processa reporte de progresso de uma missão.
        Implementa o requisito: "O rover deve reportar o progresso da missão de acordo 
        com parâmetros definidos na própria missão."
        
        Args:
            idAgent (str): Identificador do rover
            idMission (str): Identificador da missão
            progress_json (str): JSON string com dados de progresso
            ip (str): Endereço IP do rover
        """
        print(f"[DEBUG] handleMissionProgress: Processando progresso de {idAgent} para missão {idMission}")
        try:
            progress_data = json.loads(progress_json)
            print(f"[DEBUG] handleMissionProgress: Progresso parseado: {progress_data}")
            
            # Armazenar progresso
            if idMission not in self.missionProgress:
                self.missionProgress[idMission] = {}
            self.missionProgress[idMission][idAgent] = progress_data
            
            # Log do progresso
            progress_percent = progress_data.get("progress_percent", 0)
            status = progress_data.get("status", "unknown")
            print(f"[OK] Progresso da missão {idMission} (rover {idAgent}): {progress_percent}% - {status}")
            
            # Enviar confirmação
            print(f"[DEBUG] handleMissionProgress: Enviando confirmação para {idAgent}")
            # Bug fix: ackkey é uma flag, não um missionType. Usar None como missionType
            self.missionLink.send(ip, self.missionLink.port, None, idAgent, idMission, "progress_received")
            print(f"[DEBUG] handleMissionProgress: Confirmação enviada")
            
        except json.JSONDecodeError as e:
            print(f"[ERRO] handleMissionProgress: Erro ao fazer parse do progresso: {e}")
            # Bug fix: ackkey é uma flag, não um missionType. Usar None como missionType
            self.missionLink.send(ip, self.missionLink.port, None, idAgent, idMission, "parse_error")
        except Exception as e:
            print(f"[ERRO] handleMissionProgress: Erro ao processar progresso: {e}")
            import traceback
            traceback.print_exc()
            # Bug fix: ackkey é uma flag, não um missionType. Usar None como missionType
            self.missionLink.send(ip, self.missionLink.port, None, idAgent, idMission, "error")

    def addPendingMission(self, mission):
        """
        Adiciona uma missão à fila de missões pendentes.
        Estas missões serão atribuídas quando rovers solicitarem.
        
        Args:
            mission (dict): Dicionário com dados da missão
        """
        is_valid, error_msg = validateMission(mission)
        if is_valid:
            self.pendingMissions.append(mission)
            print(f"Missão {mission.get('mission_id')} adicionada à fila de pendentes")
        else:
            print(f"Erro: Missão inválida não pode ser adicionada: {error_msg}")   
        
            
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