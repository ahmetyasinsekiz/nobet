import streamlit as st
import pandas as pd
from ics import Calendar, Event

st.set_page_config(page_title="Kesin Çözüm: Asistan Takvimi", page_icon="✅")

st.title("✅ Nöbet ve Görev Takvimi (Veri Kaybı Yok)")
st.markdown("""
**Çalışma Mantığı:**
1. Senin listendeki **tüm günleri** ve görevleri çeker (Ameliyat, Poliklinik vb.).
2. Uzman listesine bakar:
   - **Nöbetse:** Nöbetçi hocayı ekler.
   - **Diğer (Pol/Ameliyat):** O günkü hocaları bulur ve sıraya göre (1. asistan 1. hocaya) dağıtır.
3. Eşleşme bulamazsa bile **görevi mutlaka takvime yazar.**
""")

# --- DOSYA YÜKLEME ---
col1, col2 = st.columns(2)
with col1:
    asistan_file = st.file_uploader("1. Asistan Listesi (Excel/CSV)", type=["xlsx", "xls", "csv"])
with col2:
    uzman_file = st.file_uploader("2. Uzman Listesi (Excel/CSV)", type=["xlsx", "xls", "csv"])

user_input = st.text_input("Adın Soyadın (Listede geçtiği gibi)", placeholder="Örn: Tahir").strip()

# --- FONKSİYONLAR ---
def tr_lower(text):
    """Türkçe karakter sorunu olmadan küçültür"""
    return str(text).replace("İ", "i").replace("I", "ı").lower().strip()

def find_col(columns, keywords):
    """Sütun başlığını bulur"""
    for col in columns:
        for key in keywords:
            if key in tr_lower(col):
                return col
    return None

def find_expert_columns(expert_cols, task_name):
    """Görevin ismine (Pol, Ameliyat) göre uzman sütunlarını bulur"""
    task_clean = tr_lower(task_name)
    found_cols = []
    
    # Anahtar kelimeler
    keywords_map = {
        "ameliyat": ["ameliyat", "masa", "salon", "oda", "op"],
        "poliklinik": ["poliklinik", "pol", "poli"],
        "servis": ["servis", "yatak", "klinik"]
    }
    
    search_terms = [task_clean] 
    for key, terms in keywords_map.items():
        if key in task_clean:
            search_terms = terms
            break

    # Uzman dosyasındaki sütunları tara (Tarih ve Nöbet hariç)
    for col in expert_cols:
        c_low = tr_lower(col)
        if "tarih" in c_low or "nöbet" in c_low or "icap" in c_low: continue
        
        for term in search_terms:
            if term in c_low:
                found_cols.append(col)
                break
    return found_cols

