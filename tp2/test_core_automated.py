#!/usr/bin/env python3
"""
Script de teste automatizado para executar dentro do CORE.
Este script testa todas as funcionalidades básicas sem precisar de múltiplos nós.

Execute este script em cada nó do CORE para verificar que tudo está funcionando.

Uso:
  python3 test_core_automated.py [node_type]
  
  node_type pode ser: nms, rover, ground_control, ou auto (detecta automaticamente)
"""

import sys
import os
import socket
import time
import json

# Adicionar diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_hostname():
    """Obtém o hostname do nó."""
    try:
        return socket.gethostname()
    except:
        return "unknown"

def get_node_type():
    """Tenta detectar o tipo de nó baseado no hostname."""
    hostname = get_hostname().lower()
    if "nave" in hostname or "mae" in hostname or hostname == "n1":
        return "nms"
    elif "rover" in hostname or hostname in ["n3", "n4"]:
        return "rover"
    elif "ground" in hostname or "control" in hostname or hostname == "n2":
        return "ground_control"
    else:
        return "unknown"

def get_interface_ip():
    """Obtém o IP da primeira interface de rede."""
    try:
        # Tentar obter IP usando socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        try:
            # Fallback: usar hostname
            return socket.gethostbyname(socket.gethostname())
        except:
            return "127.0.0.1"

def test_imports():
    """Testa se todos os imports funcionam."""
    print("\n" + "="*60)
    print("TESTE 1: IMPORTS")
    print("="*60)
    
    errors = []
    
    try:
        from protocol import MissionLink, TelemetryStream
        print("  ✓ protocol OK")
    except Exception as e:
        errors.append(f"protocol: {e}")
        print(f"  ✗ protocol: {e}")
    
    try:
        from server import NMS_Server
        print("  ✓ server OK")
    except Exception as e:
        errors.append(f"server: {e}")
        print(f"  ✗ server: {e}")
    
    try:
        from client import NMS_Agent
        print("  ✓ client OK")
    except Exception as e:
        errors.append(f"client: {e}")
        print(f"  ✗ client: {e}")
    
    try:
        from otherEntities import Limit
        print("  ✓ otherEntities OK")
    except Exception as e:
        errors.append(f"otherEntities: {e}")
        print(f"  ✗ otherEntities: {e}")
    
    try:
        from API import ObservationAPI
        print("  ✓ API OK (Flask disponível)")
    except Exception as e:
        print(f"  ⚠ API: {e} (opcional - Flask pode não estar instalado)")
    
    if errors:
        print(f"\n✗ ERROS: {len(errors)} imports falharam")
        return False
    else:
        print("\n✓ Todos os imports principais OK")
        return True

