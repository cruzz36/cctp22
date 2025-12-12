"""
Ground Control - Cliente da API de Observação

Este módulo implementa o nó Ground Control que atua como cliente da API de Observação
da Nave-Mãe, permitindo ao utilizador acompanhar a operação da missão em tempo real.

Funcionalidades:
- Visualização de rovers em operação e respetivo estado
- Visualização de missões atribuídas e seu progresso
- Visualização dos valores de telemetria mais recentes
- Atualização automática periódica
- Interface interativa em linha de comandos

Requisitos:
- requests: pip install requests
- API de Observação da Nave-Mãe a correr na porta 8082 (padrão)
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

try:
    import requests
except ImportError:
    print("ERRO: Biblioteca 'requests' não encontrada.")
    print("Instale com: pip install requests")
    sys.exit(1)


class GroundControl:
    """
    Cliente Ground Control para monitorização da Nave-Mãe.
    
    Consome a API de Observação e apresenta informação de forma legível
    sobre rovers, missões e telemetria.
    """
    
    def __init__(self, api_url: str = "http://localhost:8082"):
        """
        Inicializa o Ground Control.
        
        Args:
            api_url (str): URL base da API de Observação. Default: http://localhost:8082
        """
        self.api_url = api_url.rstrip('/')
        self.running = False
        self.update_interval = 5  # Segundos entre atualizações automáticas
        
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Faz uma requisição HTTP GET à API.
        
        Args:
            endpoint (str): Endpoint da API (ex: '/rovers')
            params (dict, optional): Parâmetros de query
            
        Returns:
            dict: Resposta JSON da API, ou None em caso de erro
        """
        try:
            url = f"{self.api_url}{endpoint}"
            # Adicionar timestamp para evitar cache
            if params is None:
                params = {}
            params['_'] = int(time.time() * 1000)  # Timestamp em milissegundos
            response = requests.get(url, params=params, timeout=5, headers={'Cache-Control': 'no-cache'})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as e:
            # Não imprimir erro aqui - deixar o chamador decidir
            return None
        except requests.exceptions.Timeout:
            return None
        except requests.exceptions.HTTPError as e:
            print(f"\n[ERRO] Erro HTTP {e.response.status_code}: {e}")
            return None
        except Exception as e:
            print(f"\n[ERRO] Erro inesperado: {e}")
            return None
    
    def _clear_screen(self):
        """Limpa o ecrã (compatível com Windows e Unix)."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def _format_timestamp(self, timestamp: Optional[str]) -> str:
        """
        Formata um timestamp ISO 8601 para formato legível.
        
        Args:
            timestamp (str, optional): Timestamp ISO 8601
            
        Returns:
            str: Timestamp formatado ou "N/A"
        """
        if not timestamp:
            return "N/A"
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return timestamp
    
    def _format_position(self, position: Optional[Dict]) -> str:
        """
        Formata uma posição para string legível.
        
        Args:
            position (dict, optional): Dicionário com x, y, z
            
        Returns:
            str: Posição formatada ou "N/A"
        """
        if not position:
            return "N/A"
        x = position.get('x', 0)
        y = position.get('y', 0)
        z = position.get('z', 0)
        return f"({x:.2f}, {y:.2f}, {z:.2f})"
    
    def show_status(self):
        """Mostra estado geral do sistema."""
        data = self._make_request('/status')
        if not data:
            return
        
        print("\n" + "="*60)
        print("ESTADO GERAL DO SISTEMA")
        print("="*60)
        print(f"Total de Rovers:        {data.get('total_rovers', 0)}")
        print(f"Rovers Ativos:          {data.get('active_rovers', 0)}")
        print(f"Total de Missões:       {data.get('total_missions', 0)}")
        print(f"Missões Ativas:          {data.get('active_missions', 0)}")
        print(f"Missões Pendentes:       {data.get('pending_missions', 0)}")
        print(f"Missões Concluídas:      {data.get('completed_missions', 0)}")
        print(f"Timestamp:               {self._format_timestamp(data.get('timestamp'))}")
        print("="*60)
    
    def show_rovers(self):
        """Mostra lista de rovers e respetivo estado."""
        data = self._make_request('/rovers')
        if not data:
            return
        
        rovers = data.get('rovers', [])
        
        print("\n" + "="*80)
        print("ROVERS EM OPERAÇÃO")
        print("="*80)
        
        if not rovers:
            print("Nenhum rover registado.")
            return
        
        for rover in rovers:
            rover_id = rover.get('rover_id', 'N/A')
            ip = rover.get('ip', 'N/A')
            status = rover.get('status', 'N/A')
            last_seen = self._format_timestamp(rover.get('last_seen'))
            current_mission = rover.get('current_mission', 'Nenhuma')
            
            print(f"\nRover ID: {rover_id}")
            print(f"  IP:              {ip}")
            print(f"  Estado:          {status}")
            print(f"  Última Atividade: {last_seen}")
            print(f"  Missão Atual:    {current_mission}")
        
        print("\n" + "="*80)
    
    def show_rover_details(self, rover_id: str):
        """
        Mostra detalhes completos de um rover específico.
        
        Args:
            rover_id (str): ID do rover
        """
        data = self._make_request(f'/rovers/{rover_id}')
        if not data:
            return
        
        if 'error' in data:
            print(f"\n[ERRO] {data['error']}")
            return
        
        print("\n" + "="*80)
        print(f"DETALHES DO ROVER: {rover_id}")
        print("="*80)
        
        print(f"\nInformação Básica:")
        print(f"  IP:              {data.get('ip', 'N/A')}")
        print(f"  Estado:          {data.get('status', 'N/A')}")
        print(f"  Última Atividade: {self._format_timestamp(data.get('last_seen'))}")
        print(f"  Missão Atual:    {data.get('current_mission', 'Nenhuma')}")
        
        # Progresso da missão
        mission_progress = data.get('mission_progress')
        if mission_progress:
            print(f"\nProgresso da Missão:")
            for rover_id_prog, progress in mission_progress.items():
                progress_percent = progress.get('progress_percent', 0)
                status = progress.get('status', 'N/A')
                position = self._format_position(progress.get('current_position'))
                print(f"  Progresso:      {progress_percent}%")
                print(f"  Estado:         {status}")
                print(f"  Posição Atual:  {position}")
        
        # Última telemetria
        latest_telemetry = data.get('latest_telemetry')
        if latest_telemetry:
            print(f"\nÚltima Telemetria:")
            self._print_telemetry_entry(latest_telemetry, indent="  ")
        else:
            print(f"\nÚltima Telemetria: Nenhuma disponível")
        
        print("\n" + "="*80)
    
    def show_missions(self, status_filter: Optional[str] = None):
        """
        Mostra lista de missões.
        
        Args:
            status_filter (str, optional): Filtrar por status (active, completed, pending)
        """
        params = {}
        if status_filter:
            params['status'] = status_filter
        
        data = self._make_request('/missions', params=params)
        if not data:
            return
        
        missions = data.get('missions', [])
        
        filter_text = f" ({status_filter})" if status_filter else ""
        print("\n" + "="*80)
        print(f"MISSÕES{filter_text.upper()}")
        print("="*80)
        
        if not missions:
            print("Nenhuma missão encontrada.")
            return
        
        for mission in missions:
            mission_id = mission.get('mission_id', 'N/A')
            rover_id = mission.get('rover_id', 'N/A')
            task = mission.get('task', 'N/A')
            status = mission.get('status', 'N/A')
            geo_area = mission.get('geographic_area', {})
            duration = mission.get('duration_minutes', 0)
            
            print(f"\nMissão ID: {mission_id}")
            print(f"  Rover:              {rover_id}")
            print(f"  Tarefa:             {task}")
            print(f"  Estado:             {status}")
            print(f"  Duração:            {duration} minutos")
            
            if geo_area:
                x1 = geo_area.get('x1', 0)
                y1 = geo_area.get('y1', 0)
                x2 = geo_area.get('x2', 0)
                y2 = geo_area.get('y2', 0)
                print(f"  Área Geográfica:    ({x1:.2f}, {y1:.2f}) a ({x2:.2f}, {y2:.2f})")
        
        print("\n" + "="*80)
    
    def show_mission_details(self, mission_id: str):
        """
        Mostra detalhes completos de uma missão específica.
        
        Args:
            mission_id (str): ID da missão
        """
        data = self._make_request(f'/missions/{mission_id}')
        if not data:
            return
        
        if 'error' in data:
            print(f"\n[ERRO] {data['error']}")
            return
        
        print("\n" + "="*80)
        print(f"DETALHES DA MISSÃO: {mission_id}")
        print("="*80)
        
        print(f"\nInformação Básica:")
        print(f"  Rover:              {data.get('rover_id', 'N/A')}")
        print(f"  Tarefa:             {data.get('task', 'N/A')}")
        print(f"  Estado:             {data.get('status', 'N/A')}")
        print(f"  Duração:            {data.get('duration_minutes', 0)} minutos")
        
        geo_area = data.get('geographic_area', {})
        if geo_area:
            x1 = geo_area.get('x1', 0)
            y1 = geo_area.get('y1', 0)
            x2 = geo_area.get('x2', 0)
            y2 = geo_area.get('y2', 0)
            print(f"  Área Geográfica:    ({x1:.2f}, {y1:.2f}) a ({x2:.2f}, {y2:.2f})")
        
        instructions = data.get('instructions')
        if instructions:
            print(f"  Instruções:          {instructions}")
        
        # Progresso
        progress = data.get('progress', {})
        if progress:
            print(f"\nProgresso:")
            for rover_id_prog, prog_data in progress.items():
                progress_percent = prog_data.get('progress_percent', 0)
                status = prog_data.get('status', 'N/A')
                position = self._format_position(prog_data.get('current_position'))
                time_elapsed = prog_data.get('time_elapsed_minutes')
                time_remaining = prog_data.get('estimated_completion_minutes')
                
                print(f"  Rover {rover_id_prog}:")
                print(f"    Progresso:      {progress_percent}%")
                print(f"    Estado:         {status}")
                print(f"    Posição Atual:  {position}")
                if time_elapsed is not None:
                    print(f"    Tempo Decorrido: {time_elapsed:.1f} minutos")
                if time_remaining is not None:
                    print(f"    Tempo Restante:  {time_remaining:.1f} minutos")
        else:
            print(f"\nProgresso: Nenhum disponível")
        
        print("\n" + "="*80)
    
    def _print_telemetry_entry(self, entry: Dict, indent: str = ""):
        """
        Imprime uma entrada de telemetria formatada.
        
        Args:
            entry (dict): Dados de telemetria
            indent (str): Indentação para formatação
        """
        print(f"{indent}Timestamp:           {self._format_timestamp(entry.get('timestamp'))}")
        
        position = entry.get('position')
        if position:
            print(f"{indent}Posição:              {self._format_position(position)}")
        
        print(f"{indent}Estado Operacional:   {entry.get('operational_status', 'N/A')}")
        
        battery = entry.get('battery')
        if battery is not None:
            print(f"{indent}Bateria:              {battery:.1f}%")
        
        velocity = entry.get('velocity')
        if velocity is not None:
            print(f"{indent}Velocidade:           {velocity:.2f} m/s")
        
        direction = entry.get('direction')
        if direction is not None:
            # Direção pode ser string (ponto cardeal) ou float (graus)
            if isinstance(direction, str):
                print(f"{indent}Direção:              {direction}")
            else:
                print(f"{indent}Direção:              {direction:.1f}°")
        
        temperature = entry.get('temperature')
        if temperature is not None:
            print(f"{indent}Temperatura:          {temperature:.1f}°C")
        
        system_health = entry.get('system_health')
        if system_health:
            print(f"{indent}Saúde do Sistema:    {system_health}")
        
        # Métricas técnicas
        cpu_usage = entry.get('cpu_usage')
        if cpu_usage is not None:
            print(f"{indent}CPU:                 {cpu_usage:.1f}%")
        
        ram_usage = entry.get('ram_usage')
        if ram_usage is not None:
            print(f"{indent}RAM:                 {ram_usage:.1f}%")
        
        latency = entry.get('latency')
        if latency:
            print(f"{indent}Latência:            {latency}")
        
        bandwidth = entry.get('bandwidth')
        if bandwidth:
            print(f"{indent}Largura de Banda:    {bandwidth}")
    
    def show_telemetry(self, rover_id: Optional[str] = None, limit: int = 10):
        """
        Mostra últimos dados de telemetria.
        
        Args:
            rover_id (str, optional): Filtrar por rover específico
            limit (int): Número máximo de registos (default: 10)
        """
        if rover_id:
            endpoint = f'/telemetry/{rover_id}'
            params = {'limit': limit}
        else:
            endpoint = '/telemetry'
            params = {'limit': limit}
            if rover_id:
                params['rover_id'] = rover_id
        
        data = self._make_request(endpoint, params=params)
        if not data:
            return
        
        if 'error' in data:
            print(f"\n[ERRO] {data['error']}")
            return
        
        telemetry = data.get('telemetry', [])
        
        title = f"TELEMETRIA{' - ' + rover_id if rover_id else ''}"
        print("\n" + "="*80)
        print(title)
        print("="*80)
        
        if not telemetry:
            print("Nenhum dado de telemetria disponível.")
            print("\n" + "="*80)
            return
        
        # Mostrar apenas as telemetrias que realmente existem (não sempre o limite máximo)
        num_entries = len(telemetry)
        print(f"Mostrando {num_entries} registo(s) de telemetria:")
        
        # Inverter ordem para mostrar mais recente primeiro (Registo 1 = mais recente, Registo N = mais antigo)
        # A API retorna ordenado do mais recente para o mais antigo, mas vamos inverter para garantir ordem correta
        telemetry_reversed = list(reversed(telemetry))
        
        for i, entry in enumerate(telemetry_reversed, 1):
            print(f"\n--- Registo {i} ---")
            self._print_telemetry_entry(entry)
        
        print("\n" + "="*80)
    
    def show_dashboard(self):
        """Mostra dashboard completo com todas as informações principais."""
        self._clear_screen()
        print("\n" + "="*80)
        print("GROUND CONTROL - DASHBOARD")
        print(f"Atualizado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        # Estado geral
        self.show_status()
        
        # Rovers
        self.show_rovers()
        
        # Missões ativas
        self.show_missions(status_filter='active')
        
        # Última telemetria (mostrar apenas as que existem, máximo 10)
        self.show_telemetry(limit=10)
    
    def run_interactive(self):
        """Executa interface interativa do Ground Control."""
        self.running = True
        
        print("\n" + "="*80)
        print("GROUND CONTROL - INTERFACE INTERATIVA")
        print("="*80)
        print("\nComandos disponíveis:")
        print("  1 - Dashboard completo")
        print("  2 - Listar rovers")
        print("  3 - Detalhes de um rover")
        print("  4 - Listar missões")
        print("  5 - Detalhes de uma missão")
        print("  6 - Telemetria (todos os rovers)")
        print("  7 - Telemetria de um rover específico")
        print("  8 - Estado geral do sistema")
        print("  9 - Atualização automática (dashboard)")
        print("  0 - Sair")
        print("="*80)
        
        while self.running:
            try:
                choice = input("\nEscolha uma opção: ").strip()
                
                if choice == '0':
                    print("\nA encerrar Ground Control...")
                    self.running = False
                    break
                
                elif choice == '1':
                    self.show_dashboard()
                
                elif choice == '2':
                    self.show_rovers()
                
                elif choice == '3':
                    rover_id = input("ID do rover: ").strip()
                    if rover_id:
                        self.show_rover_details(rover_id)
                    else:
                        print("[ERRO] ID do rover não pode estar vazio.")
                
                elif choice == '4':
                    print("\nFiltrar por status? (active/completed/pending) ou Enter para todas:")
                    status_filter = input("Status: ").strip()
                    if not status_filter:
                        status_filter = None
                    self.show_missions(status_filter=status_filter)
                
                elif choice == '5':
                    mission_id = input("ID da missão: ").strip()
                    if mission_id:
                        self.show_mission_details(mission_id)
                    else:
                        print("[ERRO] ID da missão não pode estar vazio.")
                
                elif choice == '6':
                    limit_str = input("Número de registos (default 10): ").strip()
                    limit = int(limit_str) if limit_str.isdigit() else 10
                    self.show_telemetry(limit=limit)
                
                elif choice == '7':
                    rover_id = input("ID do rover: ").strip()
                    if rover_id:
                        limit_str = input("Número de registos (default 10): ").strip()
                        limit = int(limit_str) if limit_str.isdigit() else 10
                        self.show_telemetry(rover_id=rover_id, limit=limit)
                    else:
                        print("[ERRO] ID do rover não pode estar vazio.")
                
                elif choice == '8':
                    self.show_status()
                
                elif choice == '9':
                    print("\nAtualização automática ativada. Pressione Ctrl+C para parar.")
                    interval_str = input(f"Intervalo em segundos (default {self.update_interval}): ").strip()
                    if interval_str.isdigit():
                        self.update_interval = int(interval_str)
                    
                    try:
                        while True:
                            self.show_dashboard()
                            print(f"\nPróxima atualização em {self.update_interval} segundos... (Ctrl+C para parar)")
                            time.sleep(self.update_interval)
                    except KeyboardInterrupt:
                        print("\n\nAtualização automática interrompida.")
                
                else:
                    print("[ERRO] Opção inválida. Escolha um número de 0 a 9.")
            
            except KeyboardInterrupt:
                print("\n\nA encerrar Ground Control...")
                self.running = False
                break
            except Exception as e:
                print(f"\n[ERRO] Erro inesperado: {e}")


def main():
    """Função principal para executar o Ground Control."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Ground Control - Cliente da API de Observação da Nave-Mãe',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python GroundControl.py                    # Interface interativa (API em localhost:8082)
  python GroundControl.py --api http://10.0.1.10:8082  # Especificar URL da API
  python GroundControl.py --dashboard        # Mostrar dashboard uma vez e sair
        """
    )
    
    parser.add_argument(
        '--api',
        type=str,
        default='http://localhost:8082',
        help='URL da API de Observação (default: http://localhost:8082)'
    )
    
    parser.add_argument(
        '--dashboard',
        action='store_true',
        help='Mostrar dashboard uma vez e sair (sem interface interativa)'
    )
    
    args = parser.parse_args()
    
    # Criar instância do Ground Control
    gc = GroundControl(api_url=args.api)
    
    # Verificar conexão
    print(f"Conectando à API em {args.api}...")
    test_data = gc._make_request('/status')
    if test_data is None:
        print("\n[ERRO] Não foi possível conectar à API.")
        print("Certifique-se de que:")
        print("  1. A Nave-Mãe está a correr")
        print("  2. A API de Observação está ativa")
        print("  3. A URL está correta")
        sys.exit(1)
    
    print("[OK] Conexão estabelecida com sucesso!\n")
    
    # Executar dashboard ou interface interativa
    if args.dashboard:
        gc.show_dashboard()
    else:
        gc.run_interactive()


if __name__ == '__main__':
    main()

