"""
Touchless HCI - AAC Sistemi 
"""

import cv2, mediapipe as mp, time, csv, os, json, math
import threading, queue, numpy as np
import speech_recognition as sr, urllib.request, urllib.error
from datetime import datetime

DWELL_TIME      = 1.0
GESTURE_TIMEOUT = 10.0
GESTURE_HOLD    = 0.4
VOICE_TIMEOUT   = 10.0
PARTICIPANT_ID  = "P01"

GROQ_API_KEY = "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"
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
WEB_PANEL_URL = "http://localhost:5000/api/mesaj"


BASE_W, BASE_H = 820, 600

BUTTONS = [
    (60,  120, 200, 110, "Su_Iste",      "ihtiyac",  "SU",   "Su istedin"),
    (310, 120, 200, 110, "Tuvalete_Git", "ihtiyac",  "WC",   "Tuvalete gitmek istedin"),
    (560, 120, 200, 110, "Yardim_Cagir", "ihtiyac",  "SOS",  "Yardim cagirdin"),
    (60,  280, 200, 110, "TV_Ac",        "konfor",   "TV",   "TV'yi actin"),
    (310, 280, 200, 110, "Isigi_Ac",     "konfor",   "ISIK", "Isigi actin"),
    (560, 280, 200, 110, "Aileye_Mesaj", "iletisim", "MSJ",  "Aileye mesaj gonderdin"),
    (160, 420, 500, 90,  "AI_Komut",     "ai",       "SOYLE", "Ihtiyacini soyledin"),
]

CAT_COLORS = {
    "ihtiyac":  (60,  60,  200),
    "konfor":   (200, 130, 50),
    "iletisim": (60,  180, 75),
    "ai":       (0,   150, 150),
}

VOICE_CMDS = {
    "seç":"S","sec":"S","seçim":"S","secim":"S","select":"S",
    "tamam":"S","evet":"S","onayla":"S","onay":"S","kabul":"S",
    "olur":"S","oldu":"S","tamamdir":"S","tamamdır":"S",
    "iptal":"C","cancel":"C","hayır":"C","hayir":"C",
    "vazgeç":"C","vazgec":"C","geri":"C","yok":"C","istemiyorum":"C",
}

MODE_ORDER = ["gesture", "voice", "single"]
mode_idx   = 0
MODE       = MODE_ORDER[0]

os.makedirs("logs", exist_ok=True)
LF = f"logs/{PARTICIPANT_ID}_FINAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
with open(LF, "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerow([
        "ts","pid","mode","event","button",
        "ms","unintended","ai_kat","ai_aci","ai_msg"
    ])

def log(event, button="", ms=0,
        unintended=False, ai_kat="", ai_aci="", ai_msg=""):
    with open(LF, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.now().isoformat(), PARTICIPANT_ID, MODE,
            event, button, round(ms),
            unintended, ai_kat, ai_aci, ai_msg
        ])

def send_panel(payload):
    try:
        data = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(
            WEB_PANEL_URL, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=2): pass
        print(f"Panel: gonderildi [{payload.get('kategori','')}]")
    except Exception as e:
        print(f"Panel: erisim yok ({e})")

def send_panel_aac(btn_label, btn_feedback):
    threading.Thread(target=send_panel, args=({
        "kategori":      "aac_secim",
        "aciliyet":      "dusuk",
        "mesaj":         btn_feedback,
        "hasta_ifadesi": btn_label.replace("_", " ")
    },), daemon=True).start()

class MicManager:
    def __init__(self):
        self.mode  = "idle"
        self.cmd_q = queue.Queue()
        self.ai_q  = queue.Queue()
        self.rec   = sr.Recognizer()
        self._stop = False
        threading.Thread(target=self._run, daemon=True).start()

    def set_voice(self): self.mode = "voice"
    def set_ai(self):    self.mode = "ai_listen"
    def set_idle(self):  self.mode = "idle"

    def _run(self):
        try:
            with sr.Microphone() as src:
                self.rec.adjust_for_ambient_noise(src, duration=1.5)
                self.rec.energy_threshold = 200      # Daha hassas (varsayılan 300)
                self.rec.dynamic_energy_threshold = True
                self.rec.pause_threshold = 0.6       # Konuşma duraklamasını daha hızlı yakala

                print("Mikrofon hazir.")
                while not self._stop:
                    if self.mode == "idle":
                        time.sleep(0.05); continue
                    try:
                        if self.mode == "voice":
                            audio = self.rec.listen(src, timeout=3, phrase_time_limit=4)

                            
                            text = self.rec.recognize_google(audio, language="tr-TR").lower().strip()
                            cmd = VOICE_CMDS.get(text)
                            # Tam eşleşme yoksa, kelime kelime ara
                            if cmd is None:
                               for word in text.split():
                                   if word in VOICE_CMDS:
                                        cmd = VOICE_CMDS[word]
                                        break
