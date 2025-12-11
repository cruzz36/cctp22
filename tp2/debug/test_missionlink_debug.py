#!/usr/bin/env python3
"""
Script de teste e debug para MissionLink.py

Uso:
    python test_missionlink_debug.py [teste]
    
Testes disponíveis:
    - handshake: Testa apenas o handshake 3-way
    - send_receive: Testa envio e receção de mensagem
    - file_transfer: Testa envio de ficheiro
    - all: Executa todos os testes
"""

import sys
import time
import threading
import os
from protocol import MissionLink

# Flag para ativar/desativar debug
DEBUG = True

def debug_print(msg, level="INFO"):
    """Imprime mensagem de debug se DEBUG estiver ativo"""
    if DEBUG:
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {msg}")

def test_handshake():
    """Testa apenas o handshake 3-way"""
    print("\n" + "="*60)
    print("TESTE 1: Handshake 3-Way")
    print("="*60)
    
    try:
        # Criar diretórios se não existirem
        os.makedirs("./test_server_files/", exist_ok=True)
        os.makedirs("./test_client_files/", exist_ok=True)
        
        # Criar instâncias
        debug_print("Criando instâncias MissionLink...")
        server = MissionLink.MissionLink("127.0.0.1", "./test_server_files/")
        client = MissionLink.MissionLink("127.0.0.1", "./test_client_files/")
        
        # Aumentar timeout para debug
        server.limit.timeout = 5
        client.limit.timeout = 5
        
        debug_print(f"Server timeout: {server.limit.timeout}s")
        debug_print(f"Client timeout: {client.limit.timeout}s")
        
        server_result = [None]
        client_result = [None]
        server_error = [None]
        client_error = [None]
        
        def server_thread():
            try:
                debug_print("SERVER: Aguardando conexão...")
                conn_info = server.acceptConnection()
                server_result[0] = conn_info
                debug_print(f"SERVER: ✓ Conexão estabelecida: {conn_info}")
            except Exception as e:
                server_error[0] = e
                debug_print(f"SERVER: ✗ ERRO: {e}", "ERROR")
                import traceback
                traceback.print_exc()
        
        def client_thread():
            time.sleep(0.5)  # Dar tempo ao servidor iniciar
            try:
                debug_print("CLIENT: Iniciando conexão...")
                conn_info = client.startConnection("r1", "127.0.0.1", 8080)
                client_result[0] = conn_info
                debug_print(f"CLIENT: ✓ Conexão estabelecida: {conn_info}")
            except Exception as e:
                client_error[0] = e
                debug_print(f"CLIENT: ✗ ERRO: {e}", "ERROR")
                import traceback
                traceback.print_exc()
        
        # Executar em threads
        t_server = threading.Thread(target=server_thread)
        t_client = threading.Thread(target=client_thread)
        
        t_server.start()
        t_client.start()
        
        t_server.join(timeout=10)
        t_client.join(timeout=10)
        
        # Verificar resultados
        if server_error[0]:
            print(f"\n❌ SERVER ERRO: {server_error[0]}")
            return False
        if client_error[0]:
            print(f"\n❌ CLIENT ERRO: {client_error[0]}")
            return False
        if server_result[0] and client_result[0]:
            print("\n✅ TESTE PASSOU: Handshake estabelecido com sucesso!")
            return True
        else:
            print("\n❌ TESTE FALHOU: Handshake não completado")
            return False
            
    except Exception as e:
        print(f"\n❌ ERRO NO TESTE: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_send_receive():
    """Testa envio e receção de mensagem curta"""
    print("\n" + "="*60)
    print("TESTE 2: Envio/Receção de Mensagem")
    print("="*60)
    
    try:
        os.makedirs("./test_server_files/", exist_ok=True)
        os.makedirs("./test_client_files/", exist_ok=True)
        
        server = MissionLink.MissionLink("127.0.0.1", "./test_server_files/")
        client = MissionLink.MissionLink("127.0.0.1", "./test_client_files/")
        
        server.limit.timeout = 5
        client.limit.timeout = 5
        
        server_result = [None]
        server_error = [None]
        client_error = [None]
        
        def server_thread():
            try:
                debug_print("SERVER: Aguardando mensagem...")
                result = server.recv()
                server_result[0] = result
                debug_print(f"SERVER: ✓ Mensagem recebida: {result}")
            except Exception as e:
                server_error[0] = e
                debug_print(f"SERVER: ✗ ERRO: {e}", "ERROR")
                import traceback
                traceback.print_exc()
        
        def client_thread():
            time.sleep(0.5)
            try:
                debug_print("CLIENT: Enviando mensagem...")
                message = "Hello World from MissionLink!"
                client.send("127.0.0.1", 8080, "T", "r1", "M01", message)
                debug_print(f"CLIENT: ✓ Mensagem enviada: {message}")
            except Exception as e:
                client_error[0] = e
                debug_print(f"CLIENT: ✗ ERRO: {e}", "ERROR")
                import traceback
                traceback.print_exc()
        
        t_server = threading.Thread(target=server_thread)
        t_client = threading.Thread(target=client_thread)
        
        t_server.start()
        t_client.start()
        
        t_server.join(timeout=15)
        t_client.join(timeout=15)
        
        if server_error[0]:
            print(f"\n❌ SERVER ERRO: {server_error[0]}")
            return False
        if client_error[0]:
            print(f"\n❌ CLIENT ERRO: {client_error[0]}")
            return False
        if server_result[0]:
            print(f"\n✅ TESTE PASSOU: Mensagem recebida com sucesso!")
            print(f"   Resultado: {server_result[0]}")
            return True
        else:
            print("\n❌ TESTE FALHOU: Mensagem não recebida")
            return False
            
    except Exception as e:
        print(f"\n❌ ERRO NO TESTE: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_file_transfer():
    """Testa envio de ficheiro"""
    print("\n" + "="*60)
    print("TESTE 3: Envio de Ficheiro")
    print("="*60)
    
    try:
        os.makedirs("./test_server_files/", exist_ok=True)
        os.makedirs("./test_client_files/", exist_ok=True)
        
        # Criar ficheiro de teste
        test_file = "./test_client_files/test_mission.json"
        test_content = '{"mission_id": "M-TEST", "rover_id": "r1", "task": "test"}'
        
        with open(test_file, "w") as f:
            f.write(test_content)
        
        debug_print(f"Ficheiro de teste criado: {test_file}")
        
        server = MissionLink.MissionLink("127.0.0.1", "./test_server_files/")
        client = MissionLink.MissionLink("127.0.0.1", "./test_client_files/")
        
        server.limit.timeout = 5
        client.limit.timeout = 5
        
        server_result = [None]
        server_error = [None]
        client_error = [None]
        
        def server_thread():
            try:
                debug_print("SERVER: Aguardando ficheiro...")
                result = server.recv()
                server_result[0] = result
                debug_print(f"SERVER: ✓ Ficheiro recebido: {result}")
                
                # Verificar se ficheiro foi criado
                if result and len(result) >= 4:
                    filename = result[3]
                    filepath = "./test_server_files/" + filename
                    if os.path.exists(filepath):
                        debug_print(f"SERVER: ✓ Ficheiro existe: {filepath}")
                        with open(filepath, "r") as f:
                            content = f.read()
                            debug_print(f"SERVER: Conteúdo do ficheiro: {content[:50]}...")
            except Exception as e:
                server_error[0] = e
                debug_print(f"SERVER: ✗ ERRO: {e}", "ERROR")
                import traceback
                traceback.print_exc()
        
        def client_thread():
            time.sleep(0.5)
            try:
                debug_print(f"CLIENT: Enviando ficheiro: {test_file}")
                client.send("127.0.0.1", 8080, "M", "r1", "M01", test_file)
                debug_print("CLIENT: ✓ Ficheiro enviado")
            except Exception as e:
                client_error[0] = e
                debug_print(f"CLIENT: ✗ ERRO: {e}", "ERROR")
                import traceback
                traceback.print_exc()
        
        t_server = threading.Thread(target=server_thread)
        t_client = threading.Thread(target=client_thread)
        
        t_server.start()
        t_client.start()
        
        t_server.join(timeout=20)
        t_client.join(timeout=20)
        
        if server_error[0]:
            print(f"\n❌ SERVER ERRO: {server_error[0]}")
            return False
        if client_error[0]:
            print(f"\n❌ CLIENT ERRO: {client_error[0]}")
            return False
        if server_result[0]:
            print(f"\n✅ TESTE PASSOU: Ficheiro transferido com sucesso!")
            return True
        else:
            print("\n❌ TESTE FALHOU: Ficheiro não recebido")
            return False
            
    except Exception as e:
        print(f"\n❌ ERRO NO TESTE: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Função principal"""
    print("\n" + "="*60)
    print("MISSIONLINK DEBUG TEST SUITE")
    print("="*60)
    
    # Determinar qual teste executar
    if len(sys.argv) > 1:
        test_name = sys.argv[1].lower()
    else:
        test_name = "all"
    
    results = {}
    
    if test_name in ["handshake", "all"]:
        results["handshake"] = test_handshake()
        time.sleep(1)  # Pausa entre testes
    
    if test_name in ["send_receive", "all"]:
        results["send_receive"] = test_send_receive()
        time.sleep(1)
    
    if test_name in ["file_transfer", "all"]:
        results["file_transfer"] = test_file_transfer()
        time.sleep(1)
    
    # Resumo
    print("\n" + "="*60)
    print("RESUMO DOS TESTES")
    print("="*60)
    
    for test, passed in results.items():
        status = "✅ PASSOU" if passed else "❌ FALHOU"
        print(f"  {test:20s}: {status}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    print(f"\nTotal: {passed}/{total} testes passaram")
    
    if passed == total:
        print("\n🎉 Todos os testes passaram!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} teste(s) falharam")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Teste interrompido pelo utilizador")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERRO FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

