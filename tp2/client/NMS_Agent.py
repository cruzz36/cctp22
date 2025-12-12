import socket
from protocol import MissionLink,TelemetryStream
import os
import time
import json
import threading
import math
import random

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

def degreesToCardinalDirection(degrees):
    """
    Converte graus (0-360) em pontos cardeais (Norte, Sul, Este, Oeste).
    
    Conversão:
    - Norte: 315-45° (ou seja, -45° a 45°)
    - Este: 45-135°
    - Sul: 135-225°
    - Oeste: 225-315°
    
    Args:
        degrees (float): Direção em graus (0-360, onde 0 = Norte)
        
    Returns:
        str: Ponto cardeal ("Norte", "Sul", "Este", "Oeste")
    """
    # Normalizar para 0-360
    degrees = float(degrees) % 360.0
    
    # Converter para pontos cardeais
    if degrees >= 315 or degrees < 45:
        return "Norte"
    elif degrees >= 45 and degrees < 135:
        return "Este"
    elif degrees >= 135 and degrees < 225:
        return "Sul"
    else:  # 225 <= degrees < 315
        return "Oeste"

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
        self.telemetry_interval = 5  # Intervalo padrão em segundos (telemetria a cada 5 segundos)
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
        
        A Nave-Mãe responderá enviando a missão através do MissionLink, que será recebida
        pelo recvMissionLink() que está a correr numa thread separada.
        
        Args:
            ip (str): Endereço IP da Nave-Mãe
            
        Returns:
            bool: True se o pedido foi enviado com sucesso, False caso contrário
        """
        # Delay maior para garantir que a Nave-Mãe está pronta e evitar conflitos
        time.sleep(1.0)
        
        # Enviar solicitação de missão com retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Enviar apenas o pedido - a resposta virá através do recvMissionLink()
                self.missionLink.send(ip, self.missionLink.port, self.missionLink.requestMission, self.id, "000", "request")
                return True
            except TimeoutError as e:
                if attempt < max_retries - 1:
                    print(f"[INFO] Tentativa {attempt + 1}/{max_retries} falhou, a tentar novamente...")
                    time.sleep(2)  # Delay maior entre tentativas
                    continue
                else:
                    print(f"[ERRO] requestMission: Timeout após {max_retries} tentativas: {e}")
                    return False
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[INFO] Tentativa {attempt + 1}/{max_retries} falhou: {e}, a tentar novamente...")
                    time.sleep(2)  # Delay maior entre tentativas
                    continue
                else:
                    print(f"[ERRO] requestMission: Erro ao solicitar missão após {max_retries} tentativas: {e}")
                    return False
        
        return False

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
        print(f"[DEBUG] recvMissionLink: Aguardando mensagem...")
        lista = self.missionLink.recv()
        print(f"[DEBUG] recvMissionLink: Mensagem recebida - missionType={lista[2]}, idMission={lista[1]}, idAgent={lista[0]}")
        
        if lista[2] == self.missionLink.taskRequest:
            print(f"[DEBUG] recvMissionLink: É uma missão (taskRequest), processando...")
            mission_message = lista[3]
            mission_id = lista[1]
            
            # Validar formato da missão
            print(f"[DEBUG] recvMissionLink: Validando missão {mission_id}...")
            print(f"[DEBUG] recvMissionLink: Tipo da mensagem: {type(mission_message)}, tamanho: {len(str(mission_message))} bytes")
            is_valid, error_msg = validateMission(mission_message)
            print(f"[DEBUG] recvMissionLink: Validação resultado: válida={is_valid}, erro={error_msg if not is_valid else 'N/A'}")
            
            if not is_valid:
                print(f"[DEBUG] recvMissionLink: Missão inválida, enviando resposta 'invalid'")
                self.missionLink.send(lista[4], self.missionLink.port, None, self.id, mission_id, "invalid")
                return None
            
            # Parse do JSON da missão
            try:
                if isinstance(mission_message, str):
                    print(f"[DEBUG] recvMissionLink: Fazendo parse do JSON (string)")
                    mission_data = json.loads(mission_message)
                else:
                    print(f"[DEBUG] recvMissionLink: Mensagem já é dicionário")
                    mission_data = mission_message
                print(f"[DEBUG] recvMissionLink: Parse bem-sucedido - mission_id={mission_data.get('mission_id', 'N/A')}, rover_id={mission_data.get('rover_id', 'N/A')}, task={mission_data.get('task', 'N/A')}")
            except json.JSONDecodeError as e:
                print(f"[DEBUG] recvMissionLink: Erro ao fazer parse do JSON: {e}")
                self.missionLink.send(lista[4], self.missionLink.port, None, self.id, mission_id, "parse_error")
                return None
            
            # Armazenar missão validada
            self.tasks[mission_id] = mission_data
            print(f"[DEBUG] recvMissionLink: Missão {mission_id} armazenada, enviando confirmação...")
            
            # Enviar ACK de confirmação
            self.missionLink.send(lista[4], self.missionLink.port, None, self.id, mission_id, mission_id)
            print(f"[DEBUG] recvMissionLink: Confirmação enviada para {lista[4]}:{self.missionLink.port}")
            
            # Verificar se já há missão em execução
            if self.mission_executing:
                self.mission_queue.append(mission_data)
                print(f"[INFO] Missão {mission_id} adicionada à fila")
            else:
                self.mission_executing = True
                self.current_mission = mission_data
                print(f"[INFO] Missão ID: {mission_id} recebida - iniciando execução")
                
                # Reiniciar telemetria se estiver parada
                if not self.telemetry_running:
                    self.startContinuousTelemetry(self.serverAddress, interval_seconds=self.telemetry_interval)
                
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
        # Ficar "a caminho" até entrar nas coordenadas da missão (máximo 1-3 mensagens de telemetria)
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
        
        # Função auxiliar para verificar se está dentro da área da missão
        def is_inside_area(x, y):
            return x1 <= x <= x2 and y1 <= y <= y2
        
        # Verificar se já está dentro da área
        already_inside = is_inside_area(current_x, current_y)
        
        # Ficar "a caminho" até entrar na área (máximo 1-3 mensagens de telemetria)
        num_telemetry_updates_en_route = random.randint(1, 3)
        prev_x = current_x
        prev_y = current_y
        telemetry_count = 0
        
        # Fase "a caminho" - mover até entrar na área ou atingir máximo de mensagens
        while not already_inside and telemetry_count < num_telemetry_updates_en_route:
            if distance > 0.1:
                # Mover gradualmente em direção ao centro
                progress = min(1.0, (telemetry_count + 1) / max(3, num_telemetry_updates_en_route))
                target_x = current_x + dx * progress
                target_y = current_y + dy * progress
                
                # Mudanças incrementais variadas (2 a 5 valores)
                step_x = random.choice([-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5]) if abs(target_x - prev_x) > 1 else 0
                step_y = random.choice([-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5]) if abs(target_y - prev_y) > 1 else 0
                
                new_x = prev_x + step_x
                new_y = prev_y + step_y
                
                # Garantir que não ultrapassa o destino
                if (dx > 0 and new_x > target_x) or (dx < 0 and new_x < target_x):
                    new_x = prev_x
                if (dy > 0 and new_y > target_y) or (dy < 0 and new_y < target_y):
                    new_y = prev_y
                
                # Garantir que entra na área se possível
                if not is_inside_area(new_x, new_y):
                    # Ajustar para entrar na área
                    if new_x < x1:
                        new_x = min(x1, prev_x + 5)
                    elif new_x > x2:
                        new_x = max(x2, prev_x - 5)
                    if new_y < y1:
                        new_y = min(y1, prev_y + 5)
                    elif new_y > y2:
                        new_y = max(y2, prev_y - 5)
                    
                self.updatePosition(new_x, new_y, 0.0)
                prev_x = new_x
                prev_y = new_y
                
                # Verificar se entrou na área
                already_inside = is_inside_area(new_x, new_y)
            
            telemetry_count += 1
            
            # Aguardar intervalo de telemetria (5 segundos) para enviar mensagens
            if not already_inside and telemetry_count < num_telemetry_updates_en_route:
                time.sleep(5.0)  # Intervalo de telemetria
        
        # Se ainda não está dentro, continuar movimento até entrar
        while not already_inside:
            if distance > 0.1:
                # Mover diretamente para dentro da área
                # Calcular ponto dentro da área mais próximo
                target_x = max(x1, min(x2, prev_x + (center_x - prev_x) * 0.3))
                target_y = max(y1, min(y2, prev_y + (center_y - prev_y) * 0.3))
                
                step_x = random.choice([-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5]) if abs(target_x - prev_x) > 1 else 0
                step_y = random.choice([-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5]) if abs(target_y - prev_y) > 1 else 0
                
                new_x = prev_x + step_x
                new_y = prev_y + step_y
                
                # Garantir que entra na área
                if new_x < x1:
                    new_x = x1 + random.randint(0, 5)
                elif new_x > x2:
                    new_x = x2 - random.randint(0, 5)
                if new_y < y1:
                    new_y = y1 + random.randint(0, 5)
                elif new_y > y2:
                    new_y = y2 - random.randint(0, 5)
                
                # Garantir que está dentro
                new_x = max(x1, min(x2, new_x))
                new_y = max(y1, min(y2, new_y))
                
                self.updatePosition(new_x, new_y, 0.0)
                prev_x = new_x
                prev_y = new_y
                
                # Verificar se entrou na área
                already_inside = is_inside_area(new_x, new_y)
            
            time.sleep(0.5)  # Pequeno delay para simular movimento
        
        # Mudar para "em missão" apenas quando já está dentro das coordenadas
        self.updateOperationalStatus("em missão")
        self.updateVelocity(2.0)  # Velocidade reduzida durante execução
        
        # Calcular duração total em segundos
        total_duration_seconds = float(duration_minutes) * 60.0
        update_interval_seconds = 5  # Intervalo fixo de 5 segundos (mesmo da telemetria contínua)
        
        # Executar missão com atualizações periódicas de posição e estado
        # A telemetria contínua (5s) continua a correr em paralelo
        start_time = time.time()
        
        # Padrão de movimento dentro da área (exploração em grid)
        grid_steps_x = 5
        grid_steps_y = 5
        step_size_x = (x2 - x1) / grid_steps_x
        step_size_y = (y2 - y1) / grid_steps_y
        
        # Valores anteriores para mudanças incrementais pequenas
        prev_x = self.position["x"]
        prev_y = self.position["y"]
        prev_battery = self.battery
        prev_temperature = self.temperature
        
        # Loop baseado em tempo real, não em número de iterações
        update_idx = 0
        while True:
            elapsed_time = time.time() - start_time
            
            # Verificar se a missão já terminou
            if elapsed_time >= total_duration_seconds:
                break
            
            progress_percent = min(100, int((elapsed_time / total_duration_seconds) * 100))
            
            # Calcular posição atual na área (movimento em grid)
            grid_x = (update_idx % grid_steps_x)
            grid_y = (update_idx // grid_steps_x) % grid_steps_y
            
            target_x = x1 + grid_x * step_size_x
            target_y = y1 + grid_y * step_size_y
            
            # Garantir que está dentro dos limites
            target_x = max(x1, min(x2, target_x))
            target_y = max(y1, min(y2, target_y))
            
            # Atualizar posição com mudanças variadas (2 a 5 valores)
            if abs(target_x - prev_x) > 0.1:
                step_x = random.choice([-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5])  # Mudança variada
                new_x = prev_x + step_x
                new_x = max(x1, min(x2, new_x))  # Garantir dentro dos limites
            else:
                new_x = prev_x
                
            if abs(target_y - prev_y) > 0.1:
                step_y = random.choice([-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5])  # Mudança variada
                new_y = prev_y + step_y
                new_y = max(y1, min(y2, new_y))  # Garantir dentro dos limites
            else:
                new_y = prev_y
            
            self.updatePosition(new_x, new_y, 0.0)
            prev_x = new_x
            prev_y = new_y
            
            # Atualizar bateria com mudanças muito pequenas (0% ou 0.2%)
            battery_change = random.choice([0.0, -0.2])  # Diminui muito lentamente
            new_battery = max(20.0, prev_battery + battery_change)
            self.updateBattery(new_battery)
            prev_battery = new_battery
            
            # Atualizar temperatura com mudanças pequenas (0.1°C ou 0.2°C)
            temp_change = random.choice([0.0, 0.1, 0.2])  # Aumenta muito lentamente
            new_temperature = min(35.0, prev_temperature + temp_change)
            self.updateTemperature(new_temperature)
            prev_temperature = new_temperature
            
            # NÃO enviar telemetria aqui - a telemetria contínua (5s) já faz isso
            
            # Incrementar índice para cálculo de grid
            update_idx += 1
            
            # Calcular quanto tempo falta até a próxima atualização
            next_update_time = start_time + (update_idx * update_interval_seconds)
            sleep_time = max(0.1, next_update_time - time.time())
            
            # Aguardar até próxima atualização (intervalo fixo de 5s)
            if sleep_time > 0:
                time.sleep(min(sleep_time, update_interval_seconds))
        
        # Enviar telemetria final antes de concluir missão
        self.createAndSendTelemetry(server_ip)
        
        # Reportar progresso de conclusão da missão ao servidor (com retry)
        # Pequeno delay antes de reportar para evitar conflitos com outras operações
        time.sleep(0.5)
        max_retries = 3
        progress_reported = False
        for retry in range(max_retries):
            try:
                progress_data = {
                    "mission_id": mission_id,
                    "status": "completed",
                    "progress_percent": 100,
                    "current_position": {
                        "x": self.position["x"],
                        "y": self.position["y"],
                        "z": self.position["z"]
                    }
                }
                progress_json = json.dumps(progress_data)
                self.missionLink.send(server_ip, self.missionLink.port, self.missionLink.reportProgress, self.id, mission_id, progress_json)
                progress_reported = True
                break
            except Exception as e:
                if retry < max_retries - 1:
                    print(f"[INFO] Tentativa {retry + 1}/{max_retries} de reportar conclusão falhou, a tentar novamente...")
                    time.sleep(2)  # Delay maior entre tentativas
                else:
                    print(f"[ERRO] Erro ao reportar conclusão da missão após {max_retries} tentativas: {e}")
        
        # Atualizar estado para "parado"
        self.updateOperationalStatus("parado")
        self.updateVelocity(0.0)
        
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
            else:
                # Não há mais missões na fila local - solicitar próxima missão à Nave-Mãe
                # A telemetria contínua continua rodando indefinidamente (não deve ser parada)
                
                print(f"[INFO] Missão concluída - solicitando próxima missão à Nave-Mãe")
                try:
                    # Enviar pedido de missão - a resposta virá através do recvMissionLink()
                    request_sent = self.requestMission(server_ip)
                    if request_sent:
                        print(f"[INFO] Pedido de missão enviado - aguardando resposta da Nave-Mãe")
                        # A missão será recebida pelo recvMissionLink() e iniciada automaticamente
                    else:
                        # Não foi possível enviar o pedido
                        print(f"[INFO] Não foi possível solicitar próxima missão")
                except Exception as e:
                    print(f"[ERRO] Erro ao solicitar próxima missão: {e}")

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
        telemetry["direction"] = degreesToCardinalDirection(self.direction)
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
    
    def startContinuousTelemetry(self, server_ip, interval_seconds=5):
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

    