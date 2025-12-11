#!/usr/bin/env python3
"""
Script para iniciar um Rover no CORE.

Uso: python3 start_rover.py <IP_NAVE_MAE> [ROVER_ID] [TELEMETRY_INTERVAL]

Exemplos:
  python3 start_rover.py 10.0.1.10 r1
  python3 start_rover.py 10.0.1.10 r2 10
"""

import sys
import os

# Adicionar diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from client import NMS_Agent
import threading
import time

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 start_rover.py <IP_NAVE_MAE> [ROVER_ID] [TELEMETRY_INTERVAL]")
        print("\nExemplos:")
        print("  python3 start_rover.py 10.0.1.10 r1")
        print("  python3 start_rover.py 10.0.1.10 r2 10")
        sys.exit(1)
    
    nms_ip = sys.argv[1]
    rover_id = sys.argv[2] if len(sys.argv) > 2 else "r1"
    telemetry_interval = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    
    print("="*60)
    print(f"ROVER {rover_id} - Iniciando...")
    print(f"Nave-Mãe: {nms_ip}")
    print(f"Intervalo de telemetria: {telemetry_interval} segundos")
    print("="*60)
    
    try:
        print(f"[DEBUG] start_rover: Criando instância NMS_Agent com Nave-Mãe em {nms_ip}")
        rover = NMS_Agent.NMS_Agent(nms_ip)
        rover.id = rover_id
        print(f"[DEBUG] start_rover: Rover ID definido como {rover_id}")
        
        # Registo na Nave-Mãe
        print(f"\n[DEBUG] start_rover: Iniciando processo de registo na Nave-Mãe {nms_ip}...")
        max_registration_retries = 5
        registration_success = False
        
        for attempt in range(1, max_registration_retries + 1):
            try:
                print(f"[DEBUG] start_rover: Tentativa {attempt}/{max_registration_retries} de registo...")
                rover.registerAgent(nms_ip)
                print(f"[OK] Registado como {rover_id} na Nave-Mãe {nms_ip}")
                registration_success = True
                break
            except Exception as e:
                if attempt < max_registration_retries:
                    print(f"[AVISO] Tentativa {attempt}/{max_registration_retries} falhou: {e}")
                    print(f"[DEBUG] start_rover: A tentar novamente em 2 segundos...")
                    time.sleep(2)
                else:
                    print(f"[ERRO] Falha ao registar após {max_registration_retries} tentativas: {e}")
                    print("[AVISO] Certifique-se de que:")
                    print("  1. A Nave-Mãe está a correr (python3 start_nms.py)")
                    print("  2. O IP da Nave-Mãe está correto (verificar: ping -c 2 10.0.1.10)")
                    print("  3. As rotas de rede estão configuradas (ver Guia_CORE_Unificado.md secção 1.5)")
                    print("  4. O IP forwarding está habilitado no Satélite")
                    print("  5. A porta UDP 8080 está acessível")
                    import traceback
                    traceback.print_exc()
        
        if not registration_success:
            print("[AVISO] Continuando sem registo bem-sucedido...")
        
        # Iniciar telemetria contínua
        print(f"[...] A iniciar telemetria contínua...")
        rover.startContinuousTelemetry(nms_ip, interval_seconds=telemetry_interval)
        print(f"[OK] Telemetria contínua ativa (intervalo: {telemetry_interval}s)")
        
        print("="*60)
        print(f"Rover {rover_id} pronto!")
        print("="*60)
        print("\nRover em operação. Pressione Ctrl+C para encerrar\n")
        
        # Manter rover a correr
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n\nA encerrar Rover {rover_id}...")
            rover.stopContinuousTelemetry()
            print(f"Rover {rover_id} encerrado.")
    
    except Exception as e:
        print(f"\n[ERRO] Erro ao iniciar Rover: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

