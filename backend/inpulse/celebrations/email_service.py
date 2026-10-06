"""
Kutlama Email Servisi — İSO Pulse
Doğum günü ve işe giriş yıldönümü için HTML e-posta gönderir.
SMTP bağlantısı config.py'deki ayarlardan okunur.
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date
from typing import Literal

from config import get_settings

settings = get_settings()


def _dogum_gunu_html(ad_soyad: str) -> str:
    ad = ad_soyad.split()[0]
    return f"""
<!DOCTYPE html>
<html lang="tr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0"
             style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.07);">
        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#2563eb,#7c3aed);padding:40px 40px 32px;text-align:center;">
            <div style="font-size:56px;line-height:1;margin-bottom:16px;">🎂</div>
            <h1 style="color:#fff;margin:0;font-size:28px;font-weight:700;letter-spacing:-.5px;">
              Mutlu Yıllar, {ad}!
            </h1>
            <p style="color:rgba(255,255,255,.8);margin:8px 0 0;font-size:15px;">
              İSO Pulse ailesi olarak doğum günün kutlu olsun 🎉
            </p>
          </td>
        </tr>
        <!-- Body -->
        <tr>
          <td style="padding:36px 40px;">
            <p style="color:#374151;font-size:16px;line-height:1.7;margin:0 0 20px;">
              Merhaba <strong>{ad_soyad}</strong>,
            </p>
            <p style="color:#374151;font-size:16px;line-height:1.7;margin:0 0 20px;">
              Bu özel günde tüm İSO Pulse ekibi olarak seni kutluyor, sağlık, mutluluk ve başarılar diliyoruz!
              Senin gibi değerli bir ekip arkadaşımız olmaktan çok mutluyuz. 🌟
            </p>
            <div style="background:#eff6ff;border-left:4px solid #2563eb;border-radius:4px;
                        padding:16px 20px;margin:24px 0;">
              <p style="color:#1d4ed8;font-size:14px;margin:0;font-weight:600;">
                🎁 İK Ekibinden Özel Not
              </p>
              <p style="color:#374151;font-size:14px;margin:8px 0 0;line-height:1.6;">
                Bu güzel günde yanındayız. Platform üzerinden meslektaşlarından tebrik mesajları alabilirsin!
              </p>
            </div>
            <p style="color:#6b7280;font-size:14px;line-height:1.7;margin:24px 0 0;">
              Sevgilerle,<br>
              <strong style="color:#111827;">İSO Pulse İnsan Kaynakları Ekibi</strong>
            </p>
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="background:#f9fafb;padding:20px 40px;border-top:1px solid #f3f4f6;text-align:center;">
            <p style="color:#9ca3af;font-size:12px;margin:0;">
              Bu mesaj <strong>İSO Pulse</strong> platformu tarafından otomatik olarak gönderilmiştir.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def _yil_donumu_html(ad_soyad: str, kac_yil: int) -> str:
    ad = ad_soyad.split()[0]
    yil_metni = f"{kac_yil}. Yılın"
    return f"""
<!DOCTYPE html>
<html lang="tr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0"
             style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.07);">
        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#059669,#0284c7);padding:40px 40px 32px;text-align:center;">
            <div style="font-size:56px;line-height:1;margin-bottom:16px;">🏆</div>
            <h1 style="color:#fff;margin:0;font-size:28px;font-weight:700;letter-spacing:-.5px;">
              {yil_metni} Kutlu Olsun, {ad}!
            </h1>
            <p style="color:rgba(255,255,255,.8);margin:8px 0 0;font-size:15px;">
              {kac_yil} yıl boyunca İSO ailesinin bir parçası oldun 🌟
            </p>
          </td>
        </tr>
        <!-- Body -->
        <tr>
          <td style="padding:36px 40px;">
            <p style="color:#374151;font-size:16px;line-height:1.7;margin:0 0 20px;">
              Merhaba <strong>{ad_soyad}</strong>,
            </p>
            <p style="color:#374151;font-size:16px;line-height:1.7;margin:0 0 20px;">
              Bugün bizimle geçirdiğin <strong>{kac_yil}. yılın</strong>! İSO Pulse'a katkılarının ve ekibimize
              kattığın değerin için teşekkür ederiz. Senin gibi özverili bir çalışanımız olmaktan
              gurur duyuyoruz. 🎊
            </p>
            <div style="background:#ecfdf5;border-left:4px solid #059669;border-radius:4px;
                        padding:16px 20px;margin:24px 0;">
              <p style="color:#065f46;font-size:14px;margin:0;font-weight:600;">
                🌱 {kac_yil} Yıllık Yolculuk
              </p>
              <p style="color:#374151;font-size:14px;margin:8px 0 0;line-height:1.6;">
                Bu özel günde ekibinin tebrik mesajları platform üzerinden sana iletilecek.
                Geçmiş yıllardaki başarılarına yenilerini eklemeye devam et!
              </p>
            </div>
            <p style="color:#6b7280;font-size:14px;line-height:1.7;margin:24px 0 0;">
              Sevgilerle,<br>
              <strong style="color:#111827;">İSO Pulse İnsan Kaynakları Ekibi</strong>
            </p>
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="background:#f9fafb;padding:20px 40px;border-top:1px solid #f3f4f6;text-align:center;">
            <p style="color:#9ca3af;font-size:12px;margin:0;">
              Bu mesaj <strong>İSO Pulse</strong> platformu tarafından otomatik olarak gönderilmiştir.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def _peer_html(hedef_ad_soyad: str, gonderen_ad: str, tur: str, mesaj: str, kac_yil: int | None) -> str:
    """Akran (peer-to-peer) kutlama emaili HTML şablonu."""
    hedef_ad = hedef_ad_soyad.split()[0]
    if tur == "dogum_gunu":
        emoji, baslik, renk1, renk2 = "🎂", "Doğum Günün Kutlu Olsun!", "#2563eb", "#7c3aed"
        alt_baslik = "İş arkadaşından özel bir tebrik!"
    elif tur == "yil_donumu":
        emoji = "🏆"
        baslik = f"{kac_yil}. Yılın Kutlu Olsun!" if kac_yil else "Yıl Dönümün Kutlu Olsun!"
        renk1, renk2 = "#059669", "#0284c7"
        alt_baslik = f"{kac_yil} yıl boyunca harika bir iş arkadaşısın!" if kac_yil else ""
    else:
        emoji, baslik, renk1, renk2 = "🎉", "Tebrikler!", "#f59e0b", "#ef4444"
        alt_baslik = "İş arkadaşından sana özel bir mesaj var!"

    return f"""
