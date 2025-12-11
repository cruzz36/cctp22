#!/bin/bash
# Script para verificar e aplicar rotas de rede nos nós do CORE
# Executar em cada nó após arrancar a topologia

echo "============================================================"
echo "VERIFICAÇÃO E APLICAÇÃO DE ROTAS DE REDE"
echo "============================================================"
echo ""

# Detectar qual nó estamos a executar
HOSTNAME=$(hostname)
echo "[INFO] Nó atual: $HOSTNAME"
echo ""

case $HOSTNAME in
    NaveMae)
        echo "[INFO] Configurando rotas para NaveMae..."
        echo "[DEBUG] Rotas atuais:"
        ip route show
        echo ""
        
        # Verificar se rotas já existem
        if ! ip route show | grep -q "10.0.2.0/24 via 10.0.1.1"; then
            echo "[INFO] Adicionando rota para 10.0.2.0/24 via 10.0.1.1..."
            ip route add 10.0.2.0/24 via 10.0.1.1
        else
            echo "[OK] Rota para 10.0.2.0/24 já existe"
        fi
        
        if ! ip route show | grep -q "10.0.3.0/24 via 10.0.1.1"; then
            echo "[INFO] Adicionando rota para 10.0.3.0/24 via 10.0.1.1..."
            ip route add 10.0.3.0/24 via 10.0.1.1
        else
            echo "[OK] Rota para 10.0.3.0/24 já existe"
        fi
        
        echo ""
        echo "[DEBUG] Rotas após configuração:"
        ip route show
        ;;
        
    GroundControl)
        echo "[INFO] Configurando rotas para GroundControl..."
        echo "[DEBUG] Rotas atuais:"
        ip route show
        echo ""
        
        if ! ip route show | grep -q "10.0.1.0/24 via 10.0.0.11"; then
            echo "[INFO] Adicionando rota para 10.0.1.0/24 via 10.0.0.11..."
            ip route add 10.0.1.0/24 via 10.0.0.11
        else
            echo "[OK] Rota para 10.0.1.0/24 já existe"
        fi
        
        echo ""
        echo "[DEBUG] Rotas após configuração:"
        ip route show
        ;;
        
    Satelite)
        echo "[INFO] Configurando IP forwarding para Satelite..."
        IP_FORWARD=$(cat /proc/sys/net/ipv4/ip_forward)
        echo "[DEBUG] IP forwarding atual: $IP_FORWARD"
        
        if [ "$IP_FORWARD" != "1" ]; then
            echo "[INFO] Habilitando IP forwarding..."
            echo 1 > /proc/sys/net/ipv4/ip_forward
            echo "[OK] IP forwarding habilitado"
        else
            echo "[OK] IP forwarding já está habilitado"
        fi
        
        echo ""
        echo "[DEBUG] IP forwarding após configuração:"
        cat /proc/sys/net/ipv4/ip_forward
        ;;
        
    Rover1)
        echo "[INFO] Configurando rotas para Rover1..."
        echo "[DEBUG] Rotas atuais:"
        ip route show
        echo ""
        
        if ! ip route show | grep -q "default via 10.0.3.1"; then
            echo "[INFO] Adicionando rota default via 10.0.3.1..."
            ip route add default via 10.0.3.1
        else
            echo "[OK] Rota default já existe"
        fi
        
        echo ""
        echo "[DEBUG] Rotas após configuração:"
        ip route show
        ;;
        
    Rover2)
        echo "[INFO] Configurando rotas para Rover2..."
        echo "[DEBUG] Rotas atuais:"
        ip route show
        echo ""
        
        if ! ip route show | grep -q "default via 10.0.2.1"; then
            echo "[INFO] Adicionando rota default via 10.0.2.1..."
            ip route add default via 10.0.2.1
        else
            echo "[OK] Rota default já existe"
        fi
        
        echo ""
        echo "[DEBUG] Rotas após configuração:"
        ip route show
        ;;
        
    *)
        echo "[AVISO] Nó desconhecido: $HOSTNAME"
        echo "[INFO] Rotas atuais:"
        ip route show
        ;;
esac

echo ""
echo "============================================================"
echo "TESTE DE CONECTIVIDADE"
echo "============================================================"

# Testar conectividade com NaveMae (se não formos a NaveMae)
if [ "$HOSTNAME" != "NaveMae" ]; then
    echo "[INFO] Testando conectividade com NaveMae (10.0.1.10)..."
    if ping -c 2 -W 2 10.0.1.10 > /dev/null 2>&1; then
        echo "[OK] Ping para 10.0.1.10 bem-sucedido"
    else
        echo "[ERRO] Ping para 10.0.1.10 falhou - verificar rotas e IP forwarding"
    fi
else
    echo "[INFO] Testando conectividade com rovers..."
    if ping -c 2 -W 2 10.0.2.10 > /dev/null 2>&1; then
        echo "[OK] Ping para Rover2 (10.0.2.10) bem-sucedido"
    else
        echo "[AVISO] Ping para Rover2 (10.0.2.10) falhou"
    fi
    
    if ping -c 2 -W 2 10.0.3.10 > /dev/null 2>&1; then
        echo "[OK] Ping para Rover1 (10.0.3.10) bem-sucedido"
    else
        echo "[AVISO] Ping para Rover1 (10.0.3.10) falhou"
    fi
fi

echo ""
echo "============================================================"
echo "VERIFICAÇÃO CONCLUÍDA"
echo "============================================================"

