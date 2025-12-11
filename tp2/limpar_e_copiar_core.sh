#!/bin/bash
# Script para limpar processos antigos e copiar novo código para os nós do CORE
# Uso: ./limpar_e_copiar_core.sh

set -e

echo "=========================================="
echo "LIMPEZA E CÓPIA PARA CORE"
echo "=========================================="

# 1. Obter sessão CORE
SESSION=$(ls -d /tmp/pycore.* | head -1)
if [ -z "$SESSION" ]; then
    echo "ERRO: Nenhuma sessão CORE encontrada!"
    echo "Certifica-te de que a topologia está a correr no CORE."
    exit 1
fi

echo "Sessão CORE encontrada: $SESSION"
echo ""

# 2. Usar diretório atual (não fazer cd)
PROJECT_DIR=$(pwd)

# Verificar se estamos no diretório correto
if [ ! -f "$PROJECT_DIR/copy_to_core.py" ]; then
    echo "ERRO: copy_to_core.py não encontrado no diretório atual!"
    echo "Diretório atual: $PROJECT_DIR"
    echo "Certifica-te de que estás no diretório do projeto (deve conter copy_to_core.py)"
    exit 1
fi

echo "Diretório do projeto: $PROJECT_DIR"
echo ""

# 3. Parar processos antigos
echo "=========================================="
echo "PASSO 1: A parar processos antigos..."
echo "=========================================="

for NODE in NaveMae GroundControl Rover1 Rover2; do
    echo "[$NODE] A parar processos..."
    sudo vcmd -c $SESSION/$NODE -- sh -c '
        pkill -f start_nms.py || true
        pkill -f start_rover.py || true
        pkill -f start_ground_control.py || true
        pkill -f MissionLink || true
        pkill -f TelemetryStream || true
        fuser -k 8080/udp 8081/tcp 8082/tcp 2>/dev/null || true
    ' || echo "  [AVISO] Erro ao parar processos em $NODE (pode não haver processos a correr)"
done

echo "✅ Processos parados"
echo ""

# 4. Limpar código antigo
echo "=========================================="
echo "PASSO 2: A limpar código antigo..."
echo "=========================================="

for NODE in NaveMae GroundControl Rover1 Rover2; do
    echo "[$NODE] A limpar /tmp/nms..."
    sudo vcmd -c $SESSION/$NODE -- sh -c 'rm -rf /tmp/nms' || echo "  [AVISO] Erro ao limpar $NODE"
done

echo "✅ Código antigo removido"
echo ""

# 5. Gerar novo tar.gz
echo "=========================================="
echo "PASSO 3: A gerar novo código..."
echo "=========================================="

if [ -f "copy_to_core.py" ]; then
    python3 copy_to_core.py || {
        echo "ERRO: Falha ao gerar código com copy_to_core.py"
        exit 1
    }
else
    echo "ERRO: copy_to_core.py não encontrado!"
    exit 1
fi

if [ ! -f "nms_code.tar.gz" ]; then
    echo "ERRO: nms_code.tar.gz não foi criado!"
    exit 1
fi

echo "✅ Código gerado: nms_code.tar.gz ($(du -h nms_code.tar.gz | cut -f1))"
echo ""

# 6. Copiar para todos os nós
echo "=========================================="
echo "PASSO 4: A copiar código para os nós..."
echo "=========================================="

for NODE in NaveMae GroundControl Rover1 Rover2; do
    echo "[$NODE] A copiar código..."
    sudo sh -c "cat nms_code.tar.gz | vcmd -c $SESSION/$NODE -- sh -c 'mkdir -p /tmp/nms && cd /tmp/nms && tar -xzf - && chmod +x scripts/apply_routes.sh 2>/dev/null || true'" || {
        echo "  [ERRO] Falha ao copiar para $NODE"
        exit 1
    }
    
    # Verificar que foi copiado
    if sudo vcmd -c $SESSION/$NODE -- sh -c 'test -f /tmp/nms/start_nms.py || test -f /tmp/nms/start_rover.py'; then
        echo "  ✅ Código copiado com sucesso"
    else
        echo "  [ERRO] Código não encontrado em $NODE após cópia!"
        exit 1
    fi
done

echo ""
echo "=========================================="
echo "✅ LIMPEZA E CÓPIA CONCLUÍDA!"
echo "=========================================="
echo ""
echo "PRÓXIMOS PASSOS:"
echo "1. Aplicar rotas de rede (ver GUIA_TESTE_CORE.md PASSO 3)"
echo "2. Instalar dependências se necessário (pip3 install -r requirements.txt)"
echo "3. Arrancar serviços nesta ordem:"
echo "   - NaveMae: cd /tmp/nms && python3 start_nms.py"
echo "   - Rover1: cd /tmp/nms && python3 start_rover.py 10.0.1.10 r1"
echo "   - Rover2: cd /tmp/nms && python3 start_rover.py 10.0.1.10 r2"
echo "   - GroundControl: cd /tmp/nms && python3 start_ground_control.py"
echo ""

