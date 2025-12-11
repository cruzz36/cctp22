## Guia curtinho CORE (ficheiro: `/home/core/Downloads/cctp2-main/tp2/`)

### 0) Onde está o código
- No CORE, ir para `/home/core/Downloads/cctp2-main/tp2/`.

### 1) IPs
- Nave-Mãe (n1): `10.0.1.10` (rovers) e `10.0.0.11` (GC).
- Ground Control (n2): `10.0.0.10`.
- Rover1 (n3): `10.0.3.10`. Rover2 (n4): `10.0.2.10`.
- Satélite (n5): `10.0.3.1 / 10.0.2.1 / 10.0.1.1`.

### 1.5) Rotas de Rede (CRÍTICO - executar ANTES de arrancar serviços)

**PORQUÊ É NECESSÁRIO:**
- A topologia tem múltiplas sub-redes separadas (`10.0.0.x`, `10.0.1.x`, `10.0.2.x`, `10.0.3.x`)
- Por padrão, o CORE não configura rotas automáticas entre sub-redes diferentes
- O Satélite precisa de IP forwarding habilitado para encaminhar pacotes entre sub-redes
- Sem estas configurações, os rovers não conseguem comunicar com a Nave-Mãe (10.0.1.10) e o GroundControl não consegue aceder à API

**APLICAÇÃO AUTOMÁTICA DE ROTAS (via script):**
- O ficheiro `.imn` está configurado para executar automaticamente o script `scripts/apply_routes.sh` em cada nó
- Este script detecta o hostname e aplica as rotas apropriadas automaticamente
- **IMPORTANTE:** O script deve estar em `/tmp/nms/scripts/apply_routes.sh` em cada nó antes de arrancar a topologia

**CONFIGURAÇÕES APLICADAS AUTOMATICAMENTE:**
- **Satélite:** IP forwarding habilitado (`sysctl -w net.ipv4.ip_forward=1` e `echo 1 > /proc/sys/net/ipv4/ip_forward`)
- **Nave-Mãe:** Rotas para `10.0.2.0/24` e `10.0.3.0/24` via `10.0.1.1` (Satélite)
- **Ground Control:** Rota para `10.0.1.0/24` via `10.0.0.11` (Nave-Mãe)
- **Rover1:** Rota default via `10.0.3.1` (Satélite)
- **Rover2:** Rota default via `10.0.2.1` (Satélite)

**PREPARAÇÃO ANTES DE ARRANCAR:**

1. **Copiar código para `/tmp/nms` em cada nó** (ver passo 2 do guia)
   - O código deve incluir a pasta `scripts/` com o ficheiro `apply_routes.sh`
   - **IMPORTANTE:** Após copiar, garantir que o script tem permissões de execução em cada nó:
     ```bash
     chmod +x /tmp/nms/scripts/apply_routes.sh
     ```
   - Se usares o método tar.gz, o comando já inclui o `chmod` (ver passo 2)

2. **Fechar e reabrir topologia no CORE:**
   - Se alteraste o ficheiro `.imn`, **DEVES FECHAR E REABRIR a topologia no CORE**:
     1. No CORE: File → Close (ou parar a simulação com Stop)
     2. File → Open → selecionar `topologiatp2.imn` atualizado
     3. Arrancar a simulação (botão Play/Start)

3. **Verificar se rotas foram aplicadas automaticamente:**
   - Após arrancar, em cada nó: `ip route show`
   - Se as rotas não aparecerem, aplicar manualmente (ver abaixo)

**VERIFICAÇÃO E CONFIGURAÇÃO DE ROTAS (após arrancar topologia, ANTES de arrancar serviços):**

**MÉTODO AUTOMÁTICO (RECOMENDADO):**
- Usa o script `verificar_rotas.sh` que é copiado automaticamente pelo `copy_to_core.py`
- Ver secção "SCRIPTS DE DIAGNÓSTICO E CONFIGURAÇÃO" abaixo para instruções detalhadas

