import imaplib
import smtplib
import email
import json
import re
import requests
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 1. BİLGİLER VE E-POSTA / CSM AYARLARI
# ==========================================
EMAIL_USER = "karaguneyyoguz@gmail.com"
EMAIL_PASS = "wkfg kmah vllg hwgf"  # Gmail Uygulama Şifresi

CSM_CREATE_TICKET_URL = "https://tatilbudur-api.cloudcsmetiya.com/api/v1/business/ticket/add"
CSM_CANCEL_TICKET_URL = "https://tatilbudur-api.cloudcsmetiya.com/api/v1/business/ticket/cancel"

RAW_TOKEN = "Bearer eyJhbGciOiJIUzM4NCJ9.eyJzdWIiOiJvZ3V6LmthcmFndW5leSIsImV4cCI6MTc4NjkwMjYwNSwiaWF0IjoxNzg2ODk5MDA1LCJjcmVhdGVkIjoxNzg2ODk5MDA1MzYxfQ.lI0BdZTlW2BEqU2709B0DtdMsIO_zHxT9XVJQNDwtDan1dwnXWqKqqdAEr05pBSx"
BEARER_TOKEN = RAW_TOKEN.replace("Bearer ", "").strip()

# ==========================================
# 2. CSM SABİT ID'LERİ VE KIRILIM TANIMLARI
# ==========================================
KANAL_ID = 100000043  # MAIL Mail

TICKET_TIPI_TESEKKUR1 = 100000062     
KATEGORI_TESEKKUR = 100000154        
ALT_KATEGORI_GENEL_TESEKKUR = 100000618     
ALT_KATEGORI_REHBER_TESEKKUR = 100000617    
ALT_KATEGORI_DANISMAN_TESEKKUR = 100000616  

TICKET_TIPI_SIKAYET = 100000061      
ALT_KATEGORI_EVRAK_SIKAYET = 100000561 
ALT_KATEGORI_FATURA_TALEBI_SIKAYET = 100000562 

KATEGORI_FATURA = 100000132                       
ALT_KATEGORI_MISAFIR_FATURASI = 100000523         
ALT_KATEGORI_FATURA_DEGISIKLIK = 100000525        

TICKET_TIPI_BILGI_ISTEK = 100000057  
KATEGORI_TESIS = 100000171           
ALT_KATEGORI_TESIS_ILETISIM = 100000702 

ATTR_ISLEM_TARIHI = 100000037
ATTR_KART_ILK_6 = 100000189
ATTR_KART_SON_4 = 100000190
ATTR_TUTAR = 100000192
ATTR_SIPARIS_NO = 100000194

# ==========================================
# 3. DOĞRULAMA VE KONTROL FONKSİYONLARI
# ==========================================
KUFUR_LISTESI = [
    "orospu", "amk", "aq", "salak", "aptal", "mal", "yarrak", 
    "fahişe", "piç", "göt", "sik", "sikim", "kahpe", "ibne", 
    "puşt", "yavşak", "oğlan", "sürtük"
]

def turkce_karakter_normalize(metin: str) -> str:
    metin = metin.lower()
    harf_map = {'ş': 's', 'ç': 'c', 'ğ': 'g', 'ü': 'u', 'ö': 'o', 'ı': 'i', 'i̇': 'i'}
    for k, v in harf_map.items():
        metin = metin.replace(k, v)
    return metin

def kufur_iceriyor_mu(metin: str) -> bool:
    metin_norm = turkce_karakter_normalize(metin)
    for kufur in KUFUR_LISTESI:
        kufur_norm = turkce_karakter_normalize(kufur)
        pattern = r'\b' + re.escape(kufur_norm) + r'\b'
        if re.search(pattern, metin_norm):
            return True
    return False

