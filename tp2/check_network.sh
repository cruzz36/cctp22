#!/bin/bash
# Script de diagnóstico de rede para o CORE
# Uso: ./check_network.sh
# Executar em cada nó após arrancar a topologia

echo "============================================================"
echo "DIAGNÓSTICO DE REDE - $(hostname)"
echo "============================================================"
echo ""

# Detectar qual nó estamos a executar
HOSTNAME=$(hostname)
echo "[INFO] Nó atual: $HOSTNAME"
echo ""

# 1. Verificar IPs das interfaces
echo "1. INTERFACES DE REDE:"
echo "----------------------------------------"
ip -4 addr show | grep -E "^[0-9]+:|inet " | grep -v "127.0.0.1"
echo ""

# 2. Verificar rotas
echo "2. ROTAS CONFIGURADAS:"
echo "----------------------------------------"
ip route show
echo ""

# 3. Verificar IP forwarding (se for Satélite)
if [ "$HOSTNAME" == "Satelite" ]; then
    echo "3. IP FORWARDING (Satélite):"
    echo "----------------------------------------"
    IP_FORWARD=$(cat /proc/sys/net/ipv4/ip_forward)
    if [ "$IP_FORWARD" == "1" ]; then
        echo "[OK] IP forwarding está HABILITADO (valor: $IP_FORWARD)"
    else
        echo "[ERRO] IP forwarding está DESABILITADO (valor: $IP_FORWARD)"
        echo "[INFO] Para habilitar: echo 1 > /proc/sys/net/ipv4/ip_forward"
    fi
    echo ""
fi

# 4. Testes de conectividade
echo "4. TESTES DE CONECTIVIDADE:"
echo "----------------------------------------"

case $HOSTNAME in
    NaveMae)
        echo "[INFO] Testando conectividade com rovers..."
        if ping -c 2 -W 2 10.0.2.10 > /dev/null 2>&1; then
            echo "[OK] Ping para Rover2 (10.0.2.10) bem-sucedido"
        else
            echo "[ERRO] Ping para Rover2 (10.0.2.10) falhou"
            echo "       Verificar: ip route add 10.0.2.0/24 via 10.0.1.1"
        fi
        
        if ping -c 2 -W 2 10.0.3.10 > /dev/null 2>&1; then
            echo "[OK] Ping para Rover1 (10.0.3.10) bem-sucedido"
        else
            echo "[ERRO] Ping para Rover1 (10.0.3.10) falhou"
            echo "       Verificar: ip route add 10.0.3.0/24 via 10.0.1.1"
        fi
        
        if ping -c 2 -W 2 10.0.0.10 > /dev/null 2>&1; then
            echo "[OK] Ping para GroundControl (10.0.0.10) bem-sucedido"
        else
            echo "[AVISO] Ping para GroundControl (10.0.0.10) falhou"
        fi
        ;;
        
    GroundControl)
        echo "[INFO] Testando conectividade com Nave-Mãe..."
        if ping -c 2 -W 2 10.0.1.10 > /dev/null 2>&1; then
            echo "[OK] Ping para Nave-Mãe (10.0.1.10) bem-sucedido"
        else
            echo "[ERRO] Ping para Nave-Mãe (10.0.1.10) falhou"
            echo "       Verificar: ip route add 10.0.1.0/24 via 10.0.0.11"
        fi
        
        if ping -c 2 -W 2 10.0.0.11 > /dev/null 2>&1; then
            echo "[OK] Ping para Nave-Mãe (10.0.0.11) bem-sucedido"
        else
            echo "[AVISO] Ping para Nave-Mãe (10.0.0.11) falhou"
        fi
        ;;
        
    Satelite)
        echo "[INFO] Testando conectividade com todos os nós..."
        for ip in 10.0.1.10 10.0.2.10 10.0.3.10; do
            if ping -c 1 -W 1 $ip > /dev/null 2>&1; then
                echo "[OK] Ping para $ip bem-sucedido"
            else
                echo "[AVISO] Ping para $ip falhou"
            fi
        done
        ;;
        
    Rover1)
        echo "[INFO] Testando conectividade com gateway e Nave-Mãe..."
        if ping -c 2 -W 2 10.0.3.1 > /dev/null 2>&1; then
            echo "[OK] Ping para gateway Satélite (10.0.3.1) bem-sucedido"
        else
            echo "[ERRO] Ping para gateway Satélite (10.0.3.1) falhou"
        fi
        
        if ping -c 2 -W 2 10.0.1.10 > /dev/null 2>&1; then
            echo "[OK] Ping para Nave-Mãe (10.0.1.10) bem-sucedido"
        else
            echo "[ERRO] Ping para Nave-Mãe (10.0.1.10) falhou"
            echo "       Verificar rotas: ip route show"
            echo "       Adicionar rota: ip route add default via 10.0.3.1"
        fi
        ;;
        
    Rover2)
        echo "[INFO] Testando conectividade com gateway e Nave-Mãe..."
        if ping -c 2 -W 2 10.0.2.1 > /dev/null 2>&1; then
            echo "[OK] Ping para gateway Satélite (10.0.2.1) bem-sucedido"
        else
            echo "[ERRO] Ping para gateway Satélite (10.0.2.1) falhou"
        fi
        
        if ping -c 2 -W 2 10.0.1.10 > /dev/null 2>&1; then
            echo "[OK] Ping para Nave-Mãe (10.0.1.10) bem-sucedido"
        else
            echo "[ERRO] Ping para Nave-Mãe (10.0.1.10) falhou"
            echo "       Verificar rotas: ip route show"
            echo "       Adicionar rota: ip route add default via 10.0.2.1"
        fi
        ;;
        
    *)
        echo "[AVISO] Nó desconhecido: $HOSTNAME"
        echo "[INFO] Testando conectividade básica..."
        if ping -c 2 -W 2 10.0.1.10 > /dev/null 2>&1; then
            echo "[OK] Ping para Nave-Mãe (10.0.1.10) bem-sucedido"
        else
            echo "[AVISO] Ping para Nave-Mãe (10.0.1.10) falhou"
        fi
        ;;
