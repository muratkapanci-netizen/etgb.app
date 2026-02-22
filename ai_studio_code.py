import streamlit as st
import pdfplumber
import pandas as pd
import re

# Sayfa Ayarları
st.set_page_config(page_title="ETGB Veri Analisti", page_icon="📦", layout="wide")
st.title("📦 ETGB İhracat Beyannamesi Otomasyonu")
st.markdown("E-Arşiv Faturanızı (PDF) yükleyin, GTİP ve Menşei bazlı gruplanmış verinizi alın.")

# Dosya Yükleyici
uploaded_file = st.file_uploader("PDF Formatında Fatura Yükleyiniz", type="pdf")

if uploaded_file is not None:
    with st.spinner('Belge analiz ediliyor...'):
        try:
            with pdfplumber.open(uploaded_file) as pdf:
                text = ""
                all_tables =[]
                for page in pdf.pages:
                    text += page.extract_text() + "\n"
                    tables = page.extract_table()
                    if tables:
                        all_tables.extend(tables)

            # 1. Fatura Bilgilerini Çekme (Regex)
            fatura_no = re.search(r'Fatura No\s*\s*(+)', text)
            fatura_tarihi = re.search(r'Fatura Tarihi\s*\s*(+)', text)
            net_kilo = re.search(r'Net Ağırlık\s*:\s*(+)\s*KG', text, re.IGNORECASE)
            brut_kilo = re.search(r'Brüt Ağırlık\s*:\s*(+)\s*KG', text, re.IGNORECASE)

            f_no_val = fatura_no.group(1) if fatura_no else "Bulunamadı"
            f_tarih_val = fatura_tarihi.group(1) if fatura_tarihi else "Bulunamadı"
            kilo_val = f"Brüt: {brut_kilo.group(1) if brut_kilo else '-'} KG / Net: {net_kilo.group(1) if net_kilo else '-'} KG"

            # Fatura Bilgilerini Göster
            st.success("Belge başarıyla okundu!")
            col1, col2, col3 = st.columns(3)
            col1.metric("Fatura No", f_no_val)
            col2.metric("Fatura Tarihi", f_tarih_val)
            col3.metric("Ağırlık Bilgisi", kilo_val)

            # 2. Tabloyu Pandas DataFrame'e Çevirme
            if all_tables:
                # Tablo başlıklarını bulma
                df_raw = pd.DataFrame(all_tables)
                df_raw = df_raw.dropna(how='all')
                
                # Başlık satırını tespit etme (İçinde GTİP geçen satır)
                header_idx = df_raw.index
                
                if not header_idx.empty:
                    header_idx = header_idx
                    df = pd.DataFrame(all_tables, columns=all_tables)
                    
                    # Eksik veya None sütunları temizle
                    df = df.loc
                    df.columns = df.columns.astype(str).str.replace('\n', ' ')

                    # İlgili sütunların varlığını kontrol et
                    gerekli_sutunlar =
                    mevcut_sutunlar =

                    if len(mevcut_sutunlar) > 0:
                        parsed_data =[]
                        for _, row in df.iterrows():
                            gtip = str(row.get('GTİP', '')).strip()
                            mensei = str(row.get('Menşe Ülke', '')).replace('\n', ' ').strip()
                            miktar_str = str(row.get('Miktar', '')).strip()
                            tutar_str = str(row.get('Mal Hizmet Tutarı', '')).strip()

                            if not gtip or gtip == "None" or "Toplam" in gtip:
                                continue

                            # Miktar ve Birimi ayır (Örn: "10 Adet" -> 10, "Adet")
                            miktar_match = re.search(r'(+)\s*(+)', miktar_str)
                            if miktar_match:
                                miktar_val = float(miktar_match.group(1).replace('.', '').replace(',', '.'))
                                birim_val = miktar_match.group(2)
                            else:
                                miktar_val = 1.0
                                birim_val = "Bilinmiyor"

                            # Tutarı floata çevir (Örn: "1.416,00 EUR" -> 1416.00)
                            tutar_match = re.search(r'(+)', tutar_str)
                            if tutar_match:
                                tutar_val = float(tutar_match.group(1).replace('.', '').replace(',', '.'))
                            else:
                                tutar_val = 0.0

                            # Döviz cinsini al
                            doviz_match = re.search(r'{3}', tutar_str)
                            doviz = doviz_match.group(0) if doviz_match else "EUR"

                            parsed_data.append({
                                'GTİP': gtip,
                                'Menşei': mensei,
                                'Birim': birim_val,
                                'Miktar': miktar_val,
                                'Tutar': tutar_val,
                                'Döviz': doviz
                            })

                        df_parsed = pd.DataFrame(parsed_data)

                        if not df_parsed.empty:
                            # 3. Gruplama İşlemi (GTİP, Menşei ve Birim bazında)
                            df_grouped = df_parsed.groupby().agg({
                                'Miktar': 'sum',
                                'Tutar': 'sum',
                                'Döviz': 'first'
                            }).reset_index()

                            # Çıktı formatını düzenle
                            df_grouped = df_grouped.apply(lambda x: f"{int(x) if x.is_integer() else x}")
                            df_grouped = df_grouped.apply(lambda row: f"{row:,.2f} {row}".replace(',', 'X').replace('.', ',').replace('X', '.'), axis=1)
                            df_grouped = kilo_val # Faturada kalem bazlı kilo yoksa geneli yazdırır

                            # Gösterilecek Tablo
                            final_table = df_grouped[]
                            
                            st.subheader("📊 Gruplanmış Beyan Tablosu")
                            st.dataframe(final_table, use_container_width=True)

                            # Excel Olarak İndirme Butonu
                            csv = final_table.to_csv(index=False).encode('utf-8-sig')
                            st.download_button(
                                label="📥 Excel (CSV) Olarak İndir",
                                data=csv,
                                file_name='etgb_beyan_tablosu.csv',
                                mime='text/csv',
                            )
                        else:
                            st.warning("Tablo verileri okunurken uygun format bulunamadı.")
                    else:
                        st.warning("Fatura içinde standart GTİP/Menşei sütunları bulunamadı.")
                else:
                    st.warning("PDF içerisinde standart bir tablo yapısı tespit edilemedi.")
        except Exception as e:
            st.error(f"Dosya işlenirken bir hata oluştu: {e}")