def test_nms_server():
    """Testa criação e inicialização básica do servidor NMS."""
    print("\n" + "="*60)
    print("TESTE 2: SERVIDOR NMS")
    print("="*60)
    
    try:
        from server import NMS_Server
        
        print("  Criando instância NMS_Server...")
        server = NMS_Server.NMS_Server()
        print(f"  ✓ Servidor criado")
        print(f"    ID: {server.id}")
        print(f"    IP: {server.IPADDRESS}")
        print(f"    Agentes registados: {len(server.agents)}")
        
        # Verificar que MissionLink foi criado
        if hasattr(server, 'missionLink'):
            print(f"  ✓ MissionLink inicializado (porta {server.missionLink.port})")
        else:
            print("  ✗ MissionLink não inicializado")
            return False
        
        # Verificar que TelemetryStream foi criado
        if hasattr(server, 'telemetryStream'):
            print(f"  ✓ TelemetryStream inicializado (porta {server.telemetryStream.port})")
        else:
            print("  ✗ TelemetryStream não inicializado")
            return False
        
        # Verificar API (opcional)
        if server.observation_api:
            print("  ✓ API de Observação disponível")
        else:
            print("  ⚠ API de Observação não disponível (Flask pode não estar instalado)")
        
        print("\n✓ Servidor NMS criado com sucesso")
        return True
        
    except Exception as e:
        print(f"\n✗ Erro ao criar servidor: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_rover_agent():
    """Testa criação e inicialização básica do agente Rover."""
    print("\n" + "="*60)
    print("TESTE 3: AGENTE ROVER")
    print("="*60)
    
    try:
        from client import NMS_Agent
        
        # IP fictício para teste (não vamos realmente conectar)
        test_server_ip = "10.0.1.10"
        
        print(f"  Criando instância NMS_Agent (servidor: {test_server_ip})...")
        rover = NMS_Agent.NMS_Agent(test_server_ip)
        rover.id = "test_rover"
        
        print(f"  ✓ Rover criado")
        print(f"    ID: {rover.id}")
        print(f"    IP: {rover.ipAddress}")
        print(f"    Servidor: {rover.serverAddress}")
        
        # Verificar que MissionLink foi criado
        if hasattr(rover, 'missionLink'):
            print(f"  ✓ MissionLink inicializado")
        else:
            print("  ✗ MissionLink não inicializado")
            return False
        
        # Verificar que TelemetryStream foi criado
        if hasattr(rover, 'telemetryStream'):
            print(f"  ✓ TelemetryStream inicializado")
        else:
            print("  ✗ TelemetryStream não inicializado")
            return False
        
        # Testar criação de mensagem de telemetria
        print("  Testando criação de mensagem de telemetria...")
        telemetry = rover.createTelemetryMessage()
        if telemetry and "rover_id" in telemetry:
            print(f"  ✓ Mensagem de telemetria criada")
            print(f"    Rover ID: {telemetry['rover_id']}")
            print(f"    Posição: {telemetry.get('position', {})}")
            print(f"    Estado: {telemetry.get('operational_status', 'N/A')}")
        else:
            print("  ✗ Erro ao criar mensagem de telemetria")
            return False
        
        print("\n✓ Agente Rover criado com sucesso")
        return True
        
    except Exception as e:
        print(f"\n✗ Erro ao criar rover: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ground_control():
    """Testa criação do Ground Control."""
    print("\n" + "="*60)
    print("TESTE 4: GROUND CONTROL")
    print("="*60)
    
    try:
        from GroundControl import GroundControl
        
        # URL fictícia para teste
        test_api_url = "http://10.0.1.10:8082"
        
        print(f"  Criando instância GroundControl (API: {test_api_url})...")
        gc = GroundControl(api_url=test_api_url)
        
        print(f"  ✓ Ground Control criado")
        print(f"    API URL: {gc.api_url}")
        
        print("\n✓ Ground Control criado com sucesso")
        print("  Nota: Conexão real à API requer servidor NMS em execução")
        return True
        
    except Exception as e:
        print(f"\n✗ Erro ao criar Ground Control: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_network_info():
    """Mostra informações de rede do nó."""
    print("\n" + "="*60)
    print("TESTE 5: INFORMAÇÕES DE REDE")
    print("="*60)
    
    try:
        hostname = get_hostname()
        ip = get_interface_ip()
        
        print(f"  Hostname: {hostname}")
        print(f"  IP: {ip}")
        
        # Tentar obter todas as interfaces
        try:
            import subprocess
            result = subprocess.run(['ip', '-o', '-4', 'route', 'show'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                print("\n  Interfaces de rede:")
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split()
                        if len(parts) >= 3:
                            interface = parts[2]
                            if len(parts) >= 9:
                                ip_addr = parts[8]
                                print(f"    {interface}: {ip_addr}")
        except:
            print("  (Não foi possível obter detalhes das interfaces)")
        
        print("\n✓ Informações de rede obtidas")
        return True
        
    except Exception as e:
        print(f"\n✗ Erro ao obter informações de rede: {e}")
        return False

def test_file_structure():
    """Verifica se a estrutura de ficheiros está correta."""
    print("\n" + "="*60)
    print("TESTE 6: ESTRUTURA DE FICHEIROS")
    print("="*60)
    
    required_dirs = ["protocol", "server", "client", "otherEntities"]
    required_files = ["start_nms.py", "start_rover.py", "start_ground_control.py", "requirements.txt"]
    
    missing_dirs = []
    missing_files = []
    
    for dir_name in required_dirs:
        if os.path.exists(dir_name) and os.path.isdir(dir_name):
            print(f"  ✓ {dir_name}/ existe")
        else:
            print(f"  ✗ {dir_name}/ não encontrado")
            missing_dirs.append(dir_name)
    
    for file_name in required_files:
        if os.path.exists(file_name) and os.path.isfile(file_name):
            print(f"  ✓ {file_name} existe")
        else:
            print(f"  ✗ {file_name} não encontrado")
            missing_files.append(file_name)
    
    if missing_dirs or missing_files:
        print(f"\n✗ Faltam: {len(missing_dirs)} diretórios, {len(missing_files)} ficheiros")
        return False
    else:
        print("\n✓ Estrutura de ficheiros completa")
        return True

def main():
    """Função principal."""
    print("="*60)
    print("TESTE AUTOMATIZADO PARA CORE")
    print("="*60)
    
    # Detectar tipo de nó
    node_type = sys.argv[1] if len(sys.argv) > 1 else "auto"
    if node_type == "auto":
        node_type = get_node_type()
    
    hostname = get_hostname()
    ip = get_interface_ip()
    
    print(f"\nNó: {hostname} ({ip})")
    print(f"Tipo detectado: {node_type}")
    print(f"Diretório atual: {os.getcwd()}")
    
    results = {}
    
    # Executar todos os testes básicos
    results['imports'] = test_imports()
    results['file_structure'] = test_file_structure()
    results['network'] = test_network_info()
    
    # Testes específicos por tipo de nó
    if node_type == "nms" or node_type == "unknown":
        results['nms'] = test_nms_server()
    
    if node_type == "rover" or node_type == "unknown":
        results['rover'] = test_rover_agent()
    
    if node_type == "ground_control" or node_type == "unknown":
        results['ground_control'] = test_ground_control()
    
    # Resumo final
    print("\n" + "="*60)
    print("RESUMO DOS TESTES")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASSOU" if result else "✗ FALHOU"
        print(f"  {test_name}: {status}")
    
    print(f"\nResultado: {passed}/{total} testes passaram")
    
    if passed == total:
        print("\n✓ TODOS OS TESTES PASSARAM!")
        print("\nO nó está pronto para execução.")
        print("\nPróximos passos:")
        if node_type == "nms":
            print("  python3 start_nms.py")
        elif node_type == "rover":
            print("  python3 start_rover.py 10.0.1.10 r1")
        elif node_type == "ground_control":
            print("  python3 start_ground_control.py")
        else:
            print("  Execute o script apropriado conforme o tipo de nó")
        return 0
    else:
        print("\n✗ ALGUNS TESTES FALHARAM")
        print("Corrija os erros antes de executar o sistema.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
