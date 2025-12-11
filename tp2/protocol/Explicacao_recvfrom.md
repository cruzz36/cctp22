# Explicação: `recvfrom()` - Função UDP para Receção de Datagramas

## O que é `recvfrom()`?

`recvfrom()` é uma função de socket **específica para UDP** que recebe datagramas e retorna **tanto os dados quanto o endereço de origem**.

## Sintaxe

```python
dados, (ip_origem, porta_origem) = socket.recvfrom(buffer_size)
```

**Retorna**:
- `dados` (bytes): Os dados recebidos
- `(ip_origem, porta_origem)` (tuple): Endereço IP e porta de onde vieram os dados

## Porquê `recvfrom()` e não `recv()`?

### TCP usa `recv()`:
```python
# TCP - socket já está conectado, não precisa saber origem
dados = socket.recv(buffer_size)
```

**Porquê**: TCP tem conexão estabelecida. O socket já "sabe" de onde vêm os dados porque está conectado a um endereço específico.

### UDP usa `recvfrom()`:
```python
# UDP - não tem conexão, precisa saber origem
dados, (ip, porta) = socket.recvfrom(buffer_size)
```

**Porquê**: UDP não tem conexão. Cada mensagem é independente e pode vir de qualquer endereço. Precisamos saber de onde veio para:
1. **Validar** que a mensagem vem do remetente correto
2. **Responder** ao remetente correto
3. **Rejeitar** mensagens de remetentes não autorizados

## Exemplo no MissionLink

### Handshake - Receber SYN:
```python
# Servidor recebe SYN do cliente
message, (ip, port) = self.sock.recvfrom(self.limit.buffersize)
# Agora sabemos:
# - message: dados do SYN
# - ip: IP do cliente que quer conectar
# - port: porta do cliente
# Podemos validar e responder ao cliente correto
```

### Envio de Dados - Receber ACK:
```python
# Cliente envia dados e aguarda ACK
self.sock.sendto(dados, (ip_destino, porta_destino))
text, (responseIp, responsePort) = self.sock.recvfrom(self.limit.buffersize)

# Validação: ACK deve vir do destinatário correto
if responseIp == ip_destino and responsePort == porta_destino:
    # ACK válido - dados foram recebidos
else:
    # ACK de origem desconhecida - ignorar ou rejeitar
```

## Diferenças Chave: `recv()` vs `recvfrom()`

| Característica | `recv()` (TCP) | `recvfrom()` (UDP) |
|----------------|----------------|-------------------|
| **Protocolo** | TCP | UDP |
| **Conexão** | Requer conexão estabelecida | Não requer conexão |
| **Retorno** | Apenas dados (bytes) | Dados + endereço origem (tuple) |
| **Validação** | Socket já valida origem | Aplicação deve validar origem |
| **Uso** | `dados = socket.recv(size)` | `dados, (ip, port) = socket.recvfrom(size)` |

## Porquê Validar IP/Porta no MissionLink?

No código do MissionLink, vemos validações como:

```python
if (
    responseIp == ip and
    responsePort == port and
    lista[flagPos] == self.ackkey and
    lista[ackPos] == str(seq)
):
    # Mensagem válida - processar
```

**Porquê**:
1. **Segurança**: Rejeitar mensagens de atacantes ou rovers não autorizados
2. **Correção**: Garantir que ACK vem do destinatário correto, não de outro rover
3. **Fiabilidade**: Em UDP, mensagens podem vir de qualquer lugar - precisamos filtrar

## Exemplo Completo

```python
# Servidor UDP aguarda mensagem
message, (ip_cliente, porta_cliente) = self.sock.recvfrom(1024)

# Processar mensagem
dados = message.decode()

# Responder ao cliente correto
resposta = "ACK recebido"
self.sock.sendto(resposta.encode(), (ip_cliente, porta_cliente))
```

## Resumo

- **`recvfrom()`** é usado em **UDP** porque não há conexão
- Retorna **dados + endereço de origem** (tuple)
- Permite **validar** que mensagens vêm do remetente correto
- **Necessário** para segurança e correção em protocolos UDP
- **Diferente de `recv()`** (TCP) que só retorna dados

---

**No MissionLink**: `recvfrom()` é usado em **todos os locais** onde se recebe mensagens UDP, permitindo validar que as mensagens vêm do remetente correto através da comparação de IP/porta.