# --- ANA KOD ---
if asistan_file and user_input:
    if st.button("Takvimi Oluştur"):
        try:
            # 1. DOSYALARI OKU
            df_asistan = pd.read_excel(asistan_file) if asistan_file.name.endswith('x') else pd.read_csv(asistan_file)
            df_asistan = df_asistan.dropna(how='all')
            
            df_uzman = pd.DataFrame()
            if uzman_file:
                df_uzman = pd.read_excel(uzman_file) if uzman_file.name.endswith('x') else pd.read_csv(uzman_file)
                df_uzman = df_uzman.dropna(how='all')

            # 2. SÜTUNLARI TESPİT ET
            cols_a = df_asistan.columns
            col_date_a = find_col(cols_a, ["tarih", "gün", "date"]) or cols_a[0]
            col_task_a = find_col(cols_a, ["görev", "yer", "durum"]) or (cols_a[2] if len(cols_a)>2 else cols_a[1])

            # İSMİ BULMA (Bütün sütunlarda arar)
            my_schedule = pd.DataFrame()
            found_name_col = None
            safe_input = tr_lower(user_input)

            for col in cols_a:
                if col == col_date_a: continue
                # İçinde ismin geçen satırları bul
                matches = df_asistan[df_asistan[col].astype(str).apply(lambda x: safe_input in tr_lower(x))]
                if not matches.empty:
                    my_schedule = matches
                    found_name_col = col
                    break
            
            if my_schedule.empty:
                st.error(f"❌ '{user_input}' ismi listede bulunamadı. İsmi doğru yazdığından emin ol.")
            else:
                # 3. TAKVİM OLUŞTURMA
                cal = Calendar()
                count = 0
                
                # Tarihleri düzelt
                df_asistan[col_date_a] = pd.to_datetime(df_asistan[col_date_a], dayfirst=True, errors='coerce')
                
                # Uzman tablosu hazırlığı
                col_date_u = None
                if not df_uzman.empty:
                    cols_u = df_uzman.columns
                    col_date_u = find_col(cols_u, ["tarih", "gün", "date"]) or cols_u[0]
                    col_nobet_u = find_col(cols_u, ["nöbet", "icap"])
                    df_uzman[col_date_u] = pd.to_datetime(df_uzman[col_date_u], dayfirst=True, errors='coerce')

                # SATIRLARI DÖN
                for index, row in my_schedule.iterrows():
                    current_date = row[col_date_a]
                    if pd.isna(current_date): continue # Tarih yoksa geç
                    
                    # Görevi al
                    gorev = str(row[col_task_a]).strip()
                    
                    # --- EVENT OLUŞTUR (Hata olsa bile bu oluşacak) ---
                    event = Event()
                    event.begin = current_date
                    event.make_all_day()
                    
                    baslik = gorev
                    aciklama = f"Görev: {gorev}"

                    # --- UZMAN EŞLEŞTİRME KISMI ---
                    if not df_uzman.empty and col_date_u:
                        # O günkü uzman satırını bul
                        uzman_row = df_uzman[df_uzman[col_date_u] == current_date]
                        
                        if not uzman_row.empty:
                            uzman_data = uzman_row.iloc[0]
                            gorev_low = tr_lower(gorev)

                            # A) Nöbetçi Hoca
                            if "nöbet" in gorev_low and col_nobet_u:
                                hoca = uzman_data[col_nobet_u]
                                if pd.notna(hoca):
                                    baslik += f" ({hoca})"
                                    aciklama += f"\nNöbetçi Uzman: {hoca}"
                            
                            # B) Poliklinik / Ameliyat (Sıralı Dağıtım)
                            else:
                                # Göreve uygun sütunları bul (Pol -> Pol1, Pol2...)
                                expert_cols = find_expert_columns(df_uzman.columns, gorev)
                                
                                if expert_cols:
                                    # O gün dolu olan hocaları listele
                                    aktif_hocalar = []
                                    for ec in expert_cols:
                                        h = uzman_data[ec]
                                        if pd.notna(h) and str(h).strip() != "":
                                            aktif_hocalar.append(f"{h} ({ec})") # Hoca Adı (Masa Adı)
                                    
                                    if aktif_hocalar:
                                        # O günkü asistanları bul (Sıramı belirlemek için)
                                        # İsim sütununu kullan
                                        gunun_asistanlari = df_asistan[
                                            (df_asistan[col_date_a] == current_date) & 
                                            (df_asistan[col_task_a] == row[col_task_a])
                                        ]
                                        
                                        # Listeyi al
                                        isim_listesi = gunun_asistanlari[found_name_col].astype(str).tolist()
                                        
                                        # Ben kaçıncıyım?
                                        my_index = 0
                                        for i, nm in enumerate(isim_listesi):
                                            if safe_input in tr_lower(nm):
                                                my_index = i
                                                break
                                        
                                        # Dağıtım: Ben % Hoca Sayısı
                                        atanan_index = my_index % len(aktif_hocalar)
                                        atanan_bilgi = aktif_hocalar[atanan_index]
                                        
                                        baslik += f" - {atanan_bilgi.split('(')[0]}"
                                        aciklama += f"\nEşleşilen Uzman/Masa: {atanan_bilgi}"

                    # --- EN ÖNEMLİ KISIM: Eşleşme olsa da olmasa da EKLE ---
                    event.name = baslik
                    event.description = aciklama
                    cal.events.add(event)
                    count += 1

                st.success(f"✅ Toplam {count} görev bulundu ve takvime işlendi!")
                
                # İndirme Butonu
                file_label = f"{user_input}_Takvim.ics".replace(" ", "_")
                st.download_button(
                    label="📥 Takvimi İndir",
                    data=str(cal),
                    file_name=file_label,
                    mime="text/calendar"
                )

        except Exception as e:
            st.error("Bir hata oluştu. Dosya yapısını kontrol et.")
            st.error(f"Hata Detayı: {e}")
