#!/usr/bin/env python3
"""
Script para copiar ficheiros para todos os nós do CORE.

Este script tenta copiar automaticamente os ficheiros do projeto
para todos os nós do CORE usando diferentes métodos.

Uso: python3 copy_to_core.py

Requisitos:
- CORE deve estar a correr
- Nós devem estar ativos
- Acesso ao diretório do projeto
"""

import os
import sys
import tarfile
import subprocess
import shutil

# Configuração
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
NODES = {
    # nomes iguais aos nós na topologia CORE
    "NaveMae": {"ip": "10.0.1.10", "name": "NaveMae"},
    "GroundControl": {"ip": "10.0.0.10", "name": "GroundControl"},
    "Rover1": {"ip": "10.0.3.10", "name": "Rover1"},
    "Rover2": {"ip": "10.0.2.10", "name": "Rover2"},
}

# Ficheiros e diretórios a copiar
ITEMS_TO_COPY = [
    "API",
    "protocol",
    "server",
    "client",
    "otherEntities",
    "scripts",
    "serverDB",
    "start_nms.py",
    "start_rover.py",
    "start_ground_control.py",
    "GroundControl.py",
    "requirements.txt",
    "verificar_rotas.sh",
    "check_network.sh",
]

def create_tarball():
    """Cria arquivo tar.gz com todos os ficheiros necessários."""
    print("="*60)
    print("A criar arquivo compactado...")
    print("="*60)
    
    tarball_path = os.path.join(PROJECT_DIR, "nms_code.tar.gz")
    
    # Remover arquivo antigo se existir
    if os.path.exists(tarball_path):
        os.remove(tarball_path)
    
    try:
        with tarfile.open(tarball_path, "w:gz") as tar:
            for item in ITEMS_TO_COPY:
                item_path = os.path.join(PROJECT_DIR, item)
                if os.path.exists(item_path):
                    tar.add(item_path, arcname=item)
                    print(f"  [+] {item}")
                else:
                    print(f"  [!] {item} não encontrado (ignorado)")
        
        print(f"\n[OK] Arquivo criado: {tarball_path}")
        print(f"     Tamanho: {os.path.getsize(tarball_path) / 1024:.2f} KB")
        return tarball_path
    
    except Exception as e:
        print(f"\n[ERRO] Erro ao criar arquivo: {e}")
        return None

def find_core_session():
    """Tenta encontrar a sessão do CORE ativa."""
    try:
        # Procurar diretórios de sessão do CORE
        core_sessions = []
        if os.path.exists("/tmp"):
            for item in os.listdir("/tmp"):
                if item.startswith("pycore."):
                    core_sessions.append(os.path.join("/tmp", item))
        
        if core_sessions:
            # Usar a sessão mais recente
            latest = max(core_sessions, key=os.path.getmtime)
            print(f"[INFO] Sessão CORE encontrada: {latest}")
            return latest
        
        return None
    except Exception as e:
        print(f"[AVISO] Erro ao procurar sessão CORE: {e}")
        return None

def copy_via_vcmd(node_name, tarball_path, core_session):
    """Tenta copiar usando vcmd (comando do CORE)."""
    try:
        # Criar diretório no nó
        cmd = f"vcmd -c {core_session}/{node_name} -- mkdir -p /tmp/nms"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        
        if result.returncode != 0:
            return False
        
        # Copiar arquivo para o nó
        # vcmd pode não suportar cópia direta, então vamos tentar outro método
        # Usar cat para copiar conteúdo
        with open(tarball_path, 'rb') as f:
            content = f.read()
        
        # Guardar temporariamente e copiar
        temp_path = f"/tmp/{node_name}_nms_code.tar.gz"
        with open(temp_path, 'wb') as f:
            f.write(content)
        
        # Tentar copiar via vcmd (pode não funcionar em todas as versões)
        cmd = f"vcmd -c {core_session}/{node_name} -- cp {temp_path} /tmp/nms_code.tar.gz"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            # Descompactar no nó e dar permissões ao script de rotas
            cmd = f"vcmd -c {core_session}/{node_name} -- sh -c 'cd /tmp/nms && tar -xzf /tmp/nms_code.tar.gz && chmod +x /tmp/nms/scripts/apply_routes.sh 2>/dev/null || true && rm /tmp/nms_code.tar.gz'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        
        return False
    
    except Exception as e:
        print(f"    [AVISO] vcmd falhou: {e}")
        return False

def copy_via_scp(node_ip, tarball_path):
    """Tenta copiar usando scp (requer SSH configurado)."""
    try:
        # Copiar arquivo
        cmd = f"scp -o StrictHostKeyChecking=no -o ConnectTimeout=5 {tarball_path} root@{node_ip}:/tmp/nms_code.tar.gz"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            return False
        
        # Descompactar no nó remoto e dar permissões ao script de rotas
        cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 root@{node_ip} 'mkdir -p /tmp/nms && cd /tmp/nms && tar -xzf /tmp/nms_code.tar.gz && chmod +x /tmp/nms/scripts/apply_routes.sh 2>/dev/null || true && rm /tmp/nms_code.tar.gz'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return result.returncode == 0
    
    except Exception as e:
        print(f"    [AVISO] scp falhou: {e}")
        return False

