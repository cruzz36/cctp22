# Guia de Debug para MissionLink.py

## Índice
1. [Métodos de Debug](#métodos-de-debug)
2. [Ativar Prints de Debug](#ativar-prints-de-debug)
3. [Usar Python Debugger (pdb)](#usar-python-debugger-pdb)
4. [Criar Scripts de Teste](#criar-scripts-de-teste)
5. [Usar Logging](#usar-logging)
6. [Debug Específico por Função](#debug-específico-por-função)
7. [Problemas Comuns e Soluções](#problemas-comuns-e-soluções)

---

## 1. Métodos de Debug

### 1.1 Prints de Debug (Mais Simples)

**Vantagens**: Rápido, não requer ferramentas especiais  
**Desvantagens**: Polui o código, precisa remover depois

### 1.2 Python Debugger (pdb) (Mais Poderoso)

**Vantagens**: Controlo total, inspeção de variáveis, step-by-step  
**Desvantagens**: Requer conhecimento do pdb

### 1.3 Logging (Mais Profissional)

**Vantagens**: Níveis de log, pode desativar facilmente, formatação  
**Desvantagens**: Requer configuração inicial

### 1.4 Scripts de Teste (Mais Organizado)

**Vantagens**: Testes isolados, reproduzíveis  
**Desvantagens**: Requer escrever código de teste

---

## 2. Ativar Prints de Debug

### 2.1 Descomentar Prints Existentes

O código já tem vários prints comentados. Podes descomentá-los:

```python
# No método startConnection(), linha ~213:
print("SYN ENVIADO")  # Descomentar

# Linha ~242:
print("RECEBEU O SYNACK CORRETO")  # Descomentar

# Linha ~253:
print(f"Sending ACK: seq={seqinicial}")  # Descomentar
```

### 2.2 Adicionar Novos Prints Estratégicos

**Exemplo 1: Debug do Handshake**
```python
def startConnection(self, idAgent, destAddress, destPort, retryLimit=5):
    seqinicial = 100
    retries = 0
    
    print(f"[DEBUG] Iniciando handshake com {destAddress}:{destPort}")
    print(f"[DEBUG] idAgent={idAgent}, seqinicial={seqinicial}")
    
    while retries < retryLimit:
        try:
            # Send SYN
            print(f"[DEBUG] Enviando SYN (tentativa {retries + 1}/{retryLimit})")
            self.sock.sendto(...)
            
            # Wait for SYN-ACK
            print("[DEBUG] Aguardando SYN-ACK...")
            message, _ = self.sock.recvfrom(self.limit.buffersize)
            lista = message.decode().split("|")
            print(f"[DEBUG] Recebido: {lista}")
            
            if lista[flagPos] == self.synackkey:
                print("[DEBUG] SYN-ACK recebido corretamente!")
                # ...
```

**Exemplo 2: Debug do Envio de Dados**
```python
def send(self, ip, port, missionType, idAgent, idMission, message):
    print(f"[DEBUG] send() chamado:")
    print(f"  - IP: {ip}, Port: {port}")
    print(f"  - missionType: {missionType}")
    print(f"  - idAgent: {idAgent}, idMission: {idMission}")
    print(f"  - message length: {len(message)} bytes")
    
    # Estabelecer conexão
    print("[DEBUG] Estabelecendo conexão...")
    _, idAgent, seq, ack = self.startConnection(idAgent, ip, port)
    print(f"[DEBUG] Conexão estabelecida: seq={seq}, ack={ack}")
    
    # Enviar dados
    if message.endswith(".json"):
        print(f"[DEBUG] Enviando ficheiro: {message}")
        # ...
    else:
        print(f"[DEBUG] Enviando mensagem: {message[:50]}...")
        # ...
```

**Exemplo 3: Debug da Receção**
```python
def recv(self):
    print("[DEBUG] recv() iniciado - aguardando conexão...")
    (ipDest, portDest), idAgent, seq, ack = self.acceptConnection()
    print(f"[DEBUG] Conexão aceite: {ipDest}:{portDest}, idAgent={idAgent}, seq={seq}")
    
    # Receber primeira mensagem
    print("[DEBUG] Aguardando primeira mensagem...")
    firstMessage, (ip, port) = self.sock.recvfrom(self.limit.buffersize)
    lista = firstMessage.decode().split("|")
    print(f"[DEBUG] Primeira mensagem recebida: {lista}")
    print(f"  - flag: {lista[flagPos]}")
    print(f"  - idMission: {lista[idMissionPos]}")
    print(f"  - seq: {lista[seqPos]}")
    print(f"  - missionType: {lista[missionTypePos]}")
    # ...
```

### 2.3 Print de Mensagens Completas

```python
# No formatMessage(), adicionar:
def formatMessage(self, missionType, flag, idMission, seqNum, ackNum, message):
    formatted = f"{flag}|{idMission}|{seqNum}|{ackNum}|{len(message)}|{missionType}|{message}"
    print(f"[DEBUG] Mensagem formatada: {formatted[:100]}...")  # Primeiros 100 chars
    return formatted.encode()
```

### 2.4 Print de Validações

```python
# No recv(), quando valida mensagens:
if (
    len(lista) == 7 and
    (idMission is None or lista[idMissionPos] == idMission) and
    lista[seqPos] == str(seq + 1) and
    ipDest == ip and
    port == portDest
):
    print(f"[DEBUG] Validação PASSED:")
    print(f"  - len(lista) == 7: {len(lista) == 7}")
    print(f"  - idMission match: {idMission is None or lista[idMissionPos] == idMission}")
    print(f"  - seq match: {lista[seqPos]} == {seq + 1}")
    print(f"  - IP match: {ipDest} == {ip}")
    print(f"  - Port match: {portDest} == {port}")
else:
    print(f"[DEBUG] Validação FAILED:")
    print(f"  - len(lista): {len(lista)} (esperado: 7)")
    print(f"  - idMission: {lista[idMissionPos] if len(lista) > 1 else 'N/A'} (esperado: {idMission})")
    print(f"  - seq: {lista[seqPos] if len(lista) > 2 else 'N/A'} (esperado: {seq + 1})")
    print(f"  - IP: {ip} (esperado: {ipDest})")
    print(f"  - Port: {port} (esperado: {portDest})")
```

---

## 3. Usar Python Debugger (pdb)

### 3.1 Debug Básico com breakpoint()

**Adicionar breakpoint no código:**
```python
def startConnection(self, idAgent, destAddress, destPort, retryLimit=5):
    seqinicial = 100
    retries = 0
    
    breakpoint()  # Para aqui e abre debugger
    
    while retries < retryLimit:
        # ...
```

**Quando o código parar no breakpoint:**
- `n` (next): Próxima linha
- `s` (step): Entra em funções
- `c` (continue): Continua execução
- `p variável`: Imprime valor da variável
- `pp variável`: Imprime formatado
- `l` (list): Mostra código ao redor
- `q` (quit): Sair do debugger

### 3.2 Debug Interativo

**No terminal Python:**
```python
import pdb
from protocol import MissionLink

# Criar instância
ml = MissionLink.MissionLink("127.0.0.1")

# Iniciar debugger
pdb.set_trace()

# Agora podes chamar métodos e debuggar
ml.startConnection("r1", "127.0.0.1", 8080)
```

### 3.3 Debug com pdb.run()

```python
import pdb
from protocol import MissionLink

ml = MissionLink.MissionLink("127.0.0.1")

# Debuggar uma função específica
pdb.run('ml.startConnection("r1", "127.0.0.1", 8080)')
```

### 3.4 Debug Post-Mortem (Após Erro)

```python
import pdb

try:
    # Seu código que pode dar erro
    ml.send("127.0.0.1", 8080, "T", "r1", "M01", "teste")
except Exception as e:
    print(f"Erro: {e}")
    pdb.post_mortem()  # Abre debugger no ponto do erro
```

---

## 4. Criar Scripts de Teste

### 4.1 Script de Teste Básico

Criar ficheiro `test_missionlink.py`:

```python
#!/usr/bin/env python3
"""
Script de teste para debug do MissionLink
"""

from protocol import MissionLink
import time
import threading

def test_handshake():
    """Testa apenas o handshake"""
    print("=== TESTE: Handshake ===")
    
    # Servidor
    server = MissionLink.MissionLink("127.0.0.1", "./server_files/")
    
    # Cliente
    client = MissionLink.MissionLink("127.0.0.1", "./client_files/")
    
    def server_thread():
        print("[SERVER] Aguardando conexão...")
        conn_info = server.acceptConnection()
        print(f"[SERVER] Conexão estabelecida: {conn_info}")
    
    def client_thread():
        time.sleep(0.5)  # Dar tempo ao servidor
        print("[CLIENT] Iniciando conexão...")
        conn_info = client.startConnection("r1", "127.0.0.1", 8080)
        print(f"[CLIENT] Conexão estabelecida: {conn_info}")
    
    # Executar em threads separadas
    t1 = threading.Thread(target=server_thread)
    t2 = threading.Thread(target=client_thread)
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
    print("=== TESTE CONCLUÍDO ===\n")

def test_send_receive():
    """Testa envio e receção de mensagem"""
    print("=== TESTE: Envio/Receção ===")
    
    server = MissionLink.MissionLink("127.0.0.1", "./server_files/")
    client = MissionLink.MissionLink("127.0.0.1", "./client_files/")
    
    def server_thread():
        print("[SERVER] Aguardando mensagem...")
        result = server.recv()
        print(f"[SERVER] Recebido: {result}")
    
    def client_thread():
        time.sleep(0.5)
        print("[CLIENT] Enviando mensagem...")
        client.send("127.0.0.1", 8080, "T", "r1", "M01", "Hello World!")
        print("[CLIENT] Mensagem enviada")
    
    t1 = threading.Thread(target=server_thread)
    t2 = threading.Thread(target=client_thread)
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
    print("=== TESTE CONCLUÍDO ===\n")

if __name__ == "__main__":
    print("Iniciando testes de debug do MissionLink...\n")
    
    # Teste 1: Handshake
    test_handshake()
    
    # Teste 2: Envio/Receção
    # test_send_receive()
    
    print("Todos os testes concluídos!")
```

### 4.2 Executar Testes

```bash
# No terminal
cd CC/tp2
python test_missionlink.py
```

### 4.3 Teste com Timeout Aumentado

Para debug, podes aumentar o timeout temporariamente:

```python
# No __init__ do MissionLink, temporariamente:
self.limit.timeout = 10  # 10 segundos em vez de 2
```

---

## 5. Usar Logging

### 5.1 Configurar Logging

Adicionar no início do ficheiro `MissionLink.py`:

```python
import logging

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,  # Nível: DEBUG, INFO, WARNING, ERROR
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('missionlink_debug.log'),  # Ficheiro de log
        logging.StreamHandler()  # Também imprime no console
    ]
)

logger = logging.getLogger('MissionLink')
```

### 5.2 Usar Logging nas Funções

```python
def startConnection(self, idAgent, destAddress, destPort, retryLimit=5):
    logger.debug(f"Iniciando handshake: idAgent={idAgent}, dest={destAddress}:{destPort}")
    
    seqinicial = 100
    retries = 0
    
    while retries < retryLimit:
        try:
            logger.debug(f"Enviando SYN (tentativa {retries + 1}/{retryLimit})")
            self.sock.sendto(...)
            
            logger.debug("Aguardando SYN-ACK...")
            message, _ = self.sock.recvfrom(self.limit.buffersize)
            lista = message.decode().split("|")
            logger.debug(f"Recebido: flag={lista[0] if len(lista) > 0 else 'N/A'}")
            
            if lista[flagPos] == self.synackkey:
                logger.info("SYN-ACK recebido corretamente!")
                # ...
            else:
                logger.warning(f"Flag incorreta: esperado Z, recebido {lista[flagPos]}")
                
        except socket.timeout:
            logger.warning(f"Timeout ao aguardar SYN-ACK (tentativa {retries + 1})")
            retries += 1
        except Exception as e:
            logger.error(f"Erro no handshake: {e}", exc_info=True)
            retries += 1
```

### 5.3 Controlar Nível de Log

```python
# Para desativar logs de debug (só mostrar erros):
logging.getLogger('MissionLink').setLevel(logging.ERROR)

# Para ativar tudo:
logging.getLogger('MissionLink').setLevel(logging.DEBUG)
```

---

## 6. Debug Específico por Função

### 6.1 Debug do `startConnection()`

**Problemas comuns**: Timeout, SYN-ACK não recebido

**Debug específico**:
```python
def startConnection(self, idAgent, destAddress, destPort, retryLimit=5):
    seqinicial = 100
    retries = 0
    
    print(f"[DEBUG startConnection] Início:")
    print(f"  - idAgent: {idAgent}")
    print(f"  - Destino: {destAddress}:{destPort}")
    print(f"  - seqinicial: {seqinicial}")
    print(f"  - timeout: {self.limit.timeout}s")
    
    while retries < retryLimit:
        print(f"\n[DEBUG startConnection] Tentativa {retries + 1}/{retryLimit}")
        
        try:
            # Send SYN
            syn_msg = f"{self.synkey}|{idAgent}|{seqinicial}|0|_|0|-.-"
            print(f"[DEBUG] Enviando SYN: {syn_msg}")
            self.sock.sendto(syn_msg.encode(), (destAddress, destPort))
            
            # Wait for SYN-ACK
            print("[DEBUG] Aguardando SYN-ACK (timeout: {}s)...".format(self.limit.timeout))
            start_time = time.time()
            
            try:
                message, addr = self.sock.recvfrom(self.limit.buffersize)
                elapsed = time.time() - start_time
                print(f"[DEBUG] Recebido após {elapsed:.2f}s de: {addr}")
                
                lista = message.decode().split("|")
                print(f"[DEBUG] Mensagem decodificada: {lista}")
                
                if len(lista) < 7:
                    print(f"[DEBUG] ERRO: Mensagem malformada (len={len(lista)}, esperado=7)")
                    retries += 1
                    continue
                
                print(f"[DEBUG] Flag recebida: {lista[flagPos]} (esperado: {self.synackkey})")
                
                if lista[flagPos] == self.synackkey:
                    print("[DEBUG] ✓ SYN-ACK correto!")
                    # ...
                else:
                    print(f"[DEBUG] ✗ Flag incorreta, continuando loop...")
                    # ...
                    
            except socket.timeout:
                elapsed = time.time() - start_time
                print(f"[DEBUG] TIMEOUT após {elapsed:.2f}s")
                continue
                
        except Exception as e:
            print(f"[DEBUG] EXCEÇÃO: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            retries += 1
```

### 6.2 Debug do `send()`

**Problemas comuns**: ACK não recebido, timeout, validação falha

**Debug específico**:
```python
def send(self, ip, port, missionType, idAgent, idMission, message):
    print(f"\n[DEBUG send] === INÍCIO ===")
    print(f"  - Destino: {ip}:{port}")
    print(f"  - missionType: {missionType}")
    print(f"  - idAgent: {idAgent}")
    print(f"  - idMission: {idMission}")
    print(f"  - message type: {type(message)}")
    print(f"  - message length: {len(str(message))} bytes")
    print(f"  - É ficheiro: {str(message).endswith('.json')}")
    
    # Estabelecer conexão
    print("\n[DEBUG send] Estabelecendo conexão...")
    try:
        _, idAgent, seq, ack = self.startConnection(idAgent, ip, port)
        print(f"[DEBUG send] ✓ Conexão estabelecida: seq={seq}, ack={ack}")
    except Exception as e:
        print(f"[DEBUG send] ✗ Erro ao estabelecer conexão: {e}")
        raise
    
    # Enviar dados
    if str(message).endswith(".json"):
        print(f"\n[DEBUG send] Modo: Envio de FICHEIRO")
        print(f"  - Ficheiro: {message}")
        
        # Enviar nome do ficheiro
        print("[DEBUG send] Enviando nome do ficheiro...")
        chunk_count = 0
        
        while True:
            chunk_count += 1
            print(f"[DEBUG send] Tentativa {chunk_count} de enviar nome do ficheiro")
            self.sock.sendto(self.formatMessage(...), (ip, port))
            
            try:
                text, (responseIp, responsePort) = self.sock.recvfrom(self.limit.buffersize)
                lista = text.decode().split("|")
                print(f"[DEBUG send] Resposta recebida: {lista}")
                
                if (
                    responseIp == ip and
                    responsePort == port and
                    lista[flagPos] == self.ackkey and
                    lista[ackPos] == str(seq) and
                    lista[idMissionPos] == idMission
                ):
                    print("[DEBUG send] ✓ ACK do nome do ficheiro recebido!")
                    seq += 1
                    break
                else:
                    print(f"[DEBUG send] ✗ Validação falhou:")
                    print(f"    - IP: {responseIp} == {ip}: {responseIp == ip}")
                    print(f"    - Port: {responsePort} == {port}: {responsePort == port}")
                    print(f"    - Flag: {lista[flagPos] if len(lista) > 0 else 'N/A'} == {self.ackkey}")
                    print(f"    - ACK: {lista[ackPos] if len(lista) > 3 else 'N/A'} == {seq}")
                    print(f"    - idMission: {lista[idMissionPos] if len(lista) > 1 else 'N/A'} == {idMission}")
                    
            except socket.timeout:
                print("[DEBUG send] TIMEOUT ao aguardar ACK do nome do ficheiro")
                continue
```

### 6.3 Debug do `recv()`

**Problemas comuns**: Mensagem malformada, validação falha, timeout

**Debug específico**:
```python
def recv(self):
    print("\n[DEBUG recv] === INÍCIO ===")
    
    # Estabelecer conexão
    print("[DEBUG recv] Aguardando conexão...")
    try:
        (ipDest, portDest), idAgent, seq, ack = self.acceptConnection()
        print(f"[DEBUG recv] ✓ Conexão estabelecida:")
        print(f"    - Origem: {ipDest}:{portDest}")
        print(f"    - idAgent: {idAgent}")
        print(f"    - seq: {seq}, ack: {ack}")
    except Exception as e:
        print(f"[DEBUG recv] ✗ Erro ao aceitar conexão: {e}")
        raise
    
    idMission = None
    fileName = None
    missionType = ""
    
    # Receber primeira mensagem
    print("\n[DEBUG recv] Aguardando primeira mensagem...")
    firstMessage = None
    attempts = 0
    
    while firstMessage == None:
        attempts += 1
        print(f"[DEBUG recv] Tentativa {attempts} de receber primeira mensagem")
        
        try:
            firstMessage, (ip, port) = self.sock.recvfrom(self.limit.buffersize)
            print(f"[DEBUG recv] Dados recebidos de {ip}:{port}")
            print(f"[DEBUG recv] Tamanho: {len(firstMessage)} bytes")
            
            lista = firstMessage.decode().split("|")
            print(f"[DEBUG recv] Mensagem decodificada: {lista}")
            print(f"[DEBUG recv] Número de campos: {len(lista)}")
            
            if len(lista) < 7:
                print(f"[DEBUG recv] ✗ Mensagem malformada (len={len(lista)}, esperado=7)")
                firstMessage = None
                continue
            
            print(f"[DEBUG recv] Validações:")
            print(f"    - IP: {ip} == {ipDest}: {ip == ipDest}")
            print(f"    - Port: {port} == {portDest}: {port == portDest}")
            print(f"    - seq: {lista[seqPos]} == {seq + 1}: {lista[seqPos] == str(seq + 1)}")
            
            if (
                ip == ipDest and 
                port == portDest and
                lista[seqPos] == str(seq + 1)
            ):
                print("[DEBUG recv] ✓ Validação passou!")
                
                if idMission is None:
                    idMission = lista[idMissionPos]
                    print(f"[DEBUG recv] idMission extraído: {idMission}")
                
                missionType = lista[missionTypePos]
                print(f"[DEBUG recv] missionType: {missionType}")
                
                seq += 1
                ack = seq
                
                if lista[messagePos].endswith(".json"):
                    fileName = lista[messagePos]
                    print(f"[DEBUG recv] É FICHEIRO: {fileName}")
                else:
                    firstMessage = lista[messagePos]
                    print(f"[DEBUG recv] É MENSAGEM: {firstMessage[:50]}...")
                
                # Enviar ACK
                print("[DEBUG recv] Enviando ACK...")
                self.sock.sendto(self.formatMessage(None, self.ackkey, idMission, seq, ack, self.eofkey), (ip, port))
                print("[DEBUG recv] ✓ ACK enviado")
                break
            else:
                print("[DEBUG recv] ✗ Validação falhou, resetando firstMessage")
                firstMessage = None
                
        except socket.timeout:
            print("[DEBUG recv] TIMEOUT ao aguardar primeira mensagem")
            firstMessage = None
            continue
        except Exception as e:
            print(f"[DEBUG recv] EXCEÇÃO: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            firstMessage = None
            continue
```

---

## 7. Problemas Comuns e Soluções

### 7.1 "Timeout ao aguardar SYN-ACK"

**Causas possíveis**:
- Servidor não está a correr
- Firewall bloqueia UDP
- IP/porta incorretos
- Timeout muito curto

**Debug**:
```python
# Verificar se servidor está a correr
print(f"[DEBUG] Tentando conectar a {destAddress}:{destPort}")

# Verificar timeout
print(f"[DEBUG] Timeout configurado: {self.limit.timeout}s")

# Tentar ping primeiro
import subprocess
result = subprocess.run(['ping', '-c', '1', destAddress], capture_output=True)
print(f"[DEBUG] Ping resultado: {result.returncode}")
```

### 7.2 "Mensagem malformada"

**Causas possíveis**:
- Dados corrompidos na rede
- Encoding incorreto
- Mensagem truncada

**Debug**:
```python
# Ver mensagem raw
print(f"[DEBUG] Mensagem raw (bytes): {message}")
print(f"[DEBUG] Mensagem raw (hex): {message.hex()}")

# Tentar decodificar
try:
    decoded = message.decode('utf-8')
    print(f"[DEBUG] Decodificado: {decoded}")
except UnicodeDecodeError as e:
    print(f"[DEBUG] Erro de decodificação: {e}")
    # Tentar outros encodings
    for encoding in ['latin-1', 'ascii', 'cp1252']:
        try:
            decoded = message.decode(encoding)
            print(f"[DEBUG] Decodificado com {encoding}: {decoded}")
            break
        except:
            pass
```

### 7.3 "Validação falhou: IP/Port incorretos"

**Causas possíveis**:
- ACK vem de outro processo
- Múltiplas instâncias a correr
- IP/porta mudaram

**Debug**:
```python
print(f"[DEBUG] Esperado: {ip}:{port}")
print(f"[DEBUG] Recebido: {responseIp}:{responsePort}")
print(f"[DEBUG] Match IP: {responseIp == ip}")
print(f"[DEBUG] Match Port: {responsePort == port}")

# Ver todas as conexões UDP na porta
import subprocess
result = subprocess.run(['netstat', '-an'], capture_output=True, text=True)
print(f"[DEBUG] Conexões UDP na porta {port}:")
for line in result.stdout.split('\n'):
    if f':{port}' in line and 'UDP' in line:
        print(f"  {line}")
```

### 7.4 "Sequência incorreta"

**Causas possíveis**:
- Pacote perdido
- Retransmissão não funcionou
- Sequência não incrementada

**Debug**:
```python
print(f"[DEBUG] Sequência esperada: {seq + 1}")
print(f"[DEBUG] Sequência recebida: {lista[seqPos] if len(lista) > seqPos else 'N/A'}")
print(f"[DEBUG] Sequência atual (seq): {seq}")
print(f"[DEBUG] Último ACK (ack): {ack}")

# Ver histórico de sequências
if not hasattr(self, '_seq_history'):
    self._seq_history = []
self._seq_history.append((seq, lista[seqPos] if len(lista) > seqPos else None))
print(f"[DEBUG] Histórico de sequências: {self._seq_history[-10:]}")  # Últimos 10
```

### 7.5 "idMission não corresponde"

**Causas possíveis**:
- Múltiplas missões simultâneas
- idMission extraído incorretamente
- Mensagem de outra conexão

**Debug**:
```python
print(f"[DEBUG] idMission esperado: {idMission}")
print(f"[DEBUG] idMission recebido: {lista[idMissionPos] if len(lista) > idMissionPos else 'N/A'}")
print(f"[DEBUG] idMission é None: {idMission is None}")

# Ver quando idMission foi definido
if not hasattr(self, '_idmission_set'):
    self._idmission_set = False
if idMission is not None and not self._idmission_set:
    print(f"[DEBUG] idMission definido pela primeira vez: {idMission}")
    self._idmission_set = True
```

---

## 8. Ferramentas Úteis

### 8.1 Wireshark (Captura de Pacotes)

**Instalar**: `sudo apt install wireshark` (Linux) ou download do site

**Usar**:
1. Abrir Wireshark
2. Selecionar interface de rede
3. Filtrar: `udp.port == 8080`
4. Ver pacotes em tempo real

**Ver formato das mensagens**:
- Clicar num pacote UDP
- Ver "Data" para ver conteúdo da mensagem

### 8.2 netcat (Teste Manual)

**Enviar mensagem manual**:
```bash
# Servidor (recebe)
nc -u -l 8080

# Cliente (envia)
echo "D|M01|101|101|5|T|teste" | nc -u 127.0.0.1 8080
```

### 8.3 tcpdump (Captura de Pacotes CLI)

```bash
# Capturar pacotes UDP na porta 8080
sudo tcpdump -i any -n udp port 8080 -X

# Salvar em ficheiro
sudo tcpdump -i any -n udp port 8080 -w capture.pcap

# Ler ficheiro
tcpdump -r capture.pcap -X
```

---

## 9. Checklist de Debug

Antes de começar a debuggar, verifica:

- [ ] Servidor está a correr?
- [ ] IP e porta estão corretos?
- [ ] Firewall permite UDP na porta 8080?
- [ ] Timeout é suficiente para a rede?
- [ ] Não há múltiplas instâncias a correr?
- [ ] Mensagens estão bem formatadas?
- [ ] Encoding está correto (UTF-8)?
- [ ] Validações estão a funcionar?

---

## 10. Exemplo Completo de Debug Session

```python
#!/usr/bin/env python3
"""
Exemplo completo de sessão de debug
"""

import time
import threading
from protocol import MissionLink

# Ativar prints de debug
DEBUG = True

def debug_print(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}")

# Criar instâncias
debug_print("Criando instâncias...")
server = MissionLink.MissionLink("127.0.0.1", "./server_files/")
client = MissionLink.MissionLink("127.0.0.1", "./client_files/")

# Aumentar timeout para debug
server.limit.timeout = 5
client.limit.timeout = 5

def server_side():
    debug_print("SERVER: Iniciando...")
    try:
        debug_print("SERVER: Aguardando conexão...")
        conn = server.acceptConnection()
        debug_print(f"SERVER: Conexão aceite: {conn}")
        
        debug_print("SERVER: Aguardando mensagem...")
        result = server.recv()
        debug_print(f"SERVER: Recebido: {result}")
        
    except Exception as e:
        debug_print(f"SERVER: ERRO: {e}")
        import traceback
        traceback.print_exc()

def client_side():
    time.sleep(1)  # Dar tempo ao servidor
    debug_print("CLIENT: Iniciando...")
    try:
        debug_print("CLIENT: Conectando...")
        conn = client.startConnection("r1", "127.0.0.1", 8080)
        debug_print(f"CLIENT: Conexão estabelecida: {conn}")
        
        debug_print("CLIENT: Enviando mensagem...")
        client.send("127.0.0.1", 8080, "T", "r1", "M01", "Hello from client!")
        debug_print("CLIENT: Mensagem enviada")
        
    except Exception as e:
        debug_print(f"CLIENT: ERRO: {e}")
        import traceback
        traceback.print_exc()

# Executar
t1 = threading.Thread(target=server_side)
t2 = threading.Thread(target=client_side)

t1.start()
t2.start()

t1.join()
t2.join()

debug_print("Sessão de debug concluída")
```

---

**Dica Final**: Começa sempre com prints simples. Se precisares de mais controlo, usa pdb. Para produção, usa logging.

