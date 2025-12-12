"""
API de Observação para a Nave-Mãe

Implementa uma API REST HTTP para disponibilizar informação sobre missões e estado dos rovers.
Permite consulta em tempo real ou próximo do tempo real do estado atual do sistema.

Requisitos do PDF:
- Lista de rovers ativos e respetivo estado atual
- Lista de missões (ativas e concluídas), incluindo parâmetros principais
- Últimos dados de telemetria recebidos pela Nave-Mãe

Formato: JSON
Protocolo: HTTP REST
Porta padrão: 8082
"""

try:
    from flask import Flask, jsonify, request  # type: ignore
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    # Stubs para evitar erros de sintaxe quando Flask não está instalado
    class Flask:  # type: ignore
        def __init__(self, *args, **kwargs): pass
        def route(self, *args, **kwargs): return lambda f: f
        def run(self, *args, **kwargs): pass
    def jsonify(*args, **kwargs): return {}  # type: ignore
    class request:  # type: ignore
        class args:
            @staticmethod
            def get(key, default=None): return default

import json
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional

class ObservationAPI:
    """
    API de Observação para a Nave-Mãe.
    Expõe endpoints REST para consulta de estado do sistema.
    """
    
    def __init__(self, nms_server, host='0.0.0.0', port=8082):
        """
        Inicializa a API de Observação.
        
        Args:
            nms_server (NMS_Server): Instância do servidor NMS para aceder aos dados
            host (str, optional): Endereço IP para escutar. Defaults to '0.0.0.0' (todas as interfaces)
            port (int, optional): Porta para escutar. Defaults to 8082
            
        Raises:
            ImportError: Se Flask não estiver instalado
        """
        if not FLASK_AVAILABLE:
            raise ImportError(
                "Flask não está instalado. Instale com: pip install flask\n"
                "Ou instale todas as dependências: pip install -r requirements.txt"
            )
        
        self.nms_server = nms_server
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self._setup_routes()
        self._api_thread = None
        self._running = False
    
    def _setup_routes(self):
        """
        Configura as rotas da API REST.
        """
        # Rota raiz - informação da API
        @self.app.route('/', methods=['GET'])
        def root():
            """Informação sobre a API de Observação."""
            return jsonify({
                "api": "NMS Observation API",
                "version": "1.0",
                "status": "online",
                "description": "API de Observação da Nave-Mãe para consulta de estado do sistema",
                "endpoints": {
                    "/rovers": "Lista de rovers ativos e respetivo estado",
                    "/rovers/<rover_id>": "Estado detalhado de um rover específico",
                    "/missions": "Lista de missões (ativas e concluídas)",
                    "/missions/<mission_id>": "Detalhes de uma missão específica",
                    "/telemetry": "Últimos dados de telemetria recebidos",
                    "/telemetry/<rover_id>": "Últimos dados de telemetria de um rover específico",
                    "/status": "Estado geral do sistema"
                }
            }), 200
        
        # Endpoint de health check
        @self.app.route('/health', methods=['GET'])
        def health():
            """Health check endpoint para verificar se a API está a funcionar."""
            return jsonify({
                "status": "healthy",
                "api": "NMS Observation API",
                "timestamp": datetime.now().isoformat()
            }), 200
        
        # Lista de rovers ativos
        @self.app.route('/rovers', methods=['GET'])
        def get_rovers():
            """
            Retorna lista de rovers ativos e respetivo estado atual.
            
            Returns:
                JSON com lista de rovers:
                {
                    "rovers": [
                        {
                            "rover_id": "r1",
                            "ip": "10.0.3.10",
                            "status": "active",
                            "last_seen": "2024-01-01T12:00:00",
                            "current_mission": "M-001" ou null
                        }
                    ]
                }
            """
            rovers = []
            for rover_id, ip in self.nms_server.agents.items():
                rover_info = {
                    "rover_id": rover_id,
                    "ip": ip,
                    "status": "active",  # Rovers registados são considerados ativos
                    "last_seen": self._get_last_telemetry_time(rover_id),
                    "current_mission": self._get_current_mission(rover_id)
                }
                rovers.append(rover_info)
            
            return jsonify({"rovers": rovers}), 200
        
        # Estado detalhado de um rover específico
        @self.app.route('/rovers/<rover_id>', methods=['GET'])
        def get_rover(rover_id):
            """
            Retorna estado detalhado de um rover específico.
            
            Args:
                rover_id (str): ID do rover
                
            Returns:
                JSON com estado detalhado do rover ou 404 se não encontrado
            """
            if rover_id not in self.nms_server.agents:
                return jsonify({"error": f"Rover {rover_id} não encontrado"}), 404
            
            ip = self.nms_server.agents[rover_id]
            latest_telemetry = self._get_latest_telemetry(rover_id)
            current_mission = self._get_current_mission(rover_id)
            mission_progress = self._get_mission_progress(rover_id, current_mission)
            
            rover_data = {
                "rover_id": rover_id,
                "ip": ip,
                "status": "active",
                "last_seen": self._get_last_telemetry_time(rover_id),
                "current_mission": current_mission,
                "mission_progress": mission_progress,
                "latest_telemetry": latest_telemetry
            }
            
            return jsonify(rover_data), 200
        
        # Lista de missões
        @self.app.route('/missions', methods=['GET'])
        def get_missions():
            """
            Retorna lista de missões (ativas e concluídas), incluindo parâmetros principais.
            
            Query parameters:
                - status: Filtrar por status (active, completed, pending). Se não especificado, retorna todas.
            
            Returns:
                JSON com lista de missões:
                {
                    "missions": [
                        {
                            "mission_id": "M-001",
                            "rover_id": "r1",
                            "task": "capture_images",
                            "status": "active",
                            "geographic_area": {...},
                            "duration_minutes": 30,
                            "progress": {...}
                        }
                    ]
                }
            """
            status_filter = request.args.get('status', None)
            missions = []
            
            # Missões em self.tasks (podem estar ativas ou na fila)
            # Lista de missões concluídas para remover de tasks
            completed_missions_to_remove = []
            
            for mission_id, mission_data in self.nms_server.tasks.items():
                mission_info = self._format_mission(mission_id, mission_data)
                
                # Verificar adicionalmente se a missão está realmente concluída
                # Se o status já foi marcado como "completed" em _format_mission, remover de tasks
                if mission_info["status"] == "completed":
                    completed_missions_to_remove.append(mission_id)
                
                # Só mostrar como "active" se realmente estiver em execução
                # Missões na fila aparecem como "pending"
                # Se filtro é "active", excluir missões concluídas
                if status_filter is None or mission_info["status"] == status_filter:
                    missions.append(mission_info)
            
            # Remover missões concluídas de tasks para não aparecerem mais como ativas
            for mission_id in completed_missions_to_remove:
                if mission_id in self.nms_server.tasks:
                    del self.nms_server.tasks[mission_id]
            
            # Missões pendentes
            for mission_data in self.nms_server.pendingMissions:
                if isinstance(mission_data, str):
                    try:
                        mission_data = json.loads(mission_data)
                    except:
                        continue
                
                mission_id = mission_data.get("mission_id", "unknown")
                mission_info = self._format_mission(mission_id, mission_data)
                mission_info["status"] = "pending"
                
                if status_filter is None or mission_info["status"] == status_filter:
                    missions.append(mission_info)
            
            return jsonify({"missions": missions}), 200
        
        # Detalhes de uma missão específica
        @self.app.route('/missions/<mission_id>', methods=['GET'])
        def get_mission(mission_id):
            """
            Retorna detalhes completos de uma missão específica.
            
            Args:
                mission_id (str): ID da missão
                
            Returns:
                JSON com detalhes da missão ou 404 se não encontrada
            """
            # Procurar em missões ativas
            if mission_id in self.nms_server.tasks:
                mission_data = self.nms_server.tasks[mission_id]
                if isinstance(mission_data, str):
                    try:
                        mission_data = json.loads(mission_data)
                    except:
                        return jsonify({"error": "Erro ao fazer parse da missão"}), 500
                
                mission_info = self._format_mission(mission_id, mission_data)
                mission_info["progress"] = self.nms_server.missionProgress.get(mission_id, {})
                return jsonify(mission_info), 200
            
            # Procurar em missões pendentes
            for mission_data in self.nms_server.pendingMissions:
                if isinstance(mission_data, str):
                    try:
                        mission_data = json.loads(mission_data)
                    except:
                        continue
                
                if mission_data.get("mission_id") == mission_id:
                    mission_info = self._format_mission(mission_id, mission_data)
                    mission_info["status"] = "pending"
                    return jsonify(mission_info), 200
            
            return jsonify({"error": f"Missão {mission_id} não encontrada"}), 404
        
        # Últimos dados de telemetria
        @self.app.route('/telemetry', methods=['GET'])
        def get_telemetry():
            """
            Retorna últimos dados de telemetria recebidos pela Nave-Mãe.
            
            Query parameters:
                - limit: Número máximo de registos a retornar (default: 10)
                - rover_id: Filtrar por rover específico (opcional)
            
            Returns:
                JSON com lista de dados de telemetria:
                {
                    "telemetry": [
                        {
                            "rover_id": "r1",
                            "timestamp": "2024-01-01T12:00:00",
                            "position": {...},
                            "operational_status": "em missão",
                            "battery": 75.0,
                            ...
                        }
                    ]
                }
            """
            limit = int(request.args.get('limit', 10))
            rover_filter = request.args.get('rover_id', None)
            
            telemetry_data = self._get_telemetry_data(limit, rover_filter)
            
            # Criar resposta sem cache
            response = jsonify({"telemetry": telemetry_data})
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response, 200
        
        # Últimos dados de telemetria de um rover específico
        @self.app.route('/telemetry/<rover_id>', methods=['GET'])
        def get_rover_telemetry(rover_id):
            """
            Retorna últimos dados de telemetria de um rover específico.
            
            Args:
                rover_id (str): ID do rover
                
            Query parameters:
                - limit: Número máximo de registos a retornar (default: 10)
            
            Returns:
                JSON com lista de dados de telemetria do rover ou 404 se não encontrado
            """
            if rover_id not in self.nms_server.agents:
                return jsonify({"error": f"Rover {rover_id} não encontrado"}), 404
            
            limit = int(request.args.get('limit', 10))
            telemetry_data = self._get_telemetry_data(limit, rover_id)
            
            return jsonify({"rover_id": rover_id, "telemetry": telemetry_data}), 200
        
        # Estado geral do sistema
        @self.app.route('/status', methods=['GET'])
        def get_status():
            """
            Retorna estado geral do sistema.
            
            Returns:
                JSON com estatísticas gerais:
                {
                    "total_rovers": 3,
                    "active_rovers": 3,
                    "total_missions": 5,
                    "active_missions": 2,
                    "pending_missions": 1,
                    "completed_missions": 2
                }
            """
            total_rovers = len(self.nms_server.agents)
            active_missions = len(self.nms_server.tasks)
            pending_missions = len(self.nms_server.pendingMissions)
            
            # Contar missões concluídas (missões com progresso "completed")
            completed_missions = 0
            for mission_id, progress in self.nms_server.missionProgress.items():
                if isinstance(progress, dict):
                    for rover_id, rover_progress in progress.items():
                        if isinstance(rover_progress, dict) and rover_progress.get("status") == "completed":
                            completed_missions += 1
                            break
            
            status = {
                "total_rovers": total_rovers,
                "active_rovers": total_rovers,  # Rovers registados são considerados ativos
                "total_missions": active_missions + pending_missions + completed_missions,
                "active_missions": active_missions,
                "pending_missions": pending_missions,
                "completed_missions": completed_missions,
                "timestamp": datetime.now().isoformat()
            }
            
            return jsonify(status), 200
    
    def _format_mission(self, mission_id: str, mission_data: dict) -> dict:
        """
        Formata dados de uma missão para resposta da API.
        
        Args:
            mission_id (str): ID da missão
            mission_data (dict): Dados da missão
            
        Returns:
            dict: Dados formatados da missão
        """
        if isinstance(mission_data, str):
            try:
                mission_data = json.loads(mission_data)
            except:
                mission_data = {}
        
        # Determinar status da missão
        rover_id = mission_data.get("rover_id", "unknown")
        
        # Verificar primeiro se está concluída
        status = "active"  # Default
        
        # Verificar se há progresso marcado como "completed"
        if mission_id in self.nms_server.missionProgress:
            progress = self.nms_server.missionProgress[mission_id]
            if isinstance(progress, dict):
                for rover_progress in progress.values():
                    if isinstance(rover_progress, dict):
                        progress_status = rover_progress.get("status", "")
                        if progress_status == "completed":
                            status = "completed"
                            break
                        elif progress_status == "in_progress":
                            # Esta missão está realmente em execução
                            status = "active"
                            break
        
        # Se não tem progresso marcado como "completed" ou "in_progress",
        # verificar telemetria e outras missões para determinar se está concluída
        if status == "active":
            latest_telemetry = self._get_latest_telemetry(rover_id)
            if latest_telemetry:
                operational_status = latest_telemetry.get("operational_status", "")
                # Se o rover está "parado" e não há progresso ativo, a missão foi concluída
                if operational_status == "parado":
                    # Verificar se realmente não há progresso ativo
                    has_active_progress = False
                    if mission_id in self.nms_server.missionProgress:
                        progress = self.nms_server.missionProgress[mission_id]
                        if isinstance(progress, dict) and rover_id in progress:
                            rover_progress = progress[rover_id]
                            if isinstance(rover_progress, dict):
                                progress_status = rover_progress.get("status", "")
                                if progress_status == "in_progress":
                                    has_active_progress = True
                    
                    if not has_active_progress:
                        # Missão concluída - marcar como completed
                        status = "completed"
                # Se o rover está "em missão" ou "a caminho", verificar se há outra missão mais recente
                elif operational_status in ["em missão", "a caminho"]:
                    # Verificar se há outra missão mais recente para este rover que está realmente em execução
                    for other_id, other_data in self.nms_server.tasks.items():
                        if other_id != mission_id:
                            if isinstance(other_data, str):
                                try:
                                    other_data = json.loads(other_data)
                                except:
                                    continue
                            if other_data.get("rover_id") == rover_id:
                                # Se há outra missão mais recente (ordem alfabética), esta pode estar concluída
                                if other_id > mission_id:
                                    # Verificar se a outra missão tem progresso ativo
                                    other_has_progress = False
                                    if other_id in self.nms_server.missionProgress:
                                        other_progress = self.nms_server.missionProgress[other_id]
                                        if isinstance(other_progress, dict) and rover_id in other_progress:
                                            other_rover_progress = other_progress[rover_id]
                                            if isinstance(other_rover_progress, dict):
                                                other_status = other_rover_progress.get("status", "")
                                                if other_status == "in_progress":
                                                    other_has_progress = True
                                    
                                    # Se a outra missão mais recente está ativa, esta missão antiga está concluída
                                    if other_has_progress or other_id not in self.nms_server.missionProgress:
                                        status = "completed"
                                        break
        
        # Se não tem progresso "in_progress" e há outra missão do mesmo rover com progresso,
        # esta missão está na fila (pending)
        if status == "active" and mission_id not in self.nms_server.missionProgress:
            # Verificar se há outra missão do mesmo rover com progresso "in_progress"
            for other_id, other_data in self.nms_server.tasks.items():
                if other_id != mission_id:
                    if isinstance(other_data, str):
                        try:
                            other_data = json.loads(other_data)
                        except:
                            continue
                    if other_data.get("rover_id") == rover_id:
                        if other_id in self.nms_server.missionProgress:
                            other_progress = self.nms_server.missionProgress[other_id]
                            if isinstance(other_progress, dict):
                                for rover_progress in other_progress.values():
                                    if isinstance(rover_progress, dict):
                                        if rover_progress.get("status") == "in_progress":
                                            # Há outra missão em execução, esta está na fila
                                            status = "pending"
                                            break
                                if status == "pending":
                                    break
        
        mission_info = {
            "mission_id": mission_id,
            "rover_id": mission_data.get("rover_id", "unknown"),
            "task": mission_data.get("task", "unknown"),
            "status": status,
            "geographic_area": mission_data.get("geographic_area", {}),
            "duration_minutes": mission_data.get("duration_minutes", 0)
        }
        
        # Adicionar campos opcionais se existirem
        if "instructions" in mission_data:
            mission_info["instructions"] = mission_data["instructions"]
        
        return mission_info
    
    def _get_current_mission(self, rover_id: str) -> Optional[str]:
        """
        Obtém a missão atual de um rover (a que está realmente em execução).
        
        Como não há mais reporte de progresso via MissionLink, determina a missão atual
        verificando se há missões ativas em tasks para o rover e se a telemetria indica
        que está "em missão".
        
        Args:
            rover_id (str): ID do rover
            
        Returns:
            str or None: ID da missão atual ou None se não houver
        """
        # Procurar missão ativa em tasks para este rover
        # Coletar todas as missões válidas primeiro e ordenar por mission_id (mais recente primeiro)
        valid_missions = []
        
        for mission_id, mission_data in self.nms_server.tasks.items():
            if isinstance(mission_data, str):
                try:
                    mission_data = json.loads(mission_data)
                except:
                    continue
            
            if mission_data.get("rover_id") == rover_id:
                # Verificar se a missão não está concluída
                is_completed = False
                if mission_id in self.nms_server.missionProgress:
                    progress = self.nms_server.missionProgress[mission_id]
                    if isinstance(progress, dict) and rover_id in progress:
                        rover_progress = progress[rover_id]
                        if isinstance(rover_progress, dict):
                            status = rover_progress.get("status", "")
                            if status == "completed":
                                is_completed = True
                
                # Se não está concluída, adicionar à lista de candidatas
                if not is_completed:
                    valid_missions.append((mission_id, mission_data))
        
        # Ordenar por mission_id (ordem decrescente para pegar a mais recente)
        valid_missions.sort(key=lambda x: x[0], reverse=True)
        
        # Verificar telemetria para confirmar qual missão está realmente em execução
        latest_telemetry = self._get_latest_telemetry(rover_id)
        if latest_telemetry:
            operational_status = latest_telemetry.get("operational_status", "")
            # Se está "em missão" ou "a caminho", retornar a missão mais recente
            if operational_status in ["em missão", "a caminho"]:
                if valid_missions:
                    return valid_missions[0][0]  # Retornar a missão mais recente
        else:
            # Se não há telemetria mas há missões válidas, retornar a mais recente
            if valid_missions:
                return valid_missions[0][0]
        
        return None
    
    def _get_mission_progress(self, rover_id: str, mission_id: Optional[str]) -> Optional[dict]:
        """
        Obtém progresso da missão atual de um rover.
        
        Args:
            rover_id (str): ID do rover
            mission_id (str or None): ID da missão
            
        Returns:
            dict or None: Dados de progresso ou None
        """
        if mission_id is None:
            return None
        
        progress = self.nms_server.missionProgress.get(mission_id, {})
        if isinstance(progress, dict):
            return progress.get(rover_id)
        
        return None
    
    def _get_latest_telemetry(self, rover_id: str) -> Optional[dict]:
        """
        Obtém os últimos dados de telemetria de um rover.
        
        Args:
            rover_id (str): ID do rover
            
        Returns:
            dict or None: Últimos dados de telemetria ou None
        """
        telemetry_folder = self.nms_server.telemetryStream.storefolder
        rover_folder = os.path.join(telemetry_folder, rover_id)
        
        if not os.path.exists(rover_folder):
            return None
        
        # Procurar ficheiro mais recente
        try:
            files = [f for f in os.listdir(rover_folder) if f.endswith('.json')]
            if not files:
                return None
            
            # Ordenar por data de modificação (mais recente primeiro)
            files.sort(key=lambda x: os.path.getmtime(os.path.join(rover_folder, x)), reverse=True)
            latest_file = os.path.join(rover_folder, files[0])
            
            with open(latest_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Erro ao ler telemetria de {rover_id}: {e}")
            return None
    
    def _get_telemetry_data(self, limit: int, rover_filter: Optional[str] = None, max_age_minutes: int = 5) -> List[dict]:
        """
        Obtém dados de telemetria (últimos N registos).
        
        Args:
            limit (int): Número máximo de registos
            rover_filter (str, optional): Filtrar por rover específico
            max_age_hours (int): Idade máxima em horas para considerar telemetria (default: 2 horas)
            
        Returns:
            list: Lista de dados de telemetria
        """
        # Limpar ficheiros antigos periodicamente (manter até 600 ficheiros por rover)
        self._cleanup_old_telemetry_files(max_files_per_rover=600)
        
        telemetry_folder = self.nms_server.telemetryStream.storefolder
        telemetry_data = []
        current_time = datetime.now().timestamp()
        max_age_seconds = max_age_minutes * 60  # Converter minutos para segundos
        
        # Se filtro por rover, procurar apenas na pasta desse rover
        if rover_filter:
            rover_folder = os.path.join(telemetry_folder, rover_filter)
            if os.path.exists(rover_folder):
                files = [os.path.join(rover_folder, f) for f in os.listdir(rover_folder) if f.endswith('.json')]
                # Ler TODOS os ficheiros primeiro (sem ordenação prévia)
                for file_path in files:
                    try:
                        file_mtime = os.path.getmtime(file_path)
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                            # Garantir que há timestamp (usar do JSON ou do ficheiro)
                            if "timestamp" not in data:
                                # Se não há timestamp no JSON, usar data de modificação do ficheiro
                                data["timestamp"] = datetime.fromtimestamp(file_mtime).isoformat()
                            
                            # Verificar idade do registo (filtrar por tempo)
                            timestamp_str = data.get("timestamp", "")
                            if timestamp_str:
                                try:
                                    if isinstance(timestamp_str, str):
                                        timestamp_clean = timestamp_str.replace('Z', '').replace('+00:00', '').split('+')[0]
                                        if '.' in timestamp_clean:
                                            parts = timestamp_clean.split('.')
                                            base = datetime.fromisoformat(parts[0])
                                            microseconds = int(parts[1][:6].ljust(6, '0')) if len(parts) > 1 else 0
                                            timestamp_dt = base.replace(microsecond=microseconds)
                                        else:
                                            timestamp_dt = datetime.fromisoformat(timestamp_clean)
                                        timestamp_ts = timestamp_dt.timestamp()
                                    else:
                                        timestamp_ts = float(timestamp_str)
                                    
                                    # Filtrar por idade (apenas registos das últimas X horas)
                                    age_seconds = current_time - timestamp_ts
                                    if age_seconds > max_age_seconds:
                                        continue  # Ignorar registos muito antigos
                                except Exception:
                                    # Se não conseguir parsear timestamp, usar file_mtime
                                    age_seconds = current_time - file_mtime
                                    if age_seconds > max_age_seconds:
                                        continue
                            else:
                                # Se não há timestamp, usar file_mtime
                                age_seconds = current_time - file_mtime
                                if age_seconds > max_age_seconds:
                                    continue
                            
                            # Garantir que rover_id está presente
                            if "rover_id" not in data and rover_filter:
                                data["rover_id"] = rover_filter
                            # Adicionar também o mtime como fallback para ordenação
                            data["_file_mtime"] = file_mtime
                            telemetry_data.append(data)
                    except Exception:
                        continue
        else:
            # Procurar em todas as pastas de rovers
            if os.path.exists(telemetry_folder):
                for rover_id in os.listdir(telemetry_folder):
                    rover_folder = os.path.join(telemetry_folder, rover_id)
                    if os.path.isdir(rover_folder):
                        files = [os.path.join(rover_folder, f) for f in os.listdir(rover_folder) if f.endswith('.json')]
                        # Ler TODOS os ficheiros primeiro (sem ordenação prévia)
                        for file_path in files:
                            try:
                                file_mtime = os.path.getmtime(file_path)
                                with open(file_path, 'r') as f:
                                    data = json.load(f)
                                    # Garantir que há timestamp (usar do JSON ou do ficheiro)
                                    if "timestamp" not in data:
                                        # Se não há timestamp no JSON, usar data de modificação do ficheiro
                                        data["timestamp"] = datetime.fromtimestamp(file_mtime).isoformat()
                                    
                                    # Verificar idade do registo (filtrar por tempo)
                                    timestamp_str = data.get("timestamp", "")
                                    if timestamp_str:
                                        try:
                                            if isinstance(timestamp_str, str):
                                                timestamp_clean = timestamp_str.replace('Z', '').replace('+00:00', '').split('+')[0]
                                                if '.' in timestamp_clean:
                                                    parts = timestamp_clean.split('.')
                                                    base = datetime.fromisoformat(parts[0])
                                                    microseconds = int(parts[1][:6].ljust(6, '0')) if len(parts) > 1 else 0
                                                    timestamp_dt = base.replace(microsecond=microseconds)
                                                else:
                                                    timestamp_dt = datetime.fromisoformat(timestamp_clean)
                                                timestamp_ts = timestamp_dt.timestamp()
                                            else:
                                                timestamp_ts = float(timestamp_str)
                                            
                                            # Filtrar por idade (apenas registos das últimas X horas)
                                            age_seconds = current_time - timestamp_ts
                                            if age_seconds > max_age_seconds:
                                                continue  # Ignorar registos muito antigos
                                        except Exception:
                                            # Se não conseguir parsear timestamp, usar file_mtime
                                            age_seconds = current_time - file_mtime
                                            if age_seconds > max_age_seconds:
                                                continue
                                    else:
                                        # Se não há timestamp, usar file_mtime
                                        age_seconds = current_time - file_mtime
                                        if age_seconds > max_age_seconds:
                                            continue
                                    
                                    # Garantir que rover_id está presente
                                    if "rover_id" not in data:
                                        data["rover_id"] = rover_id
                                    # Adicionar também o mtime como fallback para ordenação
                                    data["_file_mtime"] = file_mtime
                                    telemetry_data.append(data)
                            except Exception:
                                continue
        
        # Ordenar por timestamp (mais recente primeiro) e limitar
        # Usar timestamp do JSON se disponível, senão usar data de modificação do ficheiro
        def get_sort_key(entry):
            timestamp = entry.get("timestamp", "")
            file_mtime = entry.get("_file_mtime", 0)
            
            if timestamp:
                try:
                    # Tentar converter para datetime para ordenação correta
                    if isinstance(timestamp, str):
                        # Remover timezone se presente
                        timestamp_clean = timestamp.replace('Z', '').replace('+00:00', '').split('+')[0]
                        # Tentar parse ISO format
                        try:
                            # ISO format pode ter microsegundos: YYYY-MM-DDTHH:MM:SS.ffffff
                            if '.' in timestamp_clean:
                                # Tem microsegundos
                                parts = timestamp_clean.split('.')
                                base = datetime.fromisoformat(parts[0])
                                microseconds = int(parts[1][:6].ljust(6, '0')) if len(parts) > 1 else 0
                                dt = base.replace(microsecond=microseconds)
                            else:
                                dt = datetime.fromisoformat(timestamp_clean)
                            # Retornar como timestamp Unix para comparação consistente
                            return dt.timestamp()
                        except:
                            # Se falhar, tentar formatos alternativos
                            try:
                                dt = datetime.strptime(timestamp_clean, "%Y-%m-%dT%H:%M:%S")
                                return dt.timestamp()
                            except:
                                # Se tudo falhar, usar file_mtime como fallback
                                return file_mtime if file_mtime > 0 else 0
                    elif isinstance(timestamp, (int, float)):
                        # Se for número (Unix timestamp), usar diretamente
                        return float(timestamp)
                except Exception:
                    # Se falhar, usar file_mtime como fallback
                    return file_mtime if file_mtime > 0 else 0
            
            # Se não há timestamp, usar file_mtime ou datetime mínimo
            return file_mtime if file_mtime > 0 else datetime.min.timestamp()
        
        # Ordenar por timestamp (mais recente primeiro)
        telemetry_data.sort(key=get_sort_key, reverse=True)
        
        # Remover campo auxiliar antes de retornar
        for entry in telemetry_data:
            entry.pop("_file_mtime", None)
        
        # Retornar apenas os N mais recentes
        return telemetry_data[:limit]
    
    def _cleanup_old_telemetry_files(self, max_files_per_rover=600):
        """
        Remove ficheiros de telemetria antigos, mantendo apenas os N mais recentes por rover.
        Evita acumulação excessiva de ficheiros.
        
        Args:
            max_files_per_rover (int): Número máximo de ficheiros a manter por rover
        """
        telemetry_folder = self.nms_server.telemetryStream.storefolder
        
        if not os.path.exists(telemetry_folder):
            return
        
        try:
            # Processar cada pasta de rover
            for rover_id in os.listdir(telemetry_folder):
                rover_folder = os.path.join(telemetry_folder, rover_id)
                if not os.path.isdir(rover_folder):
                    continue
                
                # Obter todos os ficheiros JSON
                files = [os.path.join(rover_folder, f) for f in os.listdir(rover_folder) if f.endswith('.json')]
                
                if len(files) <= max_files_per_rover:
                    continue  # Não precisa limpar
                
                # Ordenar por data de modificação (mais recente primeiro)
                files.sort(key=os.path.getmtime, reverse=True)
                
                # Remover ficheiros antigos (manter apenas os N mais recentes)
                files_to_remove = files[max_files_per_rover:]
                for file_path in files_to_remove:
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
        except Exception:
            pass  # Ignorar erros na limpeza
    
    def _get_last_telemetry_time(self, rover_id: str) -> Optional[str]:
        """
        Obtém timestamp da última telemetria recebida de um rover.
        
        Args:
            rover_id (str): ID do rover
            
        Returns:
            str or None: Timestamp ISO ou None
        """
        latest = self._get_latest_telemetry(rover_id)
        if latest and "timestamp" in latest:
            return latest["timestamp"]
        
        # Tentar obter do ficheiro
        telemetry_folder = self.nms_server.telemetryStream.storefolder
        rover_folder = os.path.join(telemetry_folder, rover_id)
        
        if os.path.exists(rover_folder):
            try:
                files = [f for f in os.listdir(rover_folder) if f.endswith('.json')]
                if files:
                    files.sort(key=lambda x: os.path.getmtime(os.path.join(rover_folder, x)), reverse=True)
                    latest_file = os.path.join(rover_folder, files[0])
                    timestamp = os.path.getmtime(latest_file)
                    return datetime.fromtimestamp(timestamp).isoformat()
            except:
                pass
        
        return None
    
    def start(self):
        """
        Inicia o servidor da API em thread separada.
        """
        if self._running:
            print("API de Observação já está em execução")
            return
        
        self._running = True
        
        def run_api():
            """Função para executar o servidor Flask em thread separada."""
            try:
                print(f"[API] A iniciar API de Observação em http://{self.host}:{self.port}")
                # Desabilitar logs do Flask em produção (opcional)
                import logging
                log = logging.getLogger('werkzeug')
                log.setLevel(logging.ERROR)
                self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False, threaded=True)
            except Exception as e:
                print(f"[ERRO] Falha ao iniciar API de Observação: {e}")
                import traceback
                traceback.print_exc()
                self._running = False
        
        self._api_thread = threading.Thread(target=run_api, daemon=True)
        self._api_thread.start()
        
        # Aguardar um pouco para garantir que o servidor iniciou
        import time
        time.sleep(1)
        
        # Verificar se a thread está a correr
        if self._api_thread.is_alive():
            print(f"[OK] API de Observação iniciada em http://{self.host}:{self.port}")
            print(f"[INFO] Documentação disponível em http://{self.host}:{self.port}/")
        else:
            print("[AVISO] Thread da API pode não ter iniciado corretamente")
    
    def stop(self):
        """
        Para o servidor da API.
        """
        self._running = False
        # Flask não tem método stop() direto, mas como é daemon thread, termina com o programa principal
        print("API de Observação parada")