# Hala yoksa, kısmi eşleşme dene (örn. "seçtim", "iptal et")
                            if cmd is None:
                                for key, val in VOICE_CMDS.items():
                                     if key in text or text in key:
                                           cmd = val
                                           break



                            if cmd: self.cmd_q.put(cmd)
                            print(f"Ses: '{text}' -> {cmd or '?'}")
                        elif self.mode == "ai_listen":
                            self.mode = "ai_wait"
                            audio = self.rec.listen(src, timeout=7, phrase_time_limit=8)
                            text  = self.rec.recognize_google(audio, language="tr-TR")
                            print(f"AI duydu: {text}")
                            self.ai_q.put(("ok", text))
                            self.mode = "idle"
                    except sr.WaitTimeoutError:
                        if self.mode == "ai_wait":
                            self.mode = "ai_listen"
                    except sr.UnknownValueError:
                        if self.mode == "ai_wait":
                            self.mode = "ai_listen"
                    except Exception as e:
                        print(f"Mic hata: {e}")
                        if self.mode == "ai_wait":
                            self.ai_q.put(("err", str(e)[:40]))
                            self.mode = "idle"
        except Exception as e:
            print(f"Mikrofon acilamadi: {e}")

mic = MicManager()

AI_PROMPT = """Sen bir AAC sisteminin yardimcisisin.
Hasta yatakta hareket edemiyor, Turkce konusiyor.
Gorev: Hastanin ne soyledigini anla, ne istedigini kisa net Turkce mesajla yaz.
Kategori: saglik_sikayeti / temel_ihtiyac / konfor / iletisim / acil_durum
Aciliyet: dusuk / normal / yuksek / acil
Mesaj: Hastanin durumunu net Turkce yaz, max 10 kelime.
Ornek: "Hasta mide bulantisi yasıyor" veya "Hasta su istiyor"
SADECE JSON ver, baska hicbir sey yazma:
{"kategori":"...","aciliyet":"...","mesaj":"...","hasta_ifadesi":"..."}"""

def call_llm_mock(text):
    t = (text.lower()
         .replace("ğ","g").replace("ı","i").replace("ş","s")
         .replace("ç","c").replace("ö","o").replace("ü","u"))
    if any(w in t for w in ["bayil","kanam","nefes alam","oluyorum","911","imdat"]):
        kat, aci = "acil_durum", "acil"
        msg = f"ACIL: Hasta {text} bildiriyor, derhal mudahale!"
    elif any(w in t for w in ["agr","bulan","nefes","bas","mide","ates",
             "titri","kus","ishal","sanci","yanma","yorgun","bacak",
             "gogus","kalp","rahatsiz","aci","hasta"]):
        kat = "saglik_sikayeti"
        aci = "yuksek" if any(w in t for w in ["cok","siddetli","dayanam","fena"]) else "normal"
        msg = f"Hasta saglik sikayeti bildiriyor: {text}"
    elif any(w in t for w in ["su","ac","yemek","tuvalet","ilac","battaniye","yorgan"]):
        kat, aci = "temel_ihtiyac", "normal"
        msg = f"Hasta temel ihtiyac bildiriyor: {text}"
    elif any(w in t for w in ["anne","baba","aile","kardes","refak",
             "ziyaret","ara","telefon","ozled","yalniz"]):
        kat, aci = "iletisim", "dusuk"
        msg = f"Hasta yakinlariyla iletisim kurmak istiyor: {text}"
    elif any(w in t for w in ["soguk","sicak","isik","tv","muzik","pencere","rahat"]):
        kat, aci = "konfor", "dusuk"
        msg = f"Hasta konfor talebi bildiriyor: {text}"
    else:
        kat, aci = "genel", "normal"
        msg = f"Hasta bildiriyor: {text}"
    return {"kategori": kat, "aciliyet": aci,
            "mesaj": msg, "hasta_ifadesi": text}

def call_llm(text):
    try:
        pl = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": AI_PROMPT},
                {"role": "user",   "content": f"Hasta soyledi: {text}"}
            ],
            "temperature": 0.1,
            "max_tokens": 200
        }
        data = json.dumps(pl, ensure_ascii=False).encode("utf-8")
        req  = urllib.request.Request(
            GROQ_URL, data=data,
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}"
            }, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.loads(r.read().decode("utf-8"))
        raw = body["choices"][0]["message"]["content"].strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"): raw = raw[4:]
        result = json.loads(raw.strip())
        print(f"Groq sonuc: {result}")
        return result
    except urllib.error.HTTPError as e:
        print(f"Groq HTTP {e.code}: {e.read().decode()[:200]}")
        return call_llm_mock(text)
    except Exception as e:
        print(f"Groq hata: {e}")
        return call_llm_mock(text)

