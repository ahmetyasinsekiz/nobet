import streamlit as st
import pandas as pd
from ics import Calendar, Event
from datetime import datetime

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Nöbet Takvimi", page_icon="📅")

# --- BAŞLIK VE AÇIKLAMA (YENİLENDİ) ---
st.title("📅 Asistan Nöbet & İş Takvimi")

st.markdown("""
Bu araç, Excel formatındaki çalışma listenizi saniyeler içinde **telefonunuzun takvimine** aktarmanızı sağlar.
Asistan listesi ile Uzman listesini eşleştirerek, ameliyat ve poliklinik günlerinizde hangi hocayla çalıştığınızı da otomatik ekler.
""")

with st.expander("❓ Oluşan Takvimi Telefonuma Nasıl Eklerim?", expanded=True):
    st.markdown("""
    1. Aşağıdaki **"İndir"** butonuna basıp dosyayı bilgisayara/telefona kaydedin.
    2. Dosyayı kendinize **WhatsApp** veya **E-posta** yoluyla gönderin.
    3. Telefonunuzdan dosyayı açın.
    4. Çıkan ekranda **"Tümünü Ekle"** (Add All) diyerek onaylayın.
    """)

st.divider()

# --- KULLANICI GİRİŞ ALANI ---
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        target_name = st.text_input("Adınız Soyadınız", placeholder="Örn: Mehmet Tahir").strip()
        st.caption("Listede adınız nasıl geçiyorsa öyle yazın.")
    with col2:
        asistan_file = st.file_uploader("1. Asistan Listesi (Excel/CSV)", type=["csv", "xlsx"])
        uzman_file = st.file_uploader("2. Uzman Listesi (Excel/CSV)", type=["csv", "xlsx"])

# --- YARDIMCI FONKSİYONLAR (MANTIK AYNI KALDI) ---
def clean_col_name(col):
    return str(col).strip().upper()

def get_active_surgery_experts(df_uzman, current_date):
    """
    O günkü 'AMELİYAT' sütunlarındaki hocaları soldan sağa sırayla getirir.
    DİKKAT: İçinde POL, PROTEZ, CERRAHİ geçenleri ALMAZ. Sadece 'AMELİYAT' odaklıdır.
    """
    if df_uzman is None or df_uzman.empty:
        return []

    # Tarih Satırını Bul
    date_col = df_uzman.columns[0]
    row = df_uzman[df_uzman[date_col].astype(str).str.contains(current_date.strftime("%Y-%m-%d"), na=False)]
    if row.empty:
        row = df_uzman[df_uzman[date_col].astype(str).str.contains(current_date.strftime("%d.%m.%Y"), na=False)]
    
    if row.empty: return []
    row = row.iloc[0]

    active_experts = []
    # Sadece içinde "AMELİYAT" geçen ama "POL" geçmeyen sütunları bul
    surgery_cols = [c for c in df_uzman.columns if "AMELİYAT" in str(c).upper() and "POL" not in str(c).upper()]
    
    for col in surgery_cols:
        hoca_ismi = row[col]
        if pd.notna(hoca_ismi) and str(hoca_ismi).strip() not in ["nan", "", "-"]:
            active_experts.append(str(hoca_ismi).strip())
            
    return active_experts

def get_pol_expert(df_uzman, current_date, pol_index):
    """Poliklinik eşleşmesi"""
    if df_uzman is None or df_uzman.empty: return None

    date_col = df_uzman.columns[0]
    row = df_uzman[df_uzman[date_col].astype(str).str.contains(current_date.strftime("%Y-%m-%d"), na=False)]
    if row.empty:
        row = df_uzman[df_uzman[date_col].astype(str).str.contains(current_date.strftime("%d.%m.%Y"), na=False)]
    if row.empty: return None
    row = row.iloc[0]

    pol_cols = [c for c in df_uzman.columns if "POL" in str(c).upper()]
    
    if len(pol_cols) > pol_index:
        col_name = pol_cols[pol_index]
        val = row[col_name]
        if pd.notna(val): return f"{val} ({col_name})"
    return None

