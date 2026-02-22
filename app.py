import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="ETGB Veri Analisti", page_icon="📦", layout="wide")
st.title("📦 ETGB İhracat Beyannamesi Otomasyonu")
st.markdown("E-Arşiv Faturanızı (PDF) yükleyerek GTİP ve Menşei bazlı verinizi liste formatında alın.")

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

            # 1. Genel Bilgileri Çekme (Unvan, VKN, Fatura No vb.)
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            unvan_adaylari = [line for line in lines[:15] if "ŞİRKETİ" in line.upper() or "A.Ş" in line.upper() or "LTD" in line.upper() or "TİC" in line.upper()]
            unvan = unvan_adaylari[0] if unvan_adaylari else (lines[0] if lines else "Bulunamadı")

            vkn_match = re.search(r'Vergi Numaras[ıiIİ]\s*[:\-]?\s*(\d{10,11})', text)
            vkn = vkn_match.group(1) if vkn_match else "Bulunamadı"

            fatura_no_match = re.search(r'Fatura No\s*([A-Z0-9]+)', text)
            fatura_tarihi_match = re.search(r'Fatura Tarihi\s*([\d/.-]+)', text)
            net_kilo_match = re.search(r'Net Ağırlık\s*:\s*([\d,.]+)\s*KG', text, re.IGNORECASE)
            brut_kilo_match = re.search(r'Brüt Ağırlık\s*:\s*([\d,.]+)\s*KG', text, re.IGNORECASE)

            f_no = fatura_no_match.group(1) if fatura_no_match else "Bulunamadı"
            f_tarih = fatura_tarihi_match.group(1) if fatura_tarihi_match else "Bulunamadı"
            
            b_kilo = brut_kilo_match.group(1) if brut_kilo_match else "-"
            n_kilo = net_kilo_match.group(1) if net_kilo_match else "-"
            kilo_bilgisi = f"Brüt: {b_kilo} KG / Net: {n_kilo} KG"

            # ---- ÜST KISIM: UNVAN VE VKN GÖSTERİMİ ----
            st.success("Belge başarıyla okundu!")
            st.markdown("---")
            st.markdown(f"### 🏢 **Gönderen:** {unvan}")
            st.markdown(f"**🏷️ Vergi Numarası:** {vkn}")
            st.markdown("---")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Fatura No", f_no)
            c2.metric("Fatura Tarihi", f_tarih)
            c3.metric("Ağırlık Bilgisi", kilo_bilgisi)
            st.markdown("---")

            # 2. Tablo İşlemleri ve Gruplama
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
                        
                        # Mal Tanımını Çekme
                        mal_tanimi = str(row.get('Mal Hizmet', row.get('Cinsi', row.get('Ürün Kodu', '')))).replace('\n', ' ').strip()
                        
                        if not mal_tanimi or mal_tanimi.lower() in ["nan", "none"]:
                            for col in df.columns:
                                if "mal" in str(col).lower() or "hizmet" in str(col).lower() or "tanım" in str(col).lower() or "cins" in str(col).lower():
                                    if "tutar" not in str(col).lower() and "fiyat" not in str(col).lower():
                                        mal_tanimi = str(row.get(col, '')).replace('\n', ' ').strip()
                                        break
                                        
                        if not mal_tanimi or mal_tanimi.lower() in ["nan", "none"]:
                            mal_tanimi = "Tanım Bulunamadı"

                        if not gtip or gtip.lower() in ["none", "nan", ""] or "toplam" in gtip.lower():
                            continue

                        # Miktar Ayrıştırma
                        miktar_match = re.search(r'([\d,.]+)\s*(.*)', miktar_str)
                        if miktar_match:
                            miktar_val = float(miktar_match.group(1).replace('.', '').replace(',', '.'))
                            birim_val = miktar_match.group(2).strip()
                            if not birim_val: birim_val = "Adet"
                        else:
                            miktar_val = 1.0
                            birim_val = "Adet"

                        # Tutar Ayrıştırma
                        tutar_match = re.search(r'([\d,.]+)', tutar_str)
                        if tutar_match:
                            tutar_val = float(tutar_match.group(1).replace('.', '').replace(',', '.'))
                        else:
                            tutar_val = 0.0
                        
                        parsed_data.append({
                            'GTİP': gtip,
                            'Menşei': mensei,
                            'Birim': birim_val,
                            'Mal Tanımı': mal_tanimi,
                            'Toplam Miktar': miktar_val,
                            'Toplam Fiyat': tutar_val
                        })

                    if parsed_data:
                        df_parsed = pd.DataFrame(parsed_data)
                        
                        df_grouped = df_parsed.groupby(['GTİP', 'Menşei', 'Birim'], as_index=False).agg({
                            'Toplam Miktar': 'sum', 
                            'Toplam Fiyat': 'sum',
                            'Mal Tanımı': lambda x: ' | '.join(pd.unique(x)) 
                        })
                        
                        df_grouped['Toplam Fiyat'] = df_grouped['Toplam Fiyat'].apply(lambda x: f"{x:,.2f} EUR".replace(',', 'X').replace('.', ',').replace('X', '.'))
                        
                        # ---- ALT KISIM: AÇILIR KAPANIR LİSTE (POP-UP) GÖRÜNÜMÜ ----
                        st.subheader("📋 Gruplanmış Beyan Kalemleri")
                        
                        for index, row in df_grouped.iterrows():
                            tam_tanim = row['Mal Tanımı']
                            kisa_tanim = tam_tanim[:45] + "..." if len(tam_tanim) > 45 else tam_tanim
                            
                            baslik_metni = f"📦 KALEM {index + 1}  |  GTİP: {row['GTİP']}  |  {kisa_tanim}"
                            
                            # EKRANA KAPALI GELMESİ İÇİN expanded=False YAPILDI
                            with st.expander(baslik_metni, expanded=False):
                                st.markdown(f"**🏷️ Tam Mal Tanımı:** {tam_tanim}")
                                st.markdown(f"**🔹 GTİP Kodu:** {row['GTİP']}")
                                st.markdown(f"**🌍 Menşei:** {row['Menşei']}")
                                miktar_gosterim = int(row['Toplam Miktar']) if row['Toplam Miktar'].is_integer() else row['Toplam Miktar']
                                st.markdown(f"**⚖️ Toplam Miktar:** {miktar_gosterim} {row['Birim']}")
                                st.markdown(f"**💰 Toplam Fiyat:** {row['Toplam Fiyat']}")
                        
                        st.markdown("---")
                        
                        df_grouped['Brüt/Net Kilo'] = kilo_bilgisi
                        csv = df_grouped.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="📥 Bu Verileri Excel (CSV) Olarak da İndir", 
                            data=csv, 
                            file_name='etgb_kalemler.csv', 
                            mime='text/csv'
                        )
                    else:
                        st.warning("Fatura kalemleri çıkarılamadı.")
                else:
                    st.warning("Tabloda başlık satırı tespit edilemedi.")
            else:
                st.warning("PDF içerisinde okunabilir bir tablo bulunamadı.")
        except Exception as e:
            st.error(f"Dosya işlenirken hata oluştu: {e}")
