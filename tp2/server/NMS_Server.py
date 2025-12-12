import socket
from protocol import MissionLink,TelemetryStream
import threading
import time
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
        "duration_minutes": integer (obrigatório, > 0)
    }
    
    Campos opcionais:
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
        "duration_minutes": (int, float)
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
        while True:
            try:
                lista = self.missionLink.recv()
            except TimeoutError:
                continue
            except Exception:
                continue

            idAgent = lista[0]
            idMission = lista[1]
            missionType = lista[2]
            message = lista[3]
            ip = lista[4]
            
            if missionType == self.missionLink.registerAgent:  # "R"
                self.registerAgent(idAgent,ip)
                continue

            if missionType == self.missionLink.requestMission:  # "Q"
                self.handleMissionRequest(idAgent, ip)
                continue

            if missionType == self.missionLink.reportProgress:  # "P"
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
        self.missionLink.send(ip,self.missionLink.port,self.missionLink.taskRequest,idAgent,idMission,task)
        lista = self.missionLink.recv()
        retries = 0
        max_retries = 10
        while (
            (lista[0] != idAgent or
            lista[2] is not None or
            lista[4] != ip) and
            retries < max_retries
        ):
            retries += 1
            self.missionLink.send(ip,self.missionLink.port,self.missionLink.taskRequest,idAgent,idMission,task)
            lista = self.missionLink.recv()
        
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
        # O método send() já aguarda confirmação internamente e retorna True se bem-sucedido
        # Não devemos chamar recv() aqui porque estabeleceria uma nova conexão e poderia receber outras mensagens
        print(f"[DEBUG] sendMission: Iniciando envio de missão {mission_id} para rover {idAgent} ({ip}:{self.missionLink.port})")
        print(f"[DEBUG] sendMission: Tamanho da mensagem JSON: {len(mission_json)} bytes")
        retries = 0
        max_retries = 5
        
        while retries < max_retries:
            try:
                print(f"[DEBUG] sendMission: Tentativa {retries + 1}/{max_retries} - chamando missionLink.send()")
                success = self.missionLink.send(ip, self.missionLink.port, self.missionLink.taskRequest, idAgent, mission_id, mission_json)
                print(f"[DEBUG] sendMission: missionLink.send() retornou: {success}")
                if success:
                    # Missão enviada com sucesso - armazenar em tasks
                    if isinstance(mission_data, dict):
                        self.tasks[mission_id] = mission_data
                    else:
                        self.tasks[mission_id] = mission_json
                    print(f"[INFO] Missão {mission_id} enviada e confirmada por rover {idAgent}")
                    return True
                else:
                    # send() retornou False - tentar novamente
                    retries += 1
                    if retries < max_retries:
                        print(f"[INFO] Tentativa {retries}/{max_retries} de envio de missão {mission_id} falhou, a tentar novamente...")
                        time.sleep(0.5)  # Pequeno delay antes de retransmitir
            except Exception as e:
                retries += 1
                if retries < max_retries:
                    print(f"[INFO] Erro ao enviar missão {mission_id} (tentativa {retries}/{max_retries}): {e}")
                    time.sleep(0.5)
                else:
                    print(f"[ERRO] Missão {mission_id} não confirmada por rover {idAgent} após {max_retries} tentativas: {e}")
        
        print(f"[ERRO] Missão {mission_id} não confirmada por rover {idAgent} após {max_retries} tentativas")
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
            print(f"[INFO] Nave-Mãe conectada ao rover {idAgent} (IP: {ip})")
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
        
        # Coletar todas as missões válidas para este rover primeiro
        valid_missions = []
        
        for mission_file in sorted(mission_files):  # Ordenar para garantir ordem consistente
            try:
                with open(mission_file, 'r') as f:
                    mission_data = json.load(f)
                
                # Verificar se a missão é para este rover
                if mission_data.get("rover_id") == rover_id:
                    mission_id = mission_data.get("mission_id", "unknown")
                    
                    # Validar missão (ignorar campos opcionais como update_frequency_seconds se existirem)
                    is_valid, error_msg = validateMission(mission_data)
                    if not is_valid:
                        continue
                    
                    # Verificar se a missão já foi concluída (mesmo que não esteja em tasks)
                    is_completed = False
                    if mission_id in self.missionProgress:
                        progress = self.missionProgress[mission_id]
                        if isinstance(progress, dict) and rover_id in progress:
                            rover_progress = progress[rover_id]
                            if isinstance(rover_progress, dict):
                                status = rover_progress.get("status", "")
                                if status == "completed":
                                    is_completed = True
                    
                    # Se está concluída, não recarregar (já foi executada)
                    if is_completed:
                        continue
                    
                    # Verificar se já foi enviada e ainda está ativa (está em self.tasks)
                    if mission_id in self.tasks:
                        # Se está em tasks e não está concluída, ainda está ativa - pular
                        continue
                    
                    # Verificar se já está na fila para evitar duplicados
                    already_in_queue = False
                    for pending in self.pendingMissions:
                        if isinstance(pending, dict):
                            if pending.get("mission_id") == mission_id:
                                already_in_queue = True
                                break
                        elif isinstance(pending, str):
                            try:
                                pending_dict = json.loads(pending)
                                if pending_dict.get("mission_id") == mission_id:
                                    already_in_queue = True
                                    break
                            except:
                                pass
                    
                    if already_in_queue:
                        continue  # Já está na fila, pular
                    
                    # Adicionar à lista de missões válidas
                    valid_missions.append(mission_data)
                        
            except Exception:
                pass
        
        # Ordenar missões por mission_id para garantir ordem correta
        valid_missions.sort(key=lambda m: m.get("mission_id", ""))
        
        # Enviar apenas a primeira missão disponível para este rover
        # As outras missões serão enviadas quando o rover solicitar ou quando a atual for concluída
        first_mission_sent = False
        
        for mission_data in valid_missions:
            if not first_mission_sent:
                # Enviar apenas a primeira missão encontrada
                rover_ip = self.agents.get(rover_id)
                if rover_ip:
                    try:
                        success = self.sendMission(rover_ip, rover_id, mission_data)
                        if success:
                            first_mission_sent = True
                            continue  # Pular para próxima iteração
                    except Exception:
                        pass
            
            # Adicionar missões restantes à fila de pendentes
            # (adicionar todas as missões que não foram enviadas)
            self.pendingMissions.append(mission_data)


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
                "duration_minutes": 30
            },
            ...
        ]
        
        Args:
            filename (str): Caminho do ficheiro de missão JSON
            
        Returns:
            dict: Dicionário com estatísticas: {"sent": int, "failed": int, "errors": list}
        """
        try:
            file = open(filename, 'r')
            missions_data = json.load(file)
            file.close()
        except FileNotFoundError:
            print(f"[ERRO] parseMissionFile: Ficheiro {filename} não encontrado")
            return {"sent": 0, "failed": 0, "errors": [f"Ficheiro não encontrado: {filename}"]}
        except json.JSONDecodeError as e:
            print(f"[ERRO] parseMissionFile: JSON inválido em {filename}: {e}")
            return {"sent": 0, "failed": 0, "errors": [f"JSON inválido: {e}"]}
        
        # Se for um único objeto, converter para lista
        if isinstance(missions_data, dict):
            missions_data = [missions_data]
        
        stats = {"sent": 0, "failed": 0, "errors": []}
        
        for mission in missions_data:
            mission_id = mission.get('mission_id', 'desconhecida')
            # Validar missão
            is_valid, error_msg = validateMission(mission)
            if not is_valid:
                print(f"[ERRO] parseMissionFile: Missão {mission_id} inválida: {error_msg}")
                stats["failed"] += 1
                stats["errors"].append(f"Missão {mission_id}: {error_msg}")
                continue
            
            # Obter IP do rover
            rover_id = mission["rover_id"]
            rover_ip = self.agents.get(rover_id)
            
            if rover_ip is None:
                print(f"[ERRO] parseMissionFile: Rover {rover_id} não está registado")
                stats["failed"] += 1
                stats["errors"].append(f"Rover {rover_id} não está registado")
                continue
            
            # Enviar missão
            try:
                success = self.sendMission(rover_ip, rover_id, mission)
                if success:
                    stats["sent"] += 1
                else:
                    stats["failed"] += 1
                    stats["errors"].append(f"Falha ao enviar missão {mission_id} para rover {rover_id}")
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"Erro ao enviar missão {mission_id}: {e}")
        
        return stats

    def handleMissionRequest(self, idAgent, ip):
        """
        Processa solicitação de missão de um rover.
        Procura missões pendentes específicas para este rover.
        """
        # Procurar missão pendente específica para este rover
        mission_to_send = None
        for i, mission in enumerate(self.pendingMissions):
            if isinstance(mission, str):
                try:
                    mission = json.loads(mission)
                except:
                    continue
            
            if mission.get("rover_id") == idAgent:
                # Encontrou missão para este rover
                mission_to_send = self.pendingMissions.pop(i)
                break
        
        # NÃO enviar missões de outros rovers - apenas missões específicas para este rover
        # Se não encontrou missão específica, verificar se há mais missões no serverDB para este rover
        if mission_to_send is None:
            # Se não há missões pendentes específicas, verificar se há mais missões no serverDB para este rover
            self._loadMissionsForRover(idAgent)
            
            # Tentar novamente após carregar
            if self.pendingMissions:
                mission_to_send = None
                for i, mission in enumerate(self.pendingMissions):
                    if isinstance(mission, str):
                        try:
                            mission = json.loads(mission)
                        except:
                            continue
                    
                    if mission.get("rover_id") == idAgent:
                        mission_to_send = self.pendingMissions.pop(i)
                        break
                
                if mission_to_send:
                    try:
                        success = self.sendMission(ip, idAgent, mission_to_send)
                        if not success:
                            self.pendingMissions.insert(0, mission_to_send)
                    except Exception:
                        self.pendingMissions.insert(0, mission_to_send)
                else:
                    self.missionLink.send(ip, self.missionLink.port, None, idAgent, "000", "no_mission")
            else:
                self.missionLink.send(ip, self.missionLink.port, None, idAgent, "000", "no_mission")
        else:
            # Missão específica encontrada - enviar
            try:
                success = self.sendMission(ip, idAgent, mission_to_send)
                if not success:
                    self.pendingMissions.insert(0, mission_to_send)
            except Exception:
                self.pendingMissions.insert(0, mission_to_send)

    def handleMissionProgress(self, idAgent, idMission, progress_json, ip):
        """
        Processa reporte de progresso de uma missão.
        """
        try:
            progress_data = json.loads(progress_json)
            
            # Armazenar progresso
            if idMission not in self.missionProgress:
                self.missionProgress[idMission] = {}
            self.missionProgress[idMission][idAgent] = progress_data
            
            # Se a missão foi concluída, remover de tasks imediatamente
            if isinstance(progress_data, dict):
                status = progress_data.get("status", "")
                if status == "completed":
                    if idMission in self.tasks:
                        del self.tasks[idMission]
            
            # Enviar confirmação
            self.missionLink.send(ip, self.missionLink.port, None, idAgent, idMission, "progress_received")
            
        except json.JSONDecodeError:
            self.missionLink.send(ip, self.missionLink.port, None, idAgent, idMission, "parse_error")
        except Exception:
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