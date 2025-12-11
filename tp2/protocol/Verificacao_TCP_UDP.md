# Verificação: TelemetryStream (TCP) vs MissionLink (UDP)

Este documento explica como podemos confirmar que o **TelemetryStream (TS)** usa **TCP** e o **MissionLink (ML)** usa **UDP**, baseando-se no código implementado.

## 1. Evidência Principal: Criação do Socket

### TelemetryStream (TCP)

**Ficheiro**: `CC/tp2/protocol/TelemetryStream.py`

**Linha 29**:
```python
self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
```

**Evidência**: `socket.SOCK_STREAM` indica **TCP**
- `SOCK_STREAM` = TCP (Transmission Control Protocol)
- TCP é orientado a conexão (connection-oriented)
- TCP garante entrega ordenada e confiável dos dados

### MissionLink (UDP)

**Ficheiro**: `CC/tp2/protocol/MissionLink.py`

**Linha 34**:
```python
self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
```

**Evidência**: `socket.SOCK_DGRAM` indica **UDP**
- `SOCK_DGRAM` = UDP (User Datagram Protocol)
- UDP é sem conexão (connectionless)
- UDP não garante entrega ou ordem, mas é mais rápido

---

## 2. Evidência Secundária: Métodos de Comunicação

### TelemetryStream (TCP) - Métodos Orientados a Conexão

#### Servidor TCP:
```python
# Linha 114: Colocar socket em modo listening
self.socket.listen()

# Linha 120: Aceitar conexões TCP
clientSocket, (ip, _) = self.socket.accept()
```

**Características TCP**:
- `listen()`: Coloca o socket em modo servidor, aguardando conexões
- `accept()`: Aceita uma conexão TCP de um cliente
- Retorna um **novo socket** para cada conexão (permite múltiplas conexões simultâneas)

#### Cliente TCP:
```python
# Linha 258: Conectar ao servidor
client_socket.connect((ip, self.port))
```

**Características TCP**:
- `connect()`: Estabelece uma conexão TCP com o servidor
- Após `connect()`, pode usar `send()` e `recv()` diretamente
- A conexão permanece aberta até ser fechada explicitamente

#### Receção TCP:
```python
# Linha 150-178: Receção através de socket conectado
def recv(self, clientSock: socket.socket, ip, port):
    # Recebe dados através de socket TCP já conectado
    size_bytes = clientSock.recv(4)  # Não precisa especificar endereço
    filename = clientSock.recv(filename_size)
    # ...
```

**Características TCP**:
- `recv()` não precisa de endereço (socket já está conectado)
- Dados chegam como **stream contínuo** (pode precisar de múltiplos `recv()`)
- TCP garante ordem e integridade dos dados

### MissionLink (UDP) - Métodos Sem Conexão

#### Envio UDP:
```python
# Exemplo linha 272: Enviar mensagem UDP
self.sock.sendto(message, (ip, port))
```

**Características UDP**:
- `sendto()`: Envia datagrama UDP para endereço específico
- **Não há conexão**: cada `sendto()` é independente
- Precisa especificar `(ip, port)` em cada envio
- Mensagens são **datagramas independentes** (não há stream)

#### Receção UDP:
```python
# Exemplo linha 347: Receber mensagem UDP
message, (ip, port) = self.sock.recvfrom(self.limit.buffersize)
```

**Características UDP**:
- `recvfrom()`: Recebe datagrama UDP e retorna **dados + endereço de origem**
- Retorna tuplo `(dados, (ip_origem, porta_origem))`
- Cada mensagem é **independente** (não há conexão persistente)
- Não há garantia de ordem ou entrega

---

## 3. Comparação Visual

| Característica | TelemetryStream (TCP) | MissionLink (UDP) |
|----------------|----------------------|-------------------|
| **Tipo de Socket** | `SOCK_STREAM` | `SOCK_DGRAM` |
| **Orientação** | Orientado a conexão | Sem conexão |
| **Método Servidor** | `listen()` + `accept()` | `bind()` apenas |
| **Método Cliente** | `connect()` | Não precisa |
| **Envio** | `send()` (após connect) | `sendto(addr)` |
| **Receção** | `recv()` (sem endereço) | `recvfrom()` (retorna addr) |
| **Conexão** | Persistente (até close) | Não existe |
| **Garantias** | Ordem, integridade, entrega | Nenhuma (aplicação garante) |
| **Porta** | 8081 | 8080 |

---

## 4. Exemplos de Código

### TelemetryStream - Fluxo TCP Completo

**Servidor**:
```python
# 1. Criar socket TCP
self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
self.socket.bind((self.ip, self.port))

# 2. Colocar em modo listening
self.socket.listen()

# 3. Aceitar conexões (bloqueia até receber conexão)
while True:
    clientSocket, (ip, _) = self.socket.accept()  # Nova conexão TCP
    # Processar conexão em thread separada
```

**Cliente**:
```python
# 1. Criar socket TCP
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# 2. Conectar ao servidor
client_socket.connect((ip, self.port))  # Estabelece conexão TCP

# 3. Enviar/receber dados
client_socket.send(data)  # Não precisa especificar endereço
data = client_socket.recv(1024)

# 4. Fechar conexão
client_socket.close()
```