<!DOCTYPE html>
<html lang="tr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0"
             style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.07);">
        <tr>
          <td style="background:linear-gradient(135deg,{renk1},{renk2});padding:40px 40px 32px;text-align:center;">
            <div style="font-size:56px;line-height:1;margin-bottom:16px;">{emoji}</div>
            <h1 style="color:#fff;margin:0;font-size:26px;font-weight:700;">{hedef_ad}, {baslik}</h1>
            <p style="color:rgba(255,255,255,.8);margin:8px 0 0;font-size:14px;">{alt_baslik}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:36px 40px;">
            <p style="color:#374151;font-size:16px;line-height:1.7;margin:0 0 20px;">
              Merhaba <strong>{hedef_ad_soyad}</strong>,
            </p>
            <div style="background:#f3f4f6;border-radius:12px;padding:20px 24px;margin:16px 0;">
              <p style="color:#111827;font-size:15px;line-height:1.7;margin:0;font-style:italic;">
                "{mesaj}"
              </p>
              <p style="color:#6b7280;font-size:13px;margin:12px 0 0;text-align:right;">
                — <strong>{gonderen_ad}</strong>
              </p>
            </div>
            <p style="color:#6b7280;font-size:14px;line-height:1.7;margin:24px 0 0;">
              Sevgilerle,<br>
              <strong style="color:#111827;">İSO Pulse Ekibi</strong>
            </p>
          </td>
        </tr>
        <tr>
          <td style="background:#f9fafb;padding:20px 40px;border-top:1px solid #f3f4f6;text-align:center;">
            <p style="color:#9ca3af;font-size:12px;margin:0;">
              Bu mesaj <strong>İSO Pulse</strong> platformu üzerinden <strong>{gonderen_ad}</strong> tarafından gönderilmiştir.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def send_peer_celebration_email(
    to_email: str,
    hedef_ad_soyad: str,
    gonderen_ad: str,
    tur: str,
    mesaj: str,
    kac_yil: int | None = None,
) -> bool:
    """Akran (peer-to-peer) kutlama emaili gönder."""
    if not to_email:
        return False

    if tur == "dogum_gunu":
        subject = f"🎂 {hedef_ad_soyad.split()[0]}, doğum günün kutlu olsun! 🎉"
    elif tur == "yil_donumu":
        subject = f"🏆 {hedef_ad_soyad.split()[0]}, {kac_yil}. yılın kutlu olsun!" if kac_yil else f"🏆 {hedef_ad_soyad.split()[0]}, yıl dönümün kutlu olsun!"
    else:
        subject = f"🎉 {hedef_ad_soyad.split()[0]}, sana özel bir mesaj var!"

    html_body = _peer_html(hedef_ad_soyad, gonderen_ad, tur, mesaj, kac_yil)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if settings.smtp_port == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ctx) as s:
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as s:
                s.ehlo()
                try:
                    s.starttls()
                    s.ehlo()
                except Exception:
                    pass
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        print(f"[Email] ✅ Peer kutlama maili gönderildi → {to_email}")
        return True
    except Exception as exc:
        print(f"[Email] ❌ Peer gönderim hatası ({to_email}): {exc}")
        return False


