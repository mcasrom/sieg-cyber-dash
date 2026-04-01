#!/bin/bash
# setup_cron.sh — SIEG-CYBER · Configuración cron + mantenimiento Odroid
# Ejecutar una vez: bash ~/sieg-cyber-dash/setup_cron.sh

PROJECT="$HOME/sieg-cyber-dash"
LOG_DIR="$HOME/logs"
LOG_FILE="$LOG_DIR/cyber.log"
RENDER_URL="https://sieg-cyber-dash.onrender.com"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SIEG-CYBER · Setup cron + mantenimiento"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Crear directorio de logs
mkdir -p "$LOG_DIR"
echo "[OK] Directorio de logs: $LOG_DIR"

# Rotar logs si superan 10MB
if [ -f "$LOG_FILE" ] && [ $(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0) -gt 10485760 ]; then
    mv "$LOG_FILE" "$LOG_FILE.$(date +%Y%m%d).bak"
    echo "[OK] Log rotado"
fi

# Instalar crons (sin duplicar)
CRON_TEMP=$(mktemp)
crontab -l 2>/dev/null | grep -v "sieg-cyber" | grep -v "sieg_cyber" > "$CRON_TEMP"

# 1. Ping Render cada 14 min (evita sleep del free tier)
echo "*/14 * * * * curl -s $RENDER_URL/ > /dev/null 2>&1  # sieg-cyber-ping" >> "$CRON_TEMP"

# 2. Git push automático cada hora (mantiene GitHub actualizado)
echo "0 * * * * cd $PROJECT && git add -A && git diff --cached --quiet || git commit -m 'auto: sync $(date +\%Y-\%m-\%d\ \%H:\%M)' && git push >> $LOG_FILE 2>&1  # sieg-cyber-git" >> "$CRON_TEMP"

# 3. Limpieza de logs cada domingo a las 3:00
echo "0 3 * * 0 find $LOG_DIR -name '*.bak' -mtime +30 -delete >> $LOG_FILE 2>&1  # sieg-cyber-cleanup" >> "$CRON_TEMP"

# 4. Reinicio preventivo del servicio cada día a las 4:00
echo "0 4 * * * kill \$(lsof -t -i :8055 2>/dev/null) 2>/dev/null; cd $PROJECT && python3 app.py >> $LOG_FILE 2>&1 &  # sieg-cyber-restart" >> "$CRON_TEMP"

crontab "$CRON_TEMP"
rm "$CRON_TEMP"

echo "[OK] Crons instalados:"
crontab -l | grep "sieg-cyber"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Política de retención de datos"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  · SQLite: 14 días de histórico"
echo "  · Limpieza: automática en cada ciclo"
echo "  · Logs: rotación a 10MB, purga a 30 días"
echo "  · GitHub: solo código, datos excluidos"
echo ""

# Estado actual de la base de datos
DB="$PROJECT/data/cyber_historical.db"
if [ -f "$DB" ]; then
    SIZE=$(du -sh "$DB" | cut -f1)
    EVENTS=$(sqlite3 "$DB" "SELECT COUNT(*) FROM events;" 2>/dev/null || echo "?")
    CRITICOS=$(sqlite3 "$DB" "SELECT COUNT(*) FROM events WHERE risk='Crítico';" 2>/dev/null || echo "?")
    echo "  · DB actual: $SIZE · $EVENTS eventos · $CRITICOS críticos"
else
    echo "  · DB: no existe aún (se crea al arrancar)"
fi

echo ""
echo "[✅] Setup completo"
