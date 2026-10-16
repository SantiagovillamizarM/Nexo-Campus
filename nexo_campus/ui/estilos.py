"""Tema corporativo de la interfaz: base negra, acentos Ultramarino y un cielo estrellado discreto."""

import random

import streamlit as st

# Paleta Ultramarino (de la más oscura a la más clara)
ULTRAMARINO = {
    "abismo": "#071039",
    "noche": "#0F2270",
    "cobalto": "#1A3BB0",
    "azul": "#2E5DE6",
    "cielo": "#6E92F2",
    "bruma": "#AFC5F8",
    "luz": "#E6EDFD",
}

# Neutros oscuros: la base de la interfaz es casi negra y el azul queda como acento.
NEUTROS = {
    "negro": "#05070D",
    "carbon": "#0A0D16",
    "superficie": "#0E1220",
    "superficie_alta": "#141A2B",
    "gris": "#8A94B0",
}

COLORES = {
    "fondo": NEUTROS["negro"],
    "superficie": NEUTROS["superficie"],
    "primario": ULTRAMARINO["azul"],
    "primario_claro": ULTRAMARINO["cielo"],
    "texto": ULTRAMARINO["luz"],
    "tenue": NEUTROS["gris"],
    # Colores de estado, sobrios, para distinguir disponible / alerta / fuera de servicio.
    "exito": "#3FB98A",
    "info": ULTRAMARINO["cielo"],
    "alerta": "#E0A43B",
    "peligro": "#E06C6C",
}

COLORES_ESTRELLAS = ("#FFFFFF", ULTRAMARINO["luz"], ULTRAMARINO["bruma"])


def _capa_estrellas(cantidad: int, semilla: int, desenfoque: str = "0") -> str:
    """Estrellas de una capa como sombras de un solo punto (CSS puro, sin imágenes).

    La semilla fija evita que cambien de lugar cada vez que Streamlit redibuja la página.
    """
    azar = random.Random(semilla)
    return ", ".join(
        f"{azar.uniform(0, 100):.2f}vw {azar.uniform(0, 100):.2f}vh {desenfoque} {azar.choice(COLORES_ESTRELLAS)}"
        for _ in range(cantidad)
    )


def _destellos(cantidad: int, semilla: int) -> str:
    """Pocas estrellas de cuatro puntas (✦), pequeñas y lentas."""
    azar = random.Random(semilla)
    return "".join(
        '<span class="nc-destello" style="'
        f"left:{azar.uniform(20, 97):.1f}%;top:{azar.uniform(4, 95):.1f}%;"
        f"font-size:{azar.uniform(8, 13):.0f}px;color:{azar.choice(COLORES_ESTRELLAS)};"
        f"animation-duration:{azar.uniform(6, 10):.1f}s;animation-delay:-{azar.uniform(0, 10):.1f}s"
        '">✦</span>'
        for _ in range(cantidad)
    )


_CIELO = (
    '<div class="nc-cielo" aria-hidden="true">'
    '<div class="nc-nebulosa nc-nebulosa-1"></div>'
    '<div class="nc-nebulosa nc-nebulosa-2"></div>'
    '<div class="nc-estrellas nc-estrellas-1"></div>'
    '<div class="nc-estrellas nc-estrellas-2"></div>'
    '<div class="nc-estrellas nc-estrellas-3"></div>'
    f"{_destellos(14, semilla=11)}"
    '<div class="nc-planeta nc-planeta-mayor"><div class="nc-luna"></div></div>'
    '<div class="nc-planeta nc-planeta-anillo"></div>'
    '<span class="nc-fugaz" style="top:10%;left:82%;animation-delay:3s"></span>'
    '<span class="nc-fugaz" style="top:42%;left:98%;animation-delay:11s;animation-duration:21s"></span>'
    '<span class="nc-fugaz" style="top:24%;left:60%;animation-delay:17s;animation-duration:26s"></span>'
    "</div>"
)

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --nc-negro: #05070D;
  --nc-superficie: rgba(14, 18, 32, .55);
  --nc-vidrio: blur(12px) saturate(125%%);
  --nc-superficie-alta: #141A2B;
  --nc-campo: #0A0D16;
  --nc-borde: rgba(175, 197, 248, .09);
  --nc-borde-fuerte: rgba(175, 197, 248, .18);
  --nc-azul: #2E5DE6;
  --nc-cobalto: #1A3BB0;
  --nc-cielo: #6E92F2;
  --nc-bruma: #AFC5F8;
  --nc-luz: #E6EDFD;
  --nc-gris: #8A94B0;
}

