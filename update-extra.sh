#!/usr/bin/env sh
set -eu

BASE_DIR="${BASE_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)}"
PUBLIC_DIR="$BASE_DIR/public"
EXTRA_OUT="$PUBLIC_DIR/status-extra.json"
EXTRA_TMP="$PUBLIC_DIR/status-extra.json.tmp"
CONTAINERS_OUT="$PUBLIC_DIR/containers.json"
CONTAINERS_TMP="$PUBLIC_DIR/containers.json.tmp"

UPTIME_SECONDS="$(cut -d. -f1 /proc/uptime)"
DAYS=$((UPTIME_SECONDS / 86400))
HOURS=$(((UPTIME_SECONDS % 86400) / 3600))
MINUTES=$(((UPTIME_SECONDS % 3600) / 60))
if [ "$DAYS" -gt 0 ]; then
  UPTIME_HUMAN="${DAYS}d ${HOURS}h"
elif [ "$HOURS" -gt 0 ]; then
  UPTIME_HUMAN="${HOURS}h ${MINUTES}m"
else
  UPTIME_HUMAN="${MINUTES}m"
fi

LOAD_1="$(cut -d' ' -f1 /proc/loadavg)"
CONTAINERS_RUNNING="$(docker ps -q | wc -l | tr -d ' ')"
CONTAINERS_TOTAL="$(docker ps -aq | wc -l | tr -d ' ')"
CONTAINERS_UNHEALTHY="$(docker ps --filter health=unhealthy -q | wc -l | tr -d ' ')"
FAILED_SERVICES="$(systemctl --failed --no-legend 2>/dev/null | wc -l | tr -d ' ')"
DOCKER_STATE="$(systemctl is-active docker 2>/dev/null || true)"
TAILSCALE_STATE="$(systemctl is-active tailscaled 2>/dev/null || true)"

jq -n \
  --arg uptime "$UPTIME_HUMAN" \
  --arg load "$LOAD_1" \
  --arg running "$CONTAINERS_RUNNING" \
  --arg total "$CONTAINERS_TOTAL" \
  --arg unhealthy "$CONTAINERS_UNHEALTHY" \
  --arg failed "$FAILED_SERVICES" \
  --arg docker "$DOCKER_STATE" \
  --arg tailscale "$TAILSCALE_STATE" \
  --arg updated "$(date -Iseconds)" \
  '{uptime:$uptime,load1:$load,containers_running:($running|tonumber),containers_total:($total|tonumber),containers_unhealthy:($unhealthy|tonumber),failed_services:($failed|tonumber),docker:$docker,tailscale:$tailscale,updated_at:$updated}' \
  > "$EXTRA_TMP"
mv "$EXTRA_TMP" "$EXTRA_OUT"

docker ps -a --format '{{json .}}' | jq -s \
  --arg updated "$(date -Iseconds)" \
  '{updated_at:$updated,containers:map({name:.Names,image:.Image,state:.State,status:.Status,ports:(.Ports // "")})}' \
  > "$CONTAINERS_TMP"
mv "$CONTAINERS_TMP" "$CONTAINERS_OUT"

