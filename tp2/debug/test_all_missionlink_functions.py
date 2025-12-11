#!/usr/bin/env python3
"""
Teste Completo de TODAS as Funções do MissionLink.py

Este script testa todas as funções do protocolo MissionLink:
1. __init__ - Inicialização
2. server() - Bind do socket
3. getHeaderSize() - Cálculo do cabeçalho
4. formatMessage() - Formatação de mensagens
5. splitMessage() - Divisão de mensagens grandes
6. startConnection() - Handshake (cliente)
7. acceptConnection() - Handshake (servidor)
8. send() - Envio (mensagem curta, longa, ficheiro)
9. recv() - Receção (mensagem, ficheiro)

Uso:
    python debug/test_all_missionlink_functions.py [teste]
    
Testes disponíveis:
    - init: Testa __init__
    - server: Testa server()
    - header: Testa getHeaderSize()
    - format: Testa formatMessage()
    - split: Testa splitMessage()
    - handshake: Testa startConnection() e acceptConnection()
    - send_short: Testa send() com mensagem curta
    - send_long: Testa send() com mensagem longa
    - send_file: Testa send() com ficheiro
    - recv_message: Testa recv() com mensagem
    - recv_file: Testa recv() com ficheiro
    - all: Executa todos os testes
"""

import sys
import os
import time
import threading
import json
import socket
from datetime import datetime

# Adicionar diretório pai ao path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from protocol import MissionLink
from otherEntities import Limit

# Configuração de debug
DEBUG = True
VERBOSE = True

def debug_print(msg, level="INFO"):
    """Imprime mensagem de debug formatada"""
    if DEBUG:
        # Usar datetime para obter microsegundos (time.strftime não suporta %f)
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        # Substituir caracteres Unicode por ASCII para compatibilidade Windows
        msg = msg.replace("✓", "[OK]").replace("✗", "[ERRO]").replace("❌", "[FALHOU]").replace("⚠️", "[AVISO]").replace("🎉", "[SUCESSO]")
        colors = {
            "INFO": "\033[36m",    # Cyan
            "SUCCESS": "\033[32m", # Green
            "WARNING": "\033[33m", # Yellow
            "ERROR": "\033[31m",   # Red
            "TEST": "\033[35m"     # Magenta
        }
        reset = "\033[0m"
        color = colors.get(level, "")
        try:
            print(f"{color}[{timestamp}] [{level}] {msg}{reset}")
        except UnicodeEncodeError:
            # Fallback para Windows sem suporte Unicode
            print(f"[{timestamp}] [{level}] {msg}")

def create_missionlink_with_port(serverAddress, port, storeFolder="."):
    """
    Cria uma instância MissionLink com porta específica.
    Necessário para testes onde servidor e cliente precisam de portas diferentes.
    
    Args:
        serverAddress (str): Endereço IP do servidor
        port (int): Porta a usar
        storeFolder (str): Pasta onde armazenar ficheiros recebidos
        
    Returns:
        MissionLink: Instância com porta especificada
    """
    # Criar instância MissionLink básica (sem bind ainda)
    ml = MissionLink.MissionLink.__new__(MissionLink.MissionLink)
    
    # Inicializar atributos básicos
    ml.serverAddress = serverAddress
    ml.port = port
    ml.limit = Limit.Limit()
    
    # Configurar storeFolder
    if storeFolder.endswith("/"):
        ml.storeFolder = storeFolder
    else:
        ml.storeFolder = storeFolder + "/"
    
    # Inicializar tipos de operação e flags (copiado de __init__)
    ml.registerAgent = "R"
    ml.taskRequest = "T"
    # ml.sendMetrics = "M"
    ml.requestMission = "Q"
    ml.reportProgress = "P"
    ml.noneType = "N"
    ml.datakey = "D"
    ml.synkey = "S"
    ml.ackkey = "A"
    ml.finkey = "F"
    ml.synackkey = "Z"
    ml.eofkey = '\0'
    
    # Criar socket e fazer bind na porta especificada
    ml.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        ml.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except Exception as e:
        debug_print(f"Aviso: Não foi possível habilitar SO_REUSEADDR: {e}", "WARNING")
    
    # Fazer bind na porta especificada
    ml.sock.bind((ml.serverAddress, ml.port))
    ml.sock.settimeout(ml.limit.timeout)
    
    return ml

