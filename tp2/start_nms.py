#!/usr/bin/env python3
"""
Script para iniciar a Nave-Mãe no CORE.

Uso: python3 start_nms.py
"""

import sys
import os
import subprocess

# Adicionar diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import NMS_Server
import threading
import time

def cleanup_old_processes():
    """
    Liberta portas 8080/8081/8082 e termina processos antigos do NMS.
    Evita o erro "Address already in use" quando há instâncias penduradas.
    """
    print("[INFO] A limpar processos antigos e portas 8080/8081/8082...")
    cmds = [
        # Não matar o processo atual; apenas componentes antigos
        ["pkill", "-f", "MissionLink.py"],
        ["pkill", "-f", "TelemetryStream.py"],
        ["fuser", "-k", "8080/udp"],
        ["fuser", "-k", "8081/tcp"],
        ["fuser", "-k", "8082/tcp"],
    ]
    for cmd in cmds:
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            # Se pkill/fuser não existirem no ambiente, simplesmente ignora
            continue
        except Exception:
            continue
    time.sleep(0.5)

def main():
    print("="*60)
    print("NAVE-MÃE - Iniciando...")
    print("="*60)
    
    try:
        cleanup_old_processes()
        print("[DEBUG] start_nms: Criando instância NMS_Server...")
        server = NMS_Server.NMS_Server()
        print(f"[DEBUG] start_nms: NMS_Server criado, IP: {server.IPADDRESS}")
        
        # Iniciar MissionLink (UDP 8080) em thread
        print("[DEBUG] start_nms: Iniciando thread MissionLink (UDP:8080)...")
        ml_thread = threading.Thread(target=server.recvMissionLink, daemon=True)
        ml_thread.start()
        print("[OK] MissionLink (UDP:8080) iniciado")
        time.sleep(0.5)  # Pequeno delay para garantir inicialização
        
        # Iniciar TelemetryStream (TCP 8081) em thread
        print("[DEBUG] start_nms: Iniciando thread TelemetryStream (TCP:8081)...")
        ts_thread = threading.Thread(target=server.recvTelemetry, daemon=True)
        ts_thread.start()
        print("[OK] TelemetryStream (TCP:8081) iniciado")
        time.sleep(0.5)
        
        # Iniciar API de Observação (HTTP 8082) em thread
        print("[DEBUG] start_nms: Verificando disponibilidade da API de Observação...")
        if server.observation_api:
            try:
                print("[DEBUG] start_nms: Iniciando API de Observação (HTTP:8082)...")
                server.startObservationAPI()
                # Aguardar um pouco mais para garantir que a API está pronta
                time.sleep(1)
                print("[OK] API de Observação (HTTP:8082) iniciada")
                print(f"[INFO] API acessível em: http://{server.IPADDRESS}:8082")
                print(f"[INFO] API acessível em: http://0.0.0.0:8082 (todas as interfaces)")
            except Exception as e:
                print(f"[ERRO] Falha ao iniciar API de Observação: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("[AVISO] API de Observação não disponível (Flask não instalado)")
        
        print("="*60)
        print("Nave-Mãe pronta e a escutar!")
        print("="*60)
        print("\nAguardando conexões de rovers...")
        print("Pressione Ctrl+C para encerrar\n")
        
        # Manter servidor a correr
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nA encerrar Nave-Mãe...")
            print("Aguardando threads terminarem...")
            time.sleep(2)
            print("Nave-Mãe encerrada.")
    
    except Exception as e:
        print(f"\n[ERRO] Erro ao iniciar Nave-Mãe: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