def tc_kimlik_gecerli_mi(tc: str) -> bool:
    """TC Kimlik Numarası matematiksel ve kuralsal doğrulaması yapar."""
    if not re.match(r'^[1-9]\d{10}$', tc):
        return False
    digits = [int(d) for d in tc]
    # Tüm haneleri aynı olamaz (Örn: 11111111111 geçersizdir)
    if len(set(digits)) == 1:
        return False
    
    # 1. 3. 5. 7. ve 9. hanelerin toplamının 7 katından 2. 4. 6. ve 8. hanelerin toplamı çıkarıldığında,
    # elde edilen sonucun 10'a bölümünden kalan 11. haneyi vermelidir.
    d_sum1 = sum(digits[0:9:2])
    d_sum2 = sum(digits[1:8:2])
    if (d_sum1 * 7 - d_sum2) % 10 != digits[9]:
        return False
    
    # İlk 10 hanenin toplamının 10'a bölümünden kalan 11. haneyi vermelidir.
    if sum(digits[:10]) % 10 != digits[10]:
        return False
        
    return True

def vkn_gecerli_mi(vkn: str) -> bool:
    """Vergi Kimlik Numarası (VKN) algoritma doğrulaması yapar."""
    if not re.match(r'^\d{10}$', vkn):
        return False
    if len(set(vkn)) == 1:
        return False
    # Basit VKN uzunluk ve hane kontrolü
    return True

def header_metni_coz(header_val: str) -> str:
    if not header_val:
        return ""
    sonuc = ""
    for content, encoding in decode_header(header_val):
        if isinstance(content, bytes):
            enc = encoding if encoding else "utf-8"
            try:
                sonuc += content.decode(enc, errors="ignore")
            except Exception:
                sonuc += content.decode("iso-8859-9", errors="ignore")
        else:
            sonuc += str(content)
    return sonuc.strip()

def otomatik_mail_gonder(alici_email: str, orijinal_konu: str, icerik_metni: str):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = alici_email
        msg['Subject'] = f"Re: {orijinal_konu} - BİLDİRİM: Talebiniz İşleme Alınamadı"

        body = f"Sayın Müşterimiz,\n\n{icerik_metni}\n\nİyi günler dileriz."
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, alici_email, msg.as_string())
        server.quit()
        print(f"[OTOMATİK BİLDİRİDİ MAİLİ GÖNDERİLDİ] -> {alici_email}")
    except Exception as e:
        print(f"Mail gönderilirken hata oluştu: {e}")

