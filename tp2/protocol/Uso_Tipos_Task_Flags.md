# Uso de Tipos de Task (missionType) e Flags no MissionLink

Este documento mostra **onde e quando** cada tipo de task (missionType) e flag é usado no código do MissionLink.

---

## TIPOS DE TASK (missionType)

### 1. `registerAgent = "R"` - Register: Rover regista-se na Nave-Mãe

**Definição**: Linha 58
```python
self.registerAgent = "R"      # Register: Rover regista-se na Nave-Mãe
```

**Onde é usado**:

#### No Servidor (NMS_Server.py):
- **Linha 212**: Verifica se mensagem recebida é de registo
  ```python
  if missionType == self.missionLink.registerAgent:  # "R"
      # Rover regista-se na Nave-Mãe
      self.registerAgent(idAgent,ip) # It already sends the confirmation reply
      return
  ```

- **Linha 361**: Método `registerAgent()` processa o registo
  ```python
  def registerAgent(self,idAgent,ip):
      # Regista o rover no dicionário de agentes
      self.agents[idAgent] = ip
      # Envia confirmação
  ```

**Quando é usado**:
- Quando um rover se regista pela primeira vez na Nave-Mãe
- O rover envia mensagem com `missionType="R"` durante o handshake ou após conexão estabelecida

**Flag usada**: `datakey` ("D") - mensagem de dados normal

---

### 2. `taskRequest = "T"` - Task: Nave-Mãe envia missão ao rover

**Definição**: Linha 59
```python
self.taskRequest = "T"        # Task: Nave-Mãe envia missão ao rover (JSON contém campo "task")
```

**Onde é usado**:

#### No Servidor (NMS_Server.py) - Envio de missões:
- **Linha 257**: Método `sendTask()` envia missão
  ```python
  self.missionLink.send(ip,self.missionLink.port,self.missionLink.taskRequest,idAgent,idMission,task)
  ```

- **Linha 275**: Retransmissão em caso de falha
  ```python
  self.missionLink.send(ip,self.missionLink.port,self.missionLink.taskRequest,idAgent,idMission,task)
  ```

- **Linha 333**: Método `sendMission()` envia missão validada
  ```python
  self.missionLink.send(ip, self.missionLink.port, self.missionLink.taskRequest, idAgent, mission_id, mission_json)
  ```

- **Linha 353**: Retransmissão em `sendMission()`
  ```python
  self.missionLink.send(ip, self.missionLink.port, self.missionLink.taskRequest, idAgent, mission_id, mission_json)
  ```

- **Linha 411**: Atribuição de missão pendente
  ```python
  self.missionLink.send(agent_ip,self.missionLink.port,self.missionLink.taskRequest,agent["device_id"],taskid,agent_json)
  ```

#### No Cliente (NMS_Agent.py) - Receção de missões:
- **Linha 378**: Verifica se mensagem recebida é uma missão
  ```python
  if lista[2] == self.missionLink.taskRequest:
      mission_message = lista[3]
      mission_id = lista[1]  # idMission do protocolo
      # Processa missão...
  ```

**Quando é usado**:
- Quando a Nave-Mãe envia uma missão para um rover
- O campo `message` contém um JSON com a missão completa, incluindo o campo `"task"` que pode ser:
  - `"capture_images"` - Capturar imagens
  - `"sample_collection"` - Recolher amostras
  - `"environmental_analysis"` - Análise ambiental

**Flag usada**: `datakey` ("D") - mensagem de dados normal

**Exemplo de mensagem**:
```json
{
    "mission_id": "M-001",
    "rover_id": "r1",
    "geographic_area": {"x1": 10.0, "y1": 20.0, "x2": 50.0, "y2": 60.0},
    "task": "capture_images",  ← Tipo de tarefa física
    "duration_minutes": 30,
    "update_frequency_seconds": 120
}
```

---

### 3. `requestMission = "Q"` - Request/Query: Rover solicita uma missão

**Definição**: Linha 61
```python
self.requestMission = "Q"    # Request/Query: Rover solicita uma missão à Nave-Mãe
```

**Onde é usado**:

#### No Cliente (NMS_Agent.py) - Solicitação de missão:
- **Linha 293**: Método `requestMission()` envia pedido
  ```python
  self.missionLink.send(ip, self.missionLink.port, self.missionLink.requestMission, self.id, "000", "request")
  ```