### MissionLink - Fluxo UDP Completo

**Servidor/Cliente** (UDP é bidirecional):
```python
# 1. Criar socket UDP
self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
self.sock.bind((self.serverAddress, self.port))

# 2. Enviar mensagem (sem conexão)
self.sock.sendto(message, (ip, port))  # Especifica destino em cada envio

# 3. Receber mensagem (sem conexão)
message, (ip_origem, port_origem) = self.sock.recvfrom(buffer)
# Retorna dados + endereço de origem
```

---

## 5. Porquê TCP para TelemetryStream?

**TelemetryStream usa TCP porque**:
1. ✅ **Transmissão contínua**: Telemetria é enviada periodicamente, TCP mantém conexão aberta
2. ✅ **Dados grandes**: Ficheiros JSON podem ser grandes, TCP fragmenta automaticamente
3. ✅ **Confiabilidade**: Não queremos perder dados de telemetria
4. ✅ **Múltiplos rovers**: TCP permite múltiplas conexões simultâneas (uma por rover)
5. ✅ **Stream-oriented**: Dados chegam como stream contínuo, ideal para ficheiros

**Código que demonstra**:
```python
# TelemetryStream recebe dados em chunks através de conexão TCP
while True:
    chunk = clientSock.recv(1024)  # Stream contínuo
    if not chunk:
        break  # Conexão fechada
    # Processar chunk
```

---

## 6. Porquê UDP para MissionLink?

**MissionLink usa UDP porque**:
1. ✅ **Comunicação crítica e rápida**: Missões precisam ser enviadas rapidamente
2. ✅ **Mensagens pequenas**: Missões são JSON pequenos, não precisam de stream
3. ✅ **Mecanismos de fiabilidade próprios**: O protocolo implementa handshake, ACKs, retransmissão
4. ✅ **Sem overhead de conexão**: Não precisa estabelecer conexão antes de enviar
5. ✅ **Bidirecional**: Servidor e cliente podem enviar/receber sem estabelecer conexão

**Código que demonstra**:
```python
# MissionLink envia mensagens independentes via UDP
self.sock.sendto(formatMessage(...), (ip, port))  # Cada mensagem é independente

# Recebe resposta (pode vir de qualquer endereço)
response, (responseIp, responsePort) = self.sock.recvfrom(buffer)
```

**Mecanismos de fiabilidade implementados** (aplicação garante, não TCP):
- Handshake (SYN/ACK próprio)
- Números de sequência
- Acknowledgments (ACKs)
- Retransmissão em caso de timeout
- Verificação de integridade

---

## 7. Verificação Prática

### Teste 1: Verificar tipo de socket

```python
import socket

# TelemetryStream
ts_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print(f"TelemetryStream socket type: {ts_socket.type}")
# Output: socket.SOCK_STREAM (valor: 1) = TCP

# MissionLink
ml_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
print(f"MissionLink socket type: {ml_socket.type}")
# Output: socket.SOCK_DGRAM (valor: 2) = UDP
```

### Teste 2: Verificar métodos disponíveis

**TCP** tem métodos:
- `connect()`, `accept()`, `listen()`, `send()`, `recv()`

**UDP** tem métodos:
- `sendto()`, `recvfrom()` (não tem `connect()`, `accept()`, `listen()`)

### Teste 3: Usar ferramentas de rede

**Wireshark/Tcpdump**:
- **Porta 8081** (TelemetryStream): Verá tráfego **TCP** (SYN, ACK, FIN, etc.)
- **Porta 8080** (MissionLink): Verá tráfego **UDP** (datagramas independentes)

**netstat**:
```bash
# Ver conexões TCP (TelemetryStream)
netstat -an | grep 8081
# Output: tcp 0 0 0.0.0.0:8081 LISTENING (TCP)

# Ver sockets UDP (MissionLink)
netstat -an | grep 8080
# Output: udp 0 0 0.0.0.0:8080 (UDP, sem estado de conexão)
```

---

## 8. Resumo

### TelemetryStream (TS) = TCP ✅

**Evidências no código**:
1. `socket.SOCK_STREAM` (linha 29)
2. `listen()` e `accept()` (linhas 114, 120)
3. `connect()` no cliente (linha 258)
4. `recv()` sem endereço (linha 150+)
5. Conexões persistentes (uma por rover)
6. Porta 8081

### MissionLink (ML) = UDP ✅

**Evidências no código**:
1. `socket.SOCK_DGRAM` (linha 34)
2. `sendto()` com endereço (múltiplas linhas)
3. `recvfrom()` retorna endereço (múltiplas linhas)
4. Sem `connect()`, `accept()`, `listen()`
5. Mensagens independentes (datagramas)
6. Porta 8080

---

## Conclusão

A verificação é **clara e inequívoca**:
- **TelemetryStream** usa **TCP** (`SOCK_STREAM`) para transmissão contínua e confiável
- **MissionLink** usa **UDP** (`SOCK_DGRAM`) para comunicação rápida com fiabilidade a nível aplicacional

Ambos os protocolos estão corretamente implementados conforme especificado no PDF do trabalho.