# ==========================================
# 4. FATURA ATTRIBUTE AYRIŞTIRICI VE DOĞRULAYICI
# ==========================================
def fatura_attributelarini_ayristir(metin: str, gonderen_email: str) -> tuple:
    attribute_list = []
    eksik_alanlar = []

    # Şahıs Adı Kontrolü
    sahis_match = re.search(r'(?:şahıs\s*adı|sahis\s*adi|ad\s*soyad|isim|mükellef)[:\s]*([a-zA-ZğüşıöçĞÜŞİÖÇ\s]+?)(?:\r?\n|tc|vkn|fatura|$)', metin, re.IGNORECASE)
    if sahis_match:
        sahis_adi = sahis_match.group(1).strip()
        attribute_list.append({"attribute": {"id": 100000230, "shortCode": "SIRKET_ADI_SAHIS_ADI"}, "lovItem": {"id": 100054903, "name": "Şahıs Adı", "shortCode": "SAHIS_ADI"}})
        attribute_list.append({"attribute": {"id": 100000237, "shortCode": "SAHIS_ADI"}, "textValue": sahis_adi})
    else:
        eksik_alanlar.append("Şahıs Adı-Soyadı")

    # TC / VKN Kontrolü ve Algoritma Doğrulaması
    tc_match = re.search(r'(?:tc|tckn|tc\s*no|kimlik\s*no)[:\s]*(\d{11})\b', metin, re.IGNORECASE)
    vkn_match = re.search(r'(?:vkn|vergi\s*no|vergi\s*kimlik)[:\s]*(\d{10})\b', metin, re.IGNORECASE)

    if tc_match:
        tc_val = tc_match.group(1)
        if tc_kimlik_gecerli_mi(tc_val):
            attribute_list.append({"attribute": {"id": 100000231, "shortCode": "VERGI_NUMARASI_TC_NUMARASI"}, "lovItem": {"id": 100054900, "name": "TC Kimlik Numarası", "shortCode": "TC_KIMLIK_NUMARASI"}})
            attribute_list.append({"attribute": {"id": 100000236, "shortCode": "TC_KIMLIK_NUMARASI"}, "textValue": int(tc_val)})
        else:
            eksik_alanlar.append("Geçerli Bir TC Kimlik Numarası (Hatalı veya sahte TC girdiniz)")
    elif vkn_match:
        vkn_val = vkn_match.group(1)
        if vkn_gecerli_mi(vkn_val):
            attribute_list.append({"attribute": {"id": 100000231, "shortCode": "VERGI_NUMARASI_TC_NUMARASI"}, "lovItem": {"id": 100054901, "name": "Vergi Kimlik Numarası", "shortCode": "VERGI_KIMLIK_NUMARASI"}})
            attribute_list.append({"attribute": {"id": 100000235, "shortCode": "VERGI_KIMLIK_NUMARASI"}, "textValue": int(vkn_val)})
        else:
            eksik_alanlar.append("Geçerli Bir Vergi Kimlik Numarası (VKN)")
    else:
        eksik_alanlar.append("TC Kimlik Numarası veya Vergi Kimlik Numarası (VKN)")

    # Fatura Adresi Kontrolü
    adres_match = re.search(r'(?:fatura\s*adresi|adres)[:\s]*([a-zA-ZğüşıöçĞÜŞİÖÇ0-9\s/.,:-]+?)(?=\r?\n\s*(?:fatura\s*mail|mail|iyi|saygılarla|$))', metin, re.IGNORECASE)
    if not adres_match:
        adres_match = re.search(r'(?:fatura\s*adresi|adres)[:\s]*([^\n]+)', metin, re.IGNORECASE)

    if adres_match:
        fatura_adresi = adres_match.group(1).strip()
        fatura_adresi = re.split(r'fatura\s*mail|mail:', fatura_adresi, flags=re.IGNORECASE)[0].strip()
        attribute_list.append({"attribute": {"id": 100000233, "shortCode": "FATURA_ADRESI"}, "textValue": fatura_adresi})
    else:
        eksik_alanlar.append("Fatura Adresi")

    # E-Posta Kontrolü
    eposta_match = re.search(r'(?:fatura\s*e-?posta|fatura\s*mail|mail)[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', metin, re.IGNORECASE)
    fatura_email = eposta_match.group(1) if eposta_match else gonderen_email
    attribute_list.append({"attribute": {"id": 100000234, "shortCode": "E-_POSTA"}, "textValue": fatura_email})

    return attribute_list, eksik_alanlar

