import streamlit as st
import pandas as pd
from ics import Calendar, Event
from datetime import datetime

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Döngüsel Nöbet Takvimi", page_icon="🔄")

st.title("🔄 Asistan Takvimi (Sıralı Dağıtım Modu)")
st.markdown("""
**Bu versiyonda "Başa Dönme" özelliği vardır:**
Eğer siz **Ameliyat 5**'teyseniz ama Uzman dosyasında sadece **2 tane** ameliyat sütunu varsa;
Sistem 1-2-1-2-1 şeklinde sayar ve sizi **1. sütundaki** uzmanla eşleştirir.
""")

# --- KULLANICI GİRİŞ ALANI ---
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        target_name = st.text_input("Adınız Soyadınız", placeholder="Örn: Mehmet Tahir")
    with col2:
        asistan_file = st.file_uploader("1. Asistan Listesi", type=["csv", "xlsx"])
        uzman_file = st.file_uploader("2. Uzman Listesi", type=["csv", "xlsx"])

# --- YARDIMCI: DÖNGÜSEL (MODULO) EŞLEŞTİRME ---
def get_uzman_with_modulo(df_uzman, current_date, keywords, asistan_sira_index):
    """
    Uzman dosyasındaki sütun sayısı yetersizse başa döner (Modulo işlemi).
    """
    if df_uzman is None or df_uzman.empty:
        return None

    # 1. Tarihi Bul
    date_col = df_uzman.columns[0] 
    # Tarih eşleştirmesi (String ve Datetime kontrolü)
    row = df_uzman[df_uzman[date_col].astype(str).str.contains(current_date.strftime("%Y-%m-%d"), na=False)]
    if row.empty:
        row = df_uzman[df_uzman[date_col].astype(str).str.contains(current_date.strftime("%d.%m.%Y"), na=False)]
    
    if row.empty:
        return None
    
    row = row.iloc[0]

    # 2. İlgili Sütunları Bul (Örn: İçinde 'AMELİYAT' geçen tüm sütunlar)
    candidate_cols = []
    for col in df_uzman.columns:
        c_upper = str(col).upper()
        # Tarih ve Nöbet sütunlarını hariç tut, sadece görev sütunlarını al
        if any(k in c_upper for k in keywords) and "TARİH" not in c_upper and "NÖBET" not in c_upper:
            candidate_cols.append(col)
    
    # Sütunları soldan sağa sırasını garantiye alalım (Excel'deki sırayla)
    # (Pandas zaten okurken sırayı korur ama biz yine de listeye çevirdik)
    
    total_expert_cols = len(candidate_cols)
    
    if total_expert_cols == 0:
        return None

    # --- 3. KRİTİK NOKTA: MODULO İŞLEMİ ---
    # Asistanın sırası (index) uzman sütun sayısından büyükse başa sar.
    # Örn: Asistan Index 2 (Yani 3. ameliyat), Uzman Sütun Sayısı 2.
    # 2 % 2 = 0 -> Yani 1. Uzman Sütunu (Index 0)
    
    target_index = asistan_sira_index % total_expert_cols
    target_col_name = candidate_cols[target_index]
    
    hoca_ismi = row[target_col_name]
    
    if pd.isna(hoca_ismi) or str(hoca_ismi).strip() == "":
        return None
        
    return f"{str(hoca_ismi).strip()} ({target_col_name})"