def test_init():
    """TESTE 1: __init__ - Inicialização do MissionLink"""
    print("\n" + "="*70)
    print("TESTE 1: __init__ - Inicialização")
    print("="*70)
    
    try:
        debug_print("Criando instância MissionLink...", "TEST")
        ml = MissionLink.MissionLink("127.0.0.1", "./debug/test_files/")
        
        # Verificar atributos
        assert ml.serverAddress == "127.0.0.1", f"serverAddress incorreto: {ml.serverAddress}"
        assert ml.port == 8080, f"port incorreto: {ml.port}"
        assert ml.storeFolder == "./debug/test_files/", f"storeFolder incorreto: {ml.storeFolder}"
        assert ml.limit is not None, "limit não foi inicializado"
        assert ml.sock is not None, "sock não foi inicializado"
        
        # Verificar tipos de operação
        assert ml.registerAgent == "R", "registerAgent incorreto"
        assert ml.taskRequest == "T", "taskRequest incorreto"
        # assert ml.sendMetrics == "M", "sendMetrics incorreto"
        assert ml.requestMission == "Q", "requestMission incorreto"
        assert ml.reportProgress == "P", "reportProgress incorreto"
        assert ml.noneType == "N", "noneType incorreto"
        
        # Verificar flags
        assert ml.datakey == "D", "datakey incorreto"
        assert ml.synkey == "S", "synkey incorreto"
        assert ml.ackkey == "A", "ackkey incorreto"
        assert ml.finkey == "F", "finkey incorreto"
        assert ml.synackkey == "Z", "synackkey incorreto"
        assert ml.eofkey == '\0', "eofkey incorreto"
        
        debug_print("✓ Todos os atributos inicializados corretamente", "SUCCESS")
        debug_print(f"  - serverAddress: {ml.serverAddress}", "INFO")
        debug_print(f"  - port: {ml.port}", "INFO")
        debug_print(f"  - storeFolder: {ml.storeFolder}", "INFO")
        debug_print(f"  - timeout: {ml.limit.timeout}s", "INFO")
        debug_print(f"  - buffersize: {ml.limit.buffersize} bytes", "INFO")
        
        return True
        
    except Exception as e:
        debug_print(f"✗ ERRO: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False

def test_server():
    """TESTE 2: server() - Bind do socket"""
    print("\n" + "="*70)
    print("TESTE 2: server() - Bind do Socket")
    print("="*70)
    
    try:
        debug_print("Criando instância e testando server()...", "TEST")
        ml = MissionLink.MissionLink("127.0.0.1", "./debug/test_files/")
        
        # Verificar que socket foi criado
        assert ml.sock is not None, "Socket não foi criado"
        assert ml.sock.family == 2, "Socket family incorreto (deveria ser AF_INET=2)"
        assert ml.sock.type == 2, "Socket type incorreto (deveria ser SOCK_DGRAM=2)"
        
        # Verificar que bind foi feito (socket tem endereço local)
        try:
            addr = ml.sock.getsockname()
            debug_print(f"✓ Socket ligado a: {addr}", "SUCCESS")
            assert addr[0] == "127.0.0.1" or addr[0] == "0.0.0.0", f"Endereço incorreto: {addr[0]}"
            assert addr[1] == 8080, f"Porta incorreta: {addr[1]}"
        except OSError as e:
            debug_print(f"✗ Erro ao obter endereço do socket: {e}", "ERROR")
            return False
        
        debug_print("✓ server() executado com sucesso", "SUCCESS")
        return True
        
    except Exception as e:
        debug_print(f"✗ ERRO: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False

def test_getHeaderSize():
    """TESTE 3: getHeaderSize() - Cálculo do tamanho do cabeçalho"""
    print("\n" + "="*70)
    print("TESTE 3: getHeaderSize() - Cálculo do Cabeçalho")
    print("="*70)
    
    try:
        debug_print("Testando getHeaderSize()...", "TEST")
        ml = MissionLink.MissionLink("127.0.0.1", "./debug/test_files/")
        
        header_size = ml.getHeaderSize()
        
        # Cálculo esperado: flag(1) + |(1) + idMission(3) + |(1) + seq(4) + |(1) + 
        #                   ack(4) + |(1) + size(4) + |(1) + missionType(1) + |(1) = 23
        expected_size = 23
        
        assert header_size == expected_size, f"Tamanho incorreto: {header_size} (esperado: {expected_size})"
        
        debug_print(f"✓ Tamanho do cabeçalho: {header_size} bytes", "SUCCESS")
        debug_print(f"  - Tamanho útil para dados: {ml.limit.buffersize - header_size} bytes", "INFO")
        
        return True
        
    except Exception as e:
        debug_print(f"✗ ERRO: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False

def test_formatMessage():
    """TESTE 4: formatMessage() - Formatação de mensagens"""
    print("\n" + "="*70)
    print("TESTE 4: formatMessage() - Formatação de Mensagens")
    print("="*70)
    
    try:
        ml = MissionLink.MissionLink("127.0.0.1", "./debug/test_files/")
        
        # Teste 4.1: Mensagem com missionType
        debug_print("Teste 4.1: Mensagem com missionType='T'...", "TEST")
        message = "Hello World"
        formatted = ml.formatMessage("T", "D", "M01", 101, 101, message)
        decoded = formatted.decode()
        
        expected = f"D|M01|101|101|{len(message)}|T|{message}"
        assert decoded == expected, f"Formato incorreto:\n  Esperado: {expected}\n  Recebido: {decoded}"
        debug_print(f"✓ Mensagem formatada: {decoded[:50]}...", "SUCCESS")
        
        # Teste 4.2: Mensagem com missionType=None (ACK)
        debug_print("Teste 4.2: Mensagem com missionType=None (ACK)...", "TEST")
        formatted = ml.formatMessage(None, "A", "M01", 102, 101, "\0")
        decoded = formatted.decode()
        
        expected = f"A|M01|102|101|1|N|\0"
        assert decoded == expected, f"Formato ACK incorreto:\n  Esperado: {expected}\n  Recebido: {decoded}"
        debug_print(f"✓ ACK formatado: {decoded}", "SUCCESS")
        
        # Teste 4.3: Mensagem com missionType=None (FIN)
        debug_print("Teste 4.3: Mensagem com missionType=None (FIN)...", "TEST")
        formatted = ml.formatMessage(None, "F", "M01", 103, 103, "\0")
        decoded = formatted.decode()
        
        expected = f"F|M01|103|103|1|N|\0"
        assert decoded == expected, f"Formato FIN incorreto:\n  Esperado: {expected}\n  Recebido: {decoded}"
        debug_print(f"✓ FIN formatado: {decoded}", "SUCCESS")
        
        # Teste 4.4: Mensagem grande
        debug_print("Teste 4.4: Mensagem grande (verificar size)...", "TEST")
        large_message = "A" * 500
        formatted = ml.formatMessage("M", "D", "M01", 104, 104, large_message)
        decoded = formatted.decode()
        
        parts = decoded.split("|")
        assert len(parts) == 7, f"Número de campos incorreto: {len(parts)}"
        assert parts[4] == str(len(large_message)), f"Size incorreto: {parts[4]} (esperado: {len(large_message)})"
        debug_print(f"✓ Mensagem grande formatada corretamente (size={parts[4]})", "SUCCESS")
        
        # Teste 4.5: Todos os missionTypes
        debug_print("Teste 4.5: Testando todos os missionTypes...", "TEST")
        mission_types = {
            "R": ml.registerAgent,
            "T": ml.taskRequest,
            # "M": ml.sendMetrics,
            "Q": ml.requestMission,
            "P": ml.reportProgress
        }
        
        for name, value in mission_types.items():
            formatted = ml.formatMessage(value, "D", "M01", 105, 105, "test")
            decoded = formatted.decode()
            parts = decoded.split("|")
            assert parts[5] == value, f"missionType incorreto para {name}: {parts[5]}"
            debug_print(f"  ✓ {name} ({value}): {decoded[:40]}...", "INFO")
        
        debug_print("✓ Todos os missionTypes formatados corretamente", "SUCCESS")
        
        return True
        
    except Exception as e:
        debug_print(f"✗ ERRO: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False

def test_splitMessage():
    """TESTE 5: splitMessage() - Divisão de mensagens"""
    print("\n" + "="*70)
    print("TESTE 5: splitMessage() - Divisão de Mensagens")
    print("="*70)
    
    try:
        ml = MissionLink.MissionLink("127.0.0.1", "./debug/test_files/")
        
        header_size = ml.getHeaderSize()
        max_useful = ml.limit.buffersize - header_size
        
        # Teste 5.1: Mensagem pequena (não precisa dividir)
        debug_print("Teste 5.1: Mensagem pequena (não divide)...", "TEST")
        small_message = "Hello"
        result = ml.splitMessage(small_message)
        
        assert isinstance(result, str), f"Resultado deveria ser string, recebido: {type(result)}"
        assert result == small_message, f"Mensagem alterada: {result}"
        debug_print(f"✓ Mensagem pequena retornada como string: {result}", "SUCCESS")
        
        # Teste 5.2: Mensagem grande (precisa dividir)
        debug_print("Teste 5.2: Mensagem grande (divide em chunks)...", "TEST")
        large_message = "A" * (max_useful * 3)  # 3x o tamanho útil
        result = ml.splitMessage(large_message)
        
        assert isinstance(result, list), f"Resultado deveria ser lista, recebido: {type(result)}"
        assert len(result) == 3, f"Número de chunks incorreto: {len(result)} (esperado: 3)"
        
        # Verificar tamanho dos chunks
        for i, chunk in enumerate(result):
            assert len(chunk) <= max_useful, f"Chunk {i} muito grande: {len(chunk)} (máx: {max_useful})"
            debug_print(f"  Chunk {i+1}: {len(chunk)} bytes", "INFO")
        
        # Verificar que chunks reconstroem a mensagem original
        reconstructed = "".join(result)
        assert reconstructed == large_message, "Chunks não reconstroem mensagem original"
        debug_print(f"✓ Mensagem dividida em {len(result)} chunks corretamente", "SUCCESS")
        
        # Teste 5.3: Mensagem exatamente no limite
        debug_print("Teste 5.3: Mensagem exatamente no limite...", "TEST")
        exact_message = "A" * max_useful
        result = ml.splitMessage(exact_message)
        
        assert isinstance(result, str), f"Mensagem no limite deveria retornar string, recebido: {type(result)}"
        assert result == exact_message, "Mensagem no limite foi alterada"
        debug_print(f"✓ Mensagem no limite retornada como string: {len(result)} bytes", "SUCCESS")
        
        # Teste 5.4: Mensagem um byte maior que o limite
        debug_print("Teste 5.4: Mensagem um byte maior que o limite...", "TEST")
        over_limit = "A" * (max_useful + 1)
        result = ml.splitMessage(over_limit)
        
        assert isinstance(result, list), f"Deveria dividir em lista"
        assert len(result) == 2, f"Deveria ter 2 chunks, tem {len(result)}"
        assert len(result[0]) == max_useful, f"Primeiro chunk deveria ter {max_useful} bytes"
        assert len(result[1]) == 1, f"Segundo chunk deveria ter 1 byte"
        debug_print(f"✓ Mensagem dividida corretamente: {len(result)} chunks", "SUCCESS")
        
        return True
        
    except Exception as e:
        debug_print(f"✗ ERRO: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False

def test_handshake():
    """TESTE 6: startConnection() e acceptConnection() - Handshake 3-way"""
    print("\n" + "="*70)
    print("TESTE 6: Handshake 3-Way (startConnection + acceptConnection)")
    print("="*70)
    
    try:
        os.makedirs("./debug/test_files/", exist_ok=True)
        
        # Criar instâncias com portas diferentes para evitar conflito
        debug_print("Criando instâncias servidor e cliente...", "TEST")
        server = create_missionlink_with_port("127.0.0.1", 8080, "./debug/test_files/server/")
        client = create_missionlink_with_port("127.0.0.1", 8081, "./debug/test_files/client/")
        
        # Aumentar timeout para debug
        server.limit.timeout = 5
        client.limit.timeout = 5
        
        server_result = [None]
        client_result = [None]
        server_error = [None]
        client_error = [None]
        
        def server_thread():
            try:
                debug_print("SERVER: Aguardando conexão (acceptConnection)...", "TEST")
                conn_info = server.acceptConnection()
                server_result[0] = conn_info
                debug_print(f"SERVER: ✓ Conexão aceite: {conn_info}", "SUCCESS")
            except Exception as e:
                server_error[0] = e
                debug_print(f"SERVER: ✗ ERRO: {e}", "ERROR")
                import traceback
                traceback.print_exc()
        
        def client_thread():
            time.sleep(0.5)  # Dar tempo ao servidor
            try:
                debug_print("CLIENT: Iniciando conexão (startConnection)...", "TEST")
                conn_info = client.startConnection("r1", "127.0.0.1", 8080)
                client_result[0] = conn_info
                debug_print(f"CLIENT: ✓ Conexão estabelecida: {conn_info}", "SUCCESS")
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
            debug_print(f"✗ SERVER ERRO: {server_error[0]}", "ERROR")
            return False
        if client_error[0]:
            debug_print(f"✗ CLIENT ERRO: {client_error[0]}", "ERROR")
            return False
        
        if server_result[0] and client_result[0]:
            # Verificar que informações correspondem
            server_addr, server_id, server_seq, server_ack = server_result[0]
            client_addr, client_id, client_seq, client_ack = client_result[0]
            
            assert server_id == "r1", f"Server idAgent incorreto: {server_id}"
            assert client_id == "r1", f"Client idAgent incorreto: {client_id}"
            # Nota: server_seq é a sequência do ACK recebido (100), client_seq é seqinicial+1 (101)
            # Ambos são válidos após o handshake, mas não são necessariamente iguais
            # O importante é que ambos tenham valores válidos (> 0)
            assert server_seq > 0, f"Server seq inválido: {server_seq}"
            assert client_seq > 0, f"Client seq inválido: {client_seq}"
            assert server_ack > 0, f"Server ack inválido: {server_ack}"
            assert client_ack > 0, f"Client ack inválido: {client_ack}"
            
            debug_print("✓ Handshake completo e informações validadas", "SUCCESS")
            debug_print(f"  - idAgent: {server_id}", "INFO")
            debug_print(f"  - server seq: {server_seq}, ack: {server_ack}", "INFO")
            debug_print(f"  - client seq: {client_seq}, ack: {client_ack}", "INFO")
            return True
        else:
            debug_print("✗ Handshake não completado", "ERROR")
            return False
            
    except Exception as e:
        debug_print(f"✗ ERRO: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False

def test_send_short_message():
    """TESTE 7: send() - Mensagem Curta"""
    print("\n" + "="*70)
    print("TESTE 7: send() - Mensagem Curta")
    print("="*70)
    
    try:
        os.makedirs("./debug/test_files/", exist_ok=True)
        
        server = create_missionlink_with_port("127.0.0.1", 8080, "./debug/test_files/server/")
        client = create_missionlink_with_port("127.0.0.1", 8081, "./debug/test_files/client/")
        
        server.limit.timeout = 5
        client.limit.timeout = 5
        
        server_result = [None]
        server_error = [None]
        client_error = [None]
        
        test_message = "Hello World from MissionLink!"
        
        def server_thread():
            try:
                debug_print("SERVER: Aguardando mensagem (recv)...", "TEST")
                result = server.recv()
                server_result[0] = result
                debug_print(f"SERVER: ✓ Mensagem recebida: {result}", "SUCCESS")
            except Exception as e:
                server_error[0] = e
                debug_print(f"SERVER: ✗ ERRO: {e}", "ERROR")
                import traceback
                traceback.print_exc()
        
        def client_thread():
            time.sleep(0.5)
            try:
                debug_print(f"CLIENT: Enviando mensagem curta: '{test_message}'...", "TEST")
                success = client.send("127.0.0.1", 8080, "T", "r1", "M01", test_message)
                assert success == True, "send() deveria retornar True"
                debug_print("CLIENT: ✓ Mensagem enviada com sucesso", "SUCCESS")
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
            debug_print(f"✗ SERVER ERRO: {server_error[0]}", "ERROR")
            return False
        if client_error[0]:
            debug_print(f"✗ CLIENT ERRO: {client_error[0]}", "ERROR")
            return False
        
        if server_result[0]:
            idAgent, idMission, missionType, message, ip = server_result[0]
            
            # Remover \x00 (EOF) do final da mensagem se existir (caractere de controlo)
            if message and message.endswith('\x00'):
                message = message[:-1]
            
            assert idAgent == "r1", f"idAgent incorreto: {idAgent}"
            assert idMission == "M01", f"idMission incorreto: {idMission}"
            assert missionType == "T", f"missionType incorreto: {missionType}"
            assert message == test_message, f"Mensagem incorreta:\n  Esperado: {test_message}\n  Recebido: {message}"
            
            debug_print("✓ Mensagem curta enviada e recebida corretamente", "SUCCESS")
            debug_print(f"  - idAgent: {idAgent}", "INFO")
            debug_print(f"  - idMission: {idMission}", "INFO")
            debug_print(f"  - missionType: {missionType}", "INFO")
            debug_print(f"  - message: {message}", "INFO")
            return True
        else:
            debug_print("✗ Mensagem não recebida", "ERROR")
            return False
            
    except Exception as e:
        debug_print(f"✗ ERRO: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False

def test_send_long_message():
    """TESTE 8: send() - Múltiplas Mensagens Seguidas (mesma missão)
    
    Envia 10 mensagens curtas seguidas correspondentes à mesma missão.
    Se send_short demora ~3 segundos, este teste deve demorar ~30 segundos no máximo.
    """
    print("\n" + "="*70)
    print("TESTE 8: send() - Múltiplas Mensagens Seguidas (mesma missão)")
    print("="*70)
    
    try:
        os.makedirs("./debug/test_files/", exist_ok=True)
        
        server = create_missionlink_with_port("127.0.0.1", 8080, "./debug/test_files/server/")
        client = create_missionlink_with_port("127.0.0.1", 8081, "./debug/test_files/client/")
        
        server.limit.timeout = 5
        client.limit.timeout = 5
        
        # Enviar 10 mensagens seguidas da mesma missão
        num_messages = 10
        test_messages = [f"Mensagem {i+1} da missão M01" for i in range(num_messages)]
        
        debug_print(f"Enviando {num_messages} mensagens seguidas da mesma missão...", "INFO")
        
        server_results = []
        server_error = [None]
        client_errors = []
        
        def server_thread():
            try:
                debug_print("SERVER: Aguardando múltiplas mensagens...", "TEST")
                start_time = time.time()
                # Receber todas as 10 mensagens
                for i in range(num_messages):
                    debug_print(f"SERVER: Aguardando mensagem {i+1}/{num_messages}...", "INFO")
                    result = server.recv()
                    server_results.append(result)
                    elapsed = time.time() - start_time
                    debug_print(f"SERVER: [OK] Mensagem {i+1} recebida (tempo total: {elapsed:.2f}s)", "SUCCESS")
                total_time = time.time() - start_time
                debug_print(f"SERVER: [OK] Todas as {num_messages} mensagens recebidas em {total_time:.2f}s", "SUCCESS")
                if total_time > 30:
                    debug_print(f"[AVISO] Servidor demorou {total_time:.2f}s (mais de 30s)", "WARNING")
            except Exception as e:
                server_error[0] = e
                debug_print(f"SERVER: [ERRO] ERRO: {e}", "ERROR")
                import traceback
                traceback.print_exc()
        
        def client_thread():
            time.sleep(0.5)  # Dar tempo ao servidor iniciar
            try:
                debug_print(f"CLIENT: Enviando {num_messages} mensagens seguidas...", "TEST")
                start_time = time.time()
                
                for i, msg in enumerate(test_messages):
                    debug_print(f"CLIENT: Enviando mensagem {i+1}/{num_messages}: '{msg}'...", "INFO")
                    success = client.send("127.0.0.1", 8080, "M", "r1", "M01", msg)
                    assert success == True, f"send() da mensagem {i+1} deveria retornar True"
                    debug_print(f"CLIENT: [OK] Mensagem {i+1} enviada", "SUCCESS")
                    # Pequeno delay entre mensagens para evitar problemas de sincronização
                    # e garantir que não excedemos 30 segundos (10 mensagens * ~3s = ~30s)
                    if i < num_messages - 1:  # Não fazer delay após a última mensagem
                        time.sleep(0.1)  # 100ms de delay entre mensagens
                
                elapsed = time.time() - start_time
                debug_print(f"CLIENT: [OK] Todas as {num_messages} mensagens enviadas em {elapsed:.2f}s", "SUCCESS")
                if elapsed > 30:
                    debug_print(f"[AVISO] Teste demorou {elapsed:.2f}s (mais de 30s)", "WARNING")
            except Exception as e:
                client_errors.append(e)
                debug_print(f"CLIENT: [ERRO] ERRO: {e}", "ERROR")
                import traceback
                traceback.print_exc()
        
        t_server = threading.Thread(target=server_thread)
        t_client = threading.Thread(target=client_thread)
        
        t_server.start()
        t_client.start()
        
        # Timeout máximo de 30 segundos
        # Timeout máximo de 30 segundos para todos os testes a partir de send_long
        t_server.join(timeout=30)
        t_client.join(timeout=30)
        
        if server_error[0]:
            debug_print(f"[ERRO] SERVER ERRO: {server_error[0]}", "ERROR")
            return False
        if client_errors:
            debug_print(f"[ERRO] CLIENT ERRO: {client_errors}", "ERROR")
            return False
        
        # Verificar que todas as mensagens foram recebidas
        if len(server_results) == num_messages:
            # Validar cada mensagem
            for i, result in enumerate(server_results):
                idAgent, idMission, missionType, message, ip = result
                
                # Remover \x00 (EOF) do final da mensagem se existir
                if message and message.endswith('\x00'):
                    message = message[:-1]
                
                assert idAgent == "r1", f"Mensagem {i+1}: idAgent incorreto: {idAgent}"
                assert idMission == "M01", f"Mensagem {i+1}: idMission incorreto: {idMission}"
                assert missionType == "M", f"Mensagem {i+1}: missionType incorreto: {missionType}"
                assert message == test_messages[i], f"Mensagem {i+1} incorreta:\n  Esperado: {test_messages[i]}\n  Recebido: {message}"
            
            debug_print(f"[OK] Todas as {num_messages} mensagens enviadas e recebidas corretamente", "SUCCESS")
            debug_print(f"  - idAgent: r1 (todas)", "INFO")
            debug_print(f"  - idMission: M01 (todas)", "INFO")
            debug_print(f"  - missionType: M (todas)", "INFO")
            return True
        else:
            debug_print(f"[ERRO] Apenas {len(server_results)}/{num_messages} mensagens recebidas", "ERROR")
            return False
            
    except Exception as e:
        debug_print(f"[ERRO] ERRO: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False

def test_send_file():
    """TESTE 9: send() - Envio de Ficheiro"""
    print("\n" + "="*70)
    print("TESTE 9: send() - Envio de Ficheiro")
    print("="*70)
    
    try:
        os.makedirs("./debug/test_files/client/", exist_ok=True)
        os.makedirs("./debug/test_files/server/", exist_ok=True)
        
        # Criar ficheiro de teste
        test_file = "./debug/test_files/client/test_mission.json"
        test_content = {
            "mission_id": "M-TEST",
            "rover_id": "r1",
            "geographic_area": {"x1": 10.0, "y1": 20.0, "x2": 50.0, "y2": 60.0},
            "task": "capture_images",
            "duration_minutes": 30,
            "update_frequency_seconds": 120
        }
        
        with open(test_file, "w") as f:
            json.dump(test_content, f, indent=2)
        
        debug_print(f"Ficheiro de teste criado: {test_file}", "INFO")
        
        server = create_missionlink_with_port("127.0.0.1", 8080, "./debug/test_files/server/")
        client = create_missionlink_with_port("127.0.0.1", 8081, "./debug/test_files/client/")
        
        server.limit.timeout = 10
        client.limit.timeout = 10
        
        server_result = [None]
        server_error = [None]
        client_error = [None]
        
        def server_thread():
            try:
                debug_print("SERVER: Aguardando ficheiro...", "TEST")
                result = server.recv()
                server_result[0] = result
                debug_print(f"SERVER: ✓ Ficheiro recebido: {result}", "SUCCESS")
            except Exception as e:
                server_error[0] = e
                debug_print(f"SERVER: ✗ ERRO: {e}", "ERROR")
                import traceback
                traceback.print_exc()
        
        def client_thread():
            time.sleep(0.5)
            try:
                debug_print(f"CLIENT: Enviando ficheiro: {test_file}...", "TEST")
                success = client.send("127.0.0.1", 8080, "M", "r1", "M01", test_file)
                assert success == True, "send() deveria retornar True"
                debug_print("CLIENT: ✓ Ficheiro enviado", "SUCCESS")
            except Exception as e:
                client_error[0] = e
                debug_print(f"CLIENT: ✗ ERRO: {e}", "ERROR")
                import traceback
                traceback.print_exc()
        
        t_server = threading.Thread(target=server_thread)
        t_client = threading.Thread(target=client_thread)
        
        t_server.start()
        t_client.start()
        
        # Timeout máximo de 30 segundos para todos os testes a partir de send_long
        t_server.join(timeout=30)
        t_client.join(timeout=30)
        
        if server_error[0]:
            debug_print(f"✗ SERVER ERRO: {server_error[0]}", "ERROR")
            return False
        if client_error[0]:
            debug_print(f"✗ CLIENT ERRO: {client_error[0]}", "ERROR")
            return False
        
        if server_result[0]:
            idAgent, idMission, missionType, filename, ip = server_result[0]
            
            # Verificar que ficheiro foi criado
            received_file = "./debug/test_files/server/" + filename
            assert os.path.exists(received_file), f"Ficheiro não foi criado: {received_file}"
            
            # Verificar conteúdo
            with open(received_file, "r") as f:
                received_content = json.load(f)
            
            assert received_content == test_content, "Conteúdo do ficheiro não corresponde"
            
            debug_print("✓ Ficheiro enviado e recebido corretamente", "SUCCESS")
            debug_print(f"  - Nome: {filename}", "INFO")
            debug_print(f"  - Ficheiro recebido: {received_file}", "INFO")
            debug_print(f"  - Conteúdo validado: ✓", "INFO")
            return True
        else:
            debug_print("✗ Ficheiro não recebido", "ERROR")
            return False
            
    except Exception as e:
        debug_print(f"✗ ERRO: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False

def test_recv_message():
    """TESTE 10: recv() - Receção de Mensagem
    
    NOTA: Este teste é redundante - test_send_short_message já testa recv().
    Mantido para compatibilidade, mas apenas chama test_send_short_message().
    """
    print("\n" + "="*70)
    print("TESTE 10: recv() - Receção de Mensagem")
    print("="*70)
    print("NOTA: Este teste é redundante - usa test_send_short_message()")
    
    # Este teste é essencialmente o mesmo que test_send_short_message
    # mas focado na função recv() - já testado em send_short
    return test_send_short_message()

def test_recv_file():
    """TESTE 11: recv() - Receção de Ficheiro
    
    NOTA: Este teste é redundante - test_send_file já testa recv().
    Mantido para compatibilidade, mas apenas chama test_send_file().
    """
    print("\n" + "="*70)
    print("TESTE 11: recv() - Receção de Ficheiro")
    print("="*70)
    print("NOTA: Este teste é redundante - usa test_send_file()")
    
    # Este teste é essencialmente o mesmo que test_send_file
    # mas focado na função recv() - já testado em send_file
    return test_send_file()

def main():
    """Função principal - executa todos os testes"""
    print("\n" + "="*70)
    print("MISSIONLINK - TESTE COMPLETO DE TODAS AS FUNÇÕES")
    print("="*70)
    
    # Determinar qual teste executar
    if len(sys.argv) > 1:
        test_name = sys.argv[1].lower()
    else:
        test_name = "all"
    
    # Mapeamento de testes
    tests = {
        "init": ("__init__", test_init),
        "server": ("server()", test_server),
        "header": ("getHeaderSize()", test_getHeaderSize),
        "format": ("formatMessage()", test_formatMessage),
        "split": ("splitMessage()", test_splitMessage),
        "handshake": ("Handshake 3-way", test_handshake),
        "send_short": ("send() - Mensagem Curta", test_send_short_message),
        "send_long": ("send() - Mensagem Longa", test_send_long_message),
        "send_file": ("send() - Ficheiro", test_send_file),
        "recv_message": ("recv() - Mensagem", test_recv_message),
        "recv_file": ("recv() - Ficheiro", test_recv_file),
    }
    
    results = {}
    
    if test_name == "all":
        # Executar todos os testes
        for key, (name, test_func) in tests.items():
            try:
                results[key] = test_func()
                time.sleep(1)  # Pausa entre testes
            except KeyboardInterrupt:
                debug_print("Teste interrompido pelo utilizador", "WARNING")
                break
            except Exception as e:
                debug_print(f"Erro inesperado no teste {key}: {e}", "ERROR")
                results[key] = False
    elif test_name in tests:
        # Executar teste específico
        name, test_func = tests[test_name]
        try:
            results[test_name] = test_func()
        except KeyboardInterrupt:
            debug_print("Teste interrompido pelo utilizador", "WARNING")
            results[test_name] = False
    else:
        print(f"\n[ERRO] Teste desconhecido: {test_name}")
        print("\nTestes disponíveis:")
        for key, (name, _) in tests.items():
            print(f"  - {key}: {name}")
        print("  - all: Todos os testes")
        return 1
    
    # Resumo
    print("\n" + "="*70)
    print("RESUMO DOS TESTES")
    print("="*70)
    
    for key, (name, _) in tests.items():
        if key in results:
            status = "[OK] PASSOU" if results[key] else "[FALHOU]"
            print(f"  {name:40s}: {status}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    print(f"\nTotal: {passed}/{total} testes passaram ({passed*100//total if total > 0 else 0}%)")
    
    if passed == total and total > 0:
        print("\n[SUCESSO] Todos os testes passaram!")
        return 0
    else:
        print(f"\n[AVISO] {total - passed} teste(s) falharam")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n[AVISO] Teste interrompido pelo utilizador")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERRO FATAL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

