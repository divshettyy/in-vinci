#!/usr/bin/env bash
# Pull the 17 Night Reel source clips from ChatCut into ~/reel-workdir/clips/.
#
# ONE-TIME SETUP (your cookie never leaves this machine):
#   1. Open ChatCut in your browser, signed in.
#   2. DevTools (F12) -> Network tab -> click any request to api.chatcut.io
#      -> Request Headers -> copy the WHOLE value of the `cookie:` header.
#   3. Paste it into ~/reel-workdir/cookie.txt  (single line), e.g.:
#        echo 'PASTE_COOKIE_HERE' > ~/reel-workdir/cookie.txt
#   4. bash ~/reel-workdir/download_clips.sh
#
set -uo pipefail
OUT="$HOME/reel-workdir/clips"
COOKIE_FILE="$HOME/reel-workdir/cookie.txt"
PID="ab2dbed8-4041-47d6-97bb-0ec03cc36068"
BASE="https://api.chatcut.io/api/assets"
mkdir -p "$OUT"

if [[ ! -s "$COOKIE_FILE" ]]; then
  echo "ERROR: put your ChatCut cookie (one line) in $COOKIE_FILE first. See header of this script." >&2
  exit 1
fi
COOKIE="$(tr -d '\r\n' < "$COOKIE_FILE")"

# name -> asset UUID
declare -A M=(
  [d_chase_vert.mp4]=f8fa989c-db3d-4681-85ac-fcb4cf83f48e
  [d_crest_3p_LS.mp4]=cc7ab741-95df-4685-8e84-c100281f09e5
  [d_crest.mp4]=4ecfd7f7-4bbf-42a4-ac8a-e67bfd13848c
  [d_dashboot_LS.mp4]=51a7daab-59f4-4035-b3ce-491c41f82723
  [d_hero_slomo_LS.mp4]=49ab4674-5204-43f2-91c8-8dae5eae1709
  [d_pan_slomo.mp4]=a6fd9873-d6a7-4ad0-825b-6ae1e3d37d72
  [d_parked_opener.mp4]=dbe296fc-d54d-4b47-b241-cdfa461bac58
  [d_plateau_vert.mp4]=c9f53905-f7dd-4c10-b536-5ec09196766e
  [d_scenic_vert.mp4]=190fd81c-60ee-41ca-8b84-605b8363fb71
  [n_beam_flood.mp4]=877a7092-a28e-4e47-934a-2128e1c5ad00
  [n_bikeahead.mp4]=12ef94b1-471a-4fc2-a695-47cb32e85277
  [n_brushbike.mp4]=1dbe673f-2a74-4ad8-b020-747c921cc4f8
  [n_headpool_slomo.mp4]=e5c1c7a5-aea7-40a2-b4e0-7703ded31910
  [n_hiviz_hero.mp4]=58a1fdc4-2a93-4a00-bdec-424aa78e50bd
  [n_riderlit.mp4]=5a3fb456-ee1b-47e8-b2be-4ef2939566b1
  [n_speedblur.mp4]=6d406328-7dcd-4b10-9feb-de9ab1e1d28c
  [n_taillight_slomo.mp4]=fb128c22-7103-463a-a2f9-cad84055a7aa
)

ok=0; fail=0
for name in "${!M[@]}"; do
  id="${M[$name]}"
  url="$BASE/$id/download?projectId=$PID"
  code=$(curl -sS -b "chatcut=dummy" -H "cookie: $COOKIE" -w '%{http_code}' \
              -o "$OUT/$name" "$url" 2>/dev/null || echo 000)
  sz=$(stat -c%s "$OUT/$name" 2>/dev/null || echo 0)
  if [[ "$code" == "200" && "$sz" -gt 200000 ]]; then
    printf 'ok   %-24s %s bytes\n' "$name" "$sz"; ok=$((ok+1))
  else
    printf 'FAIL %-24s http=%s size=%s (bad cookie? re-copy it)\n' "$name" "$code" "$sz"
    rm -f "$OUT/$name"; fail=$((fail+1))
  fi
done
echo "---"
echo "done: $ok ok, $fail failed -> $OUT"
[[ $fail -eq 0 ]] && echo "ALL GOOD. tell Claude: clips downloaded"