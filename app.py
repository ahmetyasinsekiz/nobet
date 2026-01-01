import streamlit as st
import pandas as pd
from ics import Calendar, Event

st.set_page_config(page_title="Nöbet Takvimi (Kesin Çözüm)", page_icon="⚡")

st.title("⚡ Akıllı Nöbet Asistanı")
st.markdown("Dosyaları yükle, sadece ismini (veya isminin bir kısmını) yaz. Büyük küçük harf fark etmez.")

# --- 1. DOSYA YÜKLEME ---
col1, col2 = st.columns(2)
with col1:
    asistan_file = st.file_uploader("1. Asistan Listesi", type=["xlsx", "xls", "csv"])
with col2:
    uzman_file = st.file_uploader("2. Uzman Listesi", type=["xlsx", "xls", "csv"])

user_input = st.text_input("Adın Soyadın (Örn: Tahir)", placeholder="İsminin sadece bir kısmını yazman yeterli").strip()

# --- YARDIMCI FONKSİYONLAR ---
def tr_lower(text):
    """Türkçe karakter sorunu olmadan küçük harfe çevirir"""
    text = str(text).replace("İ", "i").replace("I", "ı").replace("Ğ", "ğ").replace("Ü", "ü").replace("Ş", "ş").replace("Ö", "ö").replace("Ç", "ç")
    return text.lower().strip()

def find_col_by_keywords(columns, keywords):
    for col in columns:
        for key in keywords:
            if key in tr_lower(col):
                return col
    return None

def find_expert_columns_by_task(expert_cols, task_name):
    task_clean = tr_lower(task_name)
    found_cols = []
    
    # Kelime haritası
    keywords_map = {
        "ameliyat": ["ameliyat", "masa", "salon", "oda"],
        "poliklinik": ["poliklinik", "pol", "poli"],
        "servis": ["servis", "klinik", "yatak"]
    }
    
    search_terms = [task_clean] 
    for key, terms in keywords_map.items():
        if key in task_clean:
            search_terms = terms
            break

    for col in expert_cols:
        c_low = tr_lower(col)
        if "tarih" in c_low or "nöbet" in c_low or "icap" in c_low: continue
        for term in search_terms:
            if term in c_low:
                found_cols.append(col)
                break
    return found_cols

