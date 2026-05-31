"""
Touchless HCI - Hasta Takip Paneli
===================================
Iki sekme:
  1. Klinik Panel  -> Hastane calisanlari icin (tum aktivite)
  2. Aile Paneli   -> Refakatci/aile icin (kisisel mesajlar)

Kullanim:
  pip install flask
  python web_panel_app.py
  Tarayici: http://localhost:5000
  Ayni WiFi'dan telefon: http://<IP>:5000
"""

from flask import Flask, request, jsonify, render_template_string
from datetime import datetime
import json, os

app = Flask(__name__)

MESSAGES_FILE = "messages.json"
messages = []

def load_messages():
    global messages
    if os.path.exists(MESSAGES_FILE):
        try:
            with open(MESSAGES_FILE, encoding="utf-8") as f:
                messages = json.load(f)
        except Exception:
            messages = []

def save_messages():
    with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

load_messages()



def is_aile(msg):
    return (msg.get("kategori") in ("iletisim",) or
            "Aileye" in msg.get("ifade","") or
            "Aileye" in msg.get("mesaj",""))

def is_klinik(msg):
    return True  

#HTML
PANEL_HTML = r"""
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Hasta Takip Paneli</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}

/* ── Header ── */
header{background:#1e293b;padding:14px 24px;border-bottom:1px solid #334155;display:flex;align-items:center;gap:16px}
header h1{font-size:1.1rem;font-weight:600;flex:1}
.live-badge{font-size:.72rem;padding:3px 10px;border-radius:999px;font-weight:600;background:#166534;color:#86efac}
.live-badge.off{background:#450a0a;color:#fca5a5}

/* ── Sekmeler ── */
.tabs{display:flex;background:#1e293b;border-bottom:1px solid #334155}
.tab{flex:1;padding:13px 0;text-align:center;cursor:pointer;font-size:.85rem;font-weight:500;color:#64748b;border-bottom:2px solid transparent;transition:.15s}
.tab.active{color:#e2e8f0;border-bottom-color:#3b82f6}
.tab.klinik.active{border-bottom-color:#f97316}
.tab.aile.active{border-bottom-color:#22c55e}
.tab-count{display:inline-block;margin-left:6px;background:#334155;border-radius:999px;font-size:.68rem;padding:1px 7px;min-width:20px;text-align:center}
.tab.klinik .tab-count{background:#431407;color:#fdba74}
.tab.aile   .tab-count{background:#052e16;color:#86efac}

/* ── Konteyner ── */
.container{max-width:720px;margin:0 auto;padding:20px 16px}
.tab-panel{display:none}.tab-panel.active{display:block}

/* ── İstatistik ── */
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:18px}
.stat{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px;text-align:center}
.stat .n{font-size:1.8rem;font-weight:700}
.stat .l{font-size:.72rem;color:#94a3b8;margin-top:3px}

/* ── Araç çubuğu ── */
.toolbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.toolbar span{font-size:.75rem;color:#64748b}
.btn-sm{padding:5px 12px;border:none;border-radius:7px;cursor:pointer;font-size:.75rem;font-weight:500}
.btn-refresh{background:#334155;color:#cbd5e1}
.btn-clear{background:#450a0a;color:#fca5a5;margin-left:6px}

/* ── Kart ── */
.card{background:#1e293b;border:1px solid #334155;border-radius:11px;padding:14px;margin-bottom:10px}
.card.acil   {border-left:4px solid #ef4444}
.card.yuksek {border-left:4px solid #f97316}
.card.normal {border-left:4px solid #3b82f6}
.card.dusuk  {border-left:4px solid #22c55e}
.card.okundu {opacity:.5}

.card-head{display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap}
.aci{font-size:.68rem;font-weight:700;padding:2px 8px;border-radius:5px;text-transform:uppercase}
.aci-acil  {background:#450a0a;color:#fca5a5}
.aci-yuksek{background:#431407;color:#fdba74}
.aci-normal{background:#172554;color:#93c5fd}
.aci-dusuk {background:#052e16;color:#86efac}
.kat{font-size:.68rem;padding:2px 8px;border-radius:5px;background:#334155;color:#94a3b8}
.kat.aac{background:#164e63;color:#67e8f9}
.zaman{margin-left:auto;font-size:.72rem;color:#64748b}
.btn-sil{background:transparent;border:none;color:#64748b;cursor:pointer;font-size:1rem;padding:2px 8px;border-radius:5px;transition:.15s}
.btn-sil:hover{background:#450a0a;color:#fca5a5}

.card-msg{font-size:.93rem;color:#e2e8f0;margin-bottom:5px;line-height:1.5}
.card-ifade{font-size:.78rem;color:#94a3b8;font-style:italic;margin-bottom:10px}

.card-actions{display:flex;gap:7px;flex-wrap:wrap}
.btn-ok{padding:6px 14px;border:none;border-radius:7px;cursor:pointer;font-size:.8rem;font-weight:500;background:#166534;color:#86efac}
.btn-acil-call{padding:6px 14px;border:none;border-radius:7px;cursor:pointer;font-size:.8rem;font-weight:500;background:#ef4444;color:#fff}

.empty{text-align:center;padding:50px 0;color:#475569;font-size:.9rem}

/* Acil banner */
.acil-banner{background:#450a0a;border:1px solid #ef4444;border-radius:10px;padding:12px 16px;margin-bottom:14px;display:none;align-items:center;gap:10px}
.acil-banner.show{display:flex}
.acil-banner span{font-size:.85rem;color:#fca5a5;flex:1}
.acil-banner strong{color:#ef4444;font-size:1rem}
</style>
</head>
<body>

<header>
  <h1> Hasta Takip Paneli</h1>
  <span id="badge" class="live-badge off">Bağlanıyor...</span>
</header>

<div class="tabs">
  <div class="tab klinik active" onclick="switchTab('klinik')">
    🏥 Klinik Panel
    <span id="cnt-klinik" class="tab-count">0</span>
  </div>
  <div class="tab aile" onclick="switchTab('aile')">
    👨‍👩‍👧 Aile / Refakatçi
    <span id="cnt-aile" class="tab-count">0</span>
  </div>
</div>

<!-- ── KLİNİK SEKME ── -->
<div id="tab-klinik" class="tab-panel active">
<div class="container">
  <div id="acil-banner" class="acil-banner">
    <strong>⚠ ACİL</strong>
    <span id="acil-text">Acil durum bildirimi var!</span>
    <button class="btn-acil-call" onclick="this.parentElement.classList.remove('show')">Görüldü</button>
  </div>
  <div class="stats">
    <div class="stat"><div class="n" id="k-toplam" style="color:#3b82f6">0</div><div class="l">Toplam</div></div>
    <div class="stat"><div class="n" id="k-okunmamis" style="color:#f97316">0</div><div class="l">Okunmamış</div></div>
    <div class="stat"><div class="n" id="k-acil" style="color:#ef4444">0</div><div class="l">Acil</div></div>
  </div>
  <div class="toolbar">
    <span id="k-guncelleme">-</span>
    <div>
      <button class="btn-sm btn-refresh" onclick="yukle()">↻ Yenile</button>
      <button class="btn-sm btn-clear" onclick="temizle()">Temizle</button>
    </div>
  </div>
  <div id="klinik-listesi"></div>
</div>
</div>

<!-- ── AİLE SEKME ── -->
<div id="tab-aile" class="tab-panel">
<div class="container">
  <div class="stats">
    <div class="stat"><div class="n" id="a-toplam" style="color:#22c55e">0</div><div class="l">Mesaj</div></div>
    <div class="stat"><div class="n" id="a-okunmamis" style="color:#f97316">0</div><div class="l">Okunmamış</div></div>
    <div class="stat"><div class="n" id="a-okundu" style="color:#64748b">0</div><div class="l">Görüldü</div></div>
  </div>
  <div class="toolbar">
    <span id="a-guncelleme">-</span>
    <div>
      <button class="btn-sm btn-refresh" onclick="yukle()">↻ Yenile</button>
    </div>
  </div>
  <div id="aile-listesi"></div>
</div>
</div>

<script>
let aktifTab = 'klinik';

function switchTab(t) {
  aktifTab = t;
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(el => el.classList.remove('active'));
  document.querySelector('.tab.' + t).classList.add('active');
  document.getElementById('tab-' + t).classList.add('active');
}

function zamanFark(iso) {
  const d = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (d < 60)   return d + 'sn önce';
  if (d < 3600) return Math.floor(d/60) + 'dk önce';
  if (d < 86400 ) return Math.floor(d/3600) + 'sa önce';
  const gun = Math.floor(d/86400);
  const kalanSaat = Math.floor ((d%86400)/3600);
  if (kalanSaat === 0) return gun + 'gun önce';
  return gun + 'gun' + kalanSaat + 'sa once';
 
}

function isAile(m) {
  return m.kategori === 'iletisim' ||
         (m.ifade  && m.ifade.includes('Aileye')) ||
         (m.mesaj  && m.mesaj.includes('Aileye'));
}

function kartHtml(m) {
  const aci   = m.aciliyet || 'normal';
  const kat   = m.kategori || '';
  const isAac = kat === 'aac_secim';
  const okundu = m.okundu ? 'okundu' : '';
  const acilBtn = aci === 'acil'
    ? `<button class="btn-acil-call" onclick="alert('Acil ekip aranıyor...')">📞 Acil Çağır</button>` : '';
  return `
    <div class="card ${aci} ${okundu}" id="kart-${m.id}">
      <div class="card-head">
        <span class="aci aci-${aci}">${aci.toUpperCase()}</span>
        <span class="kat ${isAac?'aac':''}">${kat.replace('_',' ')}</span>
        <span class="zaman">${zamanFark(m.zaman)}</span>
        <button class="btn-sil" onclick="mesajSil(${m.id})" title="Bu bildirimi sil">✕</button>
      </div>
      <div class="card-msg">${m.mesaj || ''}</div>
      <div class="card-ifade">Hasta: "${m.ifade || ''}"</div>
      <div class="card-actions">
        <button class="btn-ok" onclick="okundu(${m.id})">✓ Görüldü</button>
        ${acilBtn}
      </div>
    </div>`;
}

function yukle() {
  fetch('/api/mesajlar')
    .then(r => { if(!r.ok) throw new Error(r.status); return r.json(); })
    .then(data => {
      document.getElementById('badge').textContent = 'Canlı';
      document.getElementById('badge').className   = 'live-badge';

      const now = new Date().toLocaleTimeString('tr-TR');
      const klinik = data;
      const aile   = data.filter(isAile);

      // Klinik istatistik
      document.getElementById('k-toplam').textContent    = klinik.length;
      document.getElementById('k-okunmamis').textContent = klinik.filter(m=>!m.okundu).length;
      const acilSay = klinik.filter(m=>m.aciliyet==='acil').length;
      document.getElementById('k-acil').textContent = acilSay;
      document.getElementById('k-guncelleme').textContent = 'Son: ' + now;
      document.getElementById('cnt-klinik').textContent = klinik.filter(m=>!m.okundu).length;

      // Acil banner
      const banner = document.getElementById('acil-banner');
      if (acilSay > 0) {
        banner.classList.add('show');
        const son = klinik.filter(m=>m.aciliyet==='acil').slice(-1)[0];
        document.getElementById('acil-text').textContent = son ? son.mesaj : 'Acil durum!';
      } else {
        banner.classList.remove('show');
      }

      // Klinik liste
      const kl = document.getElementById('klinik-listesi');
      if (klinik.length === 0) {
        kl.innerHTML = '<div class="empty">Henüz kayıt yok.</div>';
      } else {
        kl.innerHTML = [...klinik].reverse().map(kartHtml).join('');
      }

      // Aile istatistik
      document.getElementById('a-toplam').textContent    = aile.length;
      document.getElementById('a-okunmamis').textContent = aile.filter(m=>!m.okundu).length;
      document.getElementById('a-okundu').textContent    = aile.filter(m=>m.okundu).length;
      document.getElementById('a-guncelleme').textContent = 'Son: ' + now;
      document.getElementById('cnt-aile').textContent = aile.filter(m=>!m.okundu).length;

      // Aile liste
      const al = document.getElementById('aile-listesi');
      if (aile.length === 0) {
        al.innerHTML = '<div class="empty">Aileye özel mesaj bulunmuyor.</div>';
      } else {
        al.innerHTML = [...aile].reverse().map(kartHtml).join('');
      }
    })
    .catch(() => {
      document.getElementById('badge').textContent = 'Bağlantı Yok';
      document.getElementById('badge').className   = 'live-badge off';
    });
}

function okundu(id) {
  fetch('/api/mesajlar/' + id + '/okundu', {method:'POST'}).then(yukle);
}

function mesajSil(id) {
  if (!confirm('Bu bildirim silinsin mi?')) return;
  fetch('/api/mesajlar/' + id, {method:'DELETE'}).then(yukle);
}

function temizle() {
  if (!confirm('Tüm kayıtlar silinsin mi?')) return;
  fetch('/api/mesajlar/temizle', {method:'POST'}).then(yukle);
}

yukle();
setInterval(yukle, 4000);
</script>
</body>
</html>
"""

