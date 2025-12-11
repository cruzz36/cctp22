#!/usr/bin/env python3
"""Script auxiliar para executar todos os testes e gerar relatório"""
import subprocess
import sys
import os

# Mudar para o diretório correto
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

tests = [
    "init",
    "server", 
    "header",
    "format",
    "split",
    "handshake",
    "send_short",
    "send_long",
    "send_file",
    "recv_message",
    "recv_file"
]

results = {}
print("="*70)
print("EXECUTANDO TODOS OS TESTES")
print("="*70)

for test in tests:
    print(f"\n>>> Executando teste: {test}")
    try:
        result = subprocess.run(
            [sys.executable, "debug/test_all_missionlink_functions.py", test],
            capture_output=True,
            text=True,
            timeout=60
        )
        # Verificar se passou (procura por "[OK] PASSOU" ou "[FALHOU]")
        if "[OK] PASSOU" in result.stdout or "100%" in result.stdout:
            results[test] = True
            print(f"✓ {test}: PASSOU")
        else:
            results[test] = False
            print(f"✗ {test}: FALHOU")
            if result.stderr:
                print(f"  Erro: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        results[test] = False
        print(f"✗ {test}: TIMEOUT")
    except Exception as e:
        results[test] = False
        print(f"✗ {test}: ERRO - {e}")

print("\n" + "="*70)
print("RESUMO FINAL")
print("="*70)
passed = sum(1 for v in results.values() if v)
total = len(results)
for test, result in results.items():
    status = "✓ PASSOU" if result else "✗ FALHOU"
    print(f"  {test:20s}: {status}")

print(f"\nTotal: {passed}/{total} testes passaram ({passed*100//total if total > 0 else 0}%)")

if passed == total:
    print("\n🎉 Todos os testes passaram!")
    sys.exit(0)
else:
    print(f"\n⚠️  {total - passed} teste(s) falharam")
    sys.exit(1)