html, body, [class*="css"], .stMarkdown, button, input, textarea { font-family: 'Inter', system-ui, sans-serif; }

/* --- Fondo: negro con un leve resplandor azul --- */
.stApp {
  background:
    radial-gradient(ellipse 55%% 40%% at 30%% -5%%, rgba(26, 59, 176, .16), transparent 70%%),
    radial-gradient(ellipse 40%% 35%% at 100%% 10%%, rgba(15, 34, 112, .22), transparent 70%%),
    var(--nc-negro);
  background-attachment: fixed;
}
[data-testid="stAppViewContainer"], [data-testid="stHeader"] { background: transparent; }
.block-container { position: relative; z-index: 1; padding-top: 2rem; padding-bottom: 2rem; max-width: 1360px; }

/* --- Cielo: estrellas, planetas y estrellas fugaces, detrás del contenido --- */
.element-container:has(.nc-cielo), [data-testid="stElementContainer"]:has(.nc-cielo) { position: absolute; height: 0; margin: 0; }
.nc-cielo { position: fixed; inset: 0; z-index: -1; overflow: hidden; pointer-events: none; }
.nc-estrellas { position: absolute; top: 0; left: 0; border-radius: 50%%; }
.nc-estrellas-1 { width: 1px; height: 1px; box-shadow: %(capa1)s; opacity: .55; animation: nc-titilar 9s ease-in-out infinite alternate; }
.nc-estrellas-2 { width: 1.5px; height: 1.5px; box-shadow: %(capa2)s; opacity: .7; animation: nc-titilar 6s ease-in-out infinite alternate-reverse; }
.nc-estrellas-3 { width: 2px; height: 2px; box-shadow: %(capa3)s; animation: nc-titilar 4.5s ease-in-out infinite alternate; }
.nc-destello {
  position: absolute; line-height: 1; opacity: .5;
  text-shadow: 0 0 6px rgba(175, 197, 248, .8), 0 0 14px rgba(110, 146, 242, .5);
  animation: nc-destellar ease-in-out infinite;
}

/* Nebulosas: nubes de color muy tenues que se desplazan lentamente */
.nc-nebulosa { position: absolute; border-radius: 50%%; filter: blur(70px); }
.nc-nebulosa-1 {
  width: 620px; height: 420px; left: 18%%; top: -8%%;
  background: radial-gradient(closest-side, rgba(46, 93, 230, .20), transparent);
  animation: nc-deriva 70s ease-in-out infinite alternate;
}
.nc-nebulosa-2 {
  width: 520px; height: 380px; right: 8%%; top: 38%%;
  background: radial-gradient(closest-side, rgba(110, 72, 230, .13), rgba(26, 59, 176, .08) 60%%, transparent);
  animation: nc-deriva 90s ease-in-out infinite alternate-reverse;
}

