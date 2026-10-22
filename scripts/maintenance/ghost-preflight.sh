#!/usr/bin/env bash
# ghost-preflight.sh — verify the homelab is healthy before a shutdown,
# and that everything self-healed after power-on.
#
# Run from aurora/UbuntuDev:  scripts/maintenance/ghost-preflight.sh
# Compare a before/after run:  ./ghost-preflight.sh > before.txt ... ./ghost-preflight.sh > after.txt && diff before.txt after.txt
#
# Read-only. No sudo needed. Fails loudly on the checks that have bitten us.

set -u
SSH="ssh -o ConnectTimeout=5 -o BatchMode=yes"
PASS=0; WARN=0; FAIL=0

ok()   { PASS=$((PASS+1)); printf 'PASS  %s\n' "$1"; }
warn() { WARN=$((WARN+1)); printf 'WARN  %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf 'FAIL  %s\n' "$1"; }
hdr()  { printf '\n== %s ==\n' "$1"; }

# ---------- ghost ----------
hdr "ghost (docker host, ZFS, homeassistant VM)"
if ! $SSH ghost 'true' 2>/dev/null; then
  bad "ghost unreachable over ssh"
else
  g() { $SSH ghost "$1" 2>/dev/null; }

  # Pools
  for pool in tank harbor frigate-media; do
    st=$(g "zpool list -H -o health $pool" 2>/dev/null)
    [ "$st" = "ONLINE" ] && ok "pool $pool ONLINE" || bad "pool $pool: ${st:-missing}"
  done
  g 'zpool status -x | grep -q "all pools are healthy"' && ok "zpool status -x clean" \
    || warn "zpool status -x reports errors (harbor has a known permanent error)"

  # Encryption keys + mounts
  unavail=$(g "zfs list -o name,keystatus -r tank/encrypted | awk '\$2==\"unavailable\"' | wc -l")
  [ "$unavail" = "0" ] && ok "all tank/encrypted keys loaded" || bad "$unavail tank/encrypted datasets WITHOUT keys"
  for m in /tank/encrypted /tank/encrypted/docker /tank/encrypted/nas /tank/encrypted/vms/homeassistant; do
    g "mountpoint -q $m" && ok "mounted $m" || bad "NOT mounted: $m (docker will bind-mount empty dirs!)"
  done

  # Boot units
  for s in docker docker.socket tailscaled libvirtd ssh.socket docker-wait-for-zfs; do
    st=$(g "systemctl is-enabled $s")
    [ "$st" = "enabled" ] && ok "$s enabled" || bad "$s is $st"
  done
  g 'systemctl show docker-wait-for-zfs.service -p ExecStart | grep -q "/bin/true"' \
    && warn "docker-wait-for-zfs is /bin/true — orders docker after zfs.target but verifies nothing (see runbook fix #1)" \
    || ok "docker-wait-for-zfs verifies mounts"
  g 'systemctl is-failed -q zfs-load-key.service' \
    && warn "zfs-load-key.service failed (expected while prompt-keyed harbor datasets exist)" \
    || ok "zfs-load-key.service not failed"

  # Containers
  norestart=$(g 'docker ps -q | xargs docker inspect -f "{{.Name}} {{.HostConfig.RestartPolicy.Name}}" | grep -vE "always$|unless-stopped$" | wc -l')
  [ "$norestart" = "0" ] && ok "all running containers have a restart policy" \
    || bad "$norestart running containers with restart=no: $(g 'docker ps -q | xargs docker inspect -f "{{.Name}} {{.HostConfig.RestartPolicy.Name}}" | grep -vE "always$|unless-stopped$" | cut -d" " -f1 | tr "\n" " "')"
  running=$(g 'docker ps -q | wc -l'); echo "      (ghost running containers: $running)"

  # VM
  va=$(g 'virsh -c qemu:///system dominfo homeassistant 2>/dev/null | awk -F: "/Autostart/{gsub(/ /,\"\",\$2);print \$2}"')
  [ "$va" = "enable" ] && ok "homeassistant VM autostart" || bad "homeassistant VM autostart=$va — run: virsh -c qemu:///system autostart homeassistant"
  g 'virsh -c qemu:///system domstate homeassistant 2>/dev/null | grep -q running' \
    && ok "homeassistant VM running" || warn "homeassistant VM not running"

  # Tailscale + LAN IP
  g 'tailscale status --peers=false >/dev/null 2>&1' && ok "tailscaled up" || bad "tailscaled down on ghost"
  ip=$(g 'ip -4 -o addr show br0 | awk "{print \$4}" | cut -d/ -f1')
  [ "$ip" = "192.168.1.9" ] && ok "LAN IP 192.168.1.9" || warn "ghost br0 IP is '$ip' (expected 192.168.1.9)"

  # Replication freshness (latest snapshot on tank/encrypted should be <2h)
  fresh=$(g 'zfs list -t snapshot -H -o creation -S creation -p tank/encrypted 2>/dev/null | head -1')
  now=$(date +%s); [ -n "$fresh" ] && age=$(( now - fresh )) || age=999999
  [ "$age" -lt 7200 ] && ok "latest tank snapshot $((age/60))min old" || warn "latest tank snapshot $((age/3600))h old — is sanoid running?"

  # Failed units + capacity
  fu=$(g 'systemctl --failed --no-legend --no-pager | wc -l')
  echo "      (failed units on ghost: $fu — expect 2: networkd-wait-online + zfs-load-key)"
  cap=$(g "zpool list -H -o capacity tank | tr -d '%'")
  [ "${cap:-0}" -lt 90 ] && ok "tank capacity ${cap}%" || warn "tank at ${cap}% — ZFS degrades past ~90%"
fi

# ---------- ghost-vault ----------
hdr "ghost-vault (replica)"
if ! $SSH ghost-vault 'true' 2>/dev/null; then
  warn "ghost-vault unreachable over ssh"
else
  v() { $SSH ghost-vault "$1" 2>/dev/null; }
  st=$(v "zpool list -H -o health tank")
  [ "$st" = "ONLINE" ] && ok "vault tank ONLINE" || bad "vault tank: ${st:-missing}"
  for s in docker.socket tailscaled; do
    [ "$(v "systemctl is-enabled $s")" = "enabled" ] && ok "vault $s enabled" || bad "vault $s not enabled"
  done
  norep=$(v 'systemctl is-active -q syncoid-replication.timer && echo yes')
  [ "$norep" = "yes" ] && ok "vault syncoid-replication.timer active" || bad "vault syncoid-replication.timer inactive"
  v 'docker ps --format "{{.Names}}" | grep -q signoz-otel-collector' && ok "vault observability collectors up" || warn "vault collectors down"
fi

# ---------- external ----------
hdr "external checks"
hc=$(curl -fsm8 -o /dev/null -w '%{http_code}' "https://hc-ping.com/uWDfVXr2W4O9rF7deuOEog/harbor-replication" 2>/dev/null)
[ "$hc" = "200" ] && ok "hc-ping reachable" || warn "hc-ping unreachable (${hc:-timeout})"
rtr=$(curl -skm5 -o /dev/null -w '%{http_code}' https://192.168.1.1:8443/ 2>/dev/null)
[ "$rtr" = "200" ] && ok "OPNsense UI up" || warn "OPNsense UI: ${rtr:-timeout}"
pi=$(curl -skm5 -o /dev/null -w '%{http_code}' https://192.168.1.4/api/info/system 2>/dev/null)
[ "$pi" = "200" ] && ok "pihole API up" || warn "pihole: ${pi:-timeout}"

# ---------- aurora self-check ----------
hdr "aurora (this machine)"
HOST_CMD=
[ -n "${CONTAINER_ID:-}" ] && command -v distrobox-host-exec >/dev/null && HOST_CMD=distrobox-host-exec
${HOST_CMD:+$HOST_CMD} systemctl is-enabled -q docker.socket 2>/dev/null && ok "aurora docker.socket enabled" || warn "aurora docker.socket not enabled"
${HOST_CMD:+$HOST_CMD} loginctl show-user nic 2>/dev/null | grep -q 'Linger=yes' && ok "linger on" || warn "linger off — user units die at logout"
systemctl --user is-enabled -q nas-backup.timer 2>/dev/null && ok "restic nas-backup.timer enabled" || warn "nas-backup.timer disabled"

hdr "summary"
printf 'PASS=%d WARN=%d FAIL=%d\n' "$PASS" "$WARN" "$FAIL"
[ "$FAIL" -eq 0 ]