# ==========================================
# 5. KIRILIM TESPİT MOTORU
# ==========================================
def kirilim_belirle(konu: str, icerik: str, gonderen_email: str) -> dict:
    ham_metin = f"{konu} {icerik}"
    metin = turkce_karakter_normalize(ham_metin)

    fatura_kelimeleri = ["fatura", "efatura", "e-fatura"]
    if any(f in metin for f in fatura_kelimeleri):
        attributes, eksik_alanlar = fatura_attributelarini_ayristir(ham_metin, gonderen_email)
        return {
            "channel_id": KANAL_ID,
            "channel_name": "Mail",
            "ticket_type_id": TICKET_TIPI_SIKAYET,
            "ticket_type_name": "Şikayet",
            "category_id": KATEGORI_FATURA,
            "category_name": "Fatura",
            "sub_category_id": ALT_KATEGORI_FATURA_TALEBI_SIKAYET,
            "sub_category_name": "Fatura Talebi Ve Şikayetleri",
            "sub_category_code": "FATURA_TALEBI_SIKAYETLERI",
            "attributes": attributes,
            "eksik_alanlar": eksik_alanlar,
            "tanim": "SIKAYET > FATURA > FATURA_TALEBI_SIKAYETLERI"
        }

    tesekkur_kelimeleri = ["tesekkur", "sagol", "tesekkurler", "tesekkur ederim", "teşekkur"]
    if any(w in metin for w in tesekkur_kelimeleri):
        if any(word in metin for word in ["rehber", "tur lideri", "oguz", "rehbere"]):
            alt_kat, alt_name, alt_code = ALT_KATEGORI_REHBER_TESEKKUR, "Rehber Teşekkür", "REHBER_TESEKKUR"
        elif any(word in metin for word in ["danisman", "temsilci", "cagri merkezi", "telefondaki"]):
            alt_kat, alt_name, alt_code = ALT_KATEGORI_DANISMAN_TESEKKUR, "Danışman Teşekkür", "DANISMAN_TESEKKUR"
        else:
            alt_kat, alt_name, alt_code = ALT_KATEGORI_GENEL_TESEKKUR, "Genel Teşekkür", "GENEL_TESEKKUR"

        return {
            "channel_id": KANAL_ID,
            "channel_name": "Mail",
            "ticket_type_id": TICKET_TIPI_TESEKKUR,
            "ticket_type_name": "Teşekkür",
            "category_id": KATEGORI_TESEKKUR,
            "category_name": "Teşekkür",
            "sub_category_id": alt_kat,
            "sub_category_name": alt_name,
            "sub_category_code": alt_code,
            "attributes": [],
            "eksik_alanlar": [],
            "tanim": f"TESEKKUR > TESEKKUR > {alt_code}"
        }

    return {
        "channel_id": KANAL_ID,
        "channel_name": "Mail",
        "ticket_type_id": TICKET_TIPI_BILGI_ISTEK,
        "ticket_type_name": "Bilgi-İstek",
        "category_id": KATEGORI_TESIS,
        "category_name": "Tesis",
        "sub_category_id": ALT_KATEGORI_TESIS_ILETISIM,
        "sub_category_name": "Tesis İletişim",
        "sub_category_code": "TESIS_ILETISIM",
        "attributes": [],
        "eksik_alanlar": [],
        "tanim": "GENEL (Varsayılan Bilgi-İstek)"
    }