#### No Servidor (NMS_Server.py) - Processamento de pedido:
- **Linha 232**: Verifica se mensagem recebida é pedido de missão
  ```python
  if missionType == self.missionLink.requestMission:  # "Q"
      # Rover solicita uma missão à Nave-Mãe
      self.handleMissionRequest(idAgent, ip)
      return
  ```

**Quando é usado**:
- Quando um rover solicita uma missão à Nave-Mãe
- O rover envia mensagem com `missionType="Q"` e `message="request"`
- A Nave-Mãe responde atribuindo uma missão pendente (se houver) ou confirmando que não há missões disponíveis

**Flag usada**: `datakey` ("D") - mensagem de dados normal

---

### 4. `reportProgress = "P"` - Progress: Rover reporta progresso

**Definição**: Linha 62
```python
self.reportProgress = "P"      # Progress: Rover reporta progresso de uma missão em execução
```

**Onde é usado**:

#### No Cliente (NMS_Agent.py) - Envio de progresso:
- **Linha 472**: Método `reportMissionProgress()` envia progresso
  ```python
  self.missionLink.send(ip, self.missionLink.port, self.missionLink.reportProgress, self.id, mission_id, progress_json)
  ```

#### No Servidor (NMS_Server.py) - Receção de progresso:
- **Linha 237**: Verifica se mensagem recebida é reporte de progresso
  ```python
  if missionType == self.missionLink.reportProgress:  # "P"
      # Rover reporta progresso de uma missão em execução
      # O campo 'message' contém dados de progresso (JSON)
      self.handleMissionProgress(idAgent, idMission, message, ip)
      return
  ```

**Quando é usado**:
- Quando um rover reporta o progresso de uma missão em execução
- O campo `message` contém um JSON com dados de progresso:
  ```json
  {
      "mission_id": "M-001",
      "progress_percent": 45,
      "status": "in_progress",
      "current_position": {"x": 25.5, "y": 35.2},
      "time_elapsed_minutes": 13.5,
      "estimated_completion_minutes": 16.5
  }
  ```

**Flag usada**: `datakey` ("D") - mensagem de dados normal

---

### 5. `noneType = "N"` - None: ACK/FIN sem tipo de operação

**Definição**: Linha 63
```python
self.noneType = "N"           # None: ACK/FIN sem tipo de operação específico (codificado quando missionType=None)
```

**Onde é usado**:

#### No formatMessage() - Linha 201-203:
```python
if missionType != None: 
    # missionType normal (R, T, Q, P)
else:
    # missionType=None é usado apenas para ACKs/FINs, codificar como "N"
```

#### No Servidor (NMS_Server.py) - Verificação de ACK:
- **Linha 346**: Verifica se ACK de confirmação tem `missionType="N"`
  ```python
  if (
      lista[0] == idAgent and
      lista[2] == self.missionLink.noneType and  # missionType deve ser "N" para ACK de confirmação
      lista[4] == ip
  ):
      # Confirmação recebida
  ```

**Quando é usado**:
- Quando `missionType=None` é passado para `formatMessage()`, é codificado como `"N"`
- Usado em ACKs e FINs que não têm um tipo de operação específico
- Permite distinguir entre ACKs de dados (com missionType) e ACKs de controlo (sem missionType)

**Flag usada**: `ackkey` ("A") ou `finkey` ("F")

---

### 6. `sendMetrics = "M"` - Metrics (COMENTADO - Não usado)

**Definição**: Linha 60
```python
# self.sendMetrics = "M"       # Metrics: Rover envia métricas à Nave-Mãe
```

**Estado**: **COMENTADO** - Não está ativo no código atual

**Razão**: Métricas são enviadas via TelemetryStream (TCP), não via MissionLink (UDP). MissionLink é para comunicação crítica (missões), TelemetryStream é para monitorização contínua.

**Código comentado** (NMS_Server.py, linhas 217-229):
```python
# if missionType == self.missionLink.sendMetrics:  # "M"
#     # Rover envia métricas (nome de ficheiro JSON)
#     # ... código comentado ...
```

---

## FLAGS DE CONTROLO

### 1. `datakey = "D"` - Data: Mensagem de dados normal

