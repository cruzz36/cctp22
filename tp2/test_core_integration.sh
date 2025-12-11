#!/bin/bash
# Script de teste de integração para executar no CORE
# Este script testa a comunicação entre nós

echo "============================================================"
echo "TESTE DE INTEGRAÇÃO NO CORE"
echo "============================================================"

HOSTNAME=$(hostname)
echo "Nó atual: $HOSTNAME"
echo "IP: $(hostname -I | awk '{print $1}')"
echo ""

# Verificar se estamos no diretório correto
if [ ! -d "protocol" ] || [ ! -d "server" ] || [ ! -d "client" ]; then
    echo "ERRO: Execute este script a partir do diretório /tmp/nms"
    exit 1
fi

# Testar imports Python
echo "Testando imports Python..."
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from server import NMS_Server
    from client import NMS_Agent
    from protocol import MissionLink, TelemetryStream
    print('✓ Imports OK')
except Exception as e:
    print(f'✗ Erro nos imports: {e}')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "ERRO: Imports falharam"
    exit 1
fi

# Executar teste automatizado
echo ""
echo "Executando testes automatizados..."
python3 test_core_automated.py auto

exit $?
