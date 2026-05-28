"""
=============================================================
  MONITOR DE CITAS DIAN - TELEGRAM
  Tramite  : Devoluciones
  Atencion : Videoatencion
  Persona  : Natural
  Intervalo: cada 2 minutos, 24/7
=============================================================
  INSTALACION (Anaconda Prompt):
    pip install playwright requests
    playwright install chromium

  USO:
    python dian_bot.py
=============================================================
"""

import asyncio
import logging
import requests
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# -------------------------------------------------------------
#  CONFIGURACION
# -------------------------------------------------------------

TELEGRAM_TOKEN   = "PEGA_TU_TOKEN_AQUI"
TELEGRAM_CHAT_ID = "PEGA_TU_CHAT_ID_AQUI"

INTERVALO_MINUTOS = 2
URL_DIAN          = "https://agendamiento.dian.gov.co/"

# -------------------------------------------------------------
#  LOGGING
# -------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("dian_bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# -------------------------------------------------------------
#  TELEGRAM
# -------------------------------------------------------------

def enviar_telegram(mensaje: str):
    url     = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            log.info("Telegram: mensaje enviado correctamente")
        else:
            log.error(f"Telegram: error {r.status_code} - {r.text}")
    except Exception as e:
        log.error(f"Telegram: excepcion - {e}")

# -------------------------------------------------------------
#  REVISION DE CITAS
# -------------------------------------------------------------

async def revisar_citas() -> bool | None:
    """
    Navega la pagina DIAN y detecta disponibilidad de citas.
    Retorna:
        True  : hay citas disponibles
        False : no hay citas (modal de error detectado)
        None  : error tecnico
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        try:
            log.info("Cargando pagina DIAN...")
            await page.goto(URL_DIAN, wait_until="networkidle", timeout=40000)
            log.info("Pagina cargada")

            # Paso 1: Agendar cita
            await page.wait_for_selector("[nombre='btnSolicitarCita']", timeout=20000)
            await page.click("[nombre='btnSolicitarCita']")
            log.info("Paso 1 completado: Agendar cita")
            await page.wait_for_timeout(1500)

            # Paso 2: Persona Natural
            await page.wait_for_selector(".btnTipoPersona[llave='1']", timeout=15000)
            await page.click(".btnTipoPersona[llave='1']")
            log.info("Paso 2 completado: Persona Natural")
            await page.wait_for_timeout(1000)

            # Paso 3: Videoatencion
            await page.wait_for_selector(".btnTipoAtencion[llave='2']", timeout=15000)
            await page.click(".btnTipoAtencion[llave='2']")
            log.info("Paso 3 completado: Videoatencion")
            await page.wait_for_timeout(1000)

            # Paso 4: Devoluciones
            await page.wait_for_selector(
                ".btnCategoria[llave='63071985-f5bd-43fe-beed-38f64c97371b']",
                timeout=15000
            )
            await page.click(".btnCategoria[llave='63071985-f5bd-43fe-beed-38f64c97371b']")
            log.info("Paso 4 completado: Devoluciones")
            await page.wait_for_timeout(4000)

            # Paso 5: Detectar resultado
            modal_visible  = await page.is_visible("[pantalla='ModalError']")
            select_visible = await page.is_visible("[nombre='Servicios']")

            log.info(f"Resultado - Modal error: {modal_visible} | Select disponible: {select_visible}")

            if select_visible:
                log.info("CITAS DISPONIBLES detectadas")
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                await page.screenshot(path=f"cita_disponible_{ts}.png")
                log.info(f"Captura guardada: cita_disponible_{ts}.png")
                return True

            elif modal_visible:
                log.info("Sin citas disponibles")
                await page.click("#control_36")
                return False

            else:
                # Segunda verificacion con espera adicional
                log.warning("Estado indeterminado, verificando nuevamente...")
                await page.wait_for_timeout(5000)

                modal_visible  = await page.is_visible("[pantalla='ModalError']")
                select_visible = await page.is_visible("[nombre='Servicios']")

                log.info(f"Segunda verificacion - Modal: {modal_visible} | Select: {select_visible}")

                if select_visible:
                    return True
                elif modal_visible:
                    await page.click("#control_36")
                    return False
                else:
                    log.error("No se pudo determinar el estado de disponibilidad")
                    return None

        except PlaywrightTimeoutError as e:
            log.error(f"Timeout al cargar elemento: {e}")
            return None

        except Exception as e:
            log.error(f"Error inesperado: {e}")
            return None

        finally:
            await browser.close()

# -------------------------------------------------------------
#  LOOP PRINCIPAL
# -------------------------------------------------------------

async def main():
    log.info("=" * 55)
    log.info("MONITOR DE CITAS DIAN - INICIADO")
    log.info(f"Tramite   : Devoluciones")
    log.info(f"Atencion  : Videoatencion")
    log.info(f"Persona   : Natural")
    log.info(f"Intervalo : cada {INTERVALO_MINUTOS} minutos")
    log.info("=" * 55)

    enviar_telegram(
        "<b>Monitor de Citas DIAN - Iniciado</b>\n\n"
        "Tramite: Devoluciones\n"
        "Tipo: Videoatencion\n"
        "Persona: Natural\n"
        f"Intervalo: cada {INTERVALO_MINUTOS} minutos\n\n"
        "Se notificara cuando haya citas disponibles."
    )

    intento = 0
    while True:
        intento += 1
        ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        log.info(f"Revision #{intento} | {ahora}")

        resultado = await revisar_citas()

        if resultado is True:
            enviar_telegram(
                "<b>CITAS DISPONIBLES - DIAN</b>\n\n"
                "Tramite: Devoluciones\n"
                "Tipo: Videoatencion\n"
                "Persona: Natural\n\n"
                "Ingrese a agendar su cita:\n"
                "https://agendamiento.dian.gov.co/\n\n"
                f"Detectado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            )
            log.info("Alerta enviada a Telegram. Proxima revision en 1 minuto.")
            await asyncio.sleep(60)

        elif resultado is False:
            log.info(f"Sin disponibilidad. Proxima revision en {INTERVALO_MINUTOS} minutos.")
            await asyncio.sleep(INTERVALO_MINUTOS * 60)

        else:
            log.warning("Error tecnico. Reintentando en 1 minuto.")
            enviar_telegram(
                "<b>Monitor DIAN - Aviso</b>\n\n"
                "Error tecnico al revisar la pagina.\n"
                "Reintentando en 1 minuto."
            )
            await asyncio.sleep(60)

# -------------------------------------------------------------
#  ENTRADA
# -------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())