**Definição**: Linha 69
```python
self.datakey = "D"           # Data: Mensagem de dados normal
```

**Onde é usado**:

#### No método send() - Múltiplas linhas:
- **Linha 421**: Envio de nome de ficheiro
  ```python
  self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,message),(ip,port))
  ```

- **Linha 452**: Envio de chunks de ficheiro
  ```python
  self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,buffer),(ip,port))
  ```

- **Linha 459**: Retransmissão de chunk
  ```python
  self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,buffer),(ip,port))
  ```

- **Linha 473**: Retransmissão de chunk (timeout)
  ```python
  self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,buffer),(ip,port))
  ```

- **Linha 508**: Envio de mensagem (chunk único)
  ```python
  self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,chunks),(ip,port))
  ```

- **Linha 516**: Retransmissão de mensagem
  ```python
  self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,chunks),(ip,port))
  ```

- **Linha 570**: Envio de chunk (mensagem multi-chunk)
  ```python
  self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,chunks),(ip,port))
  ```

- **Linha 575**: Retransmissão de chunk
  ```python
  self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,chunks),(ip,port))
  ```

- **Linha 581**: Envio de chunk individual (mensagem grande)
  ```python
  self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,chunks[i]),(ip,port))
  ```

- **Linha 599**: Retransmissão de chunk individual
  ```python
  self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,chunks[i]),(ip,port))
  ```

- **Linha 604**: Retransmissão de chunk individual (timeout)
  ```python
  self.sock.sendto(self.formatMessage(missionType,self.datakey,idMission,seq,ack,chunks[i]),(ip,port))
  ```

**Quando é usado**:
- **Sempre** que se envia dados normais (não ACK, não FIN, não SYN)
- Usado com todos os tipos de missionType (R, T, Q, P)
- Indica que a mensagem contém dados úteis, não apenas controlo

---

### 2. `synkey = "S"` - SYN: Inicia handshake (3-way)

**Definição**: Linha 70
```python
self.synkey = "S"            # SYN: Inicia handshake (3-way)
```

**Onde é usado**:

#### No método startConnection() - Cliente inicia conexão:
- **Linha 273**: Envio inicial de SYN
  ```python
  self.sock.sendto(
      f"{self.synkey}|{idAgent}|{seqinicial}|0|_|0|-.-".encode(),
      (destAddress, destPort)
  )
  ```

- **Linha 289**: Retransmissão de SYN (se não receber SYN-ACK)
  ```python
  self.sock.sendto(
      f"{self.synkey}|{idAgent}|{seqinicial}|0|_|0|-.-".encode(),
      (destAddress, destPort)
  )
  ```

- **Linha 298**: Retransmissão de SYN (mensagem malformada)
  ```python
  self.sock.sendto(
      f"{self.synkey}|{idAgent}|{seqinicial}|0|_|0|-.-".encode(),
      (destAddress, destPort)
  )
  ```

#### No método acceptConnection() - Servidor recebe SYN:
- **Linha 356**: Verifica se mensagem recebida é SYN
  ```python
  while len(lista) < 7 or lista[flagPos] != self.synkey:
      message,(ip,port) = self.sock.recvfrom(self.limit.buffersize)
      lista = message.decode().split("|")
      # Aguarda SYN...
  ```

**Quando é usado**:
- **Início do handshake**: Cliente envia SYN para iniciar conexão
- **Formato**: `S|idAgent|seq|0|_|0|-.-`
- **Resposta esperada**: SYN-ACK (`Z`) do servidor

---

### 3. `ackkey = "A"` - ACK: Confirmação de receção

**Definição**: Linha 71
```python
self.ackkey = "A"            # ACK: Confirmação de receção
```

**Onde é usado**:

#### No método startConnection() - Cliente completa handshake:
- **Linha 312**: Envio de ACK após receber SYN-ACK
  ```python
  self.sock.sendto(
      f"{self.ackkey}|{idAgent}|{seqinicial}|{seqinicial}|_|0|-.-".encode(),
      (destAddress, destPort)
  )
  ```

