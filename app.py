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

            # 1. Fatura Bilgilerini Çekme (Regex)
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
                
                # İçinde "GTİP" veya "Miktar" geçen satırı başlık olarak bul
                baslik_sira = -1
                for i, row in df.iterrows():
                    row_str = " ".join([str(x) for x in row.values if x])
                    if "GTİP" in row_str or "Miktar" in row_str:
                        baslik_sira = i
                        break
                
                if baslik_sira != -1:
                    # Başlığı ayarla ve temizle
                    df.columns = df.iloc[baslik_sira].astype(str).str.replace('\n', ' ').str.strip()
                    df = df.iloc[baslik_sira+1:].reset_index(drop=True)
                    df = df.dropna(how='all')

                    parsed_data = []
                    for _, row in df.iterrows():
                        # Sütunları güvenli bir şekilde al
                        gtip = str(row.get('GTİP', '')).strip()
                        mensei = str(row.get('Menşe Ülke', '')).replace('\n', ' ').strip()
                        miktar_str = str(row.get('Miktar', '')).strip()
                        tutar_str = str(row.get('Mal Hizmet Tutarı', '')).strip()

                        # Boş satırları veya toplam satırlarını atla
                        if not gtip or gtip.lower() in ["none", "nan", ""] or "toplam" in gtip.lower():
                            continue

                        # Miktarı ve Birimi Ayır (Örn: "10 Adet" -> 10, "Adet")
                        miktar_match = re.search(r'([\d,.]+)\s*([a-zA-ZçÇğĞı
