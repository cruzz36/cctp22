# Guia Rápido: Testar no CORE e Limpar Coisas Antigas

## 🧹 PASSO 1: Limpar Processos e Código Antigos

### No Host CORE (terminal do sistema, não dentro dos nós):

```bash
# 1. Ir para o diretório do projeto
cd /home/core/Downloads/cctp2-main/tp2

# 2. Obter número da sessão CORE atual
SESSION=$(ls -d /tmp/pycore.* | head -1)
echo "Sessão CORE: $SESSION"

# 3. Parar TODOS os processos antigos em TODOS os nós
for NODE in NaveMae GroundControl Rover1 Rover2; do
  echo "[$NODE] A parar processos antigos..."
  sudo vcmd -c $SESSION/$NODE -- sh -c 'pkill -f start_nms.py || true; pkill -f start_rover.py || true; pkill -f start_ground_control.py || true; pkill -f MissionLink || true; pkill -f TelemetryStream || true; fuser -k 8080/udp 8081/tcp 8082/tcp 2>/dev/null || true'
done

# 4. Limpar código antigo em TODOS os nós
for NODE in NaveMae GroundControl Rover1 Rover2; do
  echo "[$NODE] A limpar /tmp/nms..."
  sudo vcmd -c $SESSION/$NODE -- sh -c 'rm -rf /tmp/nms'
done

echo "✅ Limpeza concluída!"
```

### Ou manualmente em cada nó (se preferires):

Em cada terminal de cada nó (NaveMae, GroundControl, Rover1, Rover2):
```bash
# Parar processos
pkill -f start_nms.py || true
pkill -f start_rover.py || true
pkill -f start_ground_control.py || true
fuser -k 8080/udp 8081/tcp 8082/tcp 2>/dev/null || true

# Limpar código
rm -rf /tmp/nms
```

---

## 📦 PASSO 2: Copiar Novo Código para os Nós

### No Host CORE:

```bash
cd /home/core/Downloads/cctp2-main/tp2

# Gerar novo tar.gz com código atualizado
python3 copy_to_core.py

# Verificar que foi criado
ls -lh nms_code.tar.gz
```

### Copiar para todos os nós (automático):

```bash
SESSION=$(ls -d /tmp/pycore.* | head -1)

for NODE in NaveMae GroundControl Rover1 Rover2; do
  echo "[$NODE] A copiar código..."
  sudo sh -c "cat nms_code.tar.gz | vcmd -c $SESSION/$NODE -- sh -c 'mkdir -p /tmp/nms && cd /tmp/nms && tar -xzf - && chmod +x scripts/apply_routes.sh 2>/dev/null || true'"
done

echo "✅ Código copiado para todos os nós!"
```

### Verificar que funcionou:

```bash
SESSION=$(ls -d /tmp/pycore.* | head -1)
sudo vcmd -c $SESSION/NaveMae -- sh -c 'ls -la /tmp/nms/start_nms.py'
```

Se aparecer o ficheiro, está tudo OK!

---

## 🔧 PASSO 3: Configurar Rotas de Rede (CRÍTICO!)

### Opção A: Automático (RECOMENDADO)

No Host CORE:
```bash
SESSION=$(ls -d /tmp/pycore.* | head -1)

for NODE in NaveMae GroundControl Rover1 Rover2 Satelite; do
  echo "[$NODE] A aplicar rotas..."
  sudo vcmd -c $SESSION/$NODE -- sh -c 'cd /tmp/nms && chmod +x verificar_rotas.sh 2>/dev/null && ./verificar_rotas.sh 2>/dev/null || echo "Script não encontrado, aplicar manualmente"'
done
```

### Opção B: Manual (em cada nó)

**No terminal do Satélite:**
```bash
echo 1 > /proc/sys/net/ipv4/ip_forward
cat /proc/sys/net/ipv4/ip_forward  # Deve mostrar "1"
```

**No terminal da NaveMae:**
```bash
ip route add 10.0.2.0/24 via 10.0.1.1
ip route add 10.0.3.0/24 via 10.0.1.1
ip route show  # Verificar
```

**No terminal do GroundControl:**
```bash
ip route add 10.0.1.0/24 via 10.0.0.11
ip route show  # Verificar
```

**No terminal do Rover1:**
```bash
ip route add default via 10.0.3.1
ip route show  # Verificar
```

**No terminal do Rover2:**
```bash
ip route add default via 10.0.2.1
ip route show  # Verificar
```

### Testar Conectividade:

```bash
# No Rover1 ou Rover2:
ping -c 2 10.0.1.10  # Deve responder

# No GroundControl:
ping -c 2 10.0.1.10  # Deve responder
```

**⚠️ IMPORTANTE:** Só continua para o próximo passo se os pings funcionarem!

---

## 📚 PASSO 4: Instalar Dependências (se necessário)

### Em cada nó (NaveMae, GroundControl, Rover1, Rover2):

```bash
cd /tmp/nms
pip3 install -r requirements.txt
```

Se aparecer "Requirement already satisfied" para todos, podes saltar este passo.

---

## 🚀 PASSO 5: Arrancar Serviços (ORDEM IMPORTANTE!)

### 1. Nave-Mãe (n1 - NaveMae)

No terminal da NaveMae:
```bash
cd /tmp/nms
python3 start_nms.py
```

**Aguardar** até ver mensagens como:
- `[OK] MissionLink (UDP:8080) iniciado`
- `[OK] TelemetryStream (TCP:8081) iniciado`
- `[OK] API de Observação (HTTP:8082) iniciada`

### 2. Rovers (n3 e n4 - Rover1 e Rover2)

**No terminal do Rover1:**
```bash
cd /tmp/nms
python3 start_rover.py 10.0.1.10 r1
```

