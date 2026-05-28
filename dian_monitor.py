"""
=============================================================
  MONITOR DE CITAS DIAN - VERSION GITHUB ACTIONS
  Tramite  : Devoluciones
  Atencion : Videoatencion
  Persona  : Natural

  Este script corre UNA sola vez por ejecucion.
  GitHub Actions lo ejecuta cada 5 minutos.
  El TOKEN y CHAT_ID se leen de variables de entorno
  (GitHub Secrets) - no se guardan en el codigo.
=============================================================
"""

import asyncio
import logging
import os
import requests
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# -------------------------------------------------------------
#  CONFIGURACION - se lee de GitHub Secrets
# -------------------------------------------------------------

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
URL_DIAN         = "https://agendamiento.dian.gov.co/"

# -------------------------------------------------------------
#  LOGGING
# -------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger(__name__)

# -------------------------------------------------------------
#  TELEGRAM
# -------------------------------------------------------------

def enviar_telegram(mensaje: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.error("Telegram: TOKEN o CHAT_ID no configurados")
        return
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
                return True

            elif modal_visible:
                log.info("Sin citas disponibles")
                return False

            else:
                log.warning("Estado indeterminado, verificando nuevamente...")
                await page.wait_for_timeout(5000)

                modal_visible  = await page.is_visible("[pantalla='ModalError']")
                select_visible = await page.is_visible("[nombre='Servicios']")

                if select_visible:
                    return True
                elif modal_visible:
                    return False
                else:
                    log.error("No se pudo determinar el estado")
                    return None

        except PlaywrightTimeoutError as e:
            log.error(f"Timeout: {e}")
            return None

        except Exception as e:
            log.error(f"Error inesperado: {e}")
            return None

        finally:
            await browser.close()

# -------------------------------------------------------------
#  EJECUCION UNICA
# -------------------------------------------------------------

async def main():
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    log.info("=" * 55)
    log.info("MONITOR DIAN - Ejecucion unica")
    log.info(f"Hora: {ahora}")
    log.info("=" * 55)

    resultado = await revisar_citas()

    if resultado is True:
        enviar_telegram(
            "<b>CITAS DISPONIBLES - DIAN</b>\n\n"
            "Tramite: Devoluciones\n"
            "Tipo: Videoatencion\n"
            "Persona: Natural\n\n"
            "Ingrese a agendar su cita:\n"
            "https://agendamiento.dian.gov.co/\n\n"
            f"Detectado: {ahora}"
        )
        log.info("Alerta de citas enviada a Telegram")

    elif resultado is False:
        log.info("Sin disponibilidad en esta revision")

    else:
        log.warning("Error tecnico en esta revision")

if __name__ == "__main__":
    asyncio.run(main())