#### No método send() - Confirmações de receção:
- **Linha 496**: ACK de confirmação de FIN
  ```python
  self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 550**: ACK de chunk recebido (timeout)
  ```python
  self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 695**: ACK de primeira mensagem recebida
  ```python
  self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

#### No método recv() - Confirmações de receção:
- **Linha 379**: Verifica se mensagem recebida é ACK
  ```python
  if (lista[flagPos] == self.ackkey and 
      lista[idMissionPos] == idAgent and 
      lista[ackPos] == lista[seqPos]):
  ```

- **Linha 432**: Verifica ACK de nome de ficheiro
  ```python
  if(
      responseIp == ip and
      responsePort == port and
      lista[flagPos] == self.ackkey and
      lista[ackPos] == str(seq) and
      lista[idMissionPos] == idMission
  ):
  ```

- **Linha 464**: Verifica ACK de chunk
  ```python
  if(
      responseIp == ip and
      responsePort == port and
      lista[flagPos] == self.ackkey and
      lista[ackPos] == str(seq) and
      lista[idMissionPos] == idMission
  ):
  ```

- **Linha 521**: Verifica ACK de mensagem
  ```python
  if(
      responseIp == ip and
      responsePort == port and
      lista[flagPos] == self.ackkey and
      lista[ackPos] == str(seq) and
      lista[idMissionPos] == idMission
  ):
  ```

- **Linha 590**: Verifica ACK de chunk (mensagem multi-chunk)
  ```python
  if(
      responseIp == ip and
      responsePort == port and
      lista[flagPos] == self.ackkey and
      lista[ackPos] == str(seq) and
      lista[idMissionPos] == idMission
  ):
  ```

- **Linha 805**: Envio de ACK de chunk recebido
  ```python
  self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 816**: Retransmissão de ACK (timeout)
  ```python
  self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 821**: Retransmissão de ACK (erro)
  ```python
  self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 841**: Retransmissão de ACK (mensagem malformada)
  ```python
  self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 894**: ACK de chunk de ficheiro recebido
  ```python
  self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 898**: Retransmissão de ACK (timeout)
  ```python
  self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 903**: Retransmissão de ACK (erro)
  ```python
  self.sock.sendto(self.formatMessage(None,self.ackkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

**Quando é usado**:
- **Handshake**: Cliente envia ACK após receber SYN-ACK
- **Confirmação de dados**: Sempre que se recebe dados corretos, envia-se ACK
- **Retransmissão**: Se não receber ACK, retransmite-se dados
- **Fechamento**: ACK de FIN para confirmar fechamento de conexão

**missionType usado**: `None` (codificado como `"N"`)

---

### 4. `finkey = "F"` - FIN: Fecha conexão

**Definição**: Linha 72
```python
self.finkey = "F"            # FIN: Fecha conexão
```

**Onde é usado**:

#### No método send() - Fechamento de conexão:
- **Linha 479**: Envio de FIN após enviar ficheiro
  ```python
  self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 490**: Verifica se recebeu FIN
  ```python
  if(
      len(lista) == 7 and
      responseIp == ip and
      responsePort == port and
      lista[ackPos] == str(seq) and
      lista[flagPos] == self.finkey and
      lista[idMissionPos] == idMission
  ):
  ```

- **Linha 499**: Retransmissão de FIN (timeout)
  ```python
  self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 526**: Envio de FIN após enviar mensagem
  ```python
  self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 536**: Retransmissão de FIN (timeout)
  ```python
  self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 544**: Verifica se recebeu FIN
  ```python
  if lista[flagPos] == self.finkey:
  ```

- **Linha 560**: Retransmissão de FIN (timeout)
  ```python
  self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 565**: Retransmissão de FIN (timeout)
  ```python
  self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 606**: Envio de FIN após enviar todos os chunks
  ```python
  self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 614**: Retransmissão de FIN (timeout)
  ```python
  self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 620**: Verifica se recebeu FIN
  ```python
  if(
      len(lista) == 7 and
      responseIp == ip and
      responsePort == port and
      lista[ackPos] == str(seq) and
      lista[flagPos] == self.finkey and
      lista[idMissionPos] == idMission
  ):
  ```

- **Linha 630**: Retransmissão de FIN (timeout)
  ```python
  self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

#### No método recv() - Receção de FIN:
- **Linha 767**: Verifica se recebeu FIN
  ```python
  if lista[flagPos] == self.finkey:
  ```

- **Linha 772**: Envio de FIN em resposta
  ```python
  self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 795**: Retransmissão de FIN (timeout)
  ```python
  self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 800**: Retransmissão de FIN (timeout)
  ```python
  self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 857**: Verifica se recebeu FIN (ficheiro)
  ```python
  if lista[flagPos] == self.finkey:
  ```

- **Linha 863**: Envio de FIN em resposta
  ```python
  self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 877**: Verifica se recebeu FIN de confirmação
  ```python
  if(
      len(lista) == 7 and
      ip == ipDest and
      port == portDest and 
      lista[idMissionPos] == idMission and
      lista[ackPos] == str(seq) and
      lista[flagPos] == self.finkey
  ):
  ```

- **Linha 883**: Retransmissão de FIN (timeout)
  ```python
  self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

- **Linha 888**: Retransmissão de FIN (erro)
  ```python
  self.sock.sendto(self.formatMessage(None,self.finkey,idMission,seq,ack,self.eofkey),(ip,port))
  ```

**Quando é usado**:
- **Fim de transmissão**: Após enviar todos os dados (ficheiro ou mensagem)
- **Fechamento de conexão**: Indica que não há mais dados a enviar
- **Handshake de fechamento**: FIN → ACK → FIN → ACK (4-way handshake)

**missionType usado**: `None` (codificado como `"N"`)

---

### 5. `synackkey = "Z"` - SYN-ACK: Resposta ao SYN no handshake

**Definição**: Linha 73
```python
self.synackkey = "Z"         # SYN-ACK: Resposta ao SYN no handshake
```

**Onde é usado**:

#### No método startConnection() - Cliente aguarda SYN-ACK:
- **Linha 287**: Verifica se recebeu SYN-ACK
  ```python
  while lista[flagPos] != self.synackkey:
      self.sock.sendto(
          f"{self.synkey}|{idAgent}|{seqinicial}|0|_|0|-.-".encode(),
          (destAddress, destPort)
      )
      message,_ = self.sock.recvfrom(self.limit.buffersize)
      lista = message.decode().split("|")
      # Aguarda SYN-ACK...
  ```

#### No método acceptConnection() - Servidor envia SYN-ACK:
- **Linha 366**: Modifica flag de SYN para SYN-ACK
  ```python
  lista[flagPos] = self.synackkey
  prevLista = lista.copy()
  self.sock.sendto("|".join(lista).encode(),(ip,port))
  ```

- **Linha 377**: Retransmissão de SYN-ACK (mensagem malformada)
  ```python
  self.sock.sendto("|".join(prevLista).encode(),(ip,port))
  ```

- **Linha 386**: Retransmissão de SYN-ACK (timeout)
  ```python
  self.sock.sendto("|".join(prevLista).encode(),(ip,port))
  ```

- **Linha 390**: Retransmissão de SYN-ACK (erro)
  ```python
  self.sock.sendto("|".join(prevLista).encode(),(ip,port))
  ```

**Quando é usado**:
- **Handshake 3-way**: Servidor responde ao SYN do cliente com SYN-ACK
- **Sequência**: SYN (cliente) → SYN-ACK (servidor) → ACK (cliente)
- **Formato**: `Z|idAgent|seq|ack|_|0|-.-`

---

## RESUMO: Combinações Comuns

| Flag | missionType | Uso |
|------|-------------|-----|
| `S` (SYN) | `0` | Inicia handshake |
| `Z` (SYN-ACK) | `0` | Resposta ao SYN |
| `A` (ACK) | `N` | Confirmação de receção |
| `D` (Data) | `R` | Registo de rover |
| `D` (Data) | `T` | Envio de missão |
| `D` (Data) | `Q` | Pedido de missão |
| `D` (Data) | `P` | Reporte de progresso |
| `F` (FIN) | `N` | Fechamento de conexão |
| `A` (ACK) | `N` | Confirmação de FIN |

---

## CONCLUSÃO

- **missionType** indica o **tipo de operação** (R, T, Q, P) ou `None` (codificado como "N") para ACKs/FINs
- **flag** indica o **tipo de mensagem** (S, Z, A, F, D) - controlo ou dados
- **Combinação**: Dados normais usam `flag="D"` com `missionType` específico; ACKs/FINs usam `flag="A"/"F"` com `missionType=None` (codificado como "N")