**MÉTODO MANUAL (se o script automático não funcionar):**

1. **Verificar rotas em cada nó:**
   ```bash
   # Em cada terminal de nó:
   ip route show
   ```

2. **Verificar IP forwarding no Satélite:**
   ```bash
   # No terminal do Satélite:
   cat /proc/sys/net/ipv4/ip_forward
   # Deve mostrar "1". Se mostrar "0", executar: echo 1 > /proc/sys/net/ipv4/ip_forward
   ```

3. **Se as rotas não estiverem presentes, aplicá-las manualmente:**

   **No terminal de Rover1:**
   ```bash
   ip route add default via 10.0.3.1
   ip route show  # Verificar que apareceu
   ```

   **No terminal de Rover2:**
   ```bash
   ip route add default via 10.0.2.1
   ip route show  # Verificar que apareceu
   ```

   **No terminal de NaveMae:**
   ```bash
   ip route add 10.0.2.0/24 via 10.0.1.1
   ip route add 10.0.3.0/24 via 10.0.1.1
   ip route show  # Verificar que apareceram
   ```

   **No terminal de GroundControl:**
   ```bash
   ip route add 10.0.1.0/24 via 10.0.0.11
   ip route show  # Verificar que apareceu
   ```

   **No terminal do Satélite (se necessário):**
   ```bash
   echo 1 > /proc/sys/net/ipv4/ip_forward
   cat /proc/sys/net/ipv4/ip_forward  # Deve mostrar "1"
   ```

4. **Testar conectividade (após aplicar rotas):**
   ```bash
   # No Rover1:
   ping -c 2 10.0.1.10  # Deve responder
   
   # No Rover2:
   ping -c 2 10.0.1.10  # Deve responder
   
   # No GroundControl:
   ping -c 2 10.0.1.10  # Deve responder
   curl http://10.0.1.10:8082/rovers  # Deve retornar JSON (mesmo que vazio)
   ```

5. **Só depois de confirmar que os pings funcionam, arrancar os serviços** (secção 4).

**CRÍTICO - FECHAR E REABRIR TOPOLOGIA:**
- Se alteraste o ficheiro `.imn`, **DEVES FECHAR E REABRIR a topologia no CORE**:
  1. No CORE: File → Close (ou parar a simulação)
  2. File → Open → selecionar `topologiatp2.imn`
  3. Arrancar a simulação (botão Play)
- **Mesmo assim**, verifica sempre as rotas e o IP forwarding antes de arrancar serviços (os comandos em `services` podem não ser executados automaticamente)

**SCRIPTS DE DIAGNÓSTICO E CONFIGURAÇÃO:**

Os scripts `verificar_rotas.sh` e `check_network.sh` são copiados automaticamente pelo `copy_to_core.py` para `/tmp/nms` em cada nó.

**MÉTODO RECOMENDADO - Aplicar rotas automaticamente após inicializar topologia:**

1. **Inicializar a topologia no CORE:**
   - File → Open → selecionar `topologiatp2.imn`
   - Arrancar a simulação (botão Play/Start)
   - Aguardar que todos os nós fiquem verdes

2. **Aplicar rotas automaticamente em todos os nós:**
   - No **host CORE**, executa o seguinte comando para aplicar rotas em todos os nós de uma vez:
   ```bash
   SESSION=$(ls -d /tmp/pycore.* | head -1)
   for NODE in NaveMae GroundControl Rover1 Rover2 Satelite; do
     echo "[$NODE] Aplicando rotas..."
     sudo vcmd -c $SESSION/$NODE -- sh -c 'cd /tmp/nms && chmod +x verificar_rotas.sh && ./verificar_rotas.sh'
   done
   ```
   - Ou, se preferires fazer manualmente em cada nó:
     - Abre o terminal de cada nó (botão direito no nó → Shell)
     - Em cada nó, executa:
       ```bash
       cd /tmp/nms
       chmod +x verificar_rotas.sh
       ./verificar_rotas.sh
       ```

