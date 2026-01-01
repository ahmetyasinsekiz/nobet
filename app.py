import streamlit as st
import pandas as pd
from ics import Calendar, Event
import io

# Sayfa Ayarları
st.set_page_config(page_title="Kişisel Nöbet Takvimi Oluşturucu", page_icon="📅")

st.title("📅 Kişisel Nöbet & Ameliyat Programı")
st.markdown("""
Bu araç ile kendi ismine özel takvim dosyanı oluşturabilirsin.
1. **Asistan** ve **Uzman** listelerini yükle.
2. Aşağıda açılacak kutudan **kendi adını seç**.
3. **"Takvimimi İndir"** butonuna bas.
""")

# --- 1. DOSYA YÜKLEME ---
col1, col2 = st.columns(2)
with col1:
    asistan_file = st.file_uploader("📂 1. Asistan Listesi (Senin Listen)", type=["xlsx", "xls", "csv"])
with col2:
    uzman_file = st.file_uploader("📂 2. Uzman Listesi (Hocaların Listesi)", type=["xlsx", "xls", "csv"])

# --- YARDIMCI FONKSİYONLAR ---
def clean_df(df):
    """Boşlukları ve gereksiz satırları temizler"""
    df = df.dropna(how='all')
    df.columns = df.columns.astype(str).str.strip()
    return df

def find_col(columns, keywords):
    """Sütun başlığını akıllı tahmin eder"""
    for col in columns:
        for key in keywords:
            if key in col.lower():
                return col
    return None

