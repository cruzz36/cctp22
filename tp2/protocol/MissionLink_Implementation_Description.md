# Descrição Detalhada da Implementação do Protocolo MissionLink

## Índice
1. [Visão Geral](#visão-geral)
2. [Arquitetura do Protocolo](#arquitetura-do-protocolo)
3. [Formato de Mensagem](#formato-de-mensagem)
4. [Mecanismos de Fiabilidade](#mecanismos-de-fiabilidade)
5. [Handshake 3-Way](#handshake-3-way)
6. [Envio de Dados](#envio-de-dados)
7. [Receção de Dados](#receção-de-dados)
8. [Fechamento de Conexão](#fechamento-de-conexão)
9. [Tipos de Operação](#tipos-de-operação)
10. [Tratamento de Erros](#tratamento-de-erros)
11. [Estratégias Anti-Duplicação](#estratégias-anti-duplicação)
12. [Exemplos de Uso](#exemplos-de-uso)
13. [Considerações de Implementação](#considerações-de-implementação)

---

## 1. Visão Geral

O **MissionLink (ML)** é um protocolo aplicacional sobre UDP desenvolvido para comunicação crítica entre a **Nave-Mãe** (servidor) e os **rovers** (clientes). Como o UDP não fornece garantias de entrega, ordem ou deteção de duplicados, o MissionLink implementa mecanismos de fiabilidade a nível aplicacional.

### Características Principais:
- **Protocolo de transporte**: UDP (User Datagram Protocol)
- **Porta padrão**: 8080
- **Fiabilidade**: Implementada a nível aplicacional através de:
  - Handshake 3-way para estabelecimento de conexão
  - Números de sequência para controlo de ordem
  - Acknowledgments (ACKs) para confirmação de receção
  - Retransmissão automática em caso de timeout
  - Validação de integridade de mensagens
  - Fechamento de conexão com handshake 4-way

### Objetivos:
1. Garantir entrega confiável de mensagens críticas sobre UDP
2. Detetar e recuperar de perdas de pacotes
3. Manter ordem de entrega de mensagens
4. Prevenir duplicação de dados
5. Suportar envio de mensagens pequenas e ficheiros grandes

---

## 2. Arquitetura do Protocolo

### Estrutura da Classe MissionLink

```python
class MissionLink:
    def __init__(self, serverAddress, storeFolder=".")
    def server()
    def getHeaderSize()
    def formatMessage(missionType, flag, idMission, seqNum, ackNum, message)
    def splitMessage(message)
    def startConnection(idAgent, destAddress, destPort, retryLimit=5)
    def acceptConnection()
    def send(ip, port, missionType, idAgent, idMission, message)
    def recv()
```

### Componentes Principais:

1. **Socket UDP**: `socket.socket(socket.AF_INET, socket.SOCK_DGRAM)`
   - Comunicação não orientada a conexão
   - Requer implementação manual de fiabilidade

2. **Sistema de Flags**: Controlo de tipo de mensagem
   - `S` (SYN): Inicia handshake
   - `Z` (SYN-ACK): Resposta ao SYN
   - `A` (ACK): Confirmação de receção
   - `F` (FIN): Fecha conexão
   - `D` (Data): Dados normais

3. **Tipos de Operação (missionType)**: Identifica o propósito da mensagem
   - `R` (Register): Registo de rover
   - `T` (Task): Envio de missão
   - `Q` (Request): Solicitação de missão
   - `P` (Progress): Reporte de progresso
   - `N` (None): ACKs/FINs sem operação específica

**Nota**: O tipo `M` (Metrics) foi comentado, pois a telemetria contínua é tratada pelo protocolo TelemetryStream.

---

## 3. Formato de Mensagem

### Estrutura do Protocolo

Cada mensagem segue o formato:
```
flag|idMission|seq|ack|size|missionType|message
```

### Campos Detalhados:

| Campo | Posição | Tamanho | Descrição | Exemplo |
|-------|---------|---------|-----------|---------|
| `flag` | 0 | 1 byte | Tipo de controlo (S, Z, A, F, D) | `"D"` |
| `idMission` | 1 | 3 bytes | ID da missão ou rover (no handshake) | `"M01"` |
| `seq` | 2 | 4 bytes | Número de sequência | `101` |
| `ack` | 3 | 4 bytes | Número de acknowledgment | `101` |
| `size` | 4 | 4 bytes | Tamanho da mensagem em bytes | `256` |
| `missionType` | 5 | 1 byte | Tipo de operação (R, T, Q, P, N) | `"T"` |
| `message` | 6 | Variável | Conteúdo da mensagem | `"{...}"` |

### Exemplo de Mensagem:

```
D|M01|101|101|256|T|{"mission_id":"M-001","rover_id":"r1",...}
```

### Tamanho do Cabeçalho:

O cabeçalho tem **23 bytes** fixos:
- flag: 1 byte
- separadores (|): 6 bytes (6 campos)
- idMission: 3 bytes
- seq: 4 bytes
- ack: 4 bytes
- size: 4 bytes
- missionType: 1 byte

**Espaço útil para dados**: `buffersize - 23 bytes` (geralmente 1024 - 23 = 1001 bytes)

---

## 4. Mecanismos de Fiabilidade

### 4.1 Números de Sequência (seq)

**Função**: Garantir ordem de entrega e detetar pacotes perdidos.

**Como funciona**:
- Cada pacote tem um número de sequência único
- O número é incrementado para cada novo pacote enviado
- O recetor valida que recebeu o número de sequência esperado (`seq + 1`)
- Se receber um número incorreto, rejeita o pacote e solicita retransmissão

**Inicialização**: `seqinicial = 100` (pode ser aleatório)

**Incremento**: `seq += 1` após cada envio bem-sucedido

### 4.2 Acknowledgments (ACK)

**Função**: Confirmar receção de pacotes específicos.

**Como funciona**:
- Quando o recetor recebe um pacote válido, envia um ACK
- O ACK contém o número de sequência recebido no campo `ack`
- O emissor valida que o ACK corresponde ao pacote enviado
- Se não receber ACK dentro do timeout, retransmite o pacote

**Validação**: `lista[ackPos] == str(seq)` confirma que o ACK reconhece o pacote correto

### 4.3 Retransmissão

**Função**: Recuperar de perdas de pacotes.

**Como funciona**:
- Timeout configurável (padrão: 2 segundos)
- Se não receber ACK dentro do timeout, reenvia o pacote
- Limite de retries para evitar loops infinitos
- Validação de IP/porta para garantir que o ACK vem do destinatário correto

**Implementação**:
```python
try:
    # Enviar pacote
    self.sock.sendto(message, (ip, port))
    # Aguardar ACK
    response, (responseIp, responsePort) = self.sock.recvfrom(buffer)
    # Validar ACK
    if responseIp == ip and responsePort == port and ack_correto:
        break  # Sucesso
except socket.timeout:
    # Timeout - retransmitir
    continue
```

### 4.4 Validação de Integridade

**Validações realizadas**:
1. **Formato**: Verifica que a mensagem tem 7 campos (`len(lista) == 7`)
2. **IP/Porta**: Confirma que a mensagem vem do emissor correto
3. **Sequência**: Valida que o número de sequência é o esperado
4. **idMission**: Verifica que o pacote pertence à missão/conexão correta
5. **Flag**: Confirma que o tipo de mensagem é o esperado

**Segurança**: A validação de `idMission` previne ataques de impersonação onde um atacante tenta enviar ACKs falsos.

---

## 5. Handshake 3-Way

### 5.1 Objetivo

Estabelecer uma "conexão" confiável sobre UDP antes de enviar dados. O handshake garante que ambas as partes estão prontas para comunicar e sincroniza os números de sequência iniciais.

### 5.2 Processo Completo

#### Passo 1: Cliente envia SYN
```
Cliente → Servidor: flag=S|idAgent|seq=100|ack=0|size=_|missionType=0|message=-.-
```

**Código** (`startConnection()`):
```python
self.sock.sendto(
    f"{self.synkey}|{idAgent}|{seqinicial}|0|_|0|-.-".encode(),
    (destAddress, destPort)
)
```

#### Passo 2: Servidor responde com SYN-ACK
```
Servidor → Cliente: flag=Z|idAgent|seq=100|ack=100|size=_|missionType=0|message=-.-
```

**Código** (`acceptConnection()`):
```python
lista[flagPos] = self.synackkey  # Muda flag de S para Z
self.sock.sendto("|".join(lista).encode(), (ip, port))
```

#### Passo 3: Cliente envia ACK
```
Cliente → Servidor: flag=A|idAgent|seq=100|ack=100|size=_|missionType=0|message=-.-
```

**Código** (`startConnection()`):
```python
self.sock.sendto(
    f"{self.ackkey}|{idAgent}|{seqinicial}|{seqinicial}|_|0|-.-".encode(),
    (destAddress, destPort)
)
```

### 5.3 Notas Importantes

- **idMission no handshake**: No handshake, o campo `idMission` contém temporariamente o **ID do rover** (`idAgent`). Após o handshake, contém o **ID da missão**.
- **Sincronização**: O servidor guarda o mapeamento `(IP, porta) → ID do rover` durante o handshake.
- **Retry logic**: Se qualquer passo falhar (timeout), o processo é reiniciado até `retryLimit` tentativas.

---

## 6. Envio de Dados

### 6.1 Método `send()`

O método `send()` é responsável por enviar mensagens ou ficheiros através do protocolo MissionLink.

**Fluxo geral**:
1. Estabelece conexão (handshake 3-way)
2. Envia dados com confirmação
3. Fecha conexão (handshake 4-way)

### 6.2 Envio de Mensagens Curtas

**Quando**: Mensagem cabe num único pacote (`len(message) <= buffersize - headerSize`)

**Processo**:
1. Envia mensagem com `flag=D` e `missionType` apropriado
2. Aguarda ACK do recetor
3. Se não receber ACK, retransmite
4. Após ACK, inicia fechamento de conexão

**Código**:
```python
if isinstance(chunks, str):
    # Mensagem cabe num pacote
    self.sock.sendto(
        self.formatMessage(missionType, self.datakey, idMission, seq, ack, chunks),
        (ip, port)
    )
    # Aguardar ACK...
```

### 6.3 Envio de Mensagens Longas

**Quando**: Mensagem excede o tamanho do buffer

**Processo**:
1. Divide mensagem em chunks usando `splitMessage()`
2. Envia cada chunk sequencialmente
3. Aguarda ACK de cada chunk antes de enviar o próximo
4. Incrementa `seq` após cada ACK recebido
5. Após último chunk, inicia fechamento

**Fragmentação**:
```python
chunks = self.splitMessage(message)  # Lista de strings
for chunk in chunks:
    self.sock.sendto(formatMessage(...), (ip, port))
    # Aguardar ACK...
    seq += 1
```

### 6.4 Envio de Ficheiros

**Quando**: `message.endswith(".json")`

**Processo**:
1. **Primeiro**: Envia o **nome do ficheiro** e aguarda ACK
2. **Depois**: Lê ficheiro em chunks e envia cada chunk
3. **Para cada chunk**:
   - Envia chunk
   - Aguarda ACK
   - Lê próximo chunk
4. **Finalmente**: Envia FIN e fecha conexão

**Código**:
```python
if message.endswith(".json"):
    # Enviar nome do ficheiro
    self.sock.sendto(formatMessage(...), (ip, port))
    # Aguardar ACK...
    
    # Enviar conteúdo do ficheiro
    with open(message, "r") as file:
        buffer = file.read(buffersize - headerSize)
        while buffer:
            self.sock.sendto(formatMessage(...), (ip, port))
            # Aguardar ACK...
            buffer = file.read(buffersize - headerSize)
```

---

## 7. Receção de Dados

### 7.1 Método `recv()`

O método `recv()` é responsável por receber mensagens ou ficheiros através do protocolo MissionLink.

**Fluxo geral**:
1. Aceita conexão (handshake 3-way)
2. Recebe primeira mensagem para determinar tipo (ficheiro ou mensagem)
3. Recebe dados sequencialmente
4. Fecha conexão (handshake 4-way)

### 7.2 Receção de Mensagens

**Processo**:
1. Recebe primeiro pacote e determina se é ficheiro ou mensagem
2. Se for mensagem, inicializa string vazia
3. Para cada chunk recebido:
   - Valida formato, IP/porta, sequência, idMission
   - Usa estratégia anti-duplicação (escreve chunk anterior quando próximo chega)
   - Envia ACK
   - Incrementa sequência
4. Quando recebe FIN, concatena último chunk e fecha conexão

**Estratégia anti-duplicação**:
```python
prevMessage = None  # Chunk anterior
for chunk in chunks:
    if prevMessage is not None:
        message += prevMessage  # Escreve chunk anterior
    prevMessage = chunk  # Guarda chunk atual
# No final, escreve último chunk
```

### 7.3 Receção de Ficheiros

**Processo**:
1. Recebe nome do ficheiro no primeiro pacote
2. Abre ficheiro para escrita
3. Para cada chunk recebido:
   - Valida formato, IP/porta, sequência, idMission
   - Escreve chunk anterior (se existir) no ficheiro
   - Guarda chunk atual em `previous`
   - Envia ACK
4. Quando recebe FIN, escreve último chunk e fecha ficheiro

**Porquê escrever chunk anterior**:
- Se houver retransmissão, o chunk anterior já foi escrito
- Evita escrever o mesmo chunk duas vezes
- Garante que apenas chunks novos são escritos

---

## 8. Fechamento de Conexão

### 8.1 Handshake 4-Way

O fechamento de conexão usa um handshake de 4 vias para garantir que ambas as partes fecharam a conexão corretamente.

#### Passo 1: Emissor envia FIN
```
Emissor → Recetor: flag=F|idMission|seq=103|ack=103|size=1|missionType=N|message=\0
```

#### Passo 2: Recetor responde com FIN
```
Recetor → Emissor: flag=F|idMission|seq=104|ack=104|size=1|missionType=N|message=\0
```

#### Passo 3: Emissor envia ACK do FIN recebido
```
Emissor → Recetor: flag=A|idMission|seq=105|ack=104|size=1|missionType=N|message=\0
```

#### Passo 4: Recetor envia ACK do FIN enviado

### 8.2 Implementação

**Código no emissor** (`send()`):
```python
# Enviar FIN
self.sock.sendto(
    self.formatMessage(None, self.finkey, idMission, seq, ack, self.eofkey),
    (ip, port)
)

# Aguardar FIN do outro lado OU ACK do nosso FIN
while True:
    response = self.sock.recvfrom(buffer)
    if response[flag] == self.finkey:
        # Recebeu FIN - responder com ACK
        ack = int(response[seq])  # Reconhecer seq do FIN recebido
        self.sock.sendto(formatMessage(None, self.ackkey, ...), (ip, port))
        return True
    elif response[flag] == self.ackkey and response[ack] == str(seq):
        # Recebeu ACK do nosso FIN - continuar a aguardar FIN do outro lado
        continue
```

**Código no recetor** (`recv()`):
```python
# Quando recebe FIN nos dados
if lista[flagPos] == self.finkey:
    # Enviar FIN de resposta
    self.sock.sendto(formatMessage(None, self.finkey, ...), (ip, port))
    
    # Aguardar ACK do FIN enviado
    while True:
        ack_response = self.sock.recvfrom(buffer)
        if ack_response[flag] == self.ackkey and ack_response[ack] == str(seq):
            return [idAgent, idMission, missionType, message, ip]
```

---

## 9. Tipos de Operação

### 9.1 Register (R)

**Uso**: Rover regista-se na Nave-Mãe

**Formato**:
- `flag`: `D` (Data)
- `missionType`: `R` (Register)
- `idMission`: ID do rover (no handshake) ou "000"
- `message`: `"\0"` (vazio)

**Fluxo**:
1. Rover envia: `D|r1|101|101|1|R|\0`
2. Nave-Mãe responde: `D|r1|102|102|9|N|Registered`

### 9.2 Task (T)

**Uso**: Nave-Mãe envia missão ao rover

**Formato**:
- `flag`: `D` (Data)
- `missionType`: `T` (Task)
- `idMission`: ID da missão (ex: "M01")
- `message`: JSON com dados da missão

**Exemplo de JSON**:
```json
{
    "mission_id": "M-001",
    "rover_id": "r1",
    "geographic_area": {"x1": 10.0, "y1": 20.0, "x2": 50.0, "y2": 60.0},
    "task": "capture_images",
    "duration_minutes": 30,
    "update_frequency_seconds": 120
}
```

**Fluxo**:
1. Nave-Mãe envia: `D|M01|101|101|256|T|{JSON da missão}`
2. Rover responde: `D|M01|102|102|4|N|M01` (ACK com mission_id)

### 9.3 Request (Q)

**Uso**: Rover solicita uma missão à Nave-Mãe

**Formato**:
- `flag`: `D` (Data)
- `missionType`: `Q` (Request)
- `idMission`: "000" (ainda não há missão)
- `message`: "request"

**Fluxo**:
1. Rover envia: `D|000|101|101|7|Q|request`
2. Nave-Mãe responde:
   - Com missão: `D|M01|102|102|256|T|{JSON da missão}`
   - Sem missão: `D|000|102|102|10|N|no_mission`

### 9.4 Progress (P)

**Uso**: Rover reporta progresso de uma missão

**Formato**:
- `flag`: `D` (Data)
- `missionType`: `P` (Progress)
- `idMission`: ID da missão
- `message`: JSON com dados de progresso

**Exemplo de JSON**:
```json
{
    "mission_id": "M-001",
    "progress_percent": 45,
    "status": "in_progress",
    "current_position": {"x": 25.5, "y": 35.2}
}
```

**Fluxo**:
1. Rover envia: `D|M01|101|101|150|P|{JSON de progresso}`
2. Nave-Mãe responde: `D|M01|102|102|16|N|progress_received`

---

## 10. Tratamento de Erros

### 10.1 Validação de Formato

**Problema**: Mensagens malformadas podem causar `IndexError`

**Solução**: Verificar `len(lista) >= 7` antes de aceder a índices

**Código**:
```python
lista = message.decode().split("|")
if len(lista) < 7:
    # Mensagem malformada - ignorar e continuar
    continue
```

### 10.2 Timeout Handling

**Problema**: Pacotes podem ser perdidos, causando espera infinita

**Solução**: Usar `socket.timeout` e retransmitir

**Código**:
```python
self.sock.settimeout(self.limit.timeout)  # 2 segundos
try:
    response = self.sock.recvfrom(buffer)
except socket.timeout:
    # Timeout - retransmitir
    self.sock.sendto(message, (ip, port))
    continue
```

### 10.3 Retry Limits

**Problema**: Loops infinitos se validação sempre falhar

**Solução**: Limitar número de tentativas

**Código**:
```python
retries = 0
max_retries = 10
while condition and retries < max_retries:
    retries += 1
    # Tentar novamente...
```

### 10.4 Validação de IP/Porta

**Problema**: ACKs podem vir de outros emissores

**Solução**: Validar que resposta vem do destinatário correto

**Código**:
```python
if responseIp == ip and responsePort == port:
    # Resposta válida
    break
else:
    # Resposta de origem incorreta - ignorar
    continue
```

### 10.5 Validação de idMission

**Problema**: Ataques de impersonação com ACKs falsos

**Solução**: Validar que `idMission` corresponde à conexão

**Código**:
```python
if lista[idMissionPos] == idMission:
    # idMission correto - aceitar
    break
else:
    # idMission incorreto - rejeitar
    continue
```

---

## 11. Estratégias Anti-Duplicação

### 11.1 Problema

Com retransmissão, o mesmo pacote pode ser recebido múltiplas vezes. Se escrevermos imediatamente cada chunk recebido, podemos escrever o mesmo chunk duas vezes.

### 11.2 Solução: Escrita Atrasada (Delayed Write)

**Conceito**: Guardar o chunk atual e escrever o chunk anterior quando o próximo chega.

**Como funciona**:
1. Recebe chunk 1 → guarda em `prevMessage`, não escreve
2. Recebe chunk 2 → escreve chunk 1 (prevMessage), guarda chunk 2 em `prevMessage`
3. Recebe chunk 3 → escreve chunk 2, guarda chunk 3
4. Recebe FIN → escreve último chunk (chunk 3)

**Vantagens**:
- Se chunk 1 for retransmitido, já foi escrito, então não escreve novamente
- Garante que apenas chunks novos são escritos
- Previne duplicação em caso de retransmissão

**Código**:
```python
prevMessage = None
for chunk in chunks:
    if prevMessage is not None:
        message += prevMessage  # Escreve chunk anterior
    prevMessage = chunk  # Guarda chunk atual
# No final (quando recebe FIN), escreve último chunk
if prevMessage is not None:
    message += prevMessage
```

### 11.3 Aplicação

- **Mensagens**: Concatena chunks em string
- **Ficheiros**: Escreve chunks no ficheiro

---

## 12. Exemplos de Uso

### 12.1 Exemplo 1: Rover Regista-se

```python
# No rover (NMS_Agent)
rover = NMS_Agent.NMS_Agent("10.0.4.10")
rover.register("10.0.4.10")  # Regista-se na Nave-Mãe

# Fluxo:
# 1. Handshake 3-way
# 2. Envia: D|r1|101|101|1|R|\0
# 3. Recebe: D|r1|102|102|9|N|Registered
# 4. Fechamento 4-way
```

### 12.2 Exemplo 2: Nave-Mãe Envia Missão

```python
# Na Nave-Mãe (NMS_Server)
server = NMS_Server.NMS_Server()
mission = {
    "mission_id": "M-001",
    "rover_id": "r1",
    "geographic_area": {"x1": 10.0, "y1": 20.0, "x2": 50.0, "y2": 60.0},
    "task": "capture_images",
    "duration_minutes": 30,
    "update_frequency_seconds": 120
}
server.sendMission("10.0.4.11", "r1", mission)

# Fluxo:
# 1. Handshake 3-way
# 2. Envia: D|M01|101|101|256|T|{JSON da missão}
# 3. Recebe: D|M01|102|102|4|N|M01 (ACK)
# 4. Fechamento 4-way
```

### 12.3 Exemplo 3: Rover Solicita Missão

```python
# No rover
mission = rover.requestMission("10.0.4.10")

# Fluxo:
# 1. Handshake 3-way
# 2. Envia: D|000|101|101|7|Q|request
# 3. Recebe: D|M01|102|102|256|T|{JSON da missão}
# 4. Envia ACK: D|M01|103|103|4|N|M01
# 5. Fechamento 4-way
```

### 12.4 Exemplo 4: Rover Reporta Progresso

```python
# No rover
progress = {
    "mission_id": "M-001",
    "progress_percent": 45,
    "status": "in_progress"
}
rover.reportMissionProgress("10.0.4.10", "M01", progress)

# Fluxo:
# 1. Handshake 3-way
# 2. Envia: D|M01|101|101|150|P|{JSON de progresso}
# 3. Recebe: D|M01|102|102|16|N|progress_received
# 4. Fechamento 4-way
```

---

## 13. Considerações de Implementação

### 13.1 Limitações

1. **UDP não garante ordem**: O protocolo assume que pacotes chegam na ordem (valida sequência)
2. **Tamanho máximo**: Limitado pelo buffersize (1024 bytes) menos cabeçalho (23 bytes)
3. **Timeout fixo**: 2 segundos pode ser muito ou pouco dependendo da rede
4. **Sem compressão**: Dados são enviados como estão, sem compressão

### 13.2 Melhorias Possíveis

1. **Adaptive timeout**: Ajustar timeout baseado em RTT medido
2. **Compressão**: Comprimir dados grandes antes de enviar
3. **Criptografia**: Adicionar encriptação para segurança
4. **Multiplexing**: Suportar múltiplas conexões simultâneas
5. **Congestion control**: Implementar controlo de congestionamento

### 13.3 Boas Práticas

1. **Sempre validar formato** antes de aceder a índices
2. **Usar retry limits** para evitar loops infinitos
3. **Validar IP/porta e idMission** para segurança
4. **Implementar logging** para debug
5. **Tratar todas as exceções** apropriadamente

---

## 14. Conclusão

O protocolo MissionLink implementa com sucesso mecanismos de fiabilidade sobre UDP, permitindo comunicação crítica entre a Nave-Mãe e os rovers. Através de handshakes, números de sequência, acknowledgments e retransmissão, o protocolo garante entrega confiável de mensagens e ficheiros, mesmo sobre um protocolo de transporte não confiável como o UDP.

A implementação é robusta, com validações extensivas, tratamento de erros e estratégias anti-duplicação que garantem integridade dos dados transmitidos.

---

**Versão**: 1.0  
**Data**: 2024  
**Autor**: Sistema de Documentação Automática
