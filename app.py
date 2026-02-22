import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="ETGB Veri Analisti", page_icon="📦", layout="wide")
st.title("📦 ETGB İhracat Beyannamesi Otomasyonu")
st.markdown("E-Arşiv Faturanızı (PDF) yükleyerek GTİP ve Menşei bazlı gruplanmış verinizi otomatik oluşturun.")

uploaded_file = st.file_uploader("PDF Formatında Fatura Yükleyiniz", type="pdf")

if uploaded_file is not None:
    with st.spinner('Belge analiz ediliyor... Lütfen bekleyin.'):
        try:
            text = ""
            all_tables = []
            
            # PDF'i oku
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() + "\n"
                    tables = page.extract_tables()
                    for table in tables:
                        all_tables.extend(table)

            # 1. Fatura Bilgilerini Çekme
            fatura_no_match = re.search(r'Fatura No\s*([A-Z0-9]+)', text)
            fatura_tarihi_match = re.search(r'Fatura Tarihi\s*([\d/.-]+)', text)
            net_kilo_match = re.search(r'Net Ağırlık\s*:\s*([\d,.]+)\s*KG', text, re.IGNORECASE)
            brut_kilo_match = re.search(r'Brüt Ağırlık\s*:\s*([\d,.]+)\s*KG', text, re.IGNORECASE)

            f_no = fatura_no_match.group(1) if fatura_no_match else "Bulunamadı"
            f_tarih = fatura_tarihi_match.group(1) if fatura_tarihi_match else "Bulunamadı"
            
            b_kilo = brut_kilo_match.group(1) if brut_kilo_match else "-"
            n_kilo = net_kilo_match.group(1) if net_kilo_match else "-"
            kilo_bilgisi = f"Brüt: {b_kilo} KG / Net: {n_kilo} KG"

            st.success("Belge başarıyla okundu!")
            c1, c2, c3 = st.columns(3)
            c1.metric("Fatura No", f_no)
            c2.metric("Fatura Tarihi", f_tarih)
            c3.metric("Ağırlık Bilgisi", kilo_bilgisi)

            # 2. Tablo İşlemleri
            if all_tables:
                df = pd.DataFrame(all_tables)
                
                baslik_sira = -1
                for i, row in df.iterrows():
                    row_str = " ".join([str(x) for x in row.values if x])
                    if "GTİP" in row_str or "Miktar" in row_str:
                        baslik_sira = i
                        break
                
                if baslik_sira != -1:
                    df.columns = df.iloc[baslik_sira].astype(str).str.replace('\n', ' ').str.strip()
                    df = df.iloc[baslik_sira+1:].reset_index(drop=True)
                    df = df.dropna(how='all')

                    parsed_data = []
                    for _, row in df.iterrows():
                        gtip = str(row.get('GTİP', '')).strip()
                        mensei = str(row.get('Menşe Ülke', '')).replace('\n', ' ').strip()
                        miktar_str = str(row.get('Miktar', '')).strip()
                        tutar_str = str(row.get('Mal Hizmet Tutarı', '')).strip()

                        if not gtip or gtip.lower() in ["none", "nan", ""] or "toplam" in gtip.lower():
                            continue

                        # Miktarı ve Birimi Ayır (GÜNCELLENEN VE HATA VERMEYEN KISIM)
                        miktar_match = re.search(r'([\d,.]+)\s*(.*)', miktar_str)
                        if miktar_match:
                            miktar_val = float(miktar_match.group(1).replace('.', '').replace(',', '.'))
                            birim_val = miktar_match.group(2).strip()
                            if not birim_val:
                                birim_val = "Adet"
                        else:
                            miktar_val = 1.0
                            birim_val = "Adet"

                        # Tutarı Ayır
                        tutar_match = re.search(r'([\d,.]+)', tutar_str)
                        if tutar_match:
                            tutar_val = float(tutar_match.group(1).replace('.', '').replace(',', '.'))
                        else:
                            tutar_val = 0.0
                        
                        parsed_data.append({
                            'GTİP': gtip,
                            'Menşei': mensei,
                            'Birim': birim_val,
                            'Toplam Miktar': miktar_val,
                            'Toplam Fiyat': tutar_val
                        })

                    if parsed_data:
                        df_parsed = pd.DataFrame(parsed_data)
                        
                        # 3. Veriyi Grupla
                        df_grouped = df_parsed.groupby(['GTİP', 'Menşei', 'Birim'], as_index=False).agg({
                            'Toplam Miktar': 'sum', 
                            'Toplam Fiyat': 'sum'
                        })
                        
                        # Formatlama
                        df_grouped['Toplam Fiyat'] = df_grouped['Toplam Fiyat'].apply(lambda x: f"{x:,.2f} EUR".replace(',', 'X').replace('.', ',').replace('X', '.'))
                        df_grouped['Brüt/Net Kilo'] = kilo_bilgisi 
                        
                        st.subheader("📊 Gruplanmış Beyan Tablosu")
                        st.dataframe(df_grouped, use_container_width=True)
                        
                        # İndirme Butonu
                        csv = df_grouped.to_csv(index=False).encode('utf-8-sig')
                        st.download_button("📥 Excel Olarak İndir (CSV)", data=csv, file_name='etgb_tablo.csv', mime='text/csv')
                    else:
                        st.warning("Fatura kalemleri çıkarılamadı veya GTİP bulunamadı.")
                else:
                    st.warning("Tabloda 'GTİP' başlığı tespit edilemedi.")
            else:
                st.warning("PDF içerisinde okunabilir bir tablo bulunamadı.")
        except Exception as e:
            st.error(f"Dosya işlenirken hata oluştu: {e}")
