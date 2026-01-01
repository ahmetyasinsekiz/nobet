import streamlit as st
import pandas as pd
from ics import Calendar, Event

# Sayfa Ayarları
st.set_page_config(page_title="Kişisel Nöbet Takvimi (Manuel Düzeltmeli)", page_icon="🛠️")

st.title("🛠️ Nöbet Programı Oluşturucu")
st.info("Eğer isim listesinde 'Pazartesi, Salı' gibi günler çıkıyorsa, aşağıdan **Sütun Ayarları** kısmını açıp 'Asistan İsmi' sütununu değiştirin.")

# --- 1. DOSYA YÜKLEME ---
col1, col2 = st.columns(2)
with col1:
    asistan_file = st.file_uploader("📂 1. Asistan Listesi", type=["xlsx", "xls", "csv"])
with col2:
    uzman_file = st.file_uploader("📂 2. Uzman Listesi", type=["xlsx", "xls", "csv"])

# --- YARDIMCI FONKSİYONLAR ---
def clean_df(df):
    """Boşlukları temizle"""
    df = df.dropna(how='all')
    df.columns = df.columns.astype(str).str.strip()
    return df

def find_col(columns, keywords, fallback_index=0):
    """Sütun bulamazsa varsayılan indexi döndür"""
    for col in columns:
        for key in keywords:
            if key in col.lower():
                return col
    # Bulamazsa ve index geçerliyse onu döndür
    if 0 <= fallback_index < len(columns):
        return columns[fallback_index]
    return columns[0]

def get_matching_expert_columns(expert_cols, task_name):
    """Görevin ismine göre uzman sütunlarını bulur"""
    task_lower = str(task_name).lower()
    found_cols = []
    
    keywords_map = {
        "ameliyat": ["ameliyat", "masa", "salon", "oda", "operasyon"],
        "poliklinik": ["poliklinik", "pol", "poli"],
        "servis": ["servis", "yatak", "klinik"],
        "lab": ["laboratuvar", "lab"]
    }
    
    search_terms = []
    for key, terms in keywords_map.items():
        if key in task_lower:
            search_terms = terms
            break
            
    if not search_terms:
        search_terms = [task_lower]

    for col in expert_cols:
        c_low = col.lower()
        if "tarih" in c_low or "nöbet" in c_low or "icap" in c_low:
            continue
        for term in search_terms:
            if term in c_low:
                found_cols.append(col)
                break     
    return found_cols