3. **Verificar que funcionou:**
   - O script `verificar_rotas.sh` mostra automaticamente:
     - Rotas configuradas
     - IP forwarding no Satélite
     - Testes de conectividade (ping)
   - Se tudo estiver OK, verás mensagens `[OK]` e os pings devem funcionar

**Scripts disponíveis:**

1. **verificar_rotas.sh** (RECOMENDADO - aplicação automática):
   - Detecta automaticamente qual nó está a executar (NaveMae, GroundControl, Rover1, Rover2, Satelite)
   - Verifica e aplica automaticamente as rotas necessárias
   - Habilita IP forwarding no Satélite
   - Testa conectividade com pings
   - Mostra resumo completo do estado da rede

2. **check_network.sh** (diagnóstico completo):
   - Mostra IPs configurados, rotas atuais, IP forwarding
   - Testa conectividade entre nós
   - Indica exatamente o que falta configurar
   - Não aplica alterações, apenas diagnostica

### 2) Pôr código em cada nó (escolher UM método)

**NOTA:** O script `copy_to_core.py` copia automaticamente os scripts `verificar_rotas.sh` e `check_network.sh` para `/tmp/nms` em cada nó. Estes scripts são essenciais para configurar as rotas de rede após a inicialização da topologia.
- Diretório partilhado: montar esta pasta em `/tmp/nms` (Core → File Transfer → Source `/home/core/Downloads/cctp2-main/tp2/`, Destination `/tmp/nms` em cada nó).
- Zip (manual): no **host CORE** correr  
  `tar -czf nms_code.tar.gz protocol server client otherEntities scripts *.py requirements.txt --exclude='__pycache__' --exclude='*.pyc'`  
  Depois, Core → Tools → File Transfer → enviar `nms_code.tar.gz` para cada nó.  
  No **terminal de cada nó**:  
  `mkdir -p /tmp/nms && cd /tmp/nms && tar -xzf /tmp/nms_code.tar.gz && chmod +x /tmp/nms/scripts/apply_routes.sh`
- Script (automático, no **host CORE**):  
  `cd /home/core/Downloads/cctp2-main/tp2`  
  `python3 copy_to_core.py`  
  (Se falhar, usar o método Zip acima).
- Sem File Transfer (via vcmd, no **host CORE**, um nó de cada vez) — usar os nomes reais dos nós (NaveMae, GroundControl, Rover1, Rover2):
  1) Guardar sessão: `SESSION=$(ls -d /tmp/pycore.* | head -1)          SESSION=/tmp/pycore.36361`  
  2) Copiar para NaveMae:  
     `sudo sh -c "cat /home/core/Downloads/cctp2-main/tp2/nms_code.tar.gz | vcmd -c $SESSION/NaveMae -- sh -c 'mkdir -p /tmp/nms && cat > /tmp/nms_code.tar.gz && cd /tmp/nms && tar -xzf /tmp/nms_code.tar.gz && rm /tmp/nms_code.tar.gz'"`  
  3) Copiar para GroundControl: trocar `/NaveMae` por `/GroundControl`  
  4) Copiar para Rover1: trocar por `/Rover1`  
  5) Copiar para Rover2: trocar por `/Rover2`
  - Se der “No such file or directory” no SESSION, volta a correr o passo 1).
  - Para abrir terminal de cada nó: botão direito no nó → Shell (no GUI do CORE).
- Depois do `copy_to_core.py` (se a verificação por SSH falhar): abre o terminal de cada nó e confirma `ls /tmp/nms && test -f /tmp/nms/start_nms.py`. Se não existir, volta a extrair o tar no nó: `mkdir -p /tmp/nms && cd /tmp/nms && tar -xzf /tmp/nms_code.tar.gz`.

