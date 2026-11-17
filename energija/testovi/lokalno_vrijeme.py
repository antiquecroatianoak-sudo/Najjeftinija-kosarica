"""Simulirana lokacija (zadano: kontinentalna Hrvatska) i sat moraju biti u istoj vremenskoj zoni, kao i na
stvarnom uređaju. S tuđom zonom sunce i navike padaju u krive lokalne sate, pa testovi provjeravaju nemoguću
kombinaciju. Ljetno računanje vremena i dalje se provjerava (Europe/Zagreb ga ima)."""
import os
import time

os.environ["TZ"] = "Europe/Zagreb"
time.tzset()