**No terminal do Rover2:**
```bash
cd /tmp/nms
python3 start_rover.py 10.0.1.10 r2
```

**Aguardar** até ver:
- `[OK] Registado como r1/r2 na Nave-Mãe`
- `[OK] Listener de missões ativo`
- `[OK] Telemetria contínua ativa`

**O que deve acontecer automaticamente:**
- Os rovers registam-se
- O servidor carrega missões do `serverDB` automaticamente
- As missões são enviadas aos rovers
- Os rovers começam a executar as missões
- A posição é atualizada gradualmente

### 3. Ground Control (n2 - GroundControl)

**No terminal do GroundControl:**
```bash
cd /tmp/nms
python3 start_ground_control.py
```

**Aguardar** até ver:
- `[OK] Conexão estabelecida com sucesso!`

---

## ✅ PASSO 6: Verificar que Está a Funcionar

### 1. Verificar API (em qualquer nó):

```bash
curl http://10.0.1.10:8082/rovers
curl http://10.0.1.10:8082/missions?status=active
curl http://10.0.1.10:8082/telemetry?limit=5
```

### 2. Verificar Ground Control:

No terminal do GroundControl, deves ver:
- Rovers listados
- Missões ativas (M-001, M-002, M-003)
- Telemetria com posições atualizadas (não só zeros!)
- Progresso das missões

### 3. Verificar Logs dos Rovers:

Nos terminais dos rovers, deves ver:
- `[OK] Missão recebida e validada`
- `[INFO] executeMission: Iniciando execução da missão M-XXX`
- `[DEBUG] executeMission: Enviando telemetria X/Y`
- Posições a mudarem (não só 0.00, 0.00, 0.00)

### 4. Verificar Logs da Nave-Mãe:

No terminal da NaveMae, deves ver:
- `[OK] Rover r1 registado com sucesso`
- `[DEBUG] _loadMissionsForRover: Encontrada missão M-XXX para rover r1`
- `[OK] sendMission: Missão M-XXX confirmada por r1`
- `[DEBUG] handleMissionProgress: Progresso recebido`

---

## 🐛 Se Algo Não Funcionar

### Problema: Rovers não se registam

**Solução:**
1. Verificar rotas: `ip route show` em cada nó
2. Verificar IP forwarding no Satélite: `cat /proc/sys/net/ipv4/ip_forward` (deve ser "1")
3. Testar ping: `ping -c 2 10.0.1.10` (deve responder)
4. Se não funcionar, aplicar rotas manualmente (PASSO 3)

### Problema: Missões não aparecem

**Solução:**
1. Verificar que existem ficheiros em `serverDB/`:
   ```bash
   # No host CORE:
   ls -la /home/core/Downloads/cctp2-main/tp2/serverDB/mission*.json
   ```
2. Verificar que os rovers têm ID correto (r1, r2) nos ficheiros JSON
3. Verificar logs da NaveMae para ver se carregou missões

### Problema: Telemetria só mostra zeros

**Solução:**
1. Verificar que os rovers receberam missões (ver logs)
2. Verificar que `executeMission` está a correr (ver logs)
3. Aguardar alguns segundos - a telemetria atualiza com a frequência da missão

### Problema: Porta ocupada

**Solução:**
```bash
# Em cada nó:
pkill -f start_nms.py
pkill -f start_rover.py
fuser -k 8080/udp 8081/tcp 8082/tcp
# Aguardar 2 segundos e tentar novamente
```

---

## 📝 Resumo Rápido (Copy-Paste)

```bash
# 1. LIMPAR (no host CORE)
cd /home/core/Downloads/cctp2-main/tp2
SESSION=$(ls -d /tmp/pycore.* | head -1)
for NODE in NaveMae GroundControl Rover1 Rover2; do
  sudo vcmd -c $SESSION/$NODE -- sh -c 'pkill -f start_nms.py || true; pkill -f start_rover.py || true; pkill -f start_ground_control.py || true; rm -rf /tmp/nms'
done

# 2. COPIAR CÓDIGO (no host CORE)
python3 copy_to_core.py
for NODE in NaveMae GroundControl Rover1 Rover2; do
  sudo sh -c "cat nms_code.tar.gz | vcmd -c $SESSION/$NODE -- sh -c 'mkdir -p /tmp/nms && cd /tmp/nms && tar -xzf -'"
done

# 3. APLICAR ROTAS (no host CORE)
for NODE in NaveMae GroundControl Rover1 Rover2 Satelite; do
  sudo vcmd -c $SESSION/$NODE -- sh -c 'cd /tmp/nms && chmod +x verificar_rotas.sh 2>/dev/null && ./verificar_rotas.sh 2>/dev/null || true'
done

# 4. ARRANCAR (em cada nó, nesta ordem):
# NaveMae: cd /tmp/nms && python3 start_nms.py
# Rover1: cd /tmp/nms && python3 start_rover.py 10.0.1.10 r1
# Rover2: cd /tmp/nms && python3 start_rover.py 10.0.1.10 r2
# GroundControl: cd /tmp/nms && python3 start_ground_control.py
```

---

## 🎯 O Que Esperar Quando Está a Funcionar

✅ **NaveMae:**
- Missões carregadas automaticamente do `serverDB`
- Missões enviadas aos rovers
- Progresso recebido dos rovers

✅ **Rovers:**
- Registam-se automaticamente
- Recebem missões automaticamente
- Executam missões e atualizam posição
- Enviam telemetria com frequência correta

✅ **Ground Control:**
- Mostra rovers registados
- Mostra missões ativas
- Mostra telemetria com posições atualizadas (não zeros!)
- Mostra progresso das missões