def copy_to_node(node_name, node_info, tarball_path, core_session=None):
    """Copia ficheiros para um nó específico usando o melhor método disponível."""
    node_ip = node_info["ip"]
    node_display = node_info["name"]
    
    print(f"\n[{node_name}] {node_display} ({node_ip})")
    print("-" * 60)
    
    # Método 1: Tentar vcmd (se sessão CORE encontrada)
    if core_session:
        print("  Tentando método vcmd...")
        if copy_via_vcmd(node_name, tarball_path, core_session):
            print(f"  [OK] Ficheiros copiados via vcmd")
            return True
        print("  [AVISO] vcmd não funcionou, tentando scp...")
    
    # Método 2: Tentar scp
    print("  Tentando método scp...")
    if copy_via_scp(node_ip, tarball_path):
        print(f"  [OK] Ficheiros copiados via scp")
        return True
    
    # Se ambos falharem
    print(f"  [ERRO] Não foi possível copiar automaticamente")
    print(f"  [INFO] Use método manual:")
    print(f"         1. No CORE, Tools → File Transfer")
    print(f"         2. Enviar {tarball_path} para {node_name}")
    print(f"         3. No terminal do nó: mkdir -p /tmp/nms && cd /tmp/nms && tar -xzf /tmp/nms_code.tar.gz && chmod +x /tmp/nms/scripts/apply_routes.sh")
    return False

def verify_node(node_name, node_info, core_session=None):
    """Verifica se ficheiros foram copiados corretamente."""
    node_ip = node_info["ip"]
    node_display = node_info["name"]
    
    print(f"\n[{node_name}] Verificando {node_display}...")
    
    # Primeiro tentar via vcmd (não depende de SSH)
    if core_session:
        try:
            cmd = f"vcmd -c {core_session}/{node_name} -- sh -c 'test -d /tmp/nms && test -f /tmp/nms/start_nms.py && echo OK || echo FAIL'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            if "OK" in result.stdout:
                print("  [OK] Ficheiros verificados (vcmd)")
                return True
        except Exception as e:
            print(f"  [AVISO] Erro na verificação via vcmd: {e}")
    
    # Fallback: tentar via SSH (se estiver configurado)
    try:
        cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 root@{node_ip} 'test -d /tmp/nms && test -f /tmp/nms/start_nms.py && echo OK || echo FAIL'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        
        if "OK" in result.stdout:
            print(f"  [OK] Ficheiros verificados (ssh)")
            return True
        else:
            print(f"  [AVISO] Não foi possível verificar automaticamente")
            return False
    
    except Exception as e:
        print(f"  [AVISO] Erro na verificação via ssh: {e}")
        return False

def main():
    print("="*60)
    print("CÓPIA DE FICHEIROS PARA NÓS DO CORE")
    print("="*60)
    print(f"\nDiretório do projeto: {PROJECT_DIR}")
    print(f"Nós a copiar: {len(NODES)}")
    
    # Verificar que estamos no diretório correto
    if not os.path.exists(os.path.join(PROJECT_DIR, "protocol")):
        print("\n[ERRO] Diretório 'protocol' não encontrado!")
        print("       Execute este script a partir do diretório CC/tp2")
        sys.exit(1)
    
    # Criar arquivo compactado
    tarball_path = create_tarball()
    if not tarball_path:
        print("\n[ERRO] Falha ao criar arquivo compactado")
        sys.exit(1)
    
    # Procurar sessão CORE
    core_session = find_core_session()
    if not core_session:
        print("\n[AVISO] Sessão CORE não encontrada automaticamente")
        print("        Tentando métodos alternativos...")
    
    # Copiar para cada nó
    print("\n" + "="*60)
    print("A COPIAR FICHEIROS PARA NÓS")
    print("="*60)
    
    success_count = 0
    for node_name, node_info in NODES.items():
        if copy_to_node(node_name, node_info, tarball_path, core_session):
            success_count += 1
    
    # Verificar cópias
    print("\n" + "="*60)
    print("VERIFICAÇÃO")
    print("="*60)
    
    verify_count = 0
    for node_name, node_info in NODES.items():
        if verify_node(node_name, node_info, core_session):
            verify_count += 1
    
    # Resumo
    print("\n" + "="*60)
    print("RESUMO")
    print("="*60)
    print(f"Cópia bem-sucedida: {success_count}/{len(NODES)} nós")
    print(f"Verificação: {verify_count}/{len(NODES)} nós")
    
    if success_count == len(NODES):
        print("\n[OK] Todos os ficheiros foram copiados com sucesso!")
        print("\nPróximos passos:")
        print("1. Em cada nó, instalar dependências:")
        print("   cd /tmp/nms && pip3 install -r requirements.txt")
        print("2. Iniciar servidores conforme Guia_Teste_CORE.md")
    else:
        print("\n[AVISO] Alguns nós não receberam ficheiros automaticamente.")
        print("\nUse método manual:")
        print("1. No CORE: Tools → File Transfer")
        print(f"2. Enviar {tarball_path} para cada nó")
        print("3. Em cada nó:")
        print("   mkdir -p /tmp/nms")
        print("   cd /tmp/nms")
        print("   tar -xzf /tmp/nms_code.tar.gz")
        print("   chmod +x /tmp/nms/scripts/apply_routes.sh")
        print("   pip3 install -r requirements.txt")
    
    # Limpar arquivo temporário (opcional)
    # os.remove(tarball_path)

if __name__ == '__main__':
    main()

