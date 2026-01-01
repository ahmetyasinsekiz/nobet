import streamlit as st
import pandas as pd
from ics import Calendar, Event

st.set_page_config(page_title="Tüm Görevler Dağıtıcı", page_icon="🏥")

st.title("🏥 Tam Kapsamlı Akıllı Dağıtıcı")
st.markdown("""
Bu versiyon şunları yapar:
1.  **Nöbet:** 'Nöbet' yazanları nöbetçi hocayla eşler.
2.  **Ameliyat:** Görevi 'Ameliyat' olanları 'Masa/Salon' sütunlarına dağıtır.
3.  **Poliklinik:** Görevi 'Poliklinik' olanları 'Poliklinik' sütunlarına dağıtır.
4.  **Diğer:** Görev ismiyle eşleşen herhangi bir uzman sütunu varsa oraya dağıtır.
""")

col1, col2 = st.columns(2)
with col1:
    asistan_file = st.file_uploader("Asistan Listesi", type=["xlsx", "xls", "csv"], key="asistan")
with col2:
    uzman_file = st.file_uploader("Uzman Listesi (Sütun Bazlı)", type=["xlsx", "xls", "csv"], key="uzman")

def clean_df(df):
    df = df.dropna(how='all')
    df.columns = df.columns.astype(str).str.strip()
    return df

def find_col(columns, keywords):
    for col in columns:
        for key in keywords:
            if key in col.lower():
                return col
    return None

def get_matching_expert_columns(expert_cols, task_name):
    """
    Asistanın görev ismine göre Uzman dosyasındaki ilgili sütunları bulur.
    Örn: Görev 'Poliklinik' ise -> İçinde 'Pol' geçen sütunları getirir.
    """
    task_lower = task_name.lower()
    found_cols = []
    
    # Eşleştirme Kuralları (Genişletilebilir)
    keywords_map = {
        "ameliyat": ["ameliyat", "masa", "salon", "oda", "operasyon"],
        "poliklinik": ["poliklinik", "pol", "poli"],
        "servis": ["servis", "yatak", "klinik"],
        "lab": ["laboratuvar", "lab"]
    }
    
    # 1. Önce tanımlı kurallara bak
    search_terms = []
    for key, terms in keywords_map.items():
        if key in task_lower:
            search_terms = terms
            break
            
    # 2. Eğer tanımlı kural yoksa, görev isminin kendisini ara
    if not search_terms:
        search_terms = [task_lower]

    # Sütunları tara (Tarih ve Nöbet hariç)
    for col in expert_cols:
        c_low = col.lower()
        if "tarih" in c_low or "nöbet" in c_low or "icap" in c_low:
            continue
            
        for term in search_terms:
            if term in c_low:
                found_cols.append(col)
                break
                
    return found_cols

if asistan_file and uzman_file:
    try:
        df_asistan = pd.read_excel(asistan_file) if asistan_file.name.endswith('x') else pd.read_csv(asistan_file)
        df_uzman = pd.read_excel(uzman_file) if uzman_file.name.endswith('x') else pd.read_csv(uzman_file)

        df_asistan = clean_df(df_asistan)
        df_uzman = clean_df(df_uzman)

        # --- Temel Sütunları Bul ---
        cols_a = df_asistan.columns
        cols_u = df_uzman.columns

        col_date_a = find_col(cols_a, ["tarih", "gün", "date"]) or cols_a[0]
        col_name_a = find_col(cols_a, ["ad", "soyad", "isim", "asistan"]) or cols_a[1]
        col_task_a = find_col(cols_a, ["görev", "yer", "durum"]) or cols_a[2]

        col_date_u = find_col(cols_u, ["tarih", "gün", "date"]) or cols_u[0]
        col_nobet_u = find_col(cols_u, ["nöbet", "icap"])

        target_person = st.selectbox("Kimin Programı?", df_asistan[col_name_a].dropna().unique())

        if st.button("🚀 Akıllı Takvimi Oluştur"):
            cal = Calendar()
            
            # Tarih formatlama
            df_asistan[col_date_a] = pd.to_datetime(df_asistan[col_date_a], dayfirst=True, errors='coerce')
            df_uzman[col_date_u] = pd.to_datetime(df_uzman[col_date_u], dayfirst=True, errors='coerce')

            my_schedule = df_asistan[df_asistan[col_name_a] == target_person]
            
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

                # Uzman satırını bul
                uzman_row = df_uzman[df_uzman[col_date_u] == current_date]

                if not uzman_row.empty:
                    uzman_data = uzman_row.iloc[0]

                    # --- A) NÖBET KONTROLÜ ---
                    if "nöbet" in gorev_lower and col_nobet_u:
                        hoca = uzman_data[col_nobet_u]
                        if pd.notna(hoca):
                            baslik += f" ({hoca})"
                            aciklama += f"\nNöbetçi Uzman: {hoca}"

                    # --- B) DİNAMİK GÖREV EŞLEŞTİRME (Poliklinik, Ameliyat vb.) ---
                    else:
                        # Görev ismine göre uygun uzman sütunlarını bul
                        # Örn: Görev="Poliklinik" ise UzmanDosyası="Pol 1", "Pol 2" sütunlarını bulur.
                        ilgili_sutunlar = get_matching_expert_columns(cols_u, gorev)
                        
                        if ilgili_sutunlar:
                            # O sütunlardaki hocaları topla
                            aktif_hocalar = []
                            for col in ilgili_sutunlar:
                                h_isim = uzman_data[col]
                                if pd.notna(h_isim) and str(h_isim).strip() != "":
                                    aktif_hocalar.append(f"{col}: {h_isim}") # "Pol 1: Dr. X" formatında sakla
                            
                            if aktif_hocalar:
                                # Sıralama Mantığı (Round Robin)
                                gunun_asistanlari = df_asistan[
                                    (df_asistan[col_date_a] == current_date) & 
                                    (df_asistan[col_task_a] == row[col_task_a])
                                ]
                                asistan_listesi = gunun_asistanlari[col_name_a].tolist()

                                try:
                                    my_index = asistan_listesi.index(target_person)
                                    
                                    # Mod alarak eşleştir
                                    atanan_index = my_index % len(aktif_hocalar)
                                    atanan_bilgi = aktif_hocalar[atanan_index] # Örn: "Pol 1: Dr. Ahmet"
                                    
                                    # Başlığa ve Açıklamaya ekle
                                    col_name, hoca_name = atanan_bilgi.split(":", 1)
                                    baslik += f" - {hoca_name.strip()}"
                                    aciklama += f"\nEşleşme: {atanan_bilgi}"
                                    
                                except ValueError:
                                    pass

                event.name = baslik
                event.description = aciklama
                cal.events.add(event)
                count += 1

            st.success(f"{count} görev işlendi.")
            st.download_button(label="📥 İndir", data=str(cal), file_name="Takvim.ics", mime="text/calendar")

    except Exception as e:
        st.error(f"Hata: {e}")
else:
    st.info("Dosyaları yükleyin.")
