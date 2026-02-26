#!/bin/bash
# Feishu 读取能力真实联调验收脚本
#
# 用法:
#   ./scripts/validate_feishu_read.sh [URL]
#   FEISHU_TEST_URL="https://xxx.feishu.cn/docx/XXX" ./scripts/validate_feishu_read.sh
#
# 需配置 CANONICAL_FEISHU_APP_ID、CANONICAL_FEISHU_APP_SECRET
# API 需已启动: scripts/start_api.sh

set -e
cd "$(dirname "$0")/.."

URL="${1:-$FEISHU_TEST_URL}"
if [ -z "$URL" ]; then
  echo "用法: $0 <飞书文档URL>"
  echo "  或: FEISHU_TEST_URL=... $0"
  echo ""
  echo "示例: $0 'https://your-tenant.feishu.cn/docx/XXXX'"
  exit 1
fi

LOG_DIR="${LOG_DIR:-.}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/feishu_read_validation_${TIMESTAMP}.log"

echo "=== Feishu 读取验收 ===" | tee "$LOG_FILE"
echo "URL: $URL" | tee -a "$LOG_FILE"
echo "时间: $(date '+%Y-%m-%dT%H:%M:%S%z')" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 1. CLI 验收
echo "--- 1. CLI 验收 ---" | tee -a "$LOG_FILE"
PYTHON="${PYTHON:-python}"
if [ -f venv/bin/python ]; then
  PYTHON="./venv/bin/python"
fi
if $PYTHON -m canonical.cli read-feishu --url "$URL" 2>>"$LOG_FILE" | tee -a "$LOG_FILE"; then
  echo "CLI: 成功" | tee -a "$LOG_FILE"
else
  CLI_EXIT=$?
  echo "CLI: 退出码 $CLI_EXIT" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 2. API 验收（需 API 已启动在 8000 端口）
echo "--- 2. API 验收 ---" | tee -a "$LOG_FILE"
API_RESP=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:8000/api/v1/feishu/read" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"$URL\"}" 2>>"$LOG_FILE" || true)

if [ -n "$API_RESP" ]; then
  HTTP_BODY=$(echo "$API_RESP" | sed '$d')
  HTTP_CODE=$(echo "$API_RESP" | tail -1)
  echo "HTTP $HTTP_CODE" | tee -a "$LOG_FILE"
  echo "$HTTP_BODY" | python3 -m json.tool 2>/dev/null || echo "$HTTP_BODY" | tee -a "$LOG_FILE"
  if [ "$HTTP_CODE" = "200" ]; then
    echo "API: 成功" | tee -a "$LOG_FILE"
  else
    echo "API: 失败 (HTTP $HTTP_CODE)" | tee -a "$LOG_FILE"
  fi
else
  echo "API: 请求失败（请确认 API 已启动: scripts/start_api.sh）" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

echo "验收日志: $LOG_FILE"