def send_test_email(to_email: str) -> bool:
    """SMTP bağlantı testi emaili gönder."""
    html_body = """
<!DOCTYPE html>
<html lang="tr">
<head><meta charset="UTF-8"></head>
<body style="font-family:'Segoe UI',Arial,sans-serif;background:#f8fafc;padding:40px;">
  <div style="max-width:500px;margin:0 auto;background:#fff;border-radius:12px;
              padding:32px;box-shadow:0 4px 16px rgba(0,0,0,.08);">
    <div style="font-size:48px;text-align:center;margin-bottom:16px;">✅</div>
    <h2 style="color:#059669;text-align:center;margin:0 0 12px;">SMTP Bağlantısı Başarılı</h2>
    <p style="color:#374151;font-size:15px;line-height:1.6;text-align:center;">
      İSO Pulse email servisi doğru yapılandırılmış ve çalışıyor.
    </p>
    <p style="color:#9ca3af;font-size:12px;text-align:center;margin-top:24px;">
      İSO Pulse Platform — Email Bağlantı Testi
    </p>
  </div>
</body>
</html>
"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "✅ İSO Pulse — SMTP Bağlantı Testi Başarılı"
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if settings.smtp_port == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ctx) as s:
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as s:
                s.ehlo()
                try:
                    s.starttls()
                    s.ehlo()
                except Exception:
                    pass
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        print(f"[Email] ✅ Test maili gönderildi → {to_email}")
        return True
    except Exception as exc:
        print(f"[Email] ❌ Test gönderim hatası ({to_email}): {exc}")
        return False


def send_celebration_email(
    to_email: str,
    ad_soyad: str,
    tur: Literal["dogum_gunu", "yil_donumu"],
    kac_yil: int | None = None,
) -> bool:
    """
    Kutlama e-postası gönder.
    Başarılıysa True, hata olursa False döner (uygulama durmaması için).
    """
    if not to_email:
        return False

    subject = (
        f"🎂 Doğum Günün Kutlu Olsun, {ad_soyad.split()[0]}!"
        if tur == "dogum_gunu"
        else f"🏆 {kac_yil}. İş Yılın Kutlu Olsun, {ad_soyad.split()[0]}!"
    )
    html_body = (
        _dogum_gunu_html(ad_soyad)
        if tur == "dogum_gunu"
        else _yil_donumu_html(ad_soyad, kac_yil or 1)
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if settings.smtp_port == 465:
            # SSL
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ctx) as s:
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        else:
            # STARTTLS (587) veya plain dev SMTP (1025)
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as s:
                s.ehlo()
                try:
                    s.starttls()
                    s.ehlo()
                except Exception:
                    pass  # dev SMTP TLS desteklemeyebilir
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)

        print(f"[Email] ✅ {tur} maili gönderildi → {to_email}")
        return True

    except Exception as exc:
        print(f"[Email] ❌ Gönderim hatası ({to_email}): {exc}")
        return False