if asistan_file and user_input:
    if st.button("Takvimi Oluştur"):
        try:
            # Dosyaları Oku
            df_asistan = pd.read_excel(asistan_file) if asistan_file.name.endswith('x') else pd.read_csv(asistan_file)
            # Boş satırları temizle
            df_asistan = df_asistan.dropna(how='all')
            
            # Uzman Dosyası
            df_uzman = pd.DataFrame()
            if uzman_file:
                df_uzman = pd.read_excel(uzman_file) if uzman_file.name.endswith('x') else pd.read_csv(uzman_file)
                df_uzman = df_uzman.dropna(how='all')

            # --- 1. SÜTUNLARI BULMA ---
            cols_a = df_asistan.columns
            # Tarih sütununu bul
            col_date_a = find_col_by_keywords(cols_a, ["tarih", "gün", "date"]) or cols_a[0]
            # Görev sütununu bul
            col_task_a = find_col_by_keywords(cols_a, ["görev", "yer", "durum", "statü"]) 
            # Eğer görev sütunu bulamadıysa, Tarih olmayan ve İsim olmayan bir sütunu almayı dene
            if not col_task_a:
                # Basit mantık: Tarih değilse ve çok uzun metinler varsa görevdir diyebiliriz ama
                # Şimdilik 3. sütunu varsayalım
                if len(cols_a) > 2: col_task_a = cols_a[2]

            # --- 2. İSMİ BULMA (EN KRİTİK KISIM) ---
            # Kullanıcının girdiği ismi güvenli hale getir
            safe_input = tr_lower(user_input)
            
            # Hangi sütunda isim olduğunu anlamak için tüm sütunları tara
            # İçinde kullanıcının isminin geçtiği satırları bul
            my_schedule = pd.DataFrame()
            found_name_col = None

            for col in cols_a:
                # Bu sütun tarih sütunuysa atla
                if col == col_date_a: continue
                
                # Sütunu stringe çevirip küçük harf yap ve ara
                # "Dr. Tahir" içinde "tahir" var mı diye bakar.
                matches = df_asistan[df_asistan[col].apply(lambda x: safe_input in tr_lower(x))]
                
                if not matches.empty:
                    my_schedule = matches
                    found_name_col = col # İsim sütununu bulduk!
                    break # Bulduysak döngüden çık
            
            if my_schedule.empty:
                st.error(f"❌ '{user_input}' ismi dosyada bulunamadı!")
                st.warning("Dosyadaki sütun başlıkları şunlar, lütfen kontrol et:")
                st.write(cols_a.tolist())
                st.warning("Dosyanın ilk 5 satırı şöyle görünüyor (İsminin burada olduğundan emin ol):")
                st.dataframe(df_asistan.head())
            else:
                # --- BULDUK! DEVAM EDİYORUZ ---
                
                # Tarihleri düzelt
                df_asistan[col_date_a] = pd.to_datetime(df_asistan[col_date_a], dayfirst=True, errors='coerce')
                
                if not df_uzman.empty:
                    cols_u = df_uzman.columns
                    col_date_u = find_col_by_keywords(cols_u, ["tarih", "gün", "date"]) or cols_u[0]
                    col_nobet_u = find_col_by_keywords(cols_u, ["nöbet", "icap"])
                    df_uzman[col_date_u] = pd.to_datetime(df_uzman[col_date_u], dayfirst=True, errors='coerce')

                cal = Calendar()
                count = 0

                for index, row in my_schedule.iterrows():
                    current_date = row[col_date_a]
                    if pd.isna(current_date): continue
                    
                    # Görev sütunu bulunduysa al, yoksa "Bilinmeyen Görev" yaz
                    gorev = str(row[col_task_a]).strip() if col_task_a else "Görev Belirtilmedi"
                    
                    event = Event()
                    event.begin = current_date
                    event.make_all_day()
                    
                    baslik = gorev
                    aciklama = f"Görev: {gorev}"

                    # --- UZMAN EŞLEŞTİRME ---
                    if not df_uzman.empty:
                        uzman_row = df_uzman[df_uzman[col_date_u] == current_date]
                        
                        if not uzman_row.empty:
                            uzman_data = uzman_row.iloc[0]
                            
                            # 1. Nöbet
                            if "nöbet" in tr_lower(gorev) and col_nobet_u:
                                hoca = uzman_data[col_nobet_u]
                                if pd.notna(hoca):
                                    baslik += f" ({hoca})"
                                    aciklama += f"\nNöbetçi Hoca: {hoca}"
                            
                            # 2. Masa / Poliklinik (Round Robin)
                            else:
                                expert_cols = find_expert_columns_by_task(df_uzman.columns, gorev)
                                if expert_cols:
                                    aktif_hocalar = [str(uzman_data[c]) for c in expert_cols if pd.notna(uzman_data[c])]
                                    
                                    if aktif_hocalar:
                                        # Sıralama mantığı
                                        gunun_asistanlari = df_asistan[
                                            (df_asistan[col_date_a] == current_date) & 
                                            (df_asistan[col_task_a] == row[col_task_a]) if col_task_a else True
                                        ]
                                        
                                        # İsim listesini al (Daha önce bulduğumuz isim sütunundan)
                                        if found_name_col:
                                            isim_listesi = gunun_asistanlari[found_name_col].apply(lambda x: str(x)).tolist()
                                            
                                            # Benim sıramı bul (Güvenli arama)
                                            my_index = 0
                                            for i, name in enumerate(isim_listesi):
                                                if safe_input in tr_lower(name):
                                                    my_index = i
                                                    break
                                            
                                            # Eşleştir
                                            atanan_hoca = aktif_hocalar[my_index % len(aktif_hocalar)]
                                            baslik += f" - {atanan_hoca}"
                                            aciklama += f"\nEşleşilen Uzman: {atanan_hoca}"

                    event.name = baslik
                    event.description = aciklama
                    cal.events.add(event)
                    count += 1

                st.success(f"✅ {count} görev bulundu!")
                st.download_button(
                    label="📥 Takvimini İndir",
                    data=str(cal),
                    file_name=f"{user_input}_Program.ics",
                    mime="text/calendar"
                )

        except Exception as e:
            st.error("Beklenmedik bir hata oluştu.")
            st.error(f"Hata Detayı: {e}")