#API
@app.route("/")
def index():
    return render_template_string(PANEL_HTML)

@app.route("/api/mesaj", methods=["POST"])
def yeni_mesaj():
    data = request.get_json(silent=True) or {}
    msg = {
        "id":       len(messages) + 1,
        "zaman":    datetime.now().isoformat(),
        "kategori": data.get("kategori", "bilinmiyor"),
        "aciliyet": data.get("aciliyet", "normal"),
        "mesaj":    data.get("mesaj", ""),
        "ifade":    data.get("hasta_ifadesi", ""),
        "okundu":   False,
    }
    messages.append(msg)
    save_messages()
    print(f"[YENI] {msg['aciliyet'].upper()} | {msg['kategori']} | {msg['mesaj'][:50]}")
    return jsonify({"durum": "ok", "id": msg["id"]}), 201

@app.route("/api/mesajlar")
def mesajlari_getir():
    return jsonify(messages)

@app.route("/api/mesajlar/<int:mid>/okundu", methods=["POST"])
def okundu_isaretle(mid):
    for m in messages:
        if m["id"] == mid:
            m["okundu"] = True
            save_messages()
            return jsonify({"durum": "ok"})
    return jsonify({"hata": "bulunamadi"}), 404

@app.route("/api/mesajlar/<int:mid>", methods=["DELETE"])
def mesaj_sil(mid):
    global messages
    messages = [m for m in messages if m["id"] != mid]
    save_messages()
    return jsonify({"durum": "ok"})

@app.route("/api/mesajlar/temizle", methods=["POST"])
def temizle():
    global messages
    messages = []
    save_messages()
    return jsonify({"durum": "ok"})

@app.route("/api/durum")
def durum():
    return jsonify({
        "durum": "aktif",
        "toplam": len(messages),
        "okunmamis": sum(1 for m in messages if not m["okundu"])
    })

if __name__ == "__main__":
    print("\n" + "="*50)
    print("  Hasta Takip Paneli Baslatiliyor")
    print("="*50)
    print(f"  Yerel  : http://localhost:5000")
    print(f"  Telefon: http://0.0.0.0:5000")
    print("="*50 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
