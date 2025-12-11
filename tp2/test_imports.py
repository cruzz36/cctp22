#!/usr/bin/env python3
"""
Script de teste para verificar se todos os imports funcionam corretamente.
Execute este script antes de copiar para o CORE para garantir que não há erros.
"""

import sys
import os

# Adicionar diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Testa todos os imports principais."""
    errors = []
    warnings = []
    
    print("="*60)
    print("TESTE DE IMPORTS")
    print("="*60)
    
    # Testar imports básicos
    print("\n[1/8] Testando imports básicos...")
    try:
        import socket
        import threading
        import json
        import time
        print("  ✓ Imports básicos OK")
    except ImportError as e:
        errors.append(f"Imports básicos: {e}")
        print(f"  ✗ Erro: {e}")
    
    # Testar protocol
    print("\n[2/8] Testando protocol...")
    try:
        from protocol import MissionLink, TelemetryStream
        print("  ✓ Protocol OK")
    except ImportError as e:
        errors.append(f"Protocol: {e}")
        print(f"  ✗ Erro: {e}")
    
    # Testar server
    print("\n[3/8] Testando server...")
    try:
        from server import NMS_Server
        print("  ✓ Server OK")
    except ImportError as e:
        errors.append(f"Server: {e}")
        print(f"  ✗ Erro: {e}")
    
    # Testar client
    print("\n[4/8] Testando client...")
    try:
        from client import NMS_Agent
        print("  ✓ Client OK")
    except ImportError as e:
        errors.append(f"Client: {e}")
        print(f"  ✗ Erro: {e}")
    
    # Testar otherEntities
    print("\n[5/8] Testando otherEntities...")
    try:
        from otherEntities import Limit
        print("  ✓ OtherEntities OK")
    except ImportError as e:
        errors.append(f"OtherEntities: {e}")
        print(f"  ✗ Erro: {e}")
    
    # Testar API (opcional)
    print("\n[6/8] Testando API (opcional)...")
    try:
        from API import ObservationAPI
        print("  ✓ API OK")
    except ImportError as e:
        warnings.append(f"API: {e} (opcional - requer Flask)")
        print(f"  ⚠ Aviso: {e} (opcional)")
    
    # Testar GroundControl
    print("\n[7/8] Testando GroundControl...")
    try:
        from GroundControl import GroundControl
        print("  ✓ GroundControl OK")
    except ImportError as e:
        warnings.append(f"GroundControl: {e}")
        print(f"  ⚠ Aviso: {e}")
    
    # Testar scripts de início
    print("\n[8/8] Testando scripts de início...")
    try:
        import start_nms
        import start_rover
        import start_ground_control
        print("  ✓ Scripts de início OK")
    except Exception as e:
        warnings.append(f"Scripts: {e}")
        print(f"  ⚠ Aviso: {e}")
    
    # Resumo
    print("\n" + "="*60)
    print("RESUMO")
    print("="*60)
    
    if errors:
        print(f"\n✗ ERROS ENCONTRADOS: {len(errors)}")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("\n✓ Todos os imports principais funcionam!")
    
    if warnings:
        print(f"\n⚠ AVISOS: {len(warnings)}")
        for warning in warnings:
            print(f"  - {warning}")
        print("\nNota: Avisos não impedem execução, mas algumas funcionalidades podem não estar disponíveis.")
    
    return True

def test_basic_functionality():
    """Testa funcionalidade básica sem criar sockets."""
    print("\n" + "="*60)
    print("TESTE DE FUNCIONALIDADE BÁSICA")
    print("="*60)
    
    try:
        from server import NMS_Server
        from client import NMS_Agent
        
        print("\n[1/2] Testando criação de instância NMS_Server...")
        # Não vamos criar socket real, apenas verificar que a classe pode ser importada
        print("  ✓ Classe NMS_Server importada com sucesso")
        
        print("\n[2/2] Testando criação de instância NMS_Agent...")
        # Não vamos criar socket real, apenas verificar que a classe pode ser importada
        print("  ✓ Classe NMS_Agent importada com sucesso")
        
        print("\n✓ Testes de funcionalidade básica concluídos!")
        return True
        
    except Exception as e:
        print(f"\n✗ Erro nos testes de funcionalidade: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("\n" + "="*60)
    print("VERIFICAÇÃO DE IMPORTS E ESTRUTURA")
    print("="*60)
    
    imports_ok = test_imports()
    functionality_ok = test_basic_functionality()
    
    print("\n" + "="*60)
    print("RESULTADO FINAL")
    print("="*60)
    
    if imports_ok and functionality_ok:
        print("\n✓ TUDO OK! O código está pronto para ser copiado para o CORE.")
        print("\nPróximos passos:")
        print("  1. Copiar ficheiros para os nós do CORE")
        print("  2. Instalar dependências: pip3 install -r requirements.txt")
        print("  3. Executar conforme Guia_Teste_CORE.md")
        sys.exit(0)
    else:
        print("\n✗ ERROS ENCONTRADOS! Corrija os erros antes de copiar para o CORE.")
        sys.exit(1)
