#!/usr/bin/env bash
# Proba aplikacije na emulatoru (poziva je .github/workflows/android.yml). Ne treba Google račun ni internet za cijene.
set -u
mkdir -p snimke
tekst() {
  adb shell uiautomator dump /sdcard/t.xml >/dev/null 2>&1 && adb pull /sdcard/t.xml t.xml >/dev/null 2>&1 &&
  python3 -c "import re,html;print('--- zaslon $1:', ' | '.join(html.unescape(t) for t in re.findall(r' text=\"([^\"]+)\"', open('t.xml',encoding='utf-8').read())))"
}
PAKET=hr.najjeftinijakosarica.app
APK=$(find apk -name '*.apk' | head -1)
adb install -r "$APK" || exit 1
adb logcat -c
adb shell am start -W -n $PAKET/.MainActivity
sleep 20
adb exec-out screencap -p > snimke/1-pocetak.png

# Upis popisa u polje "ili upiši…".
adb shell uiautomator dump /sdcard/ui.xml >/dev/null
adb pull /sdcard/ui.xml ui.xml >/dev/null
POLJE=$(python3 - <<'PY'
import re
x = open("ui.xml", encoding="utf-8").read()
for n in re.finditer(r'<node [^>]*>', x):
    s = n.group(0)
    if 'EditText' in s or 'ili upiši' in s:
        b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', s)
        if b:
            x1, y1, x2, y2 = map(int, b.groups()); print((x1 + x2) // 2, (y1 + y2) // 2); break
PY
)
echo "Polje za upis: $POLJE"
if [ -n "$POLJE" ]; then
  adb shell input tap $POLJE
  sleep 2
  adb shell input text "kruh,%s2%slitre%smlijeka,%s6%sjaja,%spola%skile%ssira,%sxyzzy"
  adb shell input keyevent 66
  sleep 4
  adb shell input keyevent 4   # sakrij tipkovnicu
  sleep 2
  adb exec-out screencap -p > snimke/2-popis.png
  tekst 2
  VELICINA=$(adb shell wm size | grep -o '[0-9]*x[0-9]*' | tail -1)
  W=${VELICINA%x*}; H=${VELICINA#*x}
  for n in 3 4 5 6 7; do
    adb shell input swipe $((W / 2)) $((H * 8 / 10)) $((W / 2)) $((H * 3 / 10)) 500
    sleep 2
    adb exec-out screencap -p > snimke/$n-pomak.png
    tekst $n
  done
fi

adb logcat -d > snimke/logcat.txt
grep -A 3 "Kosarica" snimke/logcat.txt | head -20
if grep -q "FATAL EXCEPTION" snimke/logcat.txt; then
  echo "APLIKACIJA SE SRUŠILA:"; grep -A 30 "FATAL EXCEPTION" snimke/logcat.txt | head -60; exit 1
fi
if ! adb shell pidof $PAKET >/dev/null; then echo "Aplikacija ne radi nakon probe."; exit 1; fi
echo "Proba prošla: aplikacija radi, bez rušenja."