/* Planeta mayor: bandas de superficie que giran, terminador de sombra, tormentas y atmósfera */
.nc-planeta { position: absolute; border-radius: 50%%; }
.nc-planeta-mayor {
  width: 620px; height: 620px; right: -230px; bottom: -330px;
  background:
    radial-gradient(circle at 28%% 24%%, rgba(175, 197, 248, .14), transparent 32%%),
    repeating-linear-gradient(-24deg,
      rgba(110, 146, 242, .045) 0 12px, transparent 12px 30px,
      rgba(7, 16, 57, .30) 30px 46px, transparent 46px 70px,
      rgba(175, 197, 248, .025) 70px 78px, transparent 78px 104px),
    radial-gradient(circle at 34%% 30%%, #1F2C57 0%%, #121B40 30%%, #0A102B 58%%, #05070D 82%%);
  background-size: 100%% 100%%, 420px 420px, 100%% 100%%;
  box-shadow:
    inset -110px -80px 130px rgba(0, 0, 0, .94),
    inset 8px 8px 22px rgba(175, 197, 248, .22),
    0 0 0 1px rgba(110, 146, 242, .12),
    0 0 110px 18px rgba(46, 93, 230, .16);
  animation: nc-flotar 60s ease-in-out infinite alternate, nc-rotar-superficie 140s linear infinite;
}
.nc-planeta-mayor::before {
  content: ""; position: absolute; inset: 0; border-radius: 50%%;
  background:
    radial-gradient(ellipse 60px 26px at 38%% 40%%, rgba(175, 197, 248, .14), transparent 70%%),
    radial-gradient(ellipse 34px 14px at 52%% 30%%, rgba(110, 146, 242, .16), transparent 70%%),
    radial-gradient(ellipse 80px 30px at 30%% 58%%, rgba(7, 16, 57, .45), transparent 70%%);
  mix-blend-mode: screen;
}
.nc-planeta-mayor::after {
  content: ""; position: absolute; inset: -22px; border-radius: 50%%;
  background: radial-gradient(circle closest-side, transparent 91%%, rgba(110, 146, 242, .28) 95%%, rgba(110, 146, 242, .08) 98%%, transparent 100%%);
}
.nc-luna {
  position: absolute; top: 50%%; left: 50%%; width: 16px; height: 16px; margin: -8px 0 0 -8px; border-radius: 50%%;
  background: radial-gradient(circle at 35%% 30%%, #C9D6F8, #5E6F99 55%%, #1B2338);
  box-shadow: 0 0 10px rgba(175, 197, 248, .35);
  animation: nc-orbitar 95s linear infinite;
}
.nc-planeta-anillo {
  width: 60px; height: 60px; left: 34%%; top: 74%%; opacity: .75;
  background:
    repeating-linear-gradient(-18deg, rgba(175, 197, 248, .10) 0 3px, transparent 3px 8px),
    radial-gradient(circle at 35%% 30%%, #3A4A7A, #17204A 55%%, #070A12);
  box-shadow: inset -12px -9px 16px rgba(0, 0, 0, .8), inset 2px 2px 5px rgba(175, 197, 248, .25), 0 0 18px rgba(46, 93, 230, .18);
  animation: nc-flotar 45s ease-in-out infinite alternate-reverse;
}
.nc-planeta-anillo::before {
  content: ""; position: absolute; left: 50%%; top: 50%%; width: 120px; height: 26px;
  border: 1px solid rgba(175, 197, 248, .28); border-radius: 50%%;
  transform: translate(-50%%, -50%%) rotate(-18deg);
}
.nc-fugaz {
  position: absolute; width: 140px; height: 1px; opacity: 0;
  background: linear-gradient(90deg, rgba(255, 255, 255, .85), rgba(175, 197, 248, .35) 35%%, transparent);
  animation: nc-fugaz 16s linear infinite;
}
@keyframes nc-titilar { from { opacity: .3; } to { opacity: .9; } }
@keyframes nc-destellar { 0%%, 100%% { opacity: .15; transform: scale(.7); } 50%% { opacity: .6; transform: scale(1); } }
@keyframes nc-flotar { from { transform: translateY(0); } to { transform: translateY(-14px); } }
@keyframes nc-rotar-superficie {
  from { background-position: 0 0, 0 0, 0 0; }
  to { background-position: 0 0, 420px 0, 0 0; }
}
@keyframes nc-orbitar { from { transform: rotate(0deg) translateX(390px); } to { transform: rotate(360deg) translateX(390px); } }
@keyframes nc-deriva { from { transform: translate(0, 0) scale(1); } to { transform: translate(60px, 30px) scale(1.12); } }
@keyframes nc-aparecer { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
@keyframes nc-fugaz {
  0%% { opacity: 0; transform: rotate(-24deg) translateX(0); }
  1.2%% { opacity: .9; }
  6%% { opacity: 0; transform: rotate(-24deg) translateX(-480px); }
  100%% { opacity: 0; transform: rotate(-24deg) translateX(-480px); }
}
/* --- Transiciones: el contenido aparece con un fundido suave al cambiar de página o pestaña --- */
.stTabs [data-baseweb="tab-panel"] { animation: nc-aparecer .35s ease-out; }
.nc-pagina, .nc-card, .nc-empty, [data-testid="stForm"], [data-testid="stDataFrame"], [data-testid="stAlert"] {
  animation: nc-aparecer .45s ease-out both;
}
[data-baseweb="popover"] > div { animation: nc-aparecer .18s ease-out; }

@media (prefers-reduced-motion: reduce) {
  .nc-estrellas, .nc-destello, .nc-fugaz, .nc-planeta, .nc-luna, .nc-nebulosa,
  .stTabs [data-baseweb="tab-panel"], .nc-pagina, .nc-card, .nc-empty,
  [data-testid="stForm"], [data-testid="stDataFrame"], [data-testid="stAlert"] { animation: none !important; }
  .nc-fugaz { display: none; }
}

/* --- Menú lateral --- */
[data-testid="stSidebar"] { background: rgba(7, 9, 16, .58); backdrop-filter: var(--nc-vidrio); border-right: 1px solid var(--nc-borde); }
[data-testid="stSidebar"] > div { background: transparent; }
[data-testid="stSidebar"] .block-container, [data-testid="stSidebarContent"] { padding-top: 1.2rem; }
[data-testid="stSidebar"] [role="radiogroup"] { gap: .15rem; }
[data-testid="stSidebar"] [role="radiogroup"] label {
  width: 100%%; margin: 0; padding: .62rem .85rem; border-radius: 8px; cursor: pointer; transition: background .15s;
}
[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child { display: none; }
[data-testid="stSidebar"] [role="radiogroup"] label p { color: var(--nc-gris); font-size: .93rem; font-weight: 500; }
[data-testid="stSidebar"] [role="radiogroup"] label:hover { background: rgba(175, 197, 248, .05); }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) { background: rgba(46, 93, 230, .14); box-shadow: inset 2px 0 0 var(--nc-azul); }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p { color: #FFFFFF; font-weight: 600; }

.nc-marca { display: flex; align-items: center; gap: .75rem; padding: 0 .3rem 1.2rem; margin-bottom: .8rem; border-bottom: 1px solid var(--nc-borde); }
.nc-logo {
  position: relative; width: 36px; height: 36px; border-radius: 9px; display: grid; place-items: center;
  font-weight: 700; font-size: 1rem; color: #fff;
  background: linear-gradient(145deg, var(--nc-azul), var(--nc-cobalto));
}
.nc-logo::after { content: "✦"; position: absolute; top: -6px; right: -5px; font-size: 10px; color: var(--nc-bruma); }
.nc-marca-nombre { font-weight: 700; font-size: 1rem; color: var(--nc-luz); line-height: 1.2; }
.nc-marca-detalle { font-size: .75rem; color: var(--nc-gris); }
.nc-menu-titulo { font-size: .7rem; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--nc-gris); padding: 0 .3rem .4rem; }
.nc-sistema { margin-top: 1.4rem; padding: .9rem .3rem 0; border-top: 1px solid var(--nc-borde); }
.nc-sistema-fila { display: flex; align-items: center; gap: .55rem; font-size: .8rem; color: var(--nc-luz); opacity: .8; padding: .25rem 0; }
.nc-dot { width: 7px; height: 7px; border-radius: 50%%; display: inline-block; flex-shrink: 0; }

/* --- Encabezado de página --- */
.nc-pagina { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.1rem; }
.nc-pagina h1 { margin: 0; padding: 0; font-size: 1.55rem; font-weight: 700; color: var(--nc-luz); letter-spacing: -.01em; }
.nc-pagina p { margin: .25rem 0 0; color: var(--nc-gris); font-size: .9rem; }
.nc-fecha { color: var(--nc-gris); font-size: .82rem; white-space: nowrap; }

/* --- Sub-pestañas: subrayado discreto --- */
.stTabs [data-baseweb="tab-list"] { gap: 1.6rem; border-bottom: 1px solid var(--nc-borde); }
.stTabs [data-baseweb="tab"] { height: 2.6rem; padding: 0; background: transparent; color: var(--nc-gris); font-weight: 500; }
.stTabs [data-baseweb="tab"]:hover { color: var(--nc-luz); }
.stTabs [aria-selected="true"] { color: #FFFFFF !important; }
.stTabs [data-baseweb="tab-border"] { display: none; }
.stTabs [data-baseweb="tab-panel"] { padding-top: 1.1rem; }

/* --- Formularios, botones y campos --- */
[data-testid="stForm"] { background: var(--nc-superficie); border: 1px solid var(--nc-borde); border-radius: 12px; padding: 1.2rem 1.3rem; backdrop-filter: var(--nc-vidrio); }
.stButton > button, [data-testid="stFormSubmitButton"] > button {
  border-radius: 8px; font-weight: 500; color: var(--nc-luz);
  background: transparent; border: 1px solid var(--nc-borde-fuerte); transition: background .15s, border-color .15s;
}
.stButton > button:hover:enabled, [data-testid="stFormSubmitButton"] > button:hover:enabled {
  background: rgba(175, 197, 248, .06); border-color: var(--nc-bruma); color: #FFFFFF;
}
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"] {
  background: var(--nc-azul); border-color: var(--nc-azul); color: #FFFFFF; font-weight: 600;
}
.stButton > button[kind="primary"]:hover:enabled, [data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"]:hover:enabled {
  background: #2652CF; border-color: #2652CF;
}
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] {
  background: rgba(10, 13, 22, .6) !important; border-radius: 8px !important; border-color: var(--nc-borde-fuerte) !important;
}
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within, [data-baseweb="textarea"]:focus-within { border-color: var(--nc-cielo) !important; }
[data-testid="stWidgetLabel"] p { color: var(--nc-bruma) !important; font-size: .85rem; font-weight: 500; }
[data-testid="stDataFrame"] { border: 1px solid var(--nc-borde); border-radius: 10px; overflow: hidden; }
[data-testid="stAlert"] { border-radius: 10px; }
[data-testid="stCaptionContainer"] { color: var(--nc-gris); }
[data-testid="stVerticalBlockBorderWrapper"] { border-color: var(--nc-borde) !important; border-radius: 12px !important; }

/* --- Bloques de contenido --- */
.nc-section { margin: 0 0 .7rem; }
.nc-section h3 { margin: 0; padding: 0; font-size: .98rem; font-weight: 600; color: var(--nc-luz); }
.nc-section p { margin: .2rem 0 0; color: var(--nc-gris); font-size: .84rem; }

.nc-card {
  margin-bottom: .85rem; padding: 1rem 1.1rem; border-radius: 12px;
  background: var(--nc-superficie); border: 1px solid var(--nc-borde); backdrop-filter: var(--nc-vidrio);
  transition: border-color .15s;
}
.nc-card:hover { border-color: var(--nc-borde-fuerte); }
.nc-metrica { border-left: 3px solid var(--nc-color, var(--nc-azul)); }
.nc-metric-label { color: var(--nc-gris); font-size: .74rem; font-weight: 600; text-transform: uppercase; letter-spacing: .07em; }
.nc-metric-value { font-size: 1.85rem; font-weight: 700; color: #FFFFFF; line-height: 1.15; margin-top: .3rem; font-variant-numeric: tabular-nums; }
.nc-metric-detail { color: var(--nc-gris); font-size: .8rem; margin-top: .15rem; }

.nc-item-top { display: flex; justify-content: space-between; align-items: flex-start; gap: .6rem; margin-bottom: .35rem; }
.nc-item-title { font-weight: 600; color: var(--nc-luz); font-size: .95rem; }
.nc-item-meta { color: var(--nc-gris); font-size: .8rem; margin-top: .18rem; }
.nc-item-text { color: var(--nc-luz); font-size: .88rem; margin: .35rem 0 .45rem; line-height: 1.45; }
.nc-badges { display: flex; gap: .3rem; flex-wrap: wrap; justify-content: flex-end; }
.nc-badge {
  display: inline-flex; align-items: center; gap: .35rem; padding: .16rem .5rem; border-radius: 6px;
  font-size: .72rem; font-weight: 600; white-space: nowrap;
}
.nc-badge::before { content: ""; width: 6px; height: 6px; border-radius: 50%%; background: currentColor; }

.nc-bar-row { display: flex; justify-content: space-between; font-size: .84rem; color: var(--nc-luz); }
.nc-bar-row span:last-child { color: var(--nc-gris); font-variant-numeric: tabular-nums; }
.nc-bar { height: 6px; border-radius: 6px; background: rgba(175, 197, 248, .08); overflow: hidden; margin: .35rem 0 .75rem; }
.nc-bar > span { display: block; height: 100%%; border-radius: 6px; }

.nc-reglas { list-style: none; margin: 0; padding: 0; }
.nc-reglas li { display: flex; justify-content: space-between; gap: 1rem; padding: .5rem 0; border-bottom: 1px solid var(--nc-borde); font-size: .84rem; color: var(--nc-bruma); }
.nc-reglas li:last-child { border-bottom: 0; }
.nc-reglas li span:last-child { color: var(--nc-luz); font-weight: 600; text-align: right; }

.nc-empty { text-align: center; padding: 1.6rem 1rem; margin-bottom: .85rem; border-radius: 12px; background: rgba(14, 18, 32, .55); border: 1px dashed var(--nc-borde-fuerte); }
.nc-empty-icon { font-size: 1.2rem; color: var(--nc-bruma); }
.nc-empty h4 { margin: .4rem 0 .25rem; padding: 0; font-size: .95rem; font-weight: 600; color: var(--nc-luz); }
.nc-empty p { color: var(--nc-gris); margin: 0; font-size: .85rem; }
.nc-empty code { background: var(--nc-campo); padding: .1rem .4rem; border-radius: 5px; color: var(--nc-bruma); border: 1px solid var(--nc-borde); }
"""


def aplicar_estilos() -> None:
    css = _CSS % {
        "capa1": _capa_estrellas(300, semilla=1),
        "capa2": _capa_estrellas(110, semilla=2),
        "capa3": _capa_estrellas(32, semilla=3, desenfoque="2px"),
    }
    st.markdown(f"<style>{css}</style>{_CIELO}", unsafe_allow_html=True)
