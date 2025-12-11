# Testes rápidos após arrancar Nave-Mãe e Rovers

Pré-condições:
- NaveMae já a correr: `python3 start_nms.py` em `/tmp/nms` do nó NaveMae.
- Rovers já a correr: `python3 start_rover.py 10.0.1.10 r1` e `python3 start_rover.py 10.0.1.10 r2` em `/tmp/nms` dos rovers.
- (Opcional) GroundControl a correr: `python3 start_ground_control.py` em `/tmp/nms` do GC.

## 1) MissionLink (UDP 8080) – registo e pedidos de missão
- Onde testar: terminal da NaveMae.
- O que fazer: confirmar que aparecem logs de registo dos rovers e que não há timeouts.
- Comando útil: observar output de `start_nms.py` (já em execução). Se não houver rovers a ligar em 10s, deve aparecer `[AVISO] MissionLink timeout...` e continuar à espera.
- Se tiveres de enviar uma missão manualmente (exemplo rápido em Python, na NaveMae):
  ```bash
  python3 - <<'PY'
import client.NMS_Agent as A
a = A.NMS_Agent("10.0.1.10")
a.id = "gc-test"
a.sendMission("10.0.3.10", "r1", {"mission_id":"M-001","area":"(x1,y1)-(x2,y2)","task":"capture_images","duration":"30min","progress_interval_s":120})
print("Enviada para r1")
PY
  ```
- Esperado: rover responde ACK; NaveMae não cai; se falhar, aparece aviso mas continua.

## 2) TelemetryStream (TCP 8081) – telemetria contínua
- Onde testar: terminal da NaveMae.
- O que fazer: ver se chegam ficheiros/JSON de telemetria em `/tmp/nms/telemetry/`.
- Comando para listar últimos ficheiros:
  ```bash
  ls -lt /tmp/nms/telemetry
  ```
- Opcional: ver conteúdo rápido do ficheiro mais recente:
  ```bash
  python3 - <<'PY'
import glob, json, os
files = sorted(glob.glob("/tmp/nms/telemetry/**/*.json", recursive=True), key=os.path.getmtime)
print("Último:", files[-1] if files else "nenhum")
if files:
    print(json.load(open(files[-1])))
PY
  ```
- Esperado: cada rover envia periodicamente; ficheiros organizados por rover_id.

## 3) API de Observação (HTTP 8082)
- Onde testar: qualquer nó com curl (NaveMae ou GroundControl).
- Comando:
  ```bash
  curl http://10.0.1.10:8082/rovers
  curl http://10.0.1.10:8082/missions
  ```
- Esperado: JSON com lista de rovers e missões; se vazio, não deve dar erro 5xx.

## 4) Ground Control (cliente da API)
- Onde testar: terminal do GroundControl (se estiver a correr).
- O que fazer: abrir dashboard/CLI e confirmar que mostra rovers e estado.
- Comando exemplo (só dashboard):
  ```bash
  cd /tmp/nms
  python3 GroundControl.py --dashboard --api http://10.0.1.10:8082
  ```
- Esperado: ver rovers listados e telemetria atualizada; sem crashes.

## 5) Scripts de teste automatizado
- Ordem sugerida (sempre com serviços parados para evitar conflito de portas):
  1. No host (antes de copiar para os nós): `python3 test_imports.py`
  2. Em cada nó, depois de extrair para `/tmp/nms` e antes de arrancar serviços:  
     `cd /tmp/nms && python3 test_core_automated.py auto`  
     (ou `chmod +x test_core_integration.sh && ./test_core_integration.sh`, que só chama o anterior)
- Pode ser corrido em qualquer nó (ex.: NaveMae):
  ```bash
  cd /tmp/nms
  python3 test_core_automated.py auto
  chmod +x test_core_integration.sh && ./test_core_integration.sh
  ```
- Esperado: sem erros fatais; logs indicam sucesso dos passos.
  - Se falhar por “Address already in use”, pare serviços (`pkill -f start_nms.py` / `fuser -k 8080/udp 8081/tcp 8082/tcp`) e volte a correr.
  - Se falhar imports, falta ficheiro ou dependência: rever cópia para /tmp/nms e instalar deps (offline, se necessário).

## 6) Problemas comuns e verificações rápidas
- Timeouts ML iniciais: relança `start_nms.py` depois de subir rovers (ordem NaveMae → rovers → GroundControl).
- Porta ocupada: `pkill -f start_nms.py` e `fuser -k 8080/udp 8081/tcp 8082/tcp`, depois relançar.
- Deps faltam nos nós: usar método offline do guia (`pkgs.tgz` via vcmd) e `pip3 install --no-index --find-links /tmp/pkgs ...`.
- Sem ficheiros em `/tmp/nms/telemetry`: confirma que rovers estão a correr e não falham no registo.
