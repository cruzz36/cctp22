# Descrição Detalhada da Implementação do Protocolo TelemetryStream

## Índice
1. [Visão Geral](#visão-geral)
2. [Arquitetura do Protocolo](#arquitetura-do-protocolo)
3. [Formato de Mensagem](#formato-de-mensagem)
4. [Mecanismos de Controlo](#mecanismos-de-controlo)
5. [Estabelecimento de Conexão](#estabelecimento-de-conexão)
6. [Envio de Dados](#envio-de-dados)
7. [Receção de Dados](#receção-de-dados)
8. [Processamento Paralelo](#processamento-paralelo)
9. [Organização de Dados](#organização-de-dados)
10. [Estrutura de Dados de Telemetria](#estrutura-de-dados-de-telemetria)
11. [Tratamento de Erros](#tratamento-de-erros)
12. [Exemplos de Uso](#exemplos-de-uso)
13. [Considerações de Implementação](#considerações-de-implementação)

---

## 1. Visão Geral

O **TelemetryStream (TS)** é um protocolo aplicacional sobre TCP desenvolvido para transmissão contínua de dados de monitorização dos **rovers** para a **Nave-Mãe** (servidor). Diferentemente do MissionLink, que é usado para comunicação crítica sobre UDP, o TelemetryStream utiliza TCP para garantir entrega confiável de dados de telemetria periódicos.

### Características Principais:
- **Protocolo de transporte**: TCP (Transmission Control Protocol)
- **Porta padrão**: 8081
- **Fiabilidade**: Garantida pelo próprio TCP através de:
  - Conexões orientadas a conexão
  - Entrega garantida e ordenada
  - Deteção automática de erros
  - Retransmissão automática pelo TCP
- **Processamento paralelo**: Suporta múltiplos rovers simultaneamente usando threads
- **Organização automática**: Organiza dados recebidos por `rover_id`

### Objetivos:
1. Garantir transmissão contínua e confiável de dados de monitorização
2. Suportar múltiplos rovers em paralelo
3. Organizar dados de telemetria por rover
4. Facilitar monitorização contínua em tempo real
5. Transmitir dados de telemetria completos (posição, estado, métricas técnicas)

### Diferença vs MissionLink:
- **MissionLink (UDP)**: Comunicação crítica (missões, registos, progresso)
- **TelemetryStream (TCP)**: Monitorização contínua periódica (telemetria)

---

## 2. Arquitetura do Protocolo

### Estrutura da Classe TelemetryStream

```python
class TelemetryStream:
    def __init__(self, ip, storefolder=".", limit=1024)
    def server()
    def _handle_client(clientSocket, ip, port)
    def formatInteger(num)
    def recv(clientSock, ip, port)
    def send(ip, message)
    def endConnection()
```

### Componentes Principais:

1. **Socket TCP**: `socket.socket(socket.AF_INET, socket.SOCK_STREAM)`
   - Comunicação orientada a conexão
   - Fiabilidade garantida pelo TCP
   - Suporta múltiplas conexões simultâneas

2. **Threading**: Processamento paralelo
   - Cada conexão de rover é processada em thread separada
   - Permite receber telemetria de múltiplos rovers simultaneamente
   - Threads daemon para cleanup automático

3. **Organização de Dados**: Estrutura de pastas
   - Dados organizados por `rover_id` automaticamente
   - Facilita análise e processamento posterior

---

## 3. Formato de Mensagem

### Estrutura do Protocolo

O protocolo TelemetryStream utiliza um formato simples baseado em tamanhos prefixados:

```
[tamanho_nome(4 bytes)][nome_ficheiro][conteúdo_ficheiro]
```

### Campos Detalhados:

| Campo | Tamanho | Descrição | Exemplo |
|-------|---------|-----------|---------|
| `tamanho_nome` | 4 bytes | Tamanho do nome do ficheiro (string formatada com zeros à esquerda) | `"0025"` |
| `nome_ficheiro` | Variável (1-255 bytes) | Nome do ficheiro de telemetria | `"telemetry_r1_1234567890.json"` |
| `conteúdo_ficheiro` | Variável | Conteúdo do ficheiro (JSON com dados de telemetria) | `"{...}"` |

### Exemplo de Mensagem:

```
0025telemetry_r1_1234567890.json{"rover_id":"r1","position":{"x":10.5,"y":20.3,"z":0.0},"operational_status":"em missão",...}
```

### Formato do Nome do Ficheiro:

O nome do ficheiro segue o padrão:
```
telemetry_{rover_id}_{timestamp}.json
```

Exemplo: `telemetry_r1_1704067200.json`

---

## 4. Mecanismos de Controlo

### 4.1 Validação de Tamanho do Nome

**Função**: Prevenir ataques e garantir integridade.

**Como funciona**:
- Primeiro recebe 4 bytes que indicam o tamanho do nome
- Valida que o tamanho está entre 1 e 255 bytes
- Previne buffer overflow e ataques de negação de serviço

**Código**:
```python
fileNameLen = int(message.decode())
if fileNameLen < 1 or fileNameLen > 255:
    raise ValueError(f"Tamanho do nome do ficheiro inválido: {fileNameLen}")
```

### 4.2 Validação de Integridade

**Validações realizadas**:
1. **Tamanho do nome**: Verifica que recebeu exatamente 4 bytes para o tamanho
2. **Nome do ficheiro**: Valida que recebeu exatamente o número de bytes indicado
3. **Conteúdo**: Recebe até encontrar dados vazios (fim do stream)

### 4.3 Formatação de Tamanho

**Função**: Garantir que o tamanho do nome sempre ocupa 4 bytes.

**Como funciona**:
- Formata número inteiro como string com 4 dígitos
- Preenche com zeros à esquerda se necessário
- Exemplo: `25` → `"0025"`, `123` → `"0123"`

**Código**:
```python
def formatInteger(self, num):
    line = str(num)
    displacement = 4 - len(line)
    for i in range(displacement):
        line = "0" + line
    return line
```

---

## 5. Estabelecimento de Conexão

### 5.1 Modo Servidor

**Função**: Aceitar conexões de múltiplos rovers.

**Como funciona**:
1. Socket faz `bind()` ao endereço IP e porta 8081
2. Socket entra em modo `listen()`
3. Loop infinito aceita conexões com `accept()`
4. Cada conexão é processada em thread separada

**Código**:
```python
def server(self):
    self.socket.listen()
    while True:
        clientSocket, (ip, _) = self.socket.accept()
        # Criar thread para processar conexão
        client_thread = threading.Thread(
            target=self._handle_client,
            args=(clientSocket, ip, self.port),
            daemon=True
        )
        client_thread.start()
```

### 5.2 Modo Cliente

**Função**: Conectar ao servidor para enviar telemetria.

**Como funciona**:
1. Cria novo socket TCP para cada envio
2. Conecta ao servidor usando `connect()`
3. Envia dados
4. Fecha conexão após envio

**Nota**: Um novo socket é criado para cada envio porque o socket principal pode estar ligado como servidor.

**Código**:
```python
def send(self, ip, message):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((ip, self.port))
    # Enviar dados...
    client_socket.close()
```

---

## 6. Envio de Dados

### 6.1 Método `send()`

O método `send()` é responsável por enviar um ficheiro de telemetria para o servidor.

**Fluxo**:
1. Verifica se o ficheiro existe
2. Cria novo socket TCP
3. Conecta ao servidor
4. Envia tamanho do nome (4 bytes)
5. Envia nome do ficheiro
6. Envia conteúdo do ficheiro em chunks
7. Fecha conexão

**Código**:
```python
def send(self, ip, message):
    # Verificar se ficheiro existe
    if not os.path.exists(message):
        return False
    
    # Criar novo socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((ip, self.port))
    
    # Enviar tamanho do nome
    filename = os.path.basename(message)
    length = self.formatInteger(len(filename))
    client_socket.sendall(length.encode())
    
    # Enviar nome do ficheiro
    client_socket.sendall(filename.encode())
    
    # Enviar conteúdo em chunks
    with open(message, "r") as file:
        buffer = file.read(self.limit.buffersize)
        while buffer != "":
            client_socket.sendall(buffer.encode())
            buffer = file.read(self.limit.buffersize)
    
    client_socket.close()
    return True
```

### 6.2 Tratamento de Erros no Envio

**Erros tratados**:
- `FileNotFoundError`: Ficheiro não existe
- `ConnectionRefusedError`: Servidor não está a escutar
- `TimeoutError`: Timeout ao conectar
- `OSError`: Outros erros de conexão

Todos os erros retornam `False` e fecham o socket apropriadamente.

---

## 7. Receção de Dados

### 7.1 Método `recv()`

O método `recv()` é responsável por receber dados de telemetria de um cliente através de uma conexão TCP.

**Fluxo**:
1. Recebe 4 bytes (tamanho do nome)
2. Valida tamanho recebido
3. Recebe nome do ficheiro (número de bytes indicado)
4. Valida nome recebido
5. Recebe conteúdo do ficheiro em chunks
6. Escreve ficheiro na pasta de armazenamento
7. Retorna nome do ficheiro

**Código**:
```python
def recv(self, clientSock, ip, port):
    # Receber tamanho do nome (4 bytes)
    message = clientSock.recv(lenMessageSize)
    if len(message) != lenMessageSize:
        raise ValueError("Tamanho do nome do ficheiro inválido")
    
    fileNameLen = int(message.decode())
    
    # Validar tamanho
    if fileNameLen < 1 or fileNameLen > 255:
        raise ValueError(f"Tamanho inválido: {fileNameLen}")
    
    # Receber nome do ficheiro
    filename = clientSock.recv(fileNameLen)
    if len(filename) != fileNameLen:
        raise ValueError("Nome do ficheiro incompleto")
    
    filename_str = filename.decode()
    
    # Criar pasta se não existir
    os.makedirs(self.storefolder, exist_ok=True)
    
    # Receber e escrever conteúdo
    file_path = os.path.join(self.storefolder, filename_str)
    with open(file_path, "w") as file:
        message = clientSock.recv(self.limit.buffersize)
        while message != b"":
            file.write(message.decode())
            message = clientSock.recv(self.limit.buffersize)
    
    return filename
```

### 7.2 Tratamento de Erros na Receção

**Erros tratados**:
- `ValueError`: Tamanho ou nome do ficheiro inválido
- `OSError`: Erro ao escrever ficheiro
- `Exception`: Outros erros gerais

Todos os erros são impressos e re-levantados para tratamento no nível superior.

---

## 8. Processamento Paralelo

### 8.1 Arquitetura de Threads

**Função**: Permitir processamento simultâneo de múltiplos rovers.

**Como funciona**:
1. Servidor aceita conexões em loop infinito
2. Para cada conexão, cria thread separada
3. Thread processa dados de telemetria independentemente
4. Thread fecha conexão após processamento

**Vantagens**:
- Múltiplos rovers podem enviar telemetria simultaneamente
- Uma conexão lenta não bloqueia outras
- Melhora capacidade de processamento

**Código**:
```python
def server(self):
    self.socket.listen()
    while True:
        clientSocket, (ip, _) = self.socket.accept()
        client_thread = threading.Thread(
            target=self._handle_client,
            args=(clientSocket, ip, self.port),
            daemon=True  # Thread termina quando programa principal termina
        )
        client_thread.start()
```

### 8.2 Handler de Cliente

**Função**: Processar dados de um cliente específico.

**Como funciona**:
1. Recebe dados de telemetria via `recv()`
2. Tenta organizar ficheiro por `rover_id`
3. Imprime confirmação
4. Fecha conexão

**Código**:
```python
def _handle_client(self, clientSocket, ip, port):
    try:
        filename = self.recv(clientSocket, ip, port)
        # Tentar organizar por rover_id...
        print(f"Telemetria recebida de {ip}: {filename.decode()}")
    except Exception as e:
        print(f"Erro ao receber telemetria de {ip}: {e}")
    finally:
        clientSocket.close()
```

---

## 9. Organização de Dados

### 9.1 Organização por Rover

**Função**: Organizar dados de telemetria por `rover_id` para facilitar análise.

**Como funciona**:
1. Após receber ficheiro, tenta ler conteúdo JSON
2. Extrai `rover_id` do JSON
3. Cria pasta `{storefolder}/{rover_id}/` se não existir
4. Move ficheiro para pasta do rover

**Código**:
```python
# Ler ficheiro recebido
with open(file_path, "r") as f:
    telemetry_data = json.load(f)
    rover_id = telemetry_data.get("rover_id", "unknown")
    
    # Criar pasta por rover
    rover_folder = os.path.join(self.storefolder, rover_id)
    os.makedirs(rover_folder, exist_ok=True)
    
    # Mover ficheiro
    new_path = os.path.join(rover_folder, filename_str)
    if os.path.exists(file_path) and file_path != new_path:
        os.rename(file_path, new_path)
```

### 9.2 Estrutura de Pastas

**Estrutura resultante**:
```
storefolder/
├── rover_id_1/
│   ├── telemetry_r1_1234567890.json
│   ├── telemetry_r1_1234567920.json
│   └── ...
├── rover_id_2/
│   ├── telemetry_r2_1234567890.json
│   └── ...
└── ...
```

**Vantagens**:
- Fácil análise de dados por rover
- Organização automática
- Facilita processamento posterior

---

## 10. Estrutura de Dados de Telemetria

### 10.1 Campos Obrigatórios

Conforme requisitos do PDF, cada mensagem de telemetria deve conter:

1. **rover_id** (string): Identificação inequívoca do rover
2. **position** (dict): Localização com coordenadas
   - `x` (float): Coordenada X
   - `y` (float): Coordenada Y
   - `z` (float): Coordenada Z (opcional, padrão 0.0)
3. **operational_status** (string): Estado operacional
   - Valores possíveis: "parado", "em missão", "a caminho", "erro"

### 10.2 Campos Opcionais

Campos adicionais que podem ser incluídos:

- **battery** (float): Nível de bateria (0-100%)
- **velocity** (float): Velocidade em m/s
- **direction** (float): Direção em graus (0-360)
- **temperature** (float): Temperatura interna
- **system_health** (string): Estado de saúde do sistema
- **Métricas técnicas**: CPU, RAM, bandwidth, jitter, packet_loss, latency, etc.

### 10.3 Exemplo de JSON

```json
{
    "rover_id": "r1",
    "position": {
        "x": 10.5,
        "y": 20.3,
        "z": 0.0
    },
    "operational_status": "em missão",
    "battery": 75.0,
    "velocity": 1.5,
    "direction": 45.0,
    "temperature": 25.0,
    "system_health": "operacional",
    "cpu_usage": 45.2,
    "ram_usage": 60.5,
    "bandwidth": "100 Mbps",
    "latency": "5 ms"
}
```

---

## 11. Tratamento de Erros

### 11.1 Erros de Conexão

**ConnectionRefusedError**: Servidor não está a escutar
```python
except ConnectionRefusedError:
    print(f"Erro: Servidor {ip}:{self.port} recusou conexão")
    return False
```

**TimeoutError**: Timeout ao conectar
```python
except TimeoutError:
    print(f"Erro: Timeout ao conectar a {ip}:{self.port}")
    return False
```

### 11.2 Erros de Validação

**ValueError**: Tamanho ou nome do ficheiro inválido
```python
except ValueError as e:
    print(f"Erro de validação ao receber telemetria: {e}")
    raise
```

### 11.3 Erros de Sistema

**OSError**: Erro ao escrever ficheiro ou problemas de rede
```python
except OSError as e:
    print(f"Erro ao escrever ficheiro de telemetria: {e}")
    raise
```

### 11.4 Tratamento Robusto

- Todos os erros são capturados e tratados apropriadamente
- Conexões são sempre fechadas (usando `finally`)
- Servidor continua a funcionar mesmo se uma conexão falhar
- Mensagens de erro informativas para debug

---

## 12. Exemplos de Uso

### 12.1 Exemplo 1: Servidor Recebe Telemetria

```python
# Na Nave-Mãe (NMS_Server)
from protocol import TelemetryStream
import threading

telemetry_server = TelemetryStream.TelemetryStream("0.0.0.0", "alerts/")

# Iniciar servidor em thread separada
server_thread = threading.Thread(target=telemetry_server.server, daemon=True)
server_thread.start()

# Servidor agora está a escutar e aceitar conexões
# Cada rover que conectar será processado em thread separada
```

### 12.2 Exemplo 2: Rover Envia Telemetria Única

```python
# No rover (NMS_Agent)
from client import NMS_Agent

rover = NMS_Agent.NMS_Agent("10.0.4.10")

# Atualizar estado do rover
rover.updatePosition(10.5, 20.3, 0.0)
rover.updateOperationalStatus("em missão")
rover.updateBattery(75.0)

# Criar e enviar telemetria
success = rover.createAndSendTelemetry("10.0.4.10")
if success:
    print("Telemetria enviada com sucesso")
```

### 12.3 Exemplo 3: Monitorização Contínua

```python
# No rover
rover = NMS_Agent.NMS_Agent("10.0.4.10")

# Configurar dispositivos para recolher métricas
devices = [device1, device2]  # Lista de objetos Device
rover.setDevices(devices)

# Iniciar monitorização contínua (envia a cada 30 segundos)
rover.startContinuousTelemetry("10.0.4.10", interval_seconds=30, devices=devices)

# ... rover continua a operar ...

# Parar monitorização quando necessário
rover.stopContinuousTelemetry()
```

### 12.4 Exemplo 4: Criar Mensagem de Telemetria Manual

```python
# No rover
rover = NMS_Agent.NMS_Agent("10.0.4.10")

# Atualizar estado
rover.updatePosition(15.0, 25.0, 0.0)
rover.updateOperationalStatus("a caminho")
rover.updateBattery(80.0)

# Criar mensagem de telemetria
telemetry = rover.createTelemetryMessage()

# Adicionar métricas técnicas manualmente
metrics = {
    "cpu_usage": 50.0,
    "ram_usage": 65.0,
    "latency": "3 ms"
}
telemetry_with_metrics = rover.createTelemetryMessage(metrics)

# Salvar em ficheiro e enviar
import json
with open("telemetry.json", "w") as f:
    json.dump(telemetry_with_metrics, f, indent=2)

rover.sendTelemetry("10.0.4.10", "telemetry.json")
```

---

## 13. Considerações de Implementação

### 13.1 Vantagens do TCP

1. **Fiabilidade garantida**: TCP garante entrega e ordem
2. **Sem necessidade de ACKs manuais**: TCP trata isso automaticamente
3. **Stream-oriented**: Dados são transmitidos como stream contínuo
4. **Menos complexidade**: Não precisa implementar handshakes, sequências, etc.

### 13.2 Limitações

1. **Overhead maior**: TCP tem mais overhead que UDP
2. **Conexão por envio**: Cada envio cria nova conexão (pode ser otimizado)
3. **Sem multiplexing**: Cada conexão é independente
4. **Tamanho de buffer**: Limitado pelo buffersize (1024 bytes por chunk)

### 13.3 Melhorias Possíveis

1. **Conexões persistentes**: Manter conexão aberta para múltiplos envios
2. **Compressão**: Comprimir dados JSON antes de enviar
3. **Encriptação**: Adicionar TLS/SSL para segurança
4. **Buffering**: Agrupar múltiplas mensagens antes de enviar
5. **Priorização**: Priorizar telemetria crítica

### 13.4 Boas Práticas

1. **Sempre validar tamanhos** antes de receber dados
2. **Usar threads daemon** para cleanup automático
3. **Fechar conexões** apropriadamente (usar `finally`)
4. **Organizar dados** por rover para facilitar análise
5. **Tratar todos os erros** sem quebrar o servidor

---

## 14. Conclusão

O protocolo TelemetryStream implementa com sucesso transmissão contínua de dados de monitorização sobre TCP, permitindo que múltiplos rovers enviem telemetria simultaneamente para a Nave-Mãe. Através de processamento paralelo com threads e organização automática de dados, o protocolo facilita monitorização contínua em tempo real de todos os rovers no sistema.

A implementação é robusta, com validações extensivas, tratamento de erros apropriado e organização automática que garantem integridade e facilidade de processamento dos dados de telemetria recebidos.

---

**Versão**: 1.0  
**Data**: 2024  
**Autor**: Sistema de Documentação Automática

