"""
E-posta Bildirimleri — Jinja2 şablonları + aiosmtplib
"""
import pathlib
from jinja2 import Environment, FileSystemLoader
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import get_settings

settings = get_settings()

_TEMPLATE_DIR = pathlib.Path(__file__).parent / "email_templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))

SABLON_KONULAR = {
    "yeni_talep": "Yeni İzin Talebi — {calisan}",
    "onaylandi": "İzin Talebiniz Onaylandı",
    "reddedildi": "İzin Talebiniz Reddedildi",
}


async def izin_bildir(kime: str, sablon: str, context: dict) -> None:
    """Verilen şablonla e-posta gönderir. Hata durumunda sessizce geçer."""
    try:
        template = _jinja_env.get_template(f"{sablon}.html")
        html_body = template.render(**context)

        konu_sablonu = SABLON_KONULAR.get(sablon, "İzin Bildirimi")
        konu = konu_sablonu.format(**context)

        msg = MIMEMultipart("alternative")
        msg["From"] = settings.smtp_from
        msg["To"] = kime
        msg["Subject"] = konu
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=False,
        )
    except Exception as exc:
        # Üretim ortamında logger.error ile kaydet
        print(f"[EMAIL] Bildirim gönderilemedi → {kime}: {exc}")