# --- ANA İŞLEM ---
if asistan_file and uzman_file:
    try:
        # Dosyaları Oku
        df_asistan = pd.read_excel(asistan_file) if asistan_file.name.endswith('x') else pd.read_csv(asistan_file)
        df_uzman = pd.read_excel(uzman_file) if uzman_file.name.endswith('x') else pd.read_csv(uzman_file)

        df_asistan = clean_df(df_asistan)
        df_uzman = clean_df(df_uzman)

        # --- SÜTUNLARI BELİRLEME (KULLANICI SEÇİMİ) ---
        st.write("---")
        st.subheader("⚙️ Sütun Ayarları (Otomatik Tanılandı, Kontrol Et)")
        
        c1, c2, c3 = st.columns(3)
        
        # Otomatik tahminler
        cols_a = df_asistan.columns.tolist()
        cols_u = df_uzman.columns.tolist()

        # Asistan Tablosu Tahminleri
        # İsim genelde 2. veya 3. sütundadır (Index 1 veya 2).
        # Gün sütunu (Index 1) ile karışmaması için varsayılanı değiştirebilirsiniz.
        guess_date_a = find_col(cols_a, ["tarih", "gün", "date"], 0)
        guess_name_a = find_col(cols_a, ["ad", "soyad", "isim", "asistan", "personel"], 2) # Varsayılan 3. sütun
        guess_task_a = find_col(cols_a, ["görev", "yer", "durum"], 3) # Varsayılan 4. sütun

        # Uzman Tablosu Tahminleri
        guess_date_u = find_col(cols_u, ["tarih", "gün", "date"], 0)
        guess_nobet_u = find_col(cols_u, ["nöbet", "icap"], -1) # Bulamazsa seçme

        # KULLANICIYA SEÇTİRME
        with c1:
            col_date_a = st.selectbox("Asistan Dosyası - Tarih", cols_a, index=cols_a.index(guess_date_a))
            col_date_u = st.selectbox("Uzman Dosyası - Tarih", cols_u, index=cols_u.index(guess_date_u))
        
        with c2:
            # İşte burası sorunu çözecek olan yer:
            col_name_a = st.selectbox("Asistan Dosyası - İsim", cols_a, index=cols_a.index(guess_name_a))
            col_nobet_u = st.selectbox("Uzman Dosyası - Nöbetçi", cols_u, index=cols_u.index(guess_nobet_u) if guess_nobet_u in cols_u else 0)

        with c3:
            col_task_a = st.selectbox("Asistan Dosyası - Görev", cols_a, index=cols_a.index(guess_task_a))

        # --- İSİM LİSTESİNİ GÜNCELLE ---
        # Seçilen sütuna göre isimleri tekrar çekiyoruz
        isim_listesi = sorted([str(x) for x in df_asistan[col_name_a].dropna().unique().tolist()])
        
        st.write("---")
        target_person = st.selectbox(
            "👤 **Kendi Adınızı Seçiniz:**", 
            isim_listesi,
            index=None,
            placeholder="Listeden adınızı bulun..."
        )

        if st.button("📅 Takvimi Oluştur"):
            if not target_person:
                st.warning("Lütfen bir isim seçin!")
            else:
                cal = Calendar()
                
                # Tarih Formatla
                df_asistan[col_date_a] = pd.to_datetime(df_asistan[col_date_a], dayfirst=True, errors='coerce')
                df_uzman[col_date_u] = pd.to_datetime(df_uzman[col_date_u], dayfirst=True, errors='coerce')

                # Kişiyi filtrele
                my_schedule = df_asistan[df_asistan[col_name_a].astype(str) == str(target_person)]
                
                count = 0
                for index, row in my_schedule.iterrows():
                    current_date = row[col_date_a]
                    if pd.isna(current_date): continue
                    
                    gorev = str(row[col_task_a]).strip()
                    gorev_lower = gorev.lower()

                    event = Event()
                    event.begin = current_date
                    event.make_all_day()
                    
                    baslik = gorev
                    aciklama = f"Görev: {gorev}"

                    # Uzman Eşleştirme
                    uzman_row = df_uzman[df_uzman[col_date_u] == current_date]

                    if not uzman_row.empty:
                        uzman_data = uzman_row.iloc[0]

                        # A) Nöbet
                        if "nöbet" in gorev_lower and col_nobet_u:
                            hoca = uzman_data[col_nobet_u]
                            if pd.notna(hoca):
                                baslik += f" ({hoca})"
                                aciklama += f"\nNöbetçi Uzman: {hoca}"

                        # B) Diğer Görevler
                        else:
                            ilgili_sutunlar = get_matching_expert_columns(cols_u, gorev)
                            if ilgili_sutunlar:
                                aktif_hocalar = []
                                for col in ilgili_sutunlar:
                                    h_isim = uzman_data[col]
                                    if pd.notna(h_isim) and str(h_isim).strip() != "":
                                        aktif_hocalar.append(f"{h_isim}")
                                
                                if aktif_hocalar:
                                    # Sıralama mantığı
                                    gunun_asistanlari = df_asistan[
                                        (df_asistan[col_date_a] == current_date) & 
                                        (df_asistan[col_task_a] == row[col_task_a])
                                    ]
                                    asistan_listesi_gunluk = [str(x) for x in gunun_asistanlari[col_name_a].tolist()]

                                    try:
                                        my_index = asistan_listesi_gunluk.index(str(target_person))
                                        atanan_index = my_index % len(aktif_hocalar)
                                        atanan_hoca = aktif_hocalar[atanan_index]
                                        
                                        baslik += f" - {atanan_hoca}"
                                        aciklama += f"\nEşleşme: {atanan_hoca}"
                                    except ValueError:
                                        pass

                    event.name = baslik
                    event.description = aciklama
                    cal.events.add(event)
                    count += 1

                if count > 0:
                    st.success(f"✅ {target_person} için {count} görev bulundu!")
                    file_name_str = f"{str(target_person).replace(' ', '_')}_Program.ics"
                    st.download_button(
                        label="📥 İNDİR",
                        data=str(cal),
                        file_name=file_name_str,
                        mime="text/calendar"
                    )
                else:
                    st.warning("Bu kişi için uygun tarih/görev bulunamadı.")

    except Exception as e:
        st.error(f"Hata oluştu: {e}")

else:
    st.info("Lütfen dosyaları yükleyin.")