# --- ANA İŞLEM FONKSİYONU ---
def create_calendar(df_asistan, df_uzman, user_name):
    cal = Calendar()
    user_name = user_name.lower().strip()
    
    # Başlıkları temizle
    df_asistan.columns = [str(c).strip().upper() for c in df_asistan.columns]
    if df_uzman is not None:
        df_uzman.columns = [str(c).strip() for c in df_uzman.columns]

    # Asistan Sütun Grupları
    # Sütunları sıralı bir şekilde tespit ediyoruz ki index alabilesin.
    nobet_cols = [c for c in df_asistan.columns if "NÖBET" in c and "ERTESİ" not in c]
    # Ameliyat 1, Ameliyat 2... diye gidenleri sırasıyla bulur
    ameliyat_cols = sorted([c for c in df_asistan.columns if "AMELİYAT" in c or "MASA" in c])
    # Poliklinik 1, Poliklinik 2...
    pol_cols = sorted([c for c in df_asistan.columns if "POL" in c])
    
    tum_gorevler = ameliyat_cols + pol_cols

    count = 0

    for idx, row in df_asistan.iterrows():
        # Tarih Okuma
        date_val = row.iloc[0]
        try:
            if isinstance(date_val, str):
                for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%m/%d/%y", "%d-%m-%Y"):
                    try:
                        current_date = datetime.strptime(date_val, fmt)
                        break
                    except ValueError: continue
                else: continue
            elif isinstance(date_val, datetime):
                current_date = date_val
            else: continue
        except: continue

        # --- A) NÖBET KONTROLÜ (Düz Mantık) ---
        is_nobet = False
        nobet_ekibi = []
        for col in nobet_cols:
            val = str(row[col])
            if user_name in val.lower():
                is_nobet = True
            if val != "nan": nobet_ekibi.append(val)
            
        if is_nobet:
            e = Event()
            e.name = "🚨 Nöbet"
            e.begin = current_date
            e.make_all_day()
            desc = f"Ekip: {', '.join(nobet_ekibi)}"
            
            # Nöbetçi hocayı bul (Genelde tek sütun olur, modulo gerekmez ama yine de bakarız)
            if df_uzman is not None:
                # Nöbet kelimesi geçen sütunu bul
                nobet_hoca_col = [c for c in df_uzman.columns if "NÖBET" in str(c).upper() and "ERTESİ" not in str(c).upper()]
                if nobet_hoca_col:
                    # Tarih eşleşmesi yap
                    d_col = df_uzman.columns[0]
                    u_row = df_uzman[df_uzman[d_col].astype(str).str.contains(current_date.strftime("%Y-%m-%d"), na=False)]
                    if not u_row.empty:
                        hoca = u_row.iloc[0][nobet_hoca_col[0]]
                        if pd.notna(hoca):
                            e.name += f" ({hoca})"
                            desc += f"\nNöbetçi Uzman: {hoca}"
            
            e.description = desc
            cal.events.add(e)
            count += 1

        # --- B) AMELİYAT VE POLİKLİNİK (MODULO MANTIKLI) ---
        for col in tum_gorevler:
            val = str(row[col])
            if user_name in val.lower():
                e = Event()
                e.name = f"👨‍⚕️ {col}"
                e.begin = current_date.replace(hour=8, minute=0)
                e.end = current_date.replace(hour=17, minute=0)
                e.description = f"Görev Yeri: {col}"
                
                hoca_bilgisi = None
                
                # 1. Eğer görev AMELİYAT ise
                if col in ameliyat_cols:
                    # Asistan dosyasında kaçıncı sıradaki sütun? (0, 1, 2...)
                    my_index = ameliyat_cols.index(col)
                    # Modulo ile uzmanı bul
                    hoca_bilgisi = get_uzman_with_modulo(df_uzman, current_date, ["AMELİYAT", "MASA", "SALON"], my_index)

                # 2. Eğer görev POLİKLİNİK ise
                elif col in pol_cols:
                    my_index = pol_cols.index(col)
                    hoca_bilgisi = get_uzman_with_modulo(df_uzman, current_date, ["POL"], my_index)
                
                if hoca_bilgisi:
                    # Parantez içindeki sütun adını temizleyip sadece ismi alalım
                    hoca_adi = hoca_bilgisi.split("(")[0].strip()
                    e.name += f" - {hoca_adi}"
                    e.description += f"\n\nSorumlu Uzman: {hoca_bilgisi}"
                
                cal.events.add(e)
                count += 1

    return cal, count

# --- ÇALIŞTIRMA ---
if asistan_file and target_name:
    st.divider()
    try:
        # Asistan Oku
        if asistan_file.name.endswith('.csv'):
            df_a = pd.read_csv(asistan_file, delimiter=";")
        else:
            df_a = pd.read_excel(asistan_file)
            
        # Uzman Oku
        df_u = None
        if uzman_file:
            if uzman_file.name.endswith('.csv'):
                try: df_u = pd.read_csv(uzman_file, delimiter=";")
                except: df_u = pd.read_csv(uzman_file, delimiter=",")
            else:
                df_u = pd.read_excel(uzman_file)
            
            # Uzman tarihi datetime yap
            if df_u is not None:
                d_col = df_u.columns[0]
                df_u[d_col] = pd.to_datetime(df_u[d_col], dayfirst=True, errors='coerce')

        cal, event_count = create_calendar(df_a, df_u, target_name)
        
        if event_count > 0:
            st.success(f"✅ {event_count} görev başarıyla oluşturuldu!")
            st.download_button(
                label="📥 Takvimi İndir (.ics)",
                data=str(cal),
                file_name=f"{target_name}_Dongusel_Takvim.ics",
                mime="text/calendar"
            )
        else:
            st.warning("İsminizle eşleşen görev bulunamadı.")

    except Exception as e:
        st.error(f"Hata: {e}")
