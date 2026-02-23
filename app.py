import streamlit as st
import pdfplumber
import pandas as pd
import re
import pytesseract
from PIL import Image

st.set_page_config(page_title="ETGB Veri Analisti", page_icon="📦", layout="wide")
st.title("📦 ETGB İhracat Beyannamesi Otomasyonu")
st.markdown("PDF, JPG, PNG veya Ekran Görüntülerini **çoklu olarak** seçip yükleyebilirsiniz. Sistem tüm dosyaları birleştirip sol tarafa özet, sağ tarafa kopyalanabilir kalemler çıkarır.")

# Çoklu Dosya Yükleyici
uploaded_files = st.file_uploader("PDF veya Ekran Görüntüsü Yükleyiniz", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    with st.spinner('Tüm belgeler yapay zeka ile analiz ediliyor... Lütfen bekleyin.'):
        try:
            tum_kalemler = []
            genel_unvanlar = set()
            genel_vknler = set()
            genel_fatura_nolar = set()
            genel_tarihler = set()
            kilo_notlari = []
            
            toplam_navlun = 0.0
            toplam_sigorta = 0.0
            doviz_cinsi = "EUR"

            for file in uploaded_files:
                text = ""
                file_tables = []
                
                # Dosya Türüne Göre Okuma
                if file.name.lower().endswith('.pdf'):
                    with pdfplumber.open(file) as pdf:
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            if page_text:
                                text += page_text + "\n"
                            
                            # Tabloları liste halinde al (hepsini birbirine karıştırma)
                            tables = page.extract_tables()
                            if tables:
                                file_tables.extend(tables)
                            
                            # Eğer PDF taranmış bir resimse OCR ile oku
                            if not page_text or len(page_text.strip()) < 50:
                                img = page.to_image(resolution=200).original
                                text += pytesseract.image_to_string(img, lang='tur+eng') + "\n"
                else:
                    # Görüntü Dosyası (JPG, PNG)
                    img = Image.open(file)
                    text += pytesseract.image_to_string(img, lang='tur+eng')

                # --- 1. GENEL BİLGİLERİ BULMA ---
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                
                # Ünvan
                unvan_adaylari = [line for line in lines[:15] if "ŞİRKETİ" in line.upper() or "A.Ş" in line.upper() or "LTD" in line.upper() or "TİC" in line.upper()]
                if unvan_adaylari: genel_unvanlar.add(unvan_adaylari[0])

                # VKN (Gerçek VKN Filtrelemesi: 2222222222 gibi sahte olanları reddeder)
                vkn_matches = re.findall(r'(?:VKN|Vergi\s*No|Vergi\s*Numaras[ıiIİ])\s*[:.\-]?\s*(\d{10,11})', text, re.IGNORECASE)
                for v in vkn_matches:
                    # Rakamların hepsi aynı değilse (örn: 2222222222 değilse) kabul et
                    if len(set(v)) > 1 and not v.startswith("0000"):
                        genel_vknler.add(v)

                # Fatura No 
                f_no_match = re.findall(r'\b[A-Za-z]{3}202\d{9}\b', text)
                if f_no_match:
                    for f in f_no_match: genel_fatura_nolar.add(f)

                # Tarih
                tarih_match = re.search(r'(0[1-9]|[12][0-9]|3[01])[-/.](0[1-9]|1[012])[-/.](20\d\d)', text)
                if tarih_match: genel_tarihler.add(tarih_match.group(0))

                # Kilo ve Masraflar
                b_kilo = re.search(r'Brüt[^0-9]*([\d,.]+)\s*KG', text, re.IGNORECASE)
                n_kilo = re.search(r'Net[^0-9]*([\d,.]+)\s*KG', text, re.IGNORECASE)
                if b_kilo or n_kilo:
                    kilo_notlari.append(f"Brüt: {b_kilo.group(1) if b_kilo else '-'} / Net: {n_kilo.group(1) if n_kilo else '-'}")

                navlun_m = re.search(r'NAVLUN[^\d]*?([\d.,]+)', text, re.IGNORECASE)
                if navlun_m: toplam_navlun += float(navlun_m.group(1).replace('.', '').replace(',', '.'))
                
                sigorta_m = re.search(r'S[İI]GORTA[^\d]*?([\d.,]+)', text, re.IGNORECASE)
                if sigorta_m: toplam_sigorta += float(sigorta_m.group(1).replace('.', '').replace(',', '.'))

                # --- 2. AKILLI TABLO / KALEM OKUMA SİSTEMİ ---
                dosya_kalemleri = []
                
                # A) Tabloları Ayrı Ayrı İncele (Alt toplam tablolarını elemek için)
                for table in file_tables:
                    df = pd.DataFrame(table)
                    baslik_sira = -1
                    
                    # Bu tablonun içinde gerçekten GTİP ve Miktar başlıkları var mı?
                    for i, row in df.iterrows():
                        row_str = " ".join([str(x) for x in row.values if x]).upper()
                        if ("GTİP" in row_str or "HS CODE" in row_str or "GTIP" in row_str) and ("MİKTAR" in row_str or "QTY" in row_str or "ADET" in row_str):
                            baslik_sira = i
                            break
                    
                    if baslik_sira != -1:
                        df.columns = df.iloc[baslik_sira].astype(str).str.replace('\n', ' ').str.strip().str.upper()
                        df = df.iloc[baslik_sira+1:].dropna(how='all')
                        
                        cols = df.columns.tolist()
                        gtip_col = next((c for c in cols if 'GTIP' in c or 'GTİP' in c or 'HS CODE' in c), None)
                        miktar_col = next((c for c in cols if 'MİKTAR' in c or 'MIKTAR' in c or 'QTY' in c), None)
                        mal_col = next((c for c in cols if 'MAL' in c or 'HİZMET' in c or 'CİNS' in c or 'TANIM' in c or 'NAME' in c or 'PART' in c), None)
                        
                        # Tutarı KDV tutarıyla karıştırmamak için öncelik "MAL HİZMET" sütununda
                        tutar_col = None
                        for c in cols:
                            if ('TUTAR' in c or 'AMOUNT' in c) and 'KDV' not in c:
                                tutar_col = c
                                break
                        if not tutar_col:
                            tutar_col = next((c for c in cols if 'TUTAR' in c or 'AMOUNT' in c or 'TOPLAM' in c), None)
                            
                        mensei_col = next((c for c in cols if 'MENŞE' in c or 'ORIGIN' in c), None)
                        
                        if gtip_col and miktar_col:
                            for _, row in df.iterrows():
                                gtip = str(row.get(gtip_col, '')).replace('.', '').strip()
                                
                                # ÇOK ÖNEMLİ FİLTRE: İçinde en az 6 adet rakam yoksa bu bir GTİP değildir! (Sahte kalemleri engeller)
                                if not gtip or len(re.sub(r'\D', '', gtip)) < 6:
                                    continue
                                    
                                miktar_str = str(row.get(miktar_col, '')).strip()
                                mik_match = re.search(r'([\d,.]+)\s*(.*)', miktar_str)
                                if mik_match:
                                    miktar_val = float(mik_match.group(1).replace('.', '').replace(',', '.'))
                                    birim_val = mik_match.group(2).strip().title() if mik_match.group(2) else "Adet"
                                else:
                                    # Sadece rakam bulmaya çalış
                                    nums = re.findall(r'[\d,.]+', miktar_str)
                                    if nums:
                                        miktar_val = float(nums[0].replace('.', '').replace(',', '.'))
                                        birim_val = "Adet"
                                    else:
                                        miktar_val = 1.0
                                        birim_val = "Adet"
                                
                                mal_tanimi = str(row.get(mal_col, 'Tanım Bulunamadı')).replace('\n', ' ') if mal_col else "Tanım Bulunamadı"
                                mensei = str(row.get(mensei_col, 'Belirtilmemiş')).replace('\n', ' ') if mensei_col else 'Belirtilmemiş'
                                
                                tutar_str = str(row.get(tutar_col, '0')).strip() if tutar_col else "0"
                                tutar_match = re.search(r'([\d,.]+)', tutar_str)
                                tutar_val = float(tutar_match.group(1).replace('.', '').replace(',', '.')) if tutar_match else 0.0
                                
                                dosya_kalemleri.append({'GTİP': gtip, 'Menşei': mensei, 'Birim': birim_val, 'Mal Tanımı': mal_tanimi, 'Miktar': miktar_val, 'Fiyat': tutar_val})

                tum_kalemler.extend(dosya_kalemleri)

            # --- 3. EKRAN TASARIMI VE GRUPLAMA ---
            st.success(f"{len(uploaded_files)} Adet Belge Başarıyla Okundu ve Birleştirildi!")
            col_sol, col_sag = st.columns([1.2, 2.5])

            if tum_kalemler:
                df_parsed = pd.DataFrame(tum_kalemler)
                df_grouped = df_parsed.groupby(['GTİP', 'Menşei', 'Birim'], as_index=False).agg({
                    'Miktar': 'sum', 'Fiyat': 'sum', 'Mal Tanımı': lambda x: ' | '.join(pd.unique(x))
                })
                toplam_adet = df_grouped['Miktar'].sum()
                toplam_fiyat = df_grouped['Fiyat'].sum()
            else:
                df_grouped = pd.DataFrame()
                toplam_adet = 0
                toplam_fiyat = 0.0

            # SOL TARAF: ÖZET TABLO
            with col_sol:
                st.markdown("### 📋 ÖZET TABLO")
                
                g_unvan = "<br>".join(genel_unvanlar) if genel_unvanlar else "Bulunamadı"
                g_vkn = ", ".join(genel_vknler) if genel_vknler else "Bulunamadı"
                g_fatura = "<br>".join(genel_fatura_nolar) if genel_fatura_nolar else "Bulunamadı"
                g_tarih = ", ".join(genel_tarihler) if genel_tarihler else "Bulunamadı"
                g_kilo = "<br>".join(kilo_notlari) if kilo_notlari else "Belirtilmemiş"

                st.markdown(f"""
                <div style='font-weight: bold; font-size: 15px; line-height: 1.6;'>
                🏢 GÖNDEREN ÜNVANI:<br><span style='font-size: 16px; color:#2e7bcf;'>{g_unvan}</span><br><br>
                🏷️ VERGİ NUMARASI:<br><