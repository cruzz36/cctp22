#!/usr/bin/env python3
"""
Script para iniciar o Ground Control no CORE.

Uso: python3 start_ground_control.py [API_URL]

Exemplos:
  python3 start_ground_control.py
  python3 start_ground_control.py http://10.0.1.10:8082
"""

import sys
import os

# Adicionar diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from GroundControl import GroundControl

def main():
    # IP padrão da Nave-Mãe na topologia: 10.0.1.10 (interface eth1 para rovers)
    # A API escuta em 0.0.0.0:8082, mas o Ground Control precisa de rota para alcançar 10.0.1.10
    default_api = "http://10.0.1.10:8082"
    api_url = sys.argv[1] if len(sys.argv) > 1 else default_api
    
    print("="*60)
    print("GROUND CONTROL - Iniciando...")
    print(f"API de Observação: {api_url}")
    print("="*60)
    
    try:
        gc = GroundControl(api_url=api_url)
        
        # Verificar conexão com retries
        print(f"\n[...] A conectar à API em {api_url}...")
        max_retries = 5
        retry_delay = 2
        test_data = None
        
        for attempt in range(1, max_retries + 1):
            # Tentar primeiro o endpoint /health que é mais simples
            test_data = gc._make_request('/health')
            if test_data is None:
                # Se /health falhar, tentar /status
                test_data = gc._make_request('/status')
            
            if test_data is not None:
                break
            if attempt < max_retries:
                print(f"[...] Tentativa {attempt}/{max_retries} falhou. A tentar novamente em {retry_delay}s...")
                import time
                time.sleep(retry_delay)
        
        if test_data is None:
            print(f"\n[ERRO] Não foi possível conectar à API após {max_retries} tentativas.")
            print("Certifique-se de que:")
            print("  1. A Nave-Mãe está a correr (python3 start_nms.py)")
            print("  2. A API de Observação está ativa (verifique os logs da Nave-Mãe)")
            print("  3. A URL está correta (padrão: http://10.0.1.10:8082)")
            print("  5. As rotas de rede estão configuradas (ver Guia_CORE_Unificado.md)")
            print("  4. A conectividade de rede está funcionando")
            print("\nDica: Verifique se a Nave-Mãe mostra '[OK] API de Observação (HTTP:8082) iniciada'")
            print(f"\nTente testar manualmente: curl {api_url}/health")
            sys.exit(1)
        
        print("[OK] Conexão estabelecida com sucesso!\n")
        
        # Executar interface interativa
        gc.run_interactive()
    
    except KeyboardInterrupt:
        print("\n\nGround Control encerrado.")
    except Exception as e:
        print(f"\n[ERRO] Erro no Ground Control: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

