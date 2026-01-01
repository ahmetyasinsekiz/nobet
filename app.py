import streamlit as st
import pandas as pd
from ics import Calendar, Event
from datetime import datetime, timedelta
import io

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Nöbet Takvimi Oluşturucu", page_icon="📅")

st.title("📅 Asistan Nöbet Takvimi Dönüştürücü")
st.markdown("""
Bu araç, nöbet listenizi (Excel/CSV) telefon takviminize (Google/Apple Calendar) yükleyebileceğiniz 
**.ics** formatına dönüştürür.
""")

# --- KULLANICI GİRİŞ ALANI ---
with st.container():
    st.subheader("1. Bilgilerinizi Girin")
    col1, col2 = st.columns(2)
    
    with col1:
        # Kullanıcı ismini buradan alıyoruz
        target_name = st.text_input("Adınız Soyadınız", placeholder="Örn: Mehmet Tahir Sekizkardeş")
        st.caption("⚠️ Listede isminiz nasıl geçiyorsa öyle yazmaya çalışın (Büyük/küçük harf fark etmez).")
    
    with col2:
        uploaded_file = st.file_uploader("Dosyayı Yükleyin", type=["csv", "xlsx"])

# --- İŞLEM FONKSİYONU ---
def create_calendar(df, user_name):
    cal = Calendar()
    user_name = user_name.lower().strip()
    
    # Sütun isimlerini temizle
    df.columns = [str(c).strip() for c in df.columns]

    # Sütunları tanı
    nobet_cols = [c for c in df.columns if "NÖBET" in c and "ERTESİ" not in c]
    ertesi_cols = [c for c in df.columns if "NÖBET ERTESİ" in c]
    pol_ameliyat_cols = [c for c in df.columns if "POL" in c or "AMELİYAT" in c]

    # İstatistikler
    stats = {"nobet": 0, "pol": 0, "ameliyat": 0}

    for idx, row in df.iterrows():
        # Tarih Sütunu (Genelde ilk sütun veya 'Unnamed: 0')
        date_val = row.iloc[0] 
        
        try:
            # Tarih formatı dosyanıza göre değişebilir. 
            # Şu anki dosyada M/D/YY formatı var (12/1/25)
            if isinstance(date_val, str):
                current_date = datetime.strptime(date_val, "%m/%d/%y")
            elif isinstance(date_val, datetime):
                current_date = date_val
            else:
                continue
        except ValueError:
            continue

        # --- 1. KURAL: Nöbet Ertesi Kontrolü ---
        is_ertesi = False
        for col in ertesi_cols:
            val = str(row[col])
            if user_name in val.lower():
                is_ertesi = True
                break
        
        if is_ertesi:
            continue # Ertesi gün boş geçilir

        # --- 2. KURAL: Nöbet ---
        is_nobet = False
        nobet_ekibi = []
        for col in nobet_cols:
            val = str(row[col])
            if val != "nan" and val != "None":
                nobet_ekibi.append(val.strip())
                if user_name in val.lower():
                    is_nobet = True
        
        if is_nobet:
            e = Event()
            e.name = "🚨 Nöbet"
            e.begin = current_date
            e.make_all_day()
            e.description = f"Nöbet Ekibi: {', '.join(nobet_ekibi)}"
            cal.events.add(e)
            stats["nobet"] += 1

        # --- 3. KURAL: Poliklinik ve Ameliyat ---
        # Nöbetçi olsan bile gündüz mesaisi yazılabilir, o yüzden 'elif' değil ayrı 'if'
        for col in pol_ameliyat_cols:
            val = str(row[col])
            if user_name in val.lower():
                e = Event()
                gorev_adi = col
                e.name = f"👨‍⚕️ {gorev_adi}"
                e.description = f"Bulunduğum Birim: {gorev_adi}"
                
                # Saat: 08:00 - 17:00
                e.begin = current_date.replace(hour=8, minute=0)
                e.end = current_date.replace(hour=17, minute=0)
                
                cal.events.add(e)
                
                if "AMELİYAT" in col:
                    stats["ameliyat"] += 1
                else:
                    stats["pol"] += 1

    return cal, stats

# --- ANA AKIŞ ---
if uploaded_file is not None and target_name:
    st.divider()
    st.subheader("2. Önizleme ve İndirme")
    
    try:
        # Dosyayı oku
        if uploaded_file.name.endswith('.csv'):
            # Senin dosyan noktalı virgül kullanıyor
            df = pd.read_csv(uploaded_file, delimiter=";")
        else:
            df = pd.read_excel(uploaded_file)
            
        # Takvimi oluştur
        cal, stats = create_calendar(df, target_name)
        
        if len(cal.events) == 0:
            st.warning(f"⚠️ '{target_name}' ismiyle herhangi bir görev bulunamadı. İsmi doğru yazdığınızdan emin olun.")
        else:
            # Bilgi Kartları
            c1, c2, c3 = st.columns(3)
            c1.metric("Nöbet Sayısı", stats["nobet"])
            c2.metric("Ameliyat Günleri", stats["ameliyat"])
            c3.metric("Poliklinik Günleri", stats["pol"])
            
            # İndirme Butonu
            st.success("✅ Takvim başarıyla oluşturuldu!")
            
            cal_str = str(cal)
            st.download_button(
                label="📥 Takvimi İndir (.ics)",
                data=cal_str,
                file_name=f"{target_name.replace(' ', '_')}_takvim.ics",
                mime="text/calendar"
            )
            
            st.info("İpucu: İndirdiğiniz dosyayı kendinize Mail veya WhatsApp ile gönderip telefondan açın.")
            
    except Exception as e:
        st.error(f"Bir hata oluştu: {e}")
        st.error("Dosyanın formatının uygun olduğundan (Tarih sütunu, noktalı virgül ayrımı vb.) emin olun.")

elif uploaded_file is None:
    st.info("👆 Lütfen önce nöbet listesini (CSV veya Excel) yükleyin.")
elif not target_name:
    st.warning("👆 Lütfen adınızı girin.")
