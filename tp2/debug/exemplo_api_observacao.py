"""
Exemplo de uso da API de Observação da Nave-Mãe

Este exemplo demonstra como usar a API REST para consultar:
- Lista de rovers ativos
- Estado de missões
- Dados de telemetria
- Estado geral do sistema
"""

import requests
import json
import time

# Configuração
API_BASE_URL = "http://localhost:8082"

def print_json(data, title=""):
    """Imprime JSON formatado."""
    if title:
        print(f"\n{'='*60}")
        print(f"{title}")
        print(f"{'='*60}")
    print(json.dumps(data, indent=2, ensure_ascii=False))

def exemplo_listar_rovers():
    """Exemplo: Listar todos os rovers ativos."""
    print("\n[1] Listando rovers ativos...")
    try:
        response = requests.get(f"{API_BASE_URL}/rovers")
        if response.status_code == 200:
            print_json(response.json(), "Rovers Ativos")
        else:
            print(f"Erro: {response.status_code} - {response.text}")
    except requests.exceptions.ConnectionError:
        print("Erro: Não foi possível conectar à API. Certifique-se de que o servidor está em execução.")
    except Exception as e:
        print(f"Erro: {e}")

def exemplo_rover_especifico(rover_id="r1"):
    """Exemplo: Obter estado detalhado de um rover."""
    print(f"\n[2] Obtendo estado do rover {rover_id}...")
    try:
        response = requests.get(f"{API_BASE_URL}/rovers/{rover_id}")
        if response.status_code == 200:
            print_json(response.json(), f"Estado do Rover {rover_id}")
        elif response.status_code == 404:
            print(f"Rover {rover_id} não encontrado")
        else:
            print(f"Erro: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Erro: {e}")

def exemplo_listar_missoes(status=None):
    """Exemplo: Listar missões."""
    print(f"\n[3] Listando missões" + (f" (status: {status})" if status else "") + "...")
    try:
        url = f"{API_BASE_URL}/missions"
        if status:
            url += f"?status={status}"
        response = requests.get(url)
        if response.status_code == 200:
            print_json(response.json(), "Missões")
        else:
            print(f"Erro: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Erro: {e}")

def exemplo_missao_especifica(mission_id="M-001"):
    """Exemplo: Obter detalhes de uma missão específica."""
    print(f"\n[4] Obtendo detalhes da missão {mission_id}...")
    try:
        response = requests.get(f"{API_BASE_URL}/missions/{mission_id}")
        if response.status_code == 200:
            print_json(response.json(), f"Detalhes da Missão {mission_id}")
        elif response.status_code == 404:
            print(f"Missão {mission_id} não encontrada")
        else:
            print(f"Erro: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Erro: {e}")

def exemplo_telemetria(rover_id=None, limit=5):
    """Exemplo: Obter últimos dados de telemetria."""
    print(f"\n[5] Obtendo últimos {limit} registos de telemetria" + (f" do rover {rover_id}" if rover_id else "") + "...")
    try:
        url = f"{API_BASE_URL}/telemetry?limit={limit}"
        if rover_id:
            url = f"{API_BASE_URL}/telemetry/{rover_id}?limit={limit}"
        response = requests.get(url)
        if response.status_code == 200:
            print_json(response.json(), "Dados de Telemetria")
        else:
            print(f"Erro: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Erro: {e}")

def exemplo_status_sistema():
    """Exemplo: Obter estado geral do sistema."""
    print("\n[6] Obtendo estado geral do sistema...")
    try:
        response = requests.get(f"{API_BASE_URL}/status")
        if response.status_code == 200:
            print_json(response.json(), "Estado do Sistema")
        else:
            print(f"Erro: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Erro: {e}")

def exemplo_info_api():
    """Exemplo: Obter informação sobre a API."""
    print("\n[0] Obtendo informação da API...")
    try:
        response = requests.get(f"{API_BASE_URL}/")
        if response.status_code == 200:
            print_json(response.json(), "Informação da API")
        else:
            print(f"Erro: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    print("="*60)
    print("Exemplo de Uso da API de Observação")
    print("="*60)
    print(f"\nConectando a: {API_BASE_URL}")
    print("Certifique-se de que o servidor NMS está em execução e a API foi iniciada.")
    
    # Executar exemplos
    exemplo_info_api()
    exemplo_status_sistema()
    exemplo_listar_rovers()
    exemplo_rover_especifico("r1")
    exemplo_listar_missoes()
    exemplo_listar_missoes(status="active")
    exemplo_missao_especifica("M-001")
    exemplo_telemetria(limit=3)
    exemplo_telemetria(rover_id="r1", limit=3)
    
    print("\n" + "="*60)
    print("Exemplos concluídos!")
    print("="*60)
    print("\nPara usar a API diretamente:")
    print(f"  curl {API_BASE_URL}/rovers")
    print(f"  curl {API_BASE_URL}/missions")
    print(f"  curl {API_BASE_URL}/telemetry?limit=10")
    print(f"  curl {API_BASE_URL}/status")

