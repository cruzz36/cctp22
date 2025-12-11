# Pasta de Debug - MissionLink

Esta pasta contém ficheiros de teste e debug para o protocolo MissionLink.

## Ficheiros

### `test_all_missionlink_functions.py` ⭐ **PRINCIPAL**
Script completo que testa **TODAS** as 9 funções do `MissionLink.py`:

1. **`__init__`** - Inicialização do protocolo
2. **`server()`** - Bind do socket UDP
3. **`getHeaderSize()`** - Cálculo do tamanho do cabeçalho
4. **`formatMessage()`** - Formatação de mensagens
5. **`splitMessage()`** - Divisão de mensagens grandes
6. **`startConnection()`** - Handshake 3-way (cliente)
7. **`acceptConnection()`** - Handshake 3-way (servidor)
8. **`send()`** - Envio (mensagem curta, longa, ficheiro)
9. **`recv()`** - Receção (mensagem, ficheiro)

**Este é o script mais completo - testa todas as funções individualmente.**

### `test_missionlink_debug.py`
Script de teste básico com 3 testes principais:
- Handshake 3-way
- Envio/Receção de mensagem
- Transferência de ficheiro

**Útil para testes rápidos.**

### `DEBUG_MissionLink.md`
Guia completo de debug com:
- Métodos de debug (prints, pdb, logging)
- Exemplos de código para cada método
- Debug específico por função
- Problemas comuns e soluções
- Ferramentas úteis (Wireshark, netcat, tcpdump)

## Como Usar

### Executar Todos os Testes
```bash
cd CC/tp2
python debug/test_all_missionlink_functions.py all
```

### Executar Teste Específico
```bash
# Teste de inicialização
python debug/test_all_missionlink_functions.py init

# Teste de formatação
python debug/test_all_missionlink_functions.py format

# Teste de handshake
python debug/test_all_missionlink_functions.py handshake

# Teste de envio de mensagem curta
python debug/test_all_missionlink_functions.py send_short

# Teste de envio de mensagem longa
python debug/test_all_missionlink_functions.py send_long

# Teste de envio de ficheiro
python debug/test_all_missionlink_functions.py send_file
```

## Testes Disponíveis

| Comando | Função Testada | Descrição |
|---------|---------------|-----------|
| `init` | `__init__` | Testa inicialização e atributos |
| `server` | `server()` | Testa bind do socket |
| `header` | `getHeaderSize()` | Testa cálculo do cabeçalho |
| `format` | `formatMessage()` | Testa formatação de mensagens |
| `split` | `splitMessage()` | Testa divisão de mensagens |
| `handshake` | `startConnection()` + `acceptConnection()` | Testa handshake 3-way |
| `send_short` | `send()` | Testa envio de mensagem curta |
| `send_long` | `send()` | Testa envio de mensagem longa (chunks) |
| `send_file` | `send()` | Testa envio de ficheiro |
| `recv_message` | `recv()` | Testa receção de mensagem |
| `recv_file` | `recv()` | Testa receção de ficheiro |
| `all` | Todas | Executa todos os testes |

## Estrutura de Pastas

```
debug/
├── README.md (este ficheiro)
├── test_all_missionlink_functions.py (teste completo de todas as funções) ⭐
├── test_missionlink_debug.py (teste básico)
├── DEBUG_MissionLink.md (guia de debug)
└── test_files/
    ├── server/ (ficheiros recebidos pelo servidor)
    └── client/ (ficheiros do cliente)
```

## Output dos Testes

Os testes mostram:
- ✅ **SUCCESS**: Teste passou
- ❌ **ERROR**: Teste falhou
- **INFO**: Informações de debug
- **Resumo final**: Total de testes passados/falhados

## Notas

- Os testes usam `127.0.0.1` (localhost) para comunicação
- Timeout aumentado para 5-10 segundos durante testes
- Ficheiros de teste são criados automaticamente em `test_files/`
- Cada teste é executado em threads separadas (servidor e cliente)

## Troubleshooting

Se um teste falhar:
1. Verificar se a porta 8080 está livre
2. Verificar se não há outras instâncias a correr
3. Aumentar timeout se necessário
4. Verificar logs de erro no output