### 3) Instalar deps (em CADA nó, no terminal desse nó)
```
cd /tmp/nms
pip3 install -r requirements.txt
```
- Se não houver internet nos nós (erro de DNS/PyPI), faz offline a partir do host CORE:
  - Para saber o número da sessão CORE (para usar no vcmd): `ls -d /tmp/pycore.*` (ex.: `/tmp/pycore.41269`)
  1. No host: `mkdir -p /home/core/pkgs`
  2. No host: `pip3 download --dest /home/core/pkgs psutil==5.9.0 flask==1.1.1 itsdangerous==1.1.0 jinja2==2.10.1 markupsafe==1.1.1 werkzeug==0.16.1 click==7.0 requests==2.22.0`
  3. No host: `tar -czf /home/core/pkgs.tgz -C /home/core pkgs`
  4. Para cada nó (NaveMae/GroundControl/Rover1/Rover2, um de cada vez), no host:
     ```
     //Jipow ----------------------------------------------------------------------------------
     sudo sh -c "cat /home/core/pkgs.tgz | vcmd -c /tmp/pycore.44129/NaveMae -- sh -c 'tar -xzf - -C /tmp && pip3 install --no-index --find-links /tmp/pkgs flask==1.1.1 itsdangerous==1.1.0 jinja2==2.10.1 markupsafe==1.1.1 werkzeug==0.16.1 click==7.0 psutil==5.9.0 requests==2.22.0'"

     sudo sh -c "cat /home/core/pkgs.tgz | vcmd -c /tmp/pycore.44129/GroundControl -- sh -c 'tar -xzf - -C /tmp && pip3 install --no-index --find-links /tmp/pkgs flask==1.1.1 itsdangerous==1.1.0 jinja2==2.10.1 markupsafe==1.1.1 werkzeug==0.16.1 click==7.0 psutil==5.9.0 requests==2.22.0'"

     sudo sh -c "cat /home/core/pkgs.tgz | vcmd -c /tmp/pycore.44129/Rover1 -- sh -c 'tar -xzf - -C /tmp && pip3 install --no-index --find-links /tmp/pkgs flask==1.1.1 itsdangerous==1.1.0 jinja2==2.10.1 markupsafe==1.1.1 werkzeug==0.16.1 click==7.0 psutil==5.9.0 requests==2.22.0'"

     sudo sh -c "cat /home/core/pkgs.tgz | vcmd -c /tmp/pycore.44129/Rover2 -- sh -c 'tar -xzf - -C /tmp && pip3 install --no-index --find-links /tmp/pkgs flask==1.1.1 itsdangerous==1.1.0 jinja2==2.10.1 markupsafe==1.1.1 werkzeug==0.16.1 click==7.0 psutil==5.9.0 requests==2.22.0'"




     //Qjm ----------------------------------------------------------------------------------
     sudo sh -c "cat /home/core/pkgs.tgz | vcmd -c /tmp/pycore.41269/NaveMae -- sh -c 'tar -xzf - -C /tmp && pip3 install --no-index --find-links /tmp/pkgs flask==1.1.1 itsdangerous==1.1.0 jinja2==2.10.1 markupsafe==1.1.1 werkzeug==0.16.1 click==7.0 psutil==5.9.0 requests==2.22.0'"

     sudo sh -c "cat /home/core/pkgs.tgz | vcmd -c /tmp/pycore.41269/GroundControl -- sh -c 'tar -xzf - -C /tmp && pip3 install --no-index --find-links /tmp/pkgs flask==1.1.1 itsdangerous==1.1.0 jinja2==2.10.1 markupsafe==1.1.1 werkzeug==0.16.1 click==7.0 psutil==5.9.0 requests==2.22.0'"

     sudo sh -c "cat /home/core/pkgs.tgz | vcmd -c /tmp/pycore.41269/Rover1 -- sh -c 'tar -xzf - -C /tmp && pip3 install --no-index --find-links /tmp/pkgs flask==1.1.1 itsdangerous==1.1.0 jinja2==2.10.1 markupsafe==1.1.1 werkzeug==0.16.1 click==7.0 psutil==5.9.0 requests==2.22.0'"

     sudo sh -c "cat /home/core/pkgs.tgz | vcmd -c /tmp/pycore.41269/Rover2 -- sh -c 'tar -xzf - -C /tmp && pip3 install --no-index --find-links /tmp/pkgs flask==1.1.1 itsdangerous==1.1.0 jinja2==2.10.1 markupsafe==1.1.1 werkzeug==0.16.1 click==7.0 psutil==5.9.0 requests==2.22.0'"
     ```
  5. Confirmar num nó (substitui `XXXX` pela sessão):  
     ```
     sudo vcmd -c /tmp/pycore.XXXX/NaveMae -- python3 - <<'PY'
import psutil, requests, flask
print('OK deps')
PY
     ```
     //Jipow ----------------------------------------------------------------------------------
     (ou, sem heredoc: `echo "import psutil,requests,flask;print('OK deps')" | sudo vcmd -c /tmp/pycore.44129/NaveMae -- python3 -`)

     //Qjm ----------------------------------------------------------------------------------
     (ou, sem heredoc: `echo "import psutil,requests,flask;print('OK deps')" | sudo vcmd -c /tmp/pycore.41269/NaveMae -- python3 -`)


