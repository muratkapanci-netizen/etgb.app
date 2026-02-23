import streamlit as st
import pdfplumber
import pandas as pd
import re

# Sayfa genişliğini ayarlama
st.set_page_config(page_title="ETGB Veri Analisti", page_icon="📦", layout="wide")

# Sayfa başlığı
st.title("📦 ETGB İhracat Beyannamesi Otomasyonu")
st.markdown("E-Arşiv Faturanızı (PDF) yükleyin. Sistem sol tarafa özet tabloyu, sağ tarafa ise kopyalanabilir kalemleri çıkaracaktır.")

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

            # --- 1. GENEL BİLGİLERİ VE MASRAFLARI ÇEKME ---
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            # Unvan
            unvan_adaylari = [line for line in lines[:15] if "ŞİRKETİ" in line.upper() or "A.Ş" in line.upper() or "LTD" in line.upper() or "TİC" in line.upper()]
            unvan = unvan_adaylari[0] if unvan_adaylari else (lines[0] if lines else "Bulunamadı")

            # VKN
            vkn_match = re.search(r'Vergi Numaras[ıiIİ]\s*[:\-]?\s*(\d{10,11})', text)
            vkn = vkn_match.group(1) if vkn_match else "Bulunamadı"

            # Fatura No & Tarih
            fatura_no_match = re.search(r'Fatura No\s*([A-Z0-9]+)', text)
            f_no = fatura_no_match.group(1) if fatura_no_match else "Bulunamadı"
            
            fatura_tarihi_match = re.search(r'Fatura Tarihi\s*([\d/.-]+)', text)
            f_tarih = fatura_tarihi_match.group(1) if fatura_tarihi_match else "Bulunamadı"

            # Kilo
            net_kilo_match = re.search(r'Net Ağırlık\s*:\s*([\d,.]+)\s*KG', text, re.IGNORECASE)
            brut_kilo_match = re.search(r'Brüt Ağırlık\s*:\s*([\d,.]+)\s*KG', text, re.IGNORECASE)
            b_kilo = brut_kilo_match.group(1) if brut_kilo_match else "-"
            n_kilo = net_kilo_match.group(1) if net_kilo_match else "-"
            kilo_bilgisi = f"Brüt: {b_kilo} KG / Net: {n_kilo} KG"

            # Masrafları Arama (Navlun, Sigorta)
            navlun_match = re.search(r'NAVLUN[^\d]*?([\d.,]+)\s*([€₺$]|EUR|USD|TL|TRY)?', text, re.IGNORECASE)
            navlun_val = f"{navlun_match.group(1)} {navlun_match.group(2) or ''}".strip() if navlun_match else None

            sigorta_match = re.search(r'S[İI]GORTA[^\d]*?([\d.,]+)\s*([€₺$]|EUR|USD|TL|TRY)?', text, re.IGNORECASE)
            sigorta_val = f"{sigorta_match.group(1)} {sigorta_match.group(2) or ''}".strip() if sigorta_match else None


            # --- 2. TABLO İŞLEMLERİ VE HESAPLAMALAR ---
            df_grouped = pd.DataFrame()
            toplam_adet = 0.0
            toplam_fiyat = 0.0
            doviz_cinsi = "EUR" # Varsayılan
            
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
                        # GTİP okuma ve Notaları temizleme (Örn: 8413.91.00.00.19 -> 841391000019)
                        gtip = str(row.get('GTİP', '')).replace('.', '').strip()
                        mensei = str(row.get('Menşe Ülke', '')).replace('\n', ' ').strip()
                        miktar_str = str(row.get('Miktar', '')).strip()
                        tutar_str = str(row.get('Mal Hizmet Tutarı', '')).strip()
                        
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

                        # Miktar
                        miktar_match = re.search(r'([\d,.]+)\s*(.*)', miktar_str)
                        if miktar_match:
                            miktar_val = float(miktar_match.group(1).replace('.', '').replace(',', '.'))
                            birim_val = miktar_match.group(2).strip() or "Adet"
                        else:
                            miktar_val = 1.0
                            birim_val = "Adet"

                        # Tutar ve Döviz
                        tutar_match = re.search(r'([\d,.]+)', tutar_str)
                        if tutar_match:
                            tutar_val = float(tutar_match.group(1).replace('.', '').replace(',', '.'))
                        else:
                            tutar_val = 0.0
                            
                        # Döviz bulma (ilk satırdan EUR, USD vb. çeker)
                        doviz_match = re.search(r'([A-Za-z$€₺]{1,3})', tutar_str.replace(tutar_match.group(1) if tutar_match else '', ''))
                        if doviz_match:
                            doviz_cinsi = doviz_match.group(1).strip()
                        
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
                        
                        toplam_adet = df_grouped['Toplam Miktar'].sum()
                        toplam_fiyat = df_grouped['Toplam Fiyat'].sum()


            # --- 3. EKRAN TASARIMI (SOL VE SAĞ SÜTUN) ---
            st.success("Belge başarıyla okundu!")
            col_sol, col_sag = st.columns([1.2, 2.5]) # Sol taraf özet (dar), sağ taraf liste (geniş)

            # --- SOL TARAF: ÖZET TABLO ---
            with col_sol:
                st.markdown("### 📋 ÖZET TABLO")
                
                # Firma bilgileri ve toplamlar tamamen KALIN yazıldı
                ozet_metin = f"""
                **🏢 GÖNDEREN ÜNVANI:**  
                **{unvan}**  
                
                **🏷️ VERGİ NUMARASI:** **{vkn}**  
                
                **📄 E-ARŞİV FATURA NO:** **{f_no}**  
                
                **📅 FATURA TARİHİ:** **{f_tarih}**  
                
                **⚖️ AĞIRLIK BİLGİSİ:** **{kilo_bilgisi}**  
                
                ---
                **📦 TOPLAM ADET / MİKTAR:** **{int(toplam_adet) if toplam_adet.is_integer() else toplam_adet}**  
                
                **💰 MASRAFLAR HARİÇ TOPLAM:** **{toplam_fiyat:,.2f} {doviz_cinsi}**  
                """
                st.markdown(ozet_metin)

                st.markdown("---")
                st.markdown("### 💸 MASRAFLAR")
                # Masraflar Kırmızı ve Kalın Yazdırılır
                if navlun_val:
                    st.markdown(f"<div style='color:red; font-size:18px; font-weight:bold;'>🚢 NAVLUN: {navlun_val}</div>", unsafe_allow_html=True)
                if sigorta_val:
                    st.markdown(f"<div style='color:red; font-size:18px; font-weight:bold;'>🛡️ SİGORTA: {sigorta_val}</div>", unsafe_allow_html=True)
                    
                if not navlun_val and not sigorta_val:
                    st.markdown("<div style='color:red; font-size:16px; font-weight:bold;'>Faturada Belirtilmemiş</div>", unsafe_allow_html=True)


            # --- SAĞ TARAF: POP-UP (AÇILIR KAPANIR) LİSTE ---
            with col_sag:
                st.markdown("### 📋 GRUPLANMIŞ BEYAN KALEMLERİ")
                
                if not df_grouped.empty:
                    for index, row in df_grouped.iterrows():
                        tam_tanim = row['Mal Tanımı']
                        kisa_tanim = tam_tanim[:40] + "..." if len(tam_tanim) > 40 else tam_tanim
                        
                        baslik_metni = f"📦 KALEM {index + 1}  |  GTİP: {row['GTİP']}  |  {kisa_tanim}"
                        
                        with st.expander(baslik_metni, expanded=False):
                            # GTİP ve Mal Tanımı HTML tagleri ile BÜYÜK ve KALIN yapıldı
                            st.markdown(f"<div style='font-size: 1.25em; font-weight: bold; margin-bottom: 5px;'>🔹 GTİP Kodu: {row['GTİP']}</div>", unsafe_allow_html=True)
                            st.markdown(f"<div style='font-size: 1.15em; font-weight: bold; margin-bottom: 15px;'>🏷️ Tam Mal Tanımı: {tam_tanim}</div>", unsafe_allow_html=True)
                            
                            st.markdown(f"**🌍 Menşei:** {row['Menşei']}")
                            miktar_gosterim = int(row['Toplam Miktar']) if row['Toplam Miktar'].is_integer() else row['Toplam Miktar']
                            st.markdown(f"**⚖️ Toplam Miktar:** {miktar_gosterim} {row['Birim']}")
                            st.markdown(f"**💰 Toplam Fiyat:** {row['Toplam Fiyat']:,.2f} {doviz_cinsi}".replace(',', 'X').replace('.', ',').replace('X', '.'))

                    st.markdown("---")
                    
                    # CSV İndirme Butonu
                    df_indirme = df_grouped.copy()
                    df_indirme['Brüt/Net Kilo'] = kilo_bilgisi
                    csv = df_indirme.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 Tabloyu Excel (CSV) Olarak İndir", 
                        data=csv, 
                        file_name='etgb_kalemler.csv', 
                        mime='text/csv'
                    )
                else:
                    st.warning("Fatura kalemleri tablodan çıkarılamadı.")

        except Exception as e:
            st.error(f"Dosya işlenirken hata oluştu: {e}")
