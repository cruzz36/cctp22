"""
Exemplo de uso do Ground Control

Este script demonstra como usar o Ground Control programaticamente
ou através da interface interativa.
"""

import sys
import os

# Adicionar diretório pai ao path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from GroundControl import GroundControl


def exemplo_dashboard():
    """Exemplo: Mostrar dashboard uma vez."""
    print("="*80)
    print("EXEMPLO 1: Dashboard Completo")
    print("="*80)
    
    gc = GroundControl(api_url="http://localhost:8082")
    
    # Verificar conexão
    if gc._make_request('/status') is None:
        print("[ERRO] Não foi possível conectar à API.")
        print("Certifique-se de que a Nave-Mãe está a correr e a API está ativa.")
        return
    
    gc.show_dashboard()


def exemplo_rovers():
    """Exemplo: Listar rovers."""
    print("\n" + "="*80)
    print("EXEMPLO 2: Listar Rovers")
    print("="*80)
    
    gc = GroundControl(api_url="http://localhost:8082")
    
    if gc._make_request('/status') is None:
        print("[ERRO] Não foi possível conectar à API.")
        return
    
    gc.show_rovers()


def exemplo_rover_especifico():
    """Exemplo: Detalhes de um rover específico."""
    print("\n" + "="*80)
    print("EXEMPLO 3: Detalhes de Rover Específico")
    print("="*80)
    
    gc = GroundControl(api_url="http://localhost:8082")
    
    if gc._make_request('/status') is None:
        print("[ERRO] Não foi possível conectar à API.")
        return
    
    # Listar rovers primeiro para ver quais existem
    data = gc._make_request('/rovers')
    if data and data.get('rovers'):
        rover_id = data['rovers'][0]['rover_id']
        print(f"\nMostrando detalhes do rover: {rover_id}\n")
        gc.show_rover_details(rover_id)
    else:
        print("Nenhum rover disponível.")


def exemplo_missoes():
    """Exemplo: Listar missões."""
    print("\n" + "="*80)
    print("EXEMPLO 4: Listar Missões")
    print("="*80)
    
    gc = GroundControl(api_url="http://localhost:8082")
    
    if gc._make_request('/status') is None:
        print("[ERRO] Não foi possível conectar à API.")
        return
    
    # Todas as missões
    print("\n--- Todas as Missões ---")
    gc.show_missions()
    
    # Apenas missões ativas
    print("\n--- Missões Ativas ---")
    gc.show_missions(status_filter='active')


def exemplo_telemetria():
    """Exemplo: Ver telemetria."""
    print("\n" + "="*80)
    print("EXEMPLO 5: Telemetria")
    print("="*80)
    
    gc = GroundControl(api_url="http://localhost:8082")
    
    if gc._make_request('/status') is None:
        print("[ERRO] Não foi possível conectar à API.")
        return
    
    # Telemetria de todos os rovers (últimos 5 registos)
    print("\n--- Última Telemetria (Todos os Rovers) ---")
    gc.show_telemetry(limit=5)
    
    # Telemetria de um rover específico
    data = gc._make_request('/rovers')
    if data and data.get('rovers'):
        rover_id = data['rovers'][0]['rover_id']
        print(f"\n--- Última Telemetria do Rover {rover_id} ---")
        gc.show_telemetry(rover_id=rover_id, limit=3)


def exemplo_atualizacao_automatica():
    """Exemplo: Atualização automática (3 iterações)."""
    print("\n" + "="*80)
    print("EXEMPLO 6: Atualização Automática (3 iterações)")
    print("="*80)
    
    gc = GroundControl(api_url="http://localhost:8082")
    gc.update_interval = 3  # 3 segundos
    
    if gc._make_request('/status') is None:
        print("[ERRO] Não foi possível conectar à API.")
        return
    
    import time
    
    for i in range(3):
        print(f"\n{'='*80}")
        print(f"ITERAÇÃO {i+1}/3")
        print(f"{'='*80}")
        gc.show_dashboard()
        
        if i < 2:  # Não esperar após a última iteração
            print(f"\nPróxima atualização em {gc.update_interval} segundos...")
            time.sleep(gc.update_interval)


def main():
    """Executa todos os exemplos."""
    print("\n" + "="*80)
    print("EXEMPLOS DE USO DO GROUND CONTROL")
    print("="*80)
    print("\nEstes exemplos demonstram as funcionalidades do Ground Control.")
    print("Certifique-se de que a Nave-Mãe está a correr e a API está ativa.\n")
    
    input("Pressione Enter para continuar...")
    
    try:
        exemplo_dashboard()
        input("\nPressione Enter para continuar para o próximo exemplo...")
        
        exemplo_rovers()
        input("\nPressione Enter para continuar para o próximo exemplo...")
        
        exemplo_rover_especifico()
        input("\nPressione Enter para continuar para o próximo exemplo...")
        
        exemplo_missoes()
        input("\nPressione Enter para continuar para o próximo exemplo...")
        
        exemplo_telemetria()
        input("\nPressione Enter para continuar para o último exemplo...")
        
        exemplo_atualizacao_automatica()
        
        print("\n" + "="*80)
        print("TODOS OS EXEMPLOS CONCLUÍDOS")
        print("="*80)
        print("\nPara usar a interface interativa completa, execute:")
        print("  python GroundControl.py")
        print("="*80)
    
    except KeyboardInterrupt:
        print("\n\nExemplos interrompidos pelo utilizador.")
    except Exception as e:
        print(f"\n[ERRO] Erro ao executar exemplos: {e}")


if __name__ == '__main__':
    main()