# --- ANA İŞLEM ---
def create_calendar(df_asistan, df_uzman, user_name):
    cal = Calendar()
    user_name = user_name.lower().strip()
    
    # Sütunları temizle
    df_asistan.columns = [clean_col_name(c) for c in df_asistan.columns]
    if df_uzman is not None:
        df_uzman.columns = [clean_col_name(c) for c in df_uzman.columns]

    # Asistan Sütunlarını Grupla
    nobet_cols = [c for c in df_asistan.columns if "NÖBET" in c and "ERTESİ" not in c]
    acil_cols = [c for c in df_asistan.columns if "ACİL" in c]
    ameliyat_cols = sorted([c for c in df_asistan.columns if "AMELİYAT" in c and "SURTIME" not in c]) 
    pol_cols = sorted([c for c in df_asistan.columns if "POL" in c])
    
    tum_gorevler = ameliyat_cols + pol_cols + acil_cols
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

        # --- A) NÖBET ---
        is_nobet = False
        nobet_ekibi = []
        for col in nobet_cols:
            val = str(row[col])
            if user_name in val.lower():
                is_nobet = True
            if val != "nan" and val != "None": nobet_ekibi.append(val)
            
        if is_nobet:
            e = Event()
            e.name = "🚨 Nöbet"
            e.begin = current_date
            e.make_all_day()
            desc = f"Ekip: {', '.join(nobet_ekibi)}"
            
            # Nöbetçi Uzman
            if df_uzman is not None:
                nobet_u_cols = [c for c in df_uzman.columns if "NÖBET" in c and "ERTESİ" not in c]
                if nobet_u_cols:
                    d_col = df_uzman.columns[0]
                    u_row = df_uzman[df_uzman[d_col].astype(str).str.contains(current_date.strftime("%Y-%m-%d"), na=False)]
                    if u_row.empty: u_row = df_uzman[df_uzman[d_col].astype(str).str.contains(current_date.strftime("%d.%m.%Y"), na=False)]
                    
                    if not u_row.empty:
                        hoca = u_row.iloc[0][nobet_u_cols[0]]
                        if pd.notna(hoca):
                            e.name += f" ({hoca})"
                            desc += f"\nNöbetçi Uzman: {hoca}"
            e.description = desc
            cal.events.add(e)
            count += 1

        # --- B) GÜNDÜZ GÖREVLERİ ---
        for col in tum_gorevler:
            val = str(row[col])
            
            if pd.notna(val) and user_name in str(val).lower():
                e = Event()
                
                # İsimlendirme
                if "ACİL" in col: e.name = f"🚑 {col}"
                elif "AMELİYAT" in col: e.name = f"🔪 {col}"
                elif "POL" in col: e.name = f"👨‍⚕️ {col}"
                else: e.name = f"📋 {col}"
                
                e.begin = current_date.replace(hour=8, minute=0)
                e.end = current_date.replace(hour=17, minute=0)
                e.description = f"Görev Yeri: {col}"
                
                # 1. Ameliyat Eşleşmesi (Dinamik)
                if col in ameliyat_cols:
                    active_experts = get_active_surgery_experts(df_uzman, current_date)
                    if active_experts:
                        my_index = ameliyat_cols.index(col)
                        target_index = my_index % len(active_experts)
                        atanan_hoca = active_experts[target_index]
                        
                        e.name += f" - {atanan_hoca}"
                        e.description += f"\n\nSorumlu Uzman: {atanan_hoca}"

                # 2. Poliklinik Eşleşmesi
                elif col in pol_cols:
                    my_index = pol_cols.index(col)
                    hoca_bilgi = get_pol_expert(df_uzman, current_date, my_index)
                    if hoca_bilgi:
                        e.name += f" - {hoca_bilgi.split('(')[0]}"
                        e.description += f"\nSorumlu Uzman: {hoca_bilgi}"

                cal.events.add(e)
                count += 1

    return cal, count

# --- ÇALIŞTIRMA ---
if asistan_file and target_name:
    st.divider()
    try:
        if asistan_file.name.endswith('.csv'): df_a = pd.read_csv(asistan_file, delimiter=";")
        else: df_a = pd.read_excel(asistan_file)
            
        df_u = None
        if uzman_file:
            if uzman_file.name.endswith('.csv'):
                try: df_u = pd.read_csv(uzman_file, delimiter=";")
                except: df_u = pd.read_csv(uzman_file, delimiter=",")
            else: df_u = pd.read_excel(uzman_file)
            
            if df_u is not None:
                d_col = df_u.columns[0]
                df_u[d_col] = pd.to_datetime(df_u[d_col], dayfirst=True, errors='coerce')

        cal, cnt = create_calendar(df_a, df_u, target_name)
        
        if cnt > 0:
            st.success(f"✅ İşlem Tamam! Toplam **{cnt}** adet görev takvime işlendi.")
            safe_name = target_name.replace(' ', '_').replace('ı','i').replace('ş','s').replace('ö','o').replace('ü','u').replace('ğ','g').replace('ç','c').upper()
            
            st.download_button(
                label="📥 Takvimi İndir (.ics)",
                data=str(cal),
                file_name=f"{safe_name}_TAKVIM.ics",
                mime="text/calendar"
            )
        else:
            st.warning("⚠️ Girdiğiniz isimle listede eşleşen bir görev bulunamadı. Lütfen isminizi kontrol ediniz.")

    except Exception as e:
        st.error("Bir hata oluştu.")
        st.write(f"Teknik Detay: {e}")