esac

echo ""
echo "============================================================"
echo "RESUMO E PRÓXIMOS PASSOS"
echo "============================================================"

# Verificar se tudo está OK
ALL_OK=true

case $HOSTNAME in
    NaveMae)
        if ! ip route show | grep -q "10.0.2.0/24 via 10.0.1.1"; then
            echo "[ERRO] Falta rota para 10.0.2.0/24"
            echo "       Executar: ip route add 10.0.2.0/24 via 10.0.1.1"
            ALL_OK=false
        fi
        if ! ip route show | grep -q "10.0.3.0/24 via 10.0.1.1"; then
            echo "[ERRO] Falta rota para 10.0.3.0/24"
            echo "       Executar: ip route add 10.0.3.0/24 via 10.0.1.1"
            ALL_OK=false
        fi
        ;;
        
    GroundControl)
        if ! ip route show | grep -q "10.0.1.0/24 via 10.0.0.11"; then
            echo "[ERRO] Falta rota para 10.0.1.0/24"
            echo "       Executar: ip route add 10.0.1.0/24 via 10.0.0.11"
            ALL_OK=false
        fi
        ;;
        
    Satelite)
        IP_FORWARD=$(cat /proc/sys/net/ipv4/ip_forward)
        if [ "$IP_FORWARD" != "1" ]; then
            echo "[ERRO] IP forwarding não está habilitado"
            echo "       Executar: echo 1 > /proc/sys/net/ipv4/ip_forward"
            ALL_OK=false
        fi
        ;;
        
    Rover1)
        if ! ip route show | grep -q "default via 10.0.3.1"; then
            echo "[ERRO] Falta rota default"
            echo "       Executar: ip route add default via 10.0.3.1"
            ALL_OK=false
        fi
        ;;
        
    Rover2)
        if ! ip route show | grep -q "default via 10.0.2.1"; then
            echo "[ERRO] Falta rota default"
            echo "       Executar: ip route add default via 10.0.2.1"
            ALL_OK=false
        fi
        ;;
esac

if [ "$ALL_OK" = true ]; then
    echo "[OK] Todas as configurações de rede estão corretas!"
    echo "[INFO] Podes arrancar os serviços (start_nms.py, start_rover.py, etc.)"
else
    echo ""
    echo "[AVISO] Há problemas de configuração de rede."
    echo "[INFO] Aplica os comandos indicados acima antes de arrancar os serviços."
    echo "[INFO] Ver também: Guia_CORE_Unificado.md secção 1.5"
fi

echo ""
echo "============================================================"