### 4) Arrancar (terminal de cada nó)

**CRÍTICO: Verificar rotas e IP forwarding ANTES de arrancar serviços!**
- Se ainda não verificaste as rotas (secção 1.5), **FAZ-ISSO AGORA** antes de continuar
- Sem rotas corretas e IP forwarding no Satélite, os rovers não conseguem registar-se e o GroundControl não conecta à API
- Verifica com `ip route show` em cada nó e `cat /proc/sys/net/ipv4/ip_forward` no Satélite
- Testa conectividade com `ping -c 2 10.0.1.10` antes de arrancar

- ctrl-c/ctrl-v nos vcmd/XTerm: selecionar texto copia (depois e colar noutro terminal do core e copiar com ctrl-shift-c); para colar usar botão do meio (scroll-click).
- Ordem para evitar timeout na Nave-Mãe: arrancar NaveMae e logo a seguir os rovers (Rover1, Rover2); só depois o GroundControl. Se a thread do MissionLink cair por timeout, relança `start_nms.py` depois de subires os rovers.
- comando clear do vcmd : `TERM=vt100 clear`
- **Nave-Mãe (n1)**  
  `cd /tmp/nms`  
  `python3 start_nms.py`

- **Rover1 (n3)**  
  `cd /tmp/nms`  
  `python3 start_rover.py 10.0.1.10 r1`

- **Rover2 (n4)**  
  `cd /tmp/nms`  
  `python3 start_rover.py 10.0.1.10 r2`

- **Ground Control (n2)**  
  `cd /tmp/nms`  
  `python3 start_ground_control.py`  
  (só dashboard: `python3 GroundControl.py --dashboard --api http://10.0.1.10:8082`)

### 5) Testar
- Em qualquer nó: `cd /tmp/nms && python3 test_core_automated.py auto`
- Em qualquer nó: `cd /tmp/nms && chmod +x test_core_integration.sh && ./test_core_integration.sh`
- API (do GC ou n1): `curl http://10.0.1.10:8082/rovers`
- Quando usar cada teste:
  - Antes de copiar para os nós (no host): `python3 test_imports.py`
  - Após extrair em cada nó, antes de arrancar serviços: `python3 test_core_automated.py auto`
  - `test_core_integration.sh` é só um wrapper para o teste acima (em `/tmp/nms`)
