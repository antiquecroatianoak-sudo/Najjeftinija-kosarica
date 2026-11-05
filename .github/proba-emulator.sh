#!/usr/bin/env bash
# Proba aplikacije na emulatoru (poziva je .github/workflows/android.yml). Ne treba Google račun ni internet za cijene.
set -u
mkdir -p snimke
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
  adb shell input swipe 540 1800 540 500 600
  sleep 2
  adb exec-out screencap -p > snimke/3-rezultati.png
  adb shell input swipe 540 1800 540 500 600
  sleep 2
  adb exec-out screencap -p > snimke/4-ukupno.png
fi

adb logcat -d > snimke/logcat.txt
if grep -q "FATAL EXCEPTION" snimke/logcat.txt; then
  echo "APLIKACIJA SE SRUŠILA:"; grep -A 30 "FATAL EXCEPTION" snimke/logcat.txt | head -60; exit 1
fi
if ! adb shell pidof $PAKET >/dev/null; then echo "Aplikacija ne radi nakon probe."; exit 1; fi
echo "Proba prošla: aplikacija radi, bez rušenja."