# ==========================================
# 6. CSM PAYLOAD OLUŞTURUCU
# ==========================================
def csm_ticket_payload_olustur(gonderen_email: str, gonderen_adi: str, konu: str, icerik: str, kirilim: dict) -> dict:
    temiz_tam_isim = header_metni_coz(gonderen_adi) if gonderen_adi else "Oğuz Karagüney"
    isim_parcalari = temiz_tam_isim.split()
    
    if len(isim_parcalari) > 1:
        first_name = " ".join(isim_parcalari[:-1])
        last_name = isim_parcalari[-1]
    else:
        first_name = temiz_tam_isim if temiz_tam_isim else "Oğuz"
        last_name = "Karagüney"

    contact_medium_item = {
        "contactMediumType": {
            "id": 10000005,
            "uuid": "c38936ac-7e2c-46e7-aacc-deca59e132bf",
            "shortCode": "EMAIL"
        },
        "val": gonderen_email,
        "isPrimary": True,
        "externalId": None
    }

    party_role_obj = {
        "party": {
            "firstName": first_name,
            "lastName": last_name,
            "nationalityId": None,
            "partyType": "INDIVIDUAL",
            "fullName": f"{first_name} {last_name}",
            "preferredLanguage": {
                "country": None,
                "createDate": "2021-06-23T20:39:15.028Z",
                "displayLanguage": "Türkçe",
                "id": 1000001,
                "language": "tr",
                "rtl": None,
                "status": 1,
                "updateDate": None
            }
        },
        "partyRoleType": {
            "id": 1000022,
            "uuid": "4b7fc8ce-289c-476f-92d0-9279e7199983",
            "shortCode": "CSM_USER",
            "ownerType": True
        },
        "externalId": None,
        "attributeValueList": [],
        "contactMediumList": [contact_medium_item]
    }

    return {
        "contactParties": [
            {
                "partyRole": party_role_obj,
                "contactMediumList": [
                    {
                        "contactMedium": contact_medium_item,
                        "isPreferred": True
                    }
                ],
                "isPreferred": True,
                "preferredContactChannelList": ["EMAIL"]
            }
        ],
        "attributeList": kirilim.get("attributes", []),
        "attributeSetList": [{"attributeSet": {"shortCode": "REKLAMASYON"}, "attributeList": []}],
        "ticketRelationList": [],
        "subTicketList": [],
        "availableOperations": [],
        "stage": {"shortCode": "START"},
        "partyRole": party_role_obj,
        "description": icerik,
        "channel": {
            "shortCode": "MAIL",
            "name": kirilim["channel_name"],
            "id": kirilim["channel_id"],
            "uuid": "e0ebda2b-28da-4ee7-a5c9-1d111e72e232"
        },
        "subCategory": {
            "shortCode": kirilim["sub_category_code"],
            "name": kirilim["sub_category_name"],
            "id": kirilim["sub_category_id"],
            "uuid": "a8e13665-8d0c-41bc-b3f7-c2ce489d2458"
        },
        "category": {
            "shortCode": "FATURA",
            "name": kirilim["category_name"],
            "id": kirilim["category_id"],
            "uuid": "5e9ef86d-90d3-4efc-a8f4-dbd29eb132ea"
        },
        "ticketType": {
            "shortCode": "SIKAYET" if kirilim["ticket_type_id"] == TICKET_TIPI_SIKAYET else "TESEKKUR",
            "name": kirilim["ticket_type_name"],
            "id": kirilim["ticket_type_id"],
            "uuid": "a01dabb1-c18d-4781-80ab-ed2bdf841d1f"
        },
        "priorityLevel": {
            "shortCode": "NORMAL",
            "name": "Normal",
            "ordinal": 3,
            "id": 100000037,
            "uuid": "074266b0-efdf-45a1-ab26-75a627a4b5ed"
        },
        "isResolved": False,
        "isProactive": False,
        "isParent": True,
        "reminders": [],
        "detectedLanguage": ""
    }

# ==========================================
# 7. HTTP POST VE TICKET ID OKUMA
# ==========================================
def csm_ticket_olustur_post(payload: dict) -> bool:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "tr,en;q=0.9,en-US;q=0.8,tr-TR;q=0.7",
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Multilanguage": "true",
        "Origin": "https://tatilbudur-new-ui.cloudcsmetiya.com",
        "Referer": "https://tatilbudur-new-ui.cloudcsmetiya.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
        "userMode": "LEAD"
    }

    try:
        payload_json = json.dumps(payload, ensure_ascii=False)
        files = {
            'ticket': ('blob', payload_json.encode('utf-8'), 'application/json; charset=utf-8')
        }
        
        response = requests.post(CSM_CREATE_TICKET_URL, files=files, headers=headers)
        
        if response.status_code in [200, 201]:
            try:
                res_data = response.json()
                ticket_id = res_data.get("id") or res_data.get("ticketNo") or res_data.get("idNum") or "Oluşturuldu"
                print(f"🚀 [BAŞARILI] CSM üzerinde Ticket açıldı! Ticket ID: #{ticket_id}")
            except Exception:
                print("🚀 [BAŞARILI] CSM üzerinde Ticket açıldı!")
            return True
        else:
            print(f"⚠️ [HATA] CSM İsteği Başarısız. Kodu: {response.status_code} - Yanıt: {response.text}")
            return False
    except Exception as e:
        print(f"❌ CSM POST isteğinde istisna oluştu: {e}")
        return False

