#!/bin/bash
# ============================================================
# NODE DATA MARINGÁ — Verificação Pré-Demo
# Roda antes da reunião para garantir que tudo está no ar
# Uso: bash scripts/verificar-demo.sh
# ============================================================

DOMAIN="maringa.nodedata.com.br"
OK="\033[0;32m✓ OK\033[0m"
FAIL="\033[0;31m✗ FALHA\033[0m"
WARN="\033[0;33m⚠ AVISO\033[0m"

echo ""
echo "=========================================="
echo " Node Data Maringá — Verificação Pré-Demo"
echo "=========================================="
echo ""

ERROS=0

# 1. Backend respondendo
echo -n "1. Backend /health ............... "
HTTP=$(curl -s -o /dev/null -w "%{http_code}" "https://$DOMAIN/api/health" 2>/dev/null)
if [ "$HTTP" = "200" ]; then
  echo -e "$OK"
else
  echo -e "$FAIL (HTTP $HTTP)"
  ERROS=$((ERROS+1))
fi

# 2. Frontend carregando
echo -n "2. Frontend (HTML) ............... "
HTTP=$(curl -s -o /dev/null -w "%{http_code}" "https://$DOMAIN/" 2>/dev/null)
if [ "$HTTP" = "200" ]; then
  echo -e "$OK"
else
  echo -e "$FAIL (HTTP $HTTP)"
  ERROS=$((ERROS+1))
fi

# 3. Página Mulher Segura
echo -n "3. Mulher Segura (HTML) .......... "
HTTP=$(curl -s -o /dev/null -w "%{http_code}" "https://$DOMAIN/mulher-segura.html" 2>/dev/null)
if [ "$HTTP" = "200" ]; then
  echo -e "$OK"
else
  echo -e "$FAIL (HTTP $HTTP)"
  ERROS=$((ERROS+1))
fi

# 4. API de ocorrências
echo -n "4. API /api/ocorrencias .......... "
RESP=$(curl -s "https://$DOMAIN/api/ocorrencias" 2>/dev/null)
COUNT=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))" 2>/dev/null)
if [ -n "$COUNT" ] && [ "$COUNT" -gt 0 ]; then
  echo -e "$OK ($COUNT ocorrências)"
else
  echo -e "$FAIL (sem dados ou API fora)"
  ERROS=$((ERROS+1))
fi

# 5. API de denúncias
echo -n "5. API /api/denuncias ............ "
RESP=$(curl -s "https://$DOMAIN/api/denuncias" 2>/dev/null)
COUNT=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))" 2>/dev/null)
if [ -n "$COUNT" ] && [ "$COUNT" -gt 0 ]; then
  echo -e "$OK ($COUNT denúncias)"
else
  echo -e "$FAIL (sem dados ou API fora)"
  ERROS=$((ERROS+1))
fi

# 6. API SOS alertas
echo -n "6. API /api/sos/alertas .......... "
RESP=$(curl -s "https://$DOMAIN/api/sos/alertas" 2>/dev/null)
ATIVOS=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(sum(1 for a in d if a.get('status')=='active'))" 2>/dev/null)
if [ -n "$ATIVOS" ] && [ "$ATIVOS" -gt 0 ]; then
  echo -e "$OK ($ATIVOS alerta(s) ativo(s) — banner SOS visível)"
else
  echo -e "$WARN (nenhum alerta ativo — banner SOS não aparece)"
fi

# 7. Docker containers (se rodando localmente)
echo -n "7. Docker containers ............. "
if command -v docker &> /dev/null; then
  RUNNING=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -c "maringa\|redis\|backend\|worker\|frontend")
  if [ "$RUNNING" -gt 0 ]; then
    echo -e "$OK ($RUNNING containers rodando)"
  else
    echo -e "$WARN (nenhum container local — provavelmente rodando no Coolify)"
  fi
else
  echo -e "$WARN (Docker não instalado — rodando no Coolify)"
fi

# 8. Webhook respondendo
echo -n "8. Webhook endpoint .............. "
HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "https://$DOMAIN/webhook/unificado" -H "Content-Type: application/json" -d '{}' 2>/dev/null)
if [ "$HTTP" = "401" ] || [ "$HTTP" = "403" ] || [ "$HTTP" = "422" ] || [ "$HTTP" = "202" ]; then
  echo -e "$OK (endpoint ativo, HTTP $HTTP)"
else
  echo -e "$FAIL (HTTP $HTTP)"
  ERROS=$((ERROS+1))
fi

echo ""
echo "=========================================="
if [ "$ERROS" -eq 0 ]; then
  echo -e "\033[0;32m  TUDO OK — Pronto para a demo! 🚀\033[0m"
else
  echo -e "\033[0;31m  $ERROS FALHA(S) ENCONTRADA(S)\033[0m"
fi
echo "=========================================="
echo ""