mp_h = mp.solutions.hands
mp_d = mp.solutions.drawing_utils
cap  = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  820)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)

WN = "Touchless HCI"
cv2.namedWindow(WN, cv2.WND_PROP_FULLSCREEN)
cv2.setWindowProperty(WN, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

try:
    import tkinter as tk
    _r = tk.Tk()
    SW, SH = _r.winfo_screenwidth(), _r.winfo_screenheight()
    _r.destroy()
except Exception:
    SW, SH = 1920, 1080

def fit(img):
    """Görüntüyü ekran boyutuna sığacak şekilde ölçekle ve ortala."""
    h, w = img.shape[:2]
    # En-boy oranını koru, ekrana sığ
    s = min(SW / w, SH / h)
    nw, nh = int(w * s), int(h * s)
    r = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    # Siyah arka plan üzerine ortala
    c = np.zeros((SH, SW, 3), dtype=np.uint8)
    yo, xo = (SH - nh) // 2, (SW - nw) // 2
    c[yo:yo+nh, xo:xo+nw] = r
    return c

def tangle(lm):
    return math.degrees(math.atan2(abs(lm[4].x-lm[2].x), -(lm[4].y-lm[2].y)))

def cfing(lm):
    return sum(1 for t,p in [(8,6),(12,10),(16,14),(20,18)] if lm[t].y>lm[p].y)

def dgest(lm, u=65, d=115):
    if lm is None: return None, None
    a = tangle(lm)
    if cfing(lm) < 3: return None, a
    if a < u: return "up", a
    if a > d: return "dn", a
    return None, a

USER_UP = 65
USER_DN = 115

def dk(c, f=.5):  return tuple(int(x*f) for x in c)
def lt(c, f=.3):  return tuple(min(255,int(x+(255-x)*f)) for x in c)

def tr(text):
    return (str(text)
            .replace("ğ","g").replace("Ğ","G").replace("ı","i").replace("İ","I")
            .replace("ş","s").replace("Ş","S").replace("ç","c").replace("Ç","C")
            .replace("ö","o").replace("Ö","O").replace("ü","u").replace("Ü","U"))

def put(frame, text, pos, scale=.6, color=(255,255,255), thick=1):
    cv2.putText(frame, tr(text), pos, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick)

def draw_btn(frame, btn, prog=0, hov=False, done=False,
             pend=False, tgt=False, dim=False):
    x, y, w, h, label, cat, icon, _ = btn
    base = CAT_COLORS.get(cat, (80,80,80))
    if done:   col = (50, 200, 50)
    elif pend: col = (180, 50, 180)
    elif hov:  col = lt(base)
    else:      col = dk(base)
    if dim:    col = dk(col, .35)
    cv2.rectangle(frame, (x,y), (x+w,y+h), col, -1)
    if tgt and not done and not dim:
        cv2.rectangle(frame, (x-3,y-3), (x+w+3,y+h+3), (0,215,255), 4)
    else:
        cv2.rectangle(frame, (x,y), (x+w,y+h), (80,80,80) if dim else (220,220,220), 2)
    if hov and not done and not pend and label != "AI_Komut":
        bw = int((w-10)*prog)
        cv2.rectangle(frame, (x+5,y+h-12), (x+5+bw,y+h-5), (0,220,255), -1)
    tc = (90,90,90) if dim else (255,255,255)
    sz = 2 if not dim else 1

    # ── Ikon / Buyuk baslik ──
    if label == "AI_Komut":
        put(frame, "IHTIYACIMI SOYLE", (x+w//2-150, y+50), .95, tc, sz)
    else:
        put(frame, icon, (x+w//2-30, y+55), 1.0, tc, sz)

    # ── Alt yazi (sadece normal butonlarda) ──
    if label != "AI_Komut":
        put(frame, label.replace("_"," "), (x+15, y+h-25), .52, tc, 1)

    # ── Pending durumu hint ──
    if pend:
        hint = "'SEC'/'IPTAL'" if MODE == "voice" else "Jest yap"
        put(frame, hint, (x+15, y+h-8), .38, (255,255,0), 1)

    # ── AI butonu alt aciklama ──
    if label == "AI_Komut" and not dim:
        put(frame, "Konusarak ihtiyacinizi soyleyin",
            (x+w//2-145, y+h-12), .52, (0,230,210), 1)
        
def isin(cx, cy, btn):
    x,y,w,h = btn[0],btn[1],btn[2],btn[3]
    return x < cx < x+w and y < cy < y+h

def mname(m):
    return {"single":"Tek-Modal","voice":"Hover+Ses","gesture":"Hover+Jest"}.get(m, m)

def draw_ai_panel(frame, state, dots=0, text="", result=None):
    if state == "idle": return
    ov = frame.copy()
    cv2.rectangle(ov, (0,505), (820,600), (5,8,22), -1)
    cv2.addWeighted(ov, .9, frame, .1, 0, frame)
    dot = "." * (dots%4) + " " * (3 - dots%4)

    if state == "listening":
        cv2.rectangle(frame, (100,508), (720,597), (0,70,50), -1)
        cv2.rectangle(frame, (100,508), (720,597), (0,255,150), 3)
        put(frame, f"DINLIYORUM{dot}", (270,548), .9, (0,255,180), 3)
        put(frame, "Mesajinizi soyleyin, durunca sistem anlayacak",
            (155,580), .44, (100,255,200), 1)
    elif state == "processing":
        put(frame, f"ISLENIYOR{dot}", (300,548), .75, (0,200,255), 2)
        put(frame, f"Algilandi: \"{text[:60]}\"", (70,578), .43, (150,175,200), 1)
    elif state == "result" and result:
        aci = result.get("aciliyet","normal")
        ac  = {"dusuk":(80,200,80),"normal":(200,200,80),
               "yuksek":(50,130,255),"acil":(0,50,255)}.get(aci,(200,200,200))
        if aci == "acil":
            cv2.rectangle(frame, (0,502), (820,602), (0,0,200), 4)
        kat = result.get("kategori","").upper().replace("_"," ")
        put(frame, f"[{kat}] {aci.upper()}  |  Panele iletildi", (12,530), .5, ac, 1)
        put(frame, result.get("mesaj","")[:75], (12,556), .48, (255,255,255), 1)
        put(frame, f"Ifade: \"{result.get('hasta_ifadesi','')[:65]}\"",
            (12,580), .41, (160,160,160), 1)
    elif state == "error":
        put(frame, text, (200,555), .6, (80,80,255), 2)

def blank(): return np.zeros((600,820,3), dtype=np.uint8)

def show_welcome():
    s = blank()
    put(s, "Touchless HCI - AAC Sistemi", (100,70), 1.0, (255,255,255), 2)
    put(s, "Dokunmadan Etkilesim ile Hasta Iletisim Platformu",
        (80,115), .55, (150,150,150), 1)
    cv2.line(s, (60,135), (760,135), (60,60,60), 1)
    put(s, "AAC Nedir?", (60,175), .7, (0,200,255), 2)
    put(s, "Augmentative and Alternative Communication -", (60,210), .55, (200,200,200), 1)
    put(s, "Konusamayan veya hareket edemeyen bireylerin", (60,238), .55, (200,200,200), 1)
    put(s, "iletisim kurmasini saglayan teknoloji sistemidir.", (60,266), .55, (200,200,200), 1)
    cv2.line(s, (60,290), (760,290), (60,60,60), 1)
    put(s, "3 Etkilesim Modu:", (60,325), .65, (255,255,100), 2)
    modlar = [
        ("1", "Hover+Jest ", "Parmak uzerinde bekle, bas parmakla onayla",       (100,255,100)),
        ("2", "Hover+Ses  ", "Parmak uzerinde bekle, 'SEC' veya 'IPTAL' soyle",  (100,200,255)),
        ("3", "Tek-Modal  ", "Parmak uzerinde bekle, otomatik secilir",           (255,200,100)),
    ]
    for j,(num,mod,acik,col) in enumerate(modlar):
        y = 365 + j*52
        cv2.circle(s, (75, y-5), 14, col, -1)
        put(s, num, (69, y), .55, (0,0,0), 2)
        put(s, mod, (100, y), .6, col, 2)
        put(s, acik, (100, y+22), .47, (160,160,160), 1)
    cv2.line(s, (60,530), (760,530), (60,60,60), 1)
    put(s, f"Katilimci: {PARTICIPANT_ID}   |   Mod sirasi: {' -> '.join(MODE_ORDER)}",
        (60,558), .5, (120,120,120), 1)
    cv2.imshow(WN, fit(s))
    t0 = time.time()
    while time.time() - t0 < 4.0:
        kalan = 4.0 - (time.time() - t0)
        s2 = s.copy()
        put(s2, f"Basliyor: {kalan:.0f}...", (340,590), .65, (50,255,50), 2)
        cv2.imshow(WN, fit(s2))
        k = cv2.waitKey(30) & 0xFF
        if k == 27:
            mic._stop = True; cap.release()
            cv2.destroyAllWindows(); import sys; sys.exit(0)

def show_intro():
    s = blank()
    put(s, "Touchless HCI - AAC Sistemi", (130,80),  1.0, (255,255,255), 2)
    put(s, f"Oturum {mode_idx+1}/{len(MODE_ORDER)}: {mname(MODE)}", (130,150), .8, (0,200,255), 2)
    if   MODE=="single":  h = "Hover (1 sn): dogrudan secim"
    elif MODE=="voice":   h = "Hover sonra: 'SEC' veya 'IPTAL' soyle"
    else:                 h = "Hover sonra: Bas parmak YUKARI=ONAY / ASAGI=IPTAL"
    put(s, h, (130,220), .6, (180,220,180), 1)
    put(s, "'Ihtiyacini Soyle' butonu: konusarak ihtiyacinizi belirtin",
        (130,270), .55, (0,220,200), 1)
    put(s, "Istediginiz butonu secmekte ozgursunuz", (130,320), .55, (200,200,200), 1)
    cv2.imshow(WN, fit(s))
    t0 = time.time()
    while time.time() - t0 < 3.0:
        kalan = 3.0 - (time.time() - t0)
        s2 = s.copy()
        put(s2, f"Basliyor: {kalan:.0f}...", (340,590), .65, (50,255,50), 2)
        cv2.imshow(WN, fit(s2))
        k = cv2.waitKey(30) & 0xFF
        if k == 27:
            mic._stop = True; cap.release()
            cv2.destroyAllWindows(); import sys; sys.exit(0)

def show_summary(tt, sel_count, err):
    s = blank()
    put(s, "OTURUM TAMAMLANDI", (220,90),  1.0, (50,255,50),  2)
    put(s, mname(MODE),         (150,160), .75, (0,200,255),  1)
    for i,(lbl,val) in enumerate([
        (f"Sure:         {tt:.1f} sn", (255,255,255)),
        (f"Toplam secim: {sel_count}",  (100,255,100)),
        (f"Istem disi:   {err}",        (180,180,180)),
    ]):
        put(s, lbl, (200, 260+i*55), .65, val, 1)
    put(s, "Lutfen anketi doldurun.", (230,490), .65, (255,255,100), 1)
    put(s, "M ile sonraki moda gec  |  Q/ESC ile bitir", (180,540), .55, (140,140,140), 1)
    cv2.imshow(WN, fit(s))
    while True:
        k = cv2.waitKey(1) & 0xFF
        if k == ord('m'): return "next"
        if k in (ord('q'), 27): return "quit"

def calibrate(hands_obj):
    global USER_UP, USER_DN
    PREP, MEAS = 3.0, 2.5
    def scal(msg, sub, col, cd=None, ang=None, n=0, pg=0):
        s = blank()
        put(s, "JEST KALIBRASYONU", (230,80), 1.0, (0,200,255), 2)
        put(s, msg, (60,220), .9, col, 2)
        put(s, sub, (60,270), .6, (200,200,200), 1)
        if cd: put(s, str(cd), (390,400), 3.0, col, 6)
        if ang is not None:
            put(s, f"Aci:{ang:.0f}  Ornek:{n}", (60,370), .65, (100,255,200), 2)
            cv2.rectangle(s,(60,460),(780,490),(60,60,60),-1)
            cv2.rectangle(s,(60,460),(60+int(720*pg),490),col,-1)
        cv2.imshow(WN, fit(s))
    up_s, dn_s = [], []
    for step, (msg, sub, col, lo, hi, store) in enumerate([
        ("Adim 1/2: ONAY jesti",  "Bas parmagi YUKARI cevirin", (100,255,100), 0,  90, "up"),
        ("Adim 2/2: IPTAL jesti", "Bas parmagi ASAGI cevirin",  (100,100,255), 90,180, "dn"),
    ]):
        t0 = time.time()
        while time.time()-t0 < PREP:
            scal(msg, sub, col, cd=int(PREP-(time.time()-t0))+1); cv2.waitKey(30)
        t0 = time.time()
        while time.time()-t0 < MEAS:
            ret, frm = cap.read()
            if not ret: continue
            frm = cv2.flip(frm, 1)
            frm = cv2.resize(frm, (BASE_W, BASE_H), interpolation=cv2.INTER_LINEAR)
            res = hands_obj.process(cv2.cvtColor(frm, cv2.COLOR_BGR2RGB))
            ang = None
            if res.multi_hand_landmarks:
                lm = res.multi_hand_landmarks[0].landmark; ang = tangle(lm)
                if lo <= ang <= hi: (up_s if store=="up" else dn_s).append(ang)
            scal(msg+" - OLCULUYOR", sub, col, ang=ang,
                 n=len(up_s if store=="up" else dn_s), pg=(time.time()-t0)/MEAS)
            cv2.waitKey(1)
    if len(up_s) >= 10 and len(dn_s) >= 10:
        ua = sum(up_s)/len(up_s); da = sum(dn_s)/len(dn_s)
        USER_UP = min(80, ua+25); USER_DN = max(100, da-25)
        if USER_DN - USER_UP < 20:
            mid = (ua+da)/2; USER_UP=mid-10; USER_DN=mid+10
        log("CALIBRATION", button=f"up={USER_UP:.0f}_dn={USER_DN:.0f}")
        print(f"Kalibrasyon: UP<{USER_UP:.0f}  DN>{USER_DN:.0f}")
    else:
        print("Kalibrasyon: varsayilan kullaniliyor")

gcal = False

def run_session():
    global MODE, gcal
    hs={}; sel={}; pb=None; cg=None; gt=None
    ec=0; ts=time.time(); fb=""; fbt=0; sel_count=0
    hover_btn_idx=-1
    ai_state="idle"; ai_result=None; ai_rt=0
    ai_text=""; ai_dots=0; ai_dt=0; ai_llm_q=queue.Queue()

    if MODE == "voice": mic.set_voice()
    else:               mic.set_idle()
    while not mic.cmd_q.empty(): mic.cmd_q.get()
    while not mic.ai_q.empty():  mic.ai_q.get()
    log("SESSION_START", button=f"mode={MODE}")

    with mp_h.Hands(max_num_hands=2, min_detection_confidence=.7,
                    min_tracking_confidence=.7) as hands:
        if MODE == "gesture" and not gcal:
            calibrate(hands); gcal = True
        show_intro()

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
            frame = cv2.flip(frame, 1)
            frame = cv2.resize(frame, (BASE_W, BASE_H), interpolation=cv2.INTER_LINEAR)
            hf, wf, _ = frame.shape

            res = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            ov = frame.copy()
            cv2.rectangle(ov, (0,0), (wf,100), (0,0,0), -1)
            cv2.addWeighted(ov, .7, frame, .3, 0, frame)

            cx, cy = -1, -1; lm = None
            if res.multi_hand_landmarks:
                for hand_lm in res.multi_hand_landmarks:
                    mp_d.draw_landmarks(frame, hand_lm, mp_h.HAND_CONNECTIONS)
                lm = min(res.multi_hand_landmarks,
                         key=lambda h: h.landmark[8].x).landmark
                cx = int(lm[8].x*wf); cy = int(lm[8].y*hf)
                cv2.circle(frame, (cx,cy), 14, (0,255,255), -1)
                cv2.circle(frame, (cx,cy), 14, (0,0,0), 2)

            now = time.time()
            if now-ai_dt > .35: ai_dots=(ai_dots+1)%4; ai_dt=now

            if not mic.ai_q.empty():
                mtype, mdata = mic.ai_q.get()
                if mtype == "ok":
                    ai_text = mdata; ai_state = "processing"
                    def _llm(t):
                        r = call_llm(t); ai_llm_q.put(r)
                    threading.Thread(target=_llm, args=(mdata,), daemon=True).start()
                else:
                    ai_text = mdata; ai_state = "error"; ai_rt = now

            if not ai_llm_q.empty():
                ai_result = ai_llm_q.get(); ai_rt = now; ai_state = "result"
                log("AI_RESULT","AI_Komut",
                    ai_kat=ai_result.get("kategori",""),
                    ai_aci=ai_result.get("aciliyet",""),
                    ai_msg=ai_result.get("mesaj",""))
                threading.Thread(target=send_panel, args=(ai_result,), daemon=True).start()

            if ai_state == "result" and now-ai_rt > 6.:
                ai_state="idle"; ai_result=None; ai_text=""
            if ai_state == "error" and now-ai_rt > 1.5:
                ai_state="listening"; ai_text=""
                mic.set_idle(); time.sleep(0.2); mic.set_ai()

            vc = None
            if MODE == "voice" and not mic.cmd_q.empty(): vc = mic.cmd_q.get()
            g, ang = None, None
            if MODE == "gesture": g, ang = dgest(lm, USER_UP, USER_DN)

            if pb is not None:
                i, btn, th, tp = pb; act = None
                if MODE == "voice":
                    if   vc == "S":              act = "sel"
                    elif vc == "C":              act = "can"
                    elif now-tp > VOICE_TIMEOUT: act = "to"
                elif MODE == "gesture":
                    if now-tp > GESTURE_TIMEOUT: act = "to"
                    elif g is not None:
                        if cg == g:
                            if now-gt >= GESTURE_HOLD: act = "sel" if g=="up" else "can"
                        else: cg, gt = g, now
                    else: cg, gt = None, None

                if act == "sel":
                    bl = btn[4]
                    if bl == "AI_Komut":
                        mic.set_idle(); time.sleep(0.3)
                        while not mic.cmd_q.empty(): mic.cmd_q.get()
                        while not mic.ai_q.empty():  mic.ai_q.get()
                        ai_state = "listening"; mic.set_ai()
                        log("AI_ACTIVATED","AI_Komut")
                        pb=None; cg=None; gt=None
                    elif bl == "Aileye_Mesaj":
                        mic.set_idle(); time.sleep(0.3)
                        while not mic.cmd_q.empty(): mic.cmd_q.get()
                        while not mic.ai_q.empty():  mic.ai_q.get()
                        ai_state = "listening"; mic.set_ai()
                        log("AI_ACTIVATED","Aileye_Mesaj")
                        fb = "Mesajinizi soyleyin..."; fbt = now
                        pb=None; cg=None; gt=None
                    else:
                        sel[i]=True; sel_count+=1; fb=f"OK: {btn[7]}"; fbt=now
                        ev={"single":"SEL_HOVER","voice":"SEL_VOICE","gesture":"SEL_GEST"}[MODE]
                        log(ev, bl, ms=(now-th)*1000)
                        send_panel_aac(bl, btn[7])
                        pb=None; cg=None; gt=None
                        time.sleep(.3); sel.clear()
                elif act == "can":
                    log("CANCEL", btn[4]); fb="Iptal edildi"; fbt=now
                    pb=None; cg=None; gt=None
                elif act == "to":
                    log("TIMEOUT", btn[4], unintended=True)
                    fb="Zaman asimi"; fbt=now; ec+=1
                    pb=None; cg=None; gt=None

            ai_busy = (ai_state != "idle")
            lk = (pb is not None) or ai_busy

            hover_btn_idx = -1
            for i, btn in enumerate(BUTTONS):
                if isin(cx, cy, btn) and not sel.get(i, False):
                    hover_btn_idx = i; break

            for i, btn in enumerate(BUTTONS):
                ins = isin(cx, cy, btn); dn = sel.get(i, False)
                pnd = pb is not None and pb[0]==i
                tgt = (i == hover_btn_idx) and not dn and not pnd

                if ai_busy and not pnd:
                    if i in hs: hs.pop(i)
                    draw_btn(frame, btn, done=dn, tgt=False, dim=True); continue
                if lk and not pnd:
                    if i in hs: hs.pop(i)
                    draw_btn(frame, btn, done=dn, tgt=False, dim=True); continue

                if ins and not dn:
                    if i not in hs: hs[i]=now; log("HOVER_START", btn[4])
                    el=now-hs[i]; pg=min(el/DWELL_TIME, 1.)
                    if el >= DWELL_TIME:
                        hs.pop(i)
                        if btn[4] == "Yardim_Cagir":
                            sel[i]=True; sel_count+=1
                            fb="SOS: Yardim cagrildi!"; fbt=now
                            log("SEL_HOVER_SOS", btn[4], ms=el*1000)
                            threading.Thread(target=send_panel, args=({
                                "kategori":      "acil_durum",
                                "aciliyet":      "acil",
                                "mesaj":         "ACIL: Hasta yardim cagiriyor, derhal mudahale!",
                                "hasta_ifadesi": "Yardim Cagir"
                            },), daemon=True).start()
                            time.sleep(.3); sel.clear() 
                            
                        elif  btn[4] == "AI_Komut":
                            if MODE == "single":
                                if ai_state == "idle":
                                   mic.set_idle(); time.sleep(0.3)
                                   while not mic.cmd_q.empty(): mic.cmd_q.get()
                                   while not mic.ai_q.empty():  mic.ai_q.get()
                                   ai_state = "listening"; mic.set_ai()
                                   log("AI_ACTIVATED","AI_Komut")
                                   fb = "Ihtiyacinizi soyleyin..."; fbt = now
                            else:
                                if ai_state == "idle":
                                   pb=(i,btn,now,now); cg=None; gt=None
                                   log("HOVER_PEND","AI_Komut")

                        elif MODE == "single":
                            if btn[4] == "Aileye_Mesaj":
                                mic.set_idle(); time.sleep(0.3)
                                while not mic.cmd_q.empty(): mic.cmd_q.get()
                                while not mic.ai_q.empty():  mic.ai_q.get()
                                ai_state = "listening"; mic.set_ai()
                                log("AI_ACTIVATED","Aileye_Mesaj")
                                fb = "Mesajinizi soyleyin..."; fbt = now
                            else:
                                sel[i]=True; sel_count+=1; fb=f"OK: {btn[7]}"; fbt=now
                                log("SEL_HOVER", btn[4], ms=el*1000)
                                send_panel_aac(btn[4], btn[7])
                                time.sleep(.3); sel.clear()
                        else:
                            pb=(i,btn,now,now); cg=None; gt=None
                            log("HOVER_PEND", btn[4], ms=el*1000)

                    draw_btn(frame, btn, pg, hov=True, tgt=tgt)
                else:
                    if i in hs and not pnd:
                        el=now-hs[i]
                        if el > .3: ec+=1; log("HOVER_ABORT", btn[4], ms=el*1000, unintended=True)
                        hs.pop(i)
                    draw_btn(frame, btn, done=dn, pend=pnd, tgt=tgt)

            put(frame, mname(MODE),                (430,30), .48, (255,255,0),   1)
            put(frame, f"Secim:{sel_count} H:{ec}", (430,58), .43, (180,180,180), 1)
            put(frame, "Q/ESC:cikis M:mod R:yeniden", (400,580), .38, (120,120,120), 1)

            if pb is not None:
                _, _, _, tp = pb
                rem = max(0, (GESTURE_TIMEOUT if MODE=="gesture" else VOICE_TIMEOUT)-(now-tp))
                cv2.rectangle(frame,(100,505),(720,598),(80,60,140),-1)
                cv2.rectangle(frame,(100,505),(720,598),(200,100,255),3)
                # Geri sayim cubugu (uzerinde)
                timeout_dur = GESTURE_TIMEOUT if MODE == "gesture" else VOICE_TIMEOUT
                bar_w = int(620 * (rem / timeout_dur))
                bar_color = (100, 255, 100) if rem > 5 else ((100, 200, 255) if rem > 2 else (100, 100, 255))
                cv2.rectangle(frame, (100, 500), (100 + bar_w, 505), bar_color, -1)



                if MODE == "voice":
                    put(frame,"SES BEKLENIYOR",   (255,543), .7, (255,255,255), 2)
                    put(frame, f"'SEC' veya 'IPTAL' soyleyin ({rem:.1f}s)", (200,572), .47, (220,210,255), 1)
                else:
                    put(frame, "JEST BEKLENIYOR", (240,543), .7, (255,255,255), 2)
                    put(frame, f"YUKARI=ONAY   ASAGI=IPTAL  ({rem:.1f}s)", (185,572), .47, (220,210,255), 1)
                    if ang is not None:
                        zl=("ONAY" if ang<USER_UP else ("IPTAL" if ang>USER_DN else "BELIRSIZ"))
                        zc=((100,255,100) if ang<USER_UP else ((100,100,255) if ang>USER_DN else (150,150,150)))
                        put(frame, f"Aci:{ang:.0f}  {zl}", (15,115), .5, zc, 1)
                    if cg and gt:
                        bp=min((now-gt)/GESTURE_HOLD,1.); bc=(0,255,100) if cg=="up" else (0,100,255)
                        cv2.rectangle(frame,(100,598),(100+int(620*bp),605),bc,-1)

            if fb and (now-fbt) < 2.5:
                put(frame, fb, (60,440), .65, (0,255,100), 2)

            draw_ai_panel(frame, ai_state, dots=ai_dots, text=ai_text, result=ai_result)
            cv2.imshow(WN, fit(frame))

            k = cv2.waitKey(1) & 0xFF
            if k in (ord('q'), 27):
                mic.set_idle(); log("SESSION_END", ms=(now-ts)*1000); return "quit"
            elif k == ord('m'):
                mic.set_idle(); log("SESSION_END", ms=(now-ts)*1000); return "next"
            elif k == ord('r'):
                hs.clear(); sel.clear(); pb=None; cg=None; gt=None
                ec=0; sel_count=0; ts=now; fb=""
                ai_state="idle"; ai_result=None; ai_text=""
                if MODE == "voice": mic.set_voice()
                log("SESSION_RESTART")

    mic.set_idle()
    log("SESSION_END", ms=(time.time()-ts)*1000)
    return show_summary(time.time()-ts, sel_count, ec)

print(f"\nKatilimci : {PARTICIPANT_ID}")
print(f"Mod sirasi: {' -> '.join(MODE_ORDER)}")
print(f"Log: {LF}\n")

log("EXPERIMENT_START", button=f"order={','.join(MODE_ORDER)}")
show_welcome()

while mode_idx < len(MODE_ORDER):
    MODE = MODE_ORDER[mode_idx]
    print(f"\n>>> Mod {mode_idx+1}/{len(MODE_ORDER)}: {MODE} <<<")
    result = run_session()
    if result == "quit": break
    if result == "next": mode_idx += 1

log("EXPERIMENT_END")
mic._stop = True
cap.release()
cv2.destroyAllWindows()
print(f"\nDeney tamamlandi. Log: {LF}")