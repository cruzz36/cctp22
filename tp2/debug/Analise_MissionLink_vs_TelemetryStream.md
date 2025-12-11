# Análise: MissionLink vs TelemetryStream - Flags e Tasks

## Questão
Sabendo que o TelemetryStream (TS) é responsável pela transmissão contínua de dados de monitorização do rover para a Nave-Mãe, utilizando TCP como protocolo de transporte, não existem flags e/ou tasks a mais ou só erradas no MissionLink.py?

## Análise dos Protocolos

### MissionLink (ML) - UDP
**Propósito:** Comunicação crítica entre Nave-Mãe e rovers
**Transporte:** UDP (porta 8080)
**Uso:** Missões, registos, alertas críticos, progresso

### TelemetryStream (TS) - TCP
**Propósito:** Transmissão contínua de dados de monitorização
**Transporte:** TCP (porta 8081)
**Uso:** Telemetria contínua periódica

## Flags no MissionLink.py

### Flags de Controlo (CORRETAS):
1. ✅ `synkey = "S"` - SYN: Inicia handshake (3-way)
2. ✅ `synackkey = "Z"` - SYN-ACK: Resposta ao SYN
3. ✅ `ackkey = "A"` - ACK: Confirmação de receção
4. ✅ `finkey = "F"` - FIN: Fecha conexão
5. ✅ `datakey = "D"` - Data: Mensagem de dados normal

**Conclusão:** ✅ **TODAS CORRETAS** - Necessárias para fiabilidade sobre UDP

## Tipos de Operação (missionType) no MissionLink.py

### Tipos Implementados:
1. ✅ `registerAgent = "R"` - Register: Rover regista-se na Nave-Mãe
2. ✅ `taskRequest = "T"` - Task: Nave-Mãe envia missão ao rover
3. ⚠️ `sendMetrics = "M"` - Metrics: Rover envia métricas/alertas à Nave-Mãe
4. ✅ `requestMission = "Q"` - Request: Rover solicita uma missão
5. ✅ `reportProgress = "P"` - Progress: Rover reporta progresso
6. ✅ `noneType = "N"` - None: ACK/FIN sem tipo específico

## Análise do `sendMetrics` ("M")

### Uso Atual:
- **Formato de ficheiro:** `alert_idMission_task-XXX_iter.json`
- **Quando usado:** Quando limites de `telemetry_stream_conditions` são excedidos
- **Protocolo:** MissionLink (UDP)
- **Propósito:** Alertas críticos quando métricas excedem limites

### Diferença vs TelemetryStream:
- **MissionLink.sendMetrics ("M"):** Alertas críticos (quando limites excedidos) via UDP
- **TelemetryStream:** Telemetria contínua normal (periódica) via TCP

### Conclusão sobre `sendMetrics`:
✅ **CORRETO** - Não é redundante com TelemetryStream

**Justificativa:**
1. **Alertas críticos** precisam de confirmação imediata (UDP com ACK)
2. **Telemetria contínua** é periódica e não crítica (TCP)
3. **Separação de responsabilidades:**
   - MissionLink: Comunicação crítica (missões, alertas)
   - TelemetryStream: Monitorização contínua

## Verificação de Uso

### Onde `sendMetrics` é usado:
- `NMS_Agent.sendMetrics()` - Envia alertas quando limites são excedidos
- Formato: `alert_idMission_task-XXX_iter.json`
- Via MissionLink (UDP)

### Onde TelemetryStream é usado:
- `NMS_Agent.sendTelemetry()` - Envia telemetria contínua
- Formato: `telemetry_rover_id_timestamp.json`
- Via TelemetryStream (TCP)

## Conclusão Final

### ✅ Flags no MissionLink.py:
**TODAS CORRETAS E NECESSÁRIAS**
- S, Z, A, F, D são essenciais para fiabilidade sobre UDP
- Não há flags a mais ou erradas

### ✅ Tipos de Operação (missionType):
**TODOS CORRETOS E NECESSÁRIOS**
- R (Register) ✅ - Registro de rovers
- T (Task) ✅ - Envio de missões
- M (Metrics) ✅ - Alertas críticos (NÃO é redundante com TelemetryStream)
- Q (Request) ✅ - Solicitação de missões
- P (Progress) ✅ - Reporte de progresso
- N (None) ✅ - ACKs/FINs

### ⚠️ Nomenclatura Pode Ser Confusa:
- `sendMetrics` pode parecer que é para telemetria contínua
- Mas na verdade é para **alertas críticos** quando limites são excedidos
- **Sugestão:** Renomear para `sendAlert` ou `sendCriticalMetrics` para maior clareza

## Problema Encontrado

### ❌ Uso Incorreto em `client.py`:
- Linha 60: `client.sendTelemetry("10.0.4.10","alert_n1_task-202_1.json")`
- **Problema:** Ficheiros `alert_*` devem usar `sendMetrics()` (MissionLink/UDP), não `sendTelemetry()` (TelemetryStream/TCP)
- **Correção:** Comentado e corrigido

## Recomendação

**Status:** ✅ **TUDO CORRETO** - Não há flags ou tasks a mais ou erradas

**Observação:**
- `sendMetrics` ("M") é para alertas críticos via MissionLink (UDP)
- TelemetryStream é para telemetria contínua via TCP
- São propósitos diferentes e ambos necessários

**Correções Aplicadas:**
- ✅ Comentário adicionado em `MissionLink.py` explicando diferença entre `sendMetrics` e TelemetryStream
- ✅ Uso incorreto em `client.py` corrigido (comentado com explicação)

**Melhoria Opcional:**
- Renomear `sendMetrics` para `sendAlert` para maior clareza (não obrigatório)