# ==========================================
# 8. ANA MAİL TARAMA VE İŞLEME MOTORU
# ==========================================
def gelen_mailleri_isle():
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox")

        status, messages = mail.search(None, 'UNSEEN')
        mail_ids = messages[0].split()

        if not mail_ids:
            print("📌 Okunmamış (UNSEEN) mail bulunamadı. Son gelen mailler taranıyor...\n")
            status, all_messages = mail.search(None, 'ALL')
            all_ids = all_messages[0].split()
            if all_ids:
                mail_ids = all_ids[-1:]
            else:
                print("İşlenecek hiçbir mail bulunamadı.")
                return

        print(f"Toplam {len(mail_ids)} adet mail işleme alındı.\n")

        for mail_id in mail_ids:
            status, msg_data = mail.fetch(mail_id, "(RFC822)")
            
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    subject = header_metni_coz(msg["Subject"]) if msg["Subject"] else ""
                    raw_from = msg.get("From", "")
                    parsed_addr = email.utils.parseaddr(raw_from)
                    
                    from_email = parsed_addr[1]
                    from_name = header_metni_coz(parsed_addr[0])

                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")):
                                charset = part.get_content_charset() or 'utf-8'
                                body = part.get_payload(decode=True).decode(charset, errors="ignore")
                                break
                    else:
                        charset = msg.get_content_charset() or 'utf-8'
                        body = msg.get_payload(decode=True).decode(charset, errors="ignore")

                    temiz_konu = re.sub(r'^(re|fwd|fw)[:\s]*', '', subject.strip(), flags=re.IGNORECASE)

                    print("--------------------------------------------------")
                    print(f"Gönderen : {from_email} ({from_name})")
                    print(f"Konu     : {subject.strip()}")

                    if kufur_iceriyor_mu(f"{temiz_konu} {body}"):
                        print("❌ SONUÇ: Mail küfür/hakaret içeriyor!")
                        print("❌ Ticket oluşturulamadı.")
                        otomatik_mail_gonder(
                            from_email, 
                            subject.strip(), 
                            "Göndermiş olduğunuz e-posta uygunsuz ifadeler / hakaret içerdiği tespit edildiği için talebiniz reddedilmiş ve ticket oluşturulmamıştır."
                        )
                    else:
                        kirilim = kirilim_belirle(temiz_konu, body, from_email)
                        print("✅ SONUÇ: İçerik Temiz.")
                        print(f"📌 Seçilen Kırılım : {kirilim['tanim']}")

                        # ZORUNLU VEYA HATALI ALAN KONTROLÜ
                        if kirilim.get("eksik_alanlar"):
                            eksik_listesi_str = "\n".join([f"- {alan}" for alan in kirilim["eksik_alanlar"]])
                            print("⚠️ EKSİK VEYA HATALI BİLGİ TESPİT EDİLDİ! Ticket açılmayacak, bilgilendirme maili gönderiliyor...")
                            print(f"Hatalı/Eksik Alanlar:\n{eksik_listesi_str}")
                            
                            mail_metni = (
                                f"Sayın Müşterimiz,\n\n"
                                f"Fatura talebinizin işleme alınabilmesi için ilettiğiniz bilgilerde eksiklik veya geçersizlik tespit edilmiştir:\n\n"
                                f"{eksik_listesi_str}\n\n"
                                f"Lütfen bilgileri (doğru TC Kimlik Numarası ve eksiksiz adres ile) tamamlayarak e-postamızı yanıtlayınız."
                            )
                            otomatik_mail_gonder(from_email, subject.strip(), mail_metni)

                        else:
                            payload = csm_ticket_payload_olustur(from_email, from_name, subject.strip(), body.strip(), kirilim)
                            csm_ticket_olustur_post(payload)
                    
                    print("--------------------------------------------------\n")

        mail.logout()

    except Exception as e:
        print(f"Mail işleme hatası: {e}")

if __name__ == "__main__":
    gelen_mailleri_isle()