- Interpretação rápida:
  - Se `test_core_automated.py` falhar por porta ocupada: pare serviços (`pkill -f start_nms.py`, `fuser -k 8080/udp 8081/tcp 8082/tcp`) e repita.
  - Se falhar import/ficheiro: falta algo em `/tmp/nms` ou deps; recopie (passo 2) e reinstale deps (passo 3).
  - Para validar comunicação real, siga `TESTE_POS_START.md` (MissionLink, Telemetry, API, GC) com serviços a correr.

### 6) Se der erro
- **Rovers presos no registo / GroundControl não conecta**: **PRIMEIRO**, verifica rotas e IP forwarding (secção 1.5):
  - Em cada nó: `ip route show` (deve mostrar as rotas configuradas)
  - No Satélite: `cat /proc/sys/net/ipv4/ip_forward` (deve mostrar "1")
  - Se faltarem rotas ou IP forwarding, aplica-os manualmente conforme secção 1.5
  - Testa conectividade: `ping -c 2 10.0.1.10` (deve responder)
  - Só depois de confirmar que os pings funcionam, relança os serviços
- "Module not found": confirma `/tmp/nms` e `__init__.py`.
- Porta ocupada: `pkill -f start_nms.py` ou `pkill -f start_rover.py`.
- GC não liga: usa `--api http://10.0.1.10:8082`.
- Falhou cópia: reenviar `nms_code.tar.gz` ou montar diretório partilhado.

### 7) Depois de dar pull (para tudo ficar igual nos nós)
- No host CORE (`/home/core/Downloads/cctp2-main/tp2`):
  1. `git pull`
  2. `python3 copy_to_core.py` (gera novo `nms_code.tar.gz` (copy ja apaga o antigo); se falhar, usa método Zip do passo 2)
- Em cada nó (NaveMae, GroundControl, Rover1, Rover2):
  3. Parar processos antigos: `pkill -f start_nms.py || true && pkill -f start_rover.py || true && pkill -f start_ground_control.py || true`
  4. Limpar cópia antiga: `rm -rf /tmp/nms`
  5. Receber nova cópia (via File Transfer ou vcmd, conforme passo 2) e extrair em `/tmp/nms`
  6. **Opcional** - Reinstalar deps (só se necessário): `cd /tmp/nms && pip3 install -r requirements.txt` (ou método offline do passo 3)
     - Se aparecer "Requirement already satisfied" para todos os pacotes, podes saltar este passo
     - Se houver erros de importação depois, volta a instalar
  7. Arrancar de novo (passo 4): NaveMae → rovers → GroundControl
- Não é obrigatório fechar os terminais vcmd; basta parar os processos e recarregar `/tmp/nms`. Se quiser, pode fechar/reabrir.
- Automático pós-pull (sem internet nos nós) — tudo no host CORE:
  ```bash
  # 1) Atualizar código e copiar para nós
  cd /home/core/Downloads/cctp2-main/tp2
  SESSION=$(ls -d /tmp/pycore.* | head -1)
  git pull
  python3 copy_to_core.py  # já envia o tar para NaveMae/GroundControl/Rover1/Rover2

  # 2) Preparar deps offline
  mkdir -p /home/core/pkgs
  pip3 download --dest /home/core/pkgs \
    psutil==5.9.0 \
    flask==2.3.3 itsdangerous==2.1.2 jinja2==3.1.2 markupsafe==2.1.5 werkzeug==2.3.7 click==8.1.7 \
    requests==2.31.0
  tar -czf /home/core/pkgs.tgz -C /home/core pkgs

  # 3) Em cada nó (loop), limpar /tmp/nms, extrair tar e instalar deps offline
  for NODE in NaveMae GroundControl Rover1 Rover2; do
    sudo sh -c "vcmd -c $SESSION/$NODE -- sh -c 'pkill -f start_nms.py || true; pkill -f start_rover.py || true; pkill -f start_ground_control.py || true; rm -rf /tmp/nms; mkdir -p /tmp/nms'"
    sudo sh -c "cat /home/core/Downloads/cctp2-main/tp2/nms_code.tar.gz | vcmd -c $SESSION/$NODE -- sh -c 'cd /tmp/nms && tar -xzf -'"
    sudo sh -c "cat /home/core/pkgs.tgz | vcmd -c $SESSION/$NODE -- sh -c 'tar -xzf - -C /tmp && pip3 install --no-index --find-links /tmp/pkgs flask==2.3.3 itsdangerous==2.1.2 jinja2==3.1.2 markupsafe==2.1.5 werkzeug==2.3.7 click==8.1.7 psutil==5.9.0 requests==2.31.0'"
  done
  echo "Pronto: arrancar (passo 4): NaveMae -> rovers -> GroundControl"
  ```




  python3 copy_to_core.py

