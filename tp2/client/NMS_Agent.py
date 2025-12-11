import socket
from protocol import MissionLink,TelemetryStream
import os
import time
import json
import threading
import math

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
        self.telemetry_interval = 30  # Intervalo padrão em segundos (conforme requisitos: telemetria contínua)
        self.current_mission = None  # Missão atualmente em execução
        self.mission_queue = []  # Fila de missões pendentes (rover executa uma de cada vez)
        self.mission_executing = False  # Flag para indicar se há missão em execução

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
        self.missionLink.send(ip,self.missionLink.port,self.missionLink.registerAgent,self.id,"000","\0")
        lista = self.missionLink.recv()
        retries = 0
        max_retries = 10
        while (lista[0] != self.id or lista[4] != ip) and retries < max_retries:
            retries += 1
            self.missionLink.send(ip,self.missionLink.port,self.missionLink.registerAgent,self.id,"000","\0")
            lista = self.missionLink.recv()
        
        if retries >= max_retries:
            raise Exception(f"Máximo de tentativas ({max_retries}) atingido ao registar")
        
        print(f"[INFO] Rover {self.id} conectado à Nave-Mãe {ip}")
    
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
        # Enviar solicitação de missão
        self.missionLink.send(ip, self.missionLink.port, self.missionLink.requestMission, self.id, "000", "request")
        
        # Aguardar resposta (pode ser missão ou mensagem de "sem missão disponível")
        try:
            response = self.missionLink.recv()
            if response[2] == self.missionLink.taskRequest:
                mission_message = response[3]
                mission_id = response[1]
                
                # Validar formato da missão
                is_valid, error_msg = validateMission(mission_message)
                
                if not is_valid:
                    self.missionLink.send(response[4], self.missionLink.port, None, self.id, mission_id, "invalid")
                    return None
                
                # Parse do JSON da missão
                try:
                    if isinstance(mission_message, str):
                        mission_data = json.loads(mission_message)
                    else:
                        mission_data = mission_message
                except json.JSONDecodeError:
                    self.missionLink.send(response[4], self.missionLink.port, None, self.id, mission_id, "parse_error")
                    return None
                
                # Armazenar missão validada
                self.tasks[mission_id] = mission_data
                
                # Enviar ACK de confirmação
                self.missionLink.send(response[4], self.missionLink.port, None, self.id, mission_id, mission_id)
                
                return mission_data
            elif response[2] == self.missionLink.noneType:
                if response[3] == "no_mission":
                    print(f"[INFO] requestMission: Nave-Mãe respondeu: sem missão disponível no momento")
                return None
        except Exception as e:
            print(f"[ERRO] requestMission: Erro ao solicitar missão: {e}")
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
        }
        
        NOTA: O idAgent é usado apenas no handshake. Nas mensagens de dados,
              apenas idMission é enviado no protocolo.
        
        Returns:
            dict or None: Dicionário com dados da missão validada, ou None se não for missão válida
        """
        lista = self.missionLink.recv()
        
        if lista[2] == self.missionLink.taskRequest:
            mission_message = lista[3]
            mission_id = lista[1]
            
            # Validar formato da missão
            is_valid, error_msg = validateMission(mission_message)
            
            if not is_valid:
                self.missionLink.send(lista[4], self.missionLink.port, None, self.id, mission_id, "invalid")
                return None
            
            # Parse do JSON da missão
            try:
                if isinstance(mission_message, str):
                    mission_data = json.loads(mission_message)
                else:
                    mission_data = mission_message
            except json.JSONDecodeError:
                self.missionLink.send(lista[4], self.missionLink.port, None, self.id, mission_id, "parse_error")
                return None
            
            # Armazenar missão validada
            self.tasks[mission_id] = mission_data
            
            # Enviar ACK de confirmação
            self.missionLink.send(lista[4], self.missionLink.port, None, self.id, mission_id, mission_id)
            
            # Verificar se já há missão em execução
            if self.mission_executing:
                self.mission_queue.append(mission_data)
                print(f"[INFO] Missão {mission_id} adicionada à fila")
            else:
                self.mission_executing = True
                self.current_mission = mission_data
                print(f"[INFO] Missão ID: {mission_id} recebida - iniciando execução")
                mission_thread = threading.Thread(target=self.executeMission, args=(mission_data, self.serverAddress), daemon=True)
                mission_thread.start()
            
            return mission_data
        
        return None
    
    def executeMission(self, mission_data, server_ip):
        """
        Executa uma missão recebida, atualizando posição e enviando telemetria periodicamente.
        
        Args:
            mission_data (dict): Dicionário com dados da missão
            server_ip (str): Endereço IP da Nave-Mãe
        """
        mission_id = mission_data.get("mission_id", "unknown")
        duration_minutes = mission_data.get("duration_minutes", 30)
        geographic_area = mission_data.get("geographic_area", {})
        task = mission_data.get("task", "unknown")
        
        print(f"[INFO] Executando missão {mission_id} ({task}, {duration_minutes}min)")
        
        # Extrair coordenadas da área geográfica
        x1 = geographic_area.get("x1", 0.0)
        y1 = geographic_area.get("y1", 0.0)
        x2 = geographic_area.get("x2", 100.0)
        y2 = geographic_area.get("y2", 100.0)
        
        # Calcular centro da área como destino inicial
        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        
        # Estado inicial: mover para a área da missão
        self.updateOperationalStatus("a caminho")
        self.updateVelocity(5.0)  # 5 m/s
        
        # Calcular direção para o centro da área
        current_x = self.position["x"]
        current_y = self.position["y"]
        dx = center_x - current_x
        dy = center_y - current_y
        distance = (dx**2 + dy**2)**0.5
        
        if distance > 0.1:
            direction_rad = math.atan2(dy, dx)
            direction_deg = math.degrees(direction_rad)
            self.updateDirection(direction_deg)
        
        # Simular movimento para a área da missão
        steps_to_area = int(distance / 5.0) + 1  # Passos de 5 metros
        for step in range(steps_to_area):
            if distance > 0.1:
                # Mover gradualmente em direção ao centro
                progress = (step + 1) / steps_to_area
                new_x = current_x + dx * progress
                new_y = current_y + dy * progress
                self.updatePosition(new_x, new_y, 0.0)
            time.sleep(0.5)  # Pequeno delay para simular movimento
        
        # Chegou à área da missão - iniciar execução
        self.updateOperationalStatus("em missão")
        self.updateVelocity(2.0)  # Velocidade reduzida durante execução
        
        # Calcular número de atualizações durante a missão (usar intervalo fixo de 30s)
        total_duration_seconds = duration_minutes * 60
        update_interval_seconds = 30  # Intervalo fixo de 30 segundos (mesmo da telemetria contínua)
        num_updates = max(1, int(total_duration_seconds / update_interval_seconds))
        
        # Executar missão com atualizações periódicas de posição e estado
        # A telemetria contínua (30s) continua a correr em paralelo
        start_time = time.time()
        
        # Padrão de movimento dentro da área (exploração em grid)
        grid_steps_x = 5
        grid_steps_y = 5
        step_size_x = (x2 - x1) / grid_steps_x
        step_size_y = (y2 - y1) / grid_steps_y
        
        for update_idx in range(num_updates):
            elapsed_time = time.time() - start_time
            progress_percent = min(100, int((elapsed_time / total_duration_seconds) * 100))
            
            # Calcular posição atual na área (movimento em grid)
            grid_x = (update_idx % grid_steps_x)
            grid_y = (update_idx // grid_steps_x) % grid_steps_y
            
            mission_x = x1 + grid_x * step_size_x
            mission_y = y1 + grid_y * step_size_y
            
            # Garantir que está dentro dos limites
            mission_x = max(x1, min(x2, mission_x))
            mission_y = max(y1, min(y2, mission_y))
            
            # Atualizar posição
            self.updatePosition(mission_x, mission_y, 0.0)
            
            # Atualizar bateria (diminui gradualmente)
            battery_level = max(20.0, 100.0 - (elapsed_time / total_duration_seconds) * 30.0)
            self.updateBattery(battery_level)
            
            # Atualizar temperatura (aumenta ligeiramente durante operação)
            temperature = 20.0 + (elapsed_time / total_duration_seconds) * 15.0
            self.updateTemperature(temperature)
            
            # NÃO enviar telemetria aqui - a telemetria contínua (30s) já faz isso
            
            # Aguardar até próxima atualização (intervalo fixo de 30s)
            if update_idx < num_updates - 1:
                time.sleep(update_interval_seconds)
        
        # Missão concluída
        self.updateOperationalStatus("parado")
        self.updateVelocity(0.0)
        
        # A telemetria contínua (30s) irá mostrar o estado "parado" automaticamente
        
        print(f"[OK] Missão {mission_id} concluída")
        
        # Remover missão da lista de tarefas ativas
        if mission_id in self.tasks:
            del self.tasks[mission_id]
        
        # Limpar missão atual e verificar se há missões na fila
        if self.current_mission and self.current_mission.get("mission_id") == mission_id:
            self.current_mission = None
            self.mission_executing = False
            
            # Se há missões na fila, executar a próxima
            if self.mission_queue:
                next_mission = self.mission_queue.pop(0)
                self.mission_executing = True
                self.current_mission = next_mission
                print(f"[INFO] Iniciando próxima missão da fila: {next_mission.get('mission_id')}")
                next_thread = threading.Thread(target=self.executeMission, args=(next_mission, server_ip), daemon=True)
                next_thread.start()

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
        import time
        from datetime import datetime
        
        telemetry = {
            "rover_id": self.id,
            "position": self.position.copy(),  # Cópia para não modificar original
            "operational_status": self.operational_status,
            "timestamp": datetime.now().isoformat()  # Adicionar timestamp ISO 8601
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
        try:
            # Criar mensagem de telemetria
            telemetry = self.createTelemetryMessage(metrics)
            
            # Gerar nome do ficheiro se não fornecido
            if filename is None:
                # Usar timestamp com microsegundos para evitar colisões
                import time as time_module
                timestamp = time_module.time()  # Float com microsegundos
                timestamp_str = f"{timestamp:.6f}".replace('.', '_')  # Remover ponto decimal
                filename = f"telemetry_{self.id}_{timestamp_str}.json"
            
            # Garantir que filename está na pasta correta
            if not os.path.dirname(filename):
                filename = os.path.join(".", filename)
            
            # Salvar em ficheiro JSON
            with open(filename, "w") as f:
                json.dump(telemetry, f, indent=2)
            
            # Enviar via TelemetryStream
            success = self.sendTelemetry(server_ip, filename)
            
            if success:
                # Remover ficheiro após envio bem-sucedido
                try:
                    os.remove(filename)
                except:
                    pass
            
            return success
            
        except Exception as e:
            print(f"[ERRO] Erro ao criar e enviar telemetria: {e}")
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
            return False
        
        self.telemetry_interval = interval_seconds
        self.telemetry_running = True
        
        def telemetry_loop():
            """Loop interno para envio periódico de telemetria contínua.
            
            Conforme requisitos do PDF: "Os rovers devem reportar dados de monitorização 
            continuamente para garantir que estão a operar corretamente."
            """
            time.sleep(self.telemetry_interval)  # Aguardar intervalo antes do primeiro envio
            while self.telemetry_running:
                try:
                    # Usar timestamp com microsegundos para evitar colisões entre telemetria contínua e de missão
                    timestamp = time.time()  # Float com microsegundos
                    timestamp_str = f"{timestamp:.6f}".replace('.', '_')  # Remover ponto decimal
                    filename = f"telemetry_{self.id}_{timestamp_str}.json"
                    success = self.createAndSendTelemetry(server_ip, None, filename)
                    
                    if success:
                        print(f"[INFO] Telemetria enviada para {server_ip}")
                    
                    time.sleep(self.telemetry_interval)
                    
                except Exception as e:
                    # Continuar mesmo em caso de erro
                    time.sleep(self.telemetry_interval)
        
        # Criar e iniciar thread
        self.telemetry_thread = threading.Thread(target=telemetry_loop, daemon=True)
        self.telemetry_thread.start()
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

    