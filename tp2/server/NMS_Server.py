import socket
from protocol import MissionLink,TelemetryStream
import threading
from otherEntities import Limit
import os
import json
import glob

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
        """
        print("[DEBUG] recvMissionLink: Thread iniciada, aguardando mensagens de rovers...")
        while True:
            try:
                print("[DEBUG] recvMissionLink: Aguardando próxima mensagem...")
                lista = self.missionLink.recv()
                print(f"[DEBUG] recvMissionLink: Mensagem recebida: idAgent={lista[0]}, idMission={lista[1]}, missionType={lista[2]}, ip={lista[4]}")
            except TimeoutError as e:
                print(f"[DEBUG] recvMissionLink: Timeout ao aguardar mensagem: {e}")
                continue
            except Exception as e:
                print(f"[DEBUG] recvMissionLink: Erro ao receber mensagem: {e}")
                continue

            idAgent = lista[0]
            idMission = lista[1]
            missionType = lista[2]
            message = lista[3]
            ip = lista[4]
            
            if missionType == self.missionLink.registerAgent:  # "R"
                print(f"[DEBUG] recvMissionLink: Processando registo de rover (idAgent={idAgent}, ip={ip})")
                self.registerAgent(idAgent,ip)
                continue

            if missionType == self.missionLink.requestMission:  # "Q"
                print(f"[DEBUG] recvMissionLink: Processando solicitação de missão (idAgent={idAgent}, ip={ip})")
                self.handleMissionRequest(idAgent, ip)
                continue

            if missionType == self.missionLink.reportProgress:  # "P"
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
        # Validar formato da missão
        is_valid, error_msg = validateMission(mission_data)
        if not is_valid:
            raise ValueError(f"Formato de missão inválido: {error_msg}")
        
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
        
        # Enviar missão via MissionLink
        print(f"[DEBUG] sendMission: Enviando missão {mission_id} para rover {idAgent} ({ip})")
        self.missionLink.send(ip, self.missionLink.port, self.missionLink.taskRequest, idAgent, mission_id, mission_json)
        
        # Aguardar confirmação
        print(f"[DEBUG] sendMission: Aguardando confirmação de {idAgent}...")
        lista = self.missionLink.recv()
        print(f"[DEBUG] sendMission: Resposta recebida: idAgent={lista[0]}, missionType={lista[2]}, message={lista[3]}, ip={lista[4]}")
        retries = 0
        max_retries = 5
        
        while retries < max_retries:
            if (
                lista[0] == idAgent and
                lista[2] == self.missionLink.noneType and
                lista[4] == ip
            ):
                # Confirmação recebida
                if isinstance(mission_data, dict):
                    self.tasks[mission_id] = mission_data
                else:
                    self.tasks[mission_id] = mission_json
                print(f"[DEBUG] sendMission: Missão {mission_id} confirmada e armazenada")
                print(f"[INFO] Missão {mission_id} confirmada por rover {idAgent}")
                return True
            
            # Retransmitir
            retries += 1
            print(f"[DEBUG] sendMission: Confirmação inválida, retry {retries}/{max_retries}")
            self.missionLink.send(ip, self.missionLink.port, self.missionLink.taskRequest, idAgent, mission_id, mission_json)
            lista = self.missionLink.recv()
            print(f"[DEBUG] sendMission: Nova resposta recebida: idAgent={lista[0]}, missionType={lista[2]}, ip={lista[4]}")
        
        print(f"[DEBUG] sendMission: Falha ao enviar missão após {max_retries} tentativas")
        return False



    def registerAgent(self,idAgent,ip):
        """
        Regista um agente/rover no sistema.
        Envia confirmação de registo através do MissionLink.
        Carrega automaticamente missões do serverDB para o rover registado.
        
        Args:
            idAgent (str): Identificador único do agente
            ip (str): Endereço IP do agente
        """
        if self.agents.get(idAgent) == None:
            self.agents[idAgent] = ip
            print(f"[INFO] Rover {idAgent} conectado (IP: {ip})")
            self.missionLink.send(ip,self.missionLink.port,None,idAgent,"000","Registered")
            # Carregar missões do serverDB para este rover
            self._loadMissionsForRover(idAgent)
            return
        self.missionLink.send(ip,self.missionLink.port,None,idAgent,"000","Already registered")
    
    def _loadMissionsForRover(self, rover_id):
        """
        Carrega automaticamente missões do diretório serverDB para um rover específico.
        Procura por ficheiros mission*.json e envia missões que correspondem ao rover_id.
        
        Args:
            rover_id (str): ID do rover para o qual carregar missões
        """
        # Tentar múltiplos caminhos possíveis para serverDB
        possible_paths = [
            "serverDB",  # Diretório atual
            "/tmp/nms/serverDB",  # Caminho padrão no CORE
            os.path.join(os.path.dirname(__file__), "..", "serverDB"),  # Relativo ao módulo
        ]
        
        serverdb_dir = None
        for path in possible_paths:
            if os.path.exists(path):
                serverdb_dir = path
                break
        
        if not serverdb_dir:
            return
        
        # Procurar ficheiros mission*.json
        import glob
        mission_files = glob.glob(os.path.join(serverdb_dir, "mission*.json"))
        
        if not mission_files:
            return
        
        # Enviar apenas a primeira missão disponível para este rover
        # As outras missões serão enviadas quando o rover solicitar ou quando a atual for concluída
        first_mission_sent = False
        
        for mission_file in mission_files:
            try:
                with open(mission_file, 'r') as f:
                    mission_data = json.load(f)
                
                # Verificar se a missão é para este rover
                if mission_data.get("rover_id") == rover_id:
                    mission_id = mission_data.get("mission_id", "unknown")
                    
                    # Validar missão
                    is_valid, error_msg = validateMission(mission_data)
                    if not is_valid:
                        continue
                    
                    if not first_mission_sent:
                        # Enviar apenas a primeira missão encontrada
                        rover_ip = self.agents.get(rover_id)
                        if rover_ip:
                            try:
                                success = self.sendMission(rover_ip, rover_id, mission_data)
                                if success:
                                    print(f"[INFO] Missão {mission_id} enviada para rover {rover_id}")
                                    first_mission_sent = True
                                    continue  # Pular para próxima iteração
                            except Exception:
                                pass
                    
                    # Adicionar missões restantes à fila de pendentes
                    if first_mission_sent:
                        # Verificar se já foi enviada (está em self.tasks)
                        if mission_id not in self.tasks:
                            self.pendingMissions.append(mission_data)
                        
            except Exception:
                pass


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
        """
        print(f"[DEBUG] handleMissionRequest: Processando solicitação de missão de {idAgent} ({ip})")
        print(f"[DEBUG] handleMissionRequest: Missões pendentes: {len(self.pendingMissions)}")
        if self.pendingMissions:
            mission = self.pendingMissions.pop(0)
            mission_id = mission.get('mission_id', 'desconhecida')
            print(f"[DEBUG] handleMissionRequest: Enviando missão {mission_id} para {idAgent}")
            try:
                success = self.sendMission(ip, idAgent, mission)
                if success:
                    print(f"[DEBUG] handleMissionRequest: Missão {mission_id} atribuída com sucesso")
                else:
                    print(f"[DEBUG] handleMissionRequest: Falha ao enviar missão, recolocando na fila")
                    self.pendingMissions.insert(0, mission)
            except Exception as e:
                print(f"[DEBUG] handleMissionRequest: Erro ao enviar missão: {e}")
                self.pendingMissions.insert(0, mission)
        else:
            print(f"[DEBUG] handleMissionRequest: Sem missões disponíveis para {idAgent}")
            self.missionLink.send(ip, self.missionLink.port, None, idAgent, "000", "no_mission")

    def handleMissionProgress(self, idAgent, idMission, progress_json, ip):
        """
        Processa reporte de progresso de uma missão.
        """
        print(f"[DEBUG] handleMissionProgress: Processando progresso de {idAgent} para missão {idMission}")
        try:
            progress_data = json.loads(progress_json)
            print(f"[DEBUG] handleMissionProgress: Progresso parseado: {progress_data}")
            
            # Armazenar progresso
            if idMission not in self.missionProgress:
                self.missionProgress[idMission] = {}
            self.missionProgress[idMission][idAgent] = progress_data
            
            # Enviar confirmação
            print(f"[DEBUG] handleMissionProgress: Enviando confirmação para {idAgent}")
            self.missionLink.send(ip, self.missionLink.port, None, idAgent, idMission, "progress_received")
            print(f"[DEBUG] handleMissionProgress: Confirmação enviada")
            
        except json.JSONDecodeError as e:
            print(f"[DEBUG] handleMissionProgress: Erro ao fazer parse do JSON: {e}")
            self.missionLink.send(ip, self.missionLink.port, None, idAgent, idMission, "parse_error")
        except Exception as e:
            print(f"[DEBUG] handleMissionProgress: Erro ao processar progresso: {e}")
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