ls -d /tmp/pycore.*

mkdir -p /home/core/pkgs

pip3 download --dest /home/core/pkgs psutil==5.9.0 flask==1.1.1 itsdangerous==1.1.0 jinja2==2.10.1 markupsafe==1.1.1 werkzeug==0.16.1 click==7.0 requests==2.22.0

tar -czf /home/core/pkgs.tgz -C /home/core pkgs


sudo sh -c "cat /home/core/pkgs.tgz | vcmd -c /tmp/pycore.38885/NaveMae -- sh -c 'tar -xzf - -C /tmp && pip3 install --no-index --find-links /tmp/pkgs flask==1.1.1 itsdangerous==1.1.0 jinja2==2.10.1 markupsafe==1.1.1 werkzeug==0.16.1 click==7.0 psutil==5.9.0 requests==2.22.0'"

     sudo sh -c "cat /home/core/pkgs.tgz | vcmd -c /tmp/pycore.38885/GroundControl -- sh -c 'tar -xzf - -C /tmp && pip3 install --no-index --find-links /tmp/pkgs flask==1.1.1 itsdangerous==1.1.0 jinja2==2.10.1 markupsafe==1.1.1 werkzeug==0.16.1 click==7.0 psutil==5.9.0 requests==2.22.0'"

     sudo sh -c "cat /home/core/pkgs.tgz | vcmd -c /tmp/pycore.38885/Rover1 -- sh -c 'tar -xzf - -C /tmp && pip3 install --no-index --find-links /tmp/pkgs flask==1.1.1 itsdangerous==1.1.0 jinja2==2.10.1 markupsafe==1.1.1 werkzeug==0.16.1 click==7.0 psutil==5.9.0 requests==2.22.0'"

     sudo sh -c "cat /home/core/pkgs.tgz | vcmd -c /tmp/pycore.38885/Rover2 -- sh -c 'tar -xzf - -C /tmp && pip3 install --no-index --find-links /tmp/pkgs flask==1.1.1 itsdangerous==1.1.0 jinja2==2.10.1 markupsafe==1.1.1 werkzeug==0.16.1 click==7.0 psutil==5.9.0 requests==2.22.0'"


Dentro do core

ground control: 
ip route add 10.0.1.0/24 via 10.0.0.11 


navemae: 
ip route add 10.0.2.0/24 via 10.0.1.1
ip route add 10.0.3.0/24 via 10.0.1.1


satelite:
cat /proc/sys/net/ipv4/ip_forward

Nave-Mãe (n1)
cd /tmp/nms
python3 start_nms.py

Rover1 (n3)
cd /tmp/nms
python3 start_rover.py 10.0.1.10 r1

Rover2 (n4)
cd /tmp/nms
python3 start_rover.py 10.0.1.10 r2

Ground Control (n2)
cd /tmp/nms
python3 start_ground_control.py
(só dashboard: python3 GroundControl.py --dashboard --api http://10.0.1.10:8082)

chmod +x limpar_e_copiar_core.sh
./limpar_e_copiar_core.sh