def get_matching_expert_columns(expert_cols, task_name):
    """Görevin ismine göre (Poliklinik, Ameliyat vb.) uzman tablosundaki sütunları bulur"""
    task_lower = str(task_name).lower()
    found_cols = []
    
    # Eşleşme Anahtarları
    keywords_map = {
        "ameliyat": ["ameliyat", "masa", "salon", "oda", "operasyon"],
        "poliklinik": ["poliklinik", "pol", "poli"],
        "servis": ["servis", "yatak", "klinik"],
        "lab": ["laboratuvar", "lab"]
    }
    
    search_terms = []
    # Görev ismi haritada var mı?
    for key, terms in keywords_map.items():
        if key in task_lower:
            search_terms = terms
            break
    
    # Yoksa görevin kendisini ara
    if not search_terms:
        search_terms = [task_lower]

    # Sütunları tara
    for col in expert_cols:
        c_low = col.lower()
        # Tarih ve Nöbet sütunlarını karıştırma
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

        # --- SÜTUNLARI OTOMATİK TANI ---
        cols_a = df_asistan.columns
        cols_u = df_uzman.columns

        # Asistan Tablosu
        col_date_a = find_col(cols_a, ["tarih", "gün", "date"]) or cols_a[0]
        col_name_a = find_col(cols_a, ["ad", "soyad", "isim", "asistan", "personel"]) or cols_a[1]
        col_task_a = find_col(cols_a, ["görev", "yer", "durum"]) or cols_a[2]

        # Uzman Tablosu
        col_date_u = find_col(cols_u, ["tarih", "gün", "date"]) or cols_u[0]
        col_nobet_u = find_col(cols_u, ["nöbet", "icap"])

        # Tarihleri Formatla
        df_asistan[col_date_a] = pd.to_datetime(df_asistan[col_date_a], dayfirst=True, errors='coerce')
        df_uzman[col_date_u] = pd.to_datetime(df_uzman[col_date_u], dayfirst=True, errors='coerce')

        st.success("✅ Dosyalar başarıyla işlendi! Şimdi ismini seç.")
        st.divider()

        # --- 2. İSİM SEÇME ALANI (Burayı netleştirdik) ---
        # Listeden benzersiz isimleri alıp sıralıyoruz
        isim_listesi = sorted(df_asistan[col_name_a].dropna().unique().tolist())
        
        target_person = st.selectbox(
            "👤 Lütfen Kendi Adınızı Seçiniz:", 
            isim_listesi,
            index=None,
            placeholder="İsim seçin..."
        )

        if target_person:
            # --- TAKVİM OLUŞTURMA MANTIĞI ---
            cal = Calendar()
            
            # Sadece seçilen kişinin programını filtrele
            my_schedule = df_asistan[df_asistan[col_name_a] == target_person]
            
            count = 0
            detail_log = [] # Ekrana ne yaptığımızı yazmak için

            for index, row in my_schedule.iterrows():
                current_date = row[col_date_a]
                if pd.isna(current_date): continue
                
                gorev = str(row[col_task_a]).strip()
                gorev_lower = gorev.lower()

                # Event oluştur
                event = Event()
                event.begin = current_date
                event.make_all_day()
                
                baslik = gorev
                aciklama = f"Görev: {gorev}"

                # Uzman tablosundan o günü bul
                uzman_row = df_uzman[df_uzman[col_date_u] == current_date]

                if not uzman_row.empty:
                    uzman_data = uzman_row.iloc[0]

                    # A) Nöbetçi Eşleşmesi
                    if "nöbet" in gorev_lower and col_nobet_u:
                        hoca = uzman_data[col_nobet_u]
                        if pd.notna(hoca):
                            baslik += f" ({hoca})"
                            aciklama += f"\nNöbetçi Uzman: {hoca}"

                    # B) Masa / Poliklinik Eşleşmesi (Round Robin)
                    else:
                        ilgili_sutunlar = get_matching_expert_columns(cols_u, gorev)
                        
                        if ilgili_sutunlar:
                            # O gün dolu olan hocaları bul
                            aktif_hocalar = []
                            for col in ilgili_sutunlar:
                                h_isim = uzman_data[col]
                                if pd.notna(h_isim) and str(h_isim).strip() != "":
                                    # Sütun adını temizle (Ameliyat.1 -> Ameliyat 2 gibi gösterebiliriz ama basit kalsın)
                                    aktif_hocalar.append(f"{h_isim}") 
                            
                            if aktif_hocalar:
                                # O gün o görevdeki tüm asistanları bul (Sıralama için)
                                gunun_asistanlari = df_asistan[
                                    (df_asistan[col_date_a] == current_date) & 
                                    (df_asistan[col_task_a] == row[col_task_a])
                                ]
                                asistan_listesi_gunluk = gunun_asistanlari[col_name_a].tolist()

                                try:
                                    # Benim sıram kaç?
                                    my_index = asistan_listesi_gunluk.index(target_person)
                                    
                                    # Eşleştirme Matematiği
                                    atanan_index = my_index % len(aktif_hocalar)
                                    atanan_hoca = aktif_hocalar[atanan_index]
                                    
                                    baslik += f" - {atanan_hoca}"
                                    aciklama += f"\nEşleşilen Uzman: {atanan_hoca}\n(Sıra: {my_index+1}, Masa/Oda: {atanan_index+1})"
                                    
                                except ValueError:
                                    pass # Listede garip bir şekilde yoksam (nadiren olur)

                event.name = baslik
                event.description = aciklama
                cal.events.add(event)
                count += 1

            # --- SONUÇ VE İNDİRME ---
            st.success(f"🎉 **{target_person}** için {count} adet görev bulundu ve takvime işlendi.")
            
            # Dosya İndirme Butonu
            file_name_str = f"{target_person.replace(' ', '_')}_Nobet_Programi.ics"
            st.download_button(
                label=f"📥 {target_person} - Takvimini İndir",
                data=str(cal),
                file_name=file_name_str,
                mime="text/calendar"
            )

    except Exception as e:
        st.error("Bir hata oluştu. Lütfen dosya formatlarını kontrol et.")
        st.error(f"Teknik Hata: {e}")

else:
    st.info("👆 Lütfen önce Asistan ve Uzman listelerini yukarıdan yükleyiniz.")
