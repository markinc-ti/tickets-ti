# -*- coding: utf-8 -*-
"""
Apariencia: le da profundidad ("3D") a toda la app -- botones, tarjetas,
paneles, modales y campos -- en vez de verse planos.

Que se arregla: en todas las pantallas (panel de administracion, kiosko
de turnos, pantalla de TV de la sala de espera, cotizador, gantt, y
seguimiento de vehiculos) los botones y paneles eran completamente
planos (un solo color solido, sin sombra, esquinas cuadradas). Ahora:

  - Los botones tienen un degradado sutil (mas claro arriba, mas oscuro
    abajo) y una sombra debajo, para que se vean "elevados" como un
    boton de verdad -- y al pasar el mouse se levantan un poco mas, y
    al hacer click se "hunden" (efecto de que lo presionaste).
  - Las tarjetas, paneles, KPIs, el menu desplegable y los modales
    tienen sombra y esquinas redondeadas, para que se vean como capas
    separadas en vez de todo pegado al fondo.
  - Los campos de texto (input/select/textarea) tienen un ligero
    hundido hacia adentro, para que contrasten con los botones
    "elevados" -- y un resplandor cuando estan enfocados.

Esto es solo CSS -- no cambia ningun texto, boton, ni funcion de la
app, nomas como se ve.

Que toca:
  - frontend/index.html -- panel de administracion (botones, tarjetas,
    KPIs, modal, login, menus, tablas, campos).
  - frontend/kiosko_turnos.html -- boton grande de "Tomar turno" y los
    botones de categoria.
  - frontend/pantalla_turnos.html -- el panel de abajo con el numero de
    turno actual y el historial.
  - frontend/gantt.html -- botones de la barra de herramientas, botones
    de navegacion, boton de "completado", y el modal.
  - frontend/cotizador_costos.html -- boton de descarga, selector de
    modo, tarjetas de modulo, e interruptores (switch).
  - frontend/seguimiento.html -- la etiqueta de estado y el encabezado.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py -3 fix_apariencia_3d.py
"""
import sys

ARCHIVOS = {}

ARCHIVOS["frontend/index.html"] = [
    [
        "  :root {\n    --substrate: #1A1B1D;\n    --panel: #232427;\n    --panel-2: #2B2D30;\n    --copper: #D8192F;\n    --trace: #9B9D9F;\n    --text: #F2F1F0;\n    --muted: #9B9D9F;\n    --urgente: #D8192F;\n    --alta: #E8823D;\n    --media: #74767A;\n    --baja: #B9BABC;\n  }",
        "  :root {\n    --substrate: #1A1B1D;\n    --panel: #232427;\n    --panel-2: #2B2D30;\n    --copper: #D8192F;\n    --copper-light: #F0374F;\n    --copper-dark: #A81222;\n    --trace: #9B9D9F;\n    --text: #F2F1F0;\n    --muted: #9B9D9F;\n    --urgente: #D8192F;\n    --alta: #E8823D;\n    --media: #74767A;\n    --baja: #B9BABC;\n    /* Tokens de profundidad -- para que botones, tarjetas y paneles se\n       vean elevados (tipo \"3D\") en vez de planos, en toda la app. */\n    --radius-sm: 5px;\n    --radius: 8px;\n    --radius-lg: 14px;\n    --shadow-sm: 0 1px 3px rgba(0,0,0,0.4);\n    --shadow-md: 0 4px 14px rgba(0,0,0,0.45);\n    --shadow-lg: 0 14px 38px rgba(0,0,0,0.55);\n    --shadow-inset: inset 0 1px 4px rgba(0,0,0,0.5);\n    --highlight-top: inset 0 1px 0 rgba(255,255,255,0.07);\n  }",
    ],
    [
        "  button.primary, a.primary {\n    background: var(--copper);\n    color: #fff;\n    border: none;\n    font-family: 'JetBrains Mono', monospace;\n    font-weight: 700;\n    font-size: 13px;\n    padding: 10px 16px;\n    cursor: pointer;\n  }\n  button.primary:hover, a.primary:hover { opacity: 0.9; }\n  button.secondary, label.secondary, a.secondary {\n    background: transparent;\n    color: var(--text);\n    border: 1px solid var(--muted);\n    font-family: 'JetBrains Mono', monospace;\n    font-size: 12px;\n    padding: 9px 14px;\n    cursor: pointer;\n    text-decoration: none;\n    box-sizing: border-box;\n  }\n  a.secondary:hover { opacity: 0.85; }\n  button.danger { background: transparent; color: var(--copper); border: 1px solid var(--copper); font-family: 'JetBrains Mono', monospace; font-size: 11px; padding: 5px 10px; cursor: pointer; }",
        "  button.primary, a.primary {\n    background: linear-gradient(180deg, var(--copper-light) 0%, var(--copper) 55%, var(--copper-dark) 100%);\n    color: #fff;\n    border: 1px solid var(--copper-dark);\n    border-radius: var(--radius);\n    font-family: 'JetBrains Mono', monospace;\n    font-weight: 700;\n    font-size: 13px;\n    padding: 10px 16px;\n    cursor: pointer;\n    box-shadow: var(--shadow-md), var(--highlight-top);\n    transition: transform 0.1s ease, box-shadow 0.1s ease, filter 0.15s ease;\n  }\n  button.primary:hover, a.primary:hover {\n    filter: brightness(1.08);\n    box-shadow: var(--shadow-lg), var(--highlight-top);\n    transform: translateY(-1px);\n  }\n  button.primary:active, a.primary:active {\n    transform: translateY(1px);\n    box-shadow: var(--shadow-sm), var(--shadow-inset);\n    filter: brightness(0.96);\n  }\n  button.primary:disabled {\n    filter: grayscale(0.5) brightness(0.75); cursor: not-allowed; transform: none; box-shadow: var(--shadow-sm);\n  }\n  button.secondary, label.secondary, a.secondary {\n    background: linear-gradient(180deg, var(--panel-2) 0%, var(--panel) 100%);\n    color: var(--text);\n    border: 1px solid rgba(155,157,159,0.4);\n    border-radius: var(--radius);\n    font-family: 'JetBrains Mono', monospace;\n    font-size: 12px;\n    padding: 9px 14px;\n    cursor: pointer;\n    text-decoration: none;\n    box-sizing: border-box;\n    box-shadow: var(--shadow-sm), var(--highlight-top);\n    transition: transform 0.1s ease, box-shadow 0.1s ease, border-color 0.15s ease;\n  }\n  button.secondary:hover, a.secondary:hover {\n    border-color: var(--copper);\n    box-shadow: var(--shadow-md), var(--highlight-top);\n    transform: translateY(-1px);\n  }\n  button.secondary:active, a.secondary:active { transform: translateY(1px); box-shadow: var(--shadow-inset); }\n  button.danger {\n    background: linear-gradient(180deg, rgba(216,25,47,0.14) 0%, rgba(216,25,47,0.05) 100%);\n    color: var(--copper); border: 1px solid var(--copper); border-radius: var(--radius-sm);\n    font-family: 'JetBrains Mono', monospace; font-size: 11px; padding: 5px 10px; cursor: pointer;\n    box-shadow: var(--shadow-sm);\n    transition: transform 0.1s ease, box-shadow 0.1s ease, background 0.15s ease;\n  }\n  button.danger:hover { background: rgba(216,25,47,0.2); box-shadow: var(--shadow-md); transform: translateY(-1px); }\n  button.danger:active { transform: translateY(1px); box-shadow: var(--shadow-inset); }",
    ],
    [
        "  details.menu-desplegable > summary {\n    list-style: none; cursor: pointer; user-select: none;\n    background: transparent; color: var(--text);\n    border: 1px solid var(--muted); font-family: 'JetBrains Mono', monospace;\n    font-size: 12px; padding: 9px 14px; display: inline-flex; align-items: center; gap: 6px;\n  }",
        "  details.menu-desplegable > summary {\n    list-style: none; cursor: pointer; user-select: none;\n    background: linear-gradient(180deg, var(--panel-2) 0%, var(--panel) 100%); color: var(--text);\n    border: 1px solid rgba(155,157,159,0.4); border-radius: var(--radius); font-family: 'JetBrains Mono', monospace;\n    font-size: 12px; padding: 9px 14px; display: inline-flex; align-items: center; gap: 6px;\n    box-shadow: var(--shadow-sm), var(--highlight-top);\n    transition: box-shadow 0.12s ease, border-color 0.15s ease;\n  }\n  details.menu-desplegable > summary:hover { box-shadow: var(--shadow-md), var(--highlight-top); }",
    ],
    [
        "  .kpi {\n    background: var(--panel);\n    border: 1px solid rgba(155,157,159,0.25);\n    padding: 8px 14px;\n    font-family: 'JetBrains Mono', monospace;\n    font-size: 12px;\n    display: flex;\n    flex-direction: column;\n    gap: 2px;\n    min-width: 92px;\n  }",
        "  .kpi {\n    background: linear-gradient(180deg, var(--panel-2) 0%, var(--panel) 100%);\n    border: 1px solid rgba(155,157,159,0.25);\n    border-radius: var(--radius);\n    padding: 8px 14px;\n    font-family: 'JetBrains Mono', monospace;\n    font-size: 12px;\n    display: flex;\n    flex-direction: column;\n    gap: 2px;\n    min-width: 92px;\n    box-shadow: var(--shadow-sm), var(--highlight-top);\n  }",
    ],
    [
        "  .column { background: rgba(35,36,39,0.5); border: 1px solid rgba(155,157,159,0.15); min-height: 200px; }",
        "  .column { background: rgba(35,36,39,0.5); border: 1px solid rgba(155,157,159,0.15); border-radius: var(--radius); min-height: 200px; box-shadow: var(--shadow-sm); overflow: hidden; }",
    ],
    [
        "  .card {\n    background: var(--panel-2);\n    border: 1px solid rgba(216,25,47,0.2);\n    padding: 12px 12px 14px;\n    cursor: pointer;\n    position: relative;\n  }",
        "  .card {\n    background: linear-gradient(165deg, var(--panel-2) 0%, #26272A 100%);\n    border: 1px solid rgba(216,25,47,0.2);\n    border-radius: var(--radius);\n    padding: 12px 12px 14px;\n    cursor: pointer;\n    position: relative;\n    box-shadow: var(--shadow-sm);\n    transition: transform 0.12s ease, box-shadow 0.12s ease, border-color 0.15s ease;\n  }",
    ],
    [
        "  .card:hover { border-color: var(--copper); }",
        "  .card:hover { border-color: var(--copper); box-shadow: var(--shadow-md); transform: translateY(-2px); }",
    ],
    [
        "  .modal {\n    background: var(--panel); border: 1px solid var(--copper);\n    max-width: 560px; width: 100%; padding: 24px;\n    max-height: 85vh; overflow-y: auto;\n  }",
        "  .modal {\n    background: linear-gradient(165deg, var(--panel) 0%, #1F2022 100%); border: 1px solid var(--copper);\n    border-radius: var(--radius-lg);\n    max-width: 560px; width: 100%; padding: 24px;\n    max-height: 85vh; overflow-y: auto;\n    box-shadow: var(--shadow-lg);\n  }",
    ],
    [
        "  input, textarea, select {\n    width: 100%; background: var(--substrate); border: 1px solid rgba(155,157,159,0.3);\n    color: var(--text); padding: 9px 10px; font-family: 'IBM Plex Sans', sans-serif; font-size: 13px;\n  }",
        "  input, textarea, select {\n    width: 100%; background: var(--substrate); border: 1px solid rgba(155,157,159,0.3);\n    border-radius: var(--radius-sm);\n    color: var(--text); padding: 9px 10px; font-family: 'IBM Plex Sans', sans-serif; font-size: 13px;\n    box-shadow: var(--shadow-inset);\n    transition: border-color 0.15s ease, box-shadow 0.15s ease;\n  }\n  input:focus, textarea:focus, select:focus {\n    outline: none; border-color: var(--copper);\n    box-shadow: var(--shadow-inset), 0 0 0 3px rgba(216,25,47,0.18);\n  }",
    ],
    [
        "  .close-btn { background: none; border: 1px solid var(--muted); color: var(--muted); font-family: 'JetBrains Mono', monospace; padding: 6px 10px; cursor: pointer; float: right; }",
        "  .close-btn { background: linear-gradient(180deg, var(--panel-2) 0%, var(--panel) 100%); border: 1px solid rgba(155,157,159,0.4); border-radius: var(--radius-sm); color: var(--muted); font-family: 'JetBrains Mono', monospace; padding: 6px 10px; cursor: pointer; float: right; box-shadow: var(--shadow-sm); transition: box-shadow 0.12s ease, transform 0.1s ease; }\n  .close-btn:hover { box-shadow: var(--shadow-md); }\n  .close-btn:active { transform: translateY(1px); box-shadow: var(--shadow-inset); }",
    ],
    [
        "  .login-box { background: var(--panel); border: 1px solid var(--copper); padding: 32px; width: 100%; max-width: 340px; }",
        "  .login-box { background: linear-gradient(165deg, var(--panel) 0%, #1F2022 100%); border: 1px solid var(--copper); border-radius: var(--radius-lg); padding: 32px; width: 100%; max-width: 340px; box-shadow: var(--shadow-lg); }",
    ],
    [
        "  .tabla-fija-wrap { overflow: auto; max-height: 68vh; border: 1px solid rgba(155,157,159,0.2); }",
        "  .tabla-fija-wrap { overflow: auto; max-height: 68vh; border: 1px solid rgba(155,157,159,0.2); border-radius: var(--radius); box-shadow: var(--shadow-sm); }",
    ],
    [
        "  .menu-boton {\n    background: var(--panel); border: 1px solid rgba(155,157,159,0.3); color: var(--text);\n    font-family: 'JetBrains Mono', monospace; font-size: 14px; text-transform: uppercase;\n    padding: 28px 16px; cursor: pointer; text-align: center; letter-spacing: 0.03em;\n    display: flex; flex-direction: column; align-items: center; gap: 8px; transition: border-color 0.15s, background 0.15s;\n  }\n  .menu-boton:hover { border-color: var(--copper); background: rgba(216,25,47,0.06); }",
        "  .menu-boton {\n    background: linear-gradient(180deg, var(--panel) 0%, var(--panel-2) 100%); border: 1px solid rgba(155,157,159,0.3); color: var(--text);\n    font-family: 'JetBrains Mono', monospace; font-size: 14px; text-transform: uppercase;\n    border-radius: var(--radius);\n    padding: 28px 16px; cursor: pointer; text-align: center; letter-spacing: 0.03em;\n    display: flex; flex-direction: column; align-items: center; gap: 8px;\n    box-shadow: var(--shadow-sm), var(--highlight-top);\n    transition: border-color 0.15s, background 0.15s, transform 0.12s, box-shadow 0.12s;\n  }\n  .menu-boton:hover { border-color: var(--copper); background: linear-gradient(180deg, var(--panel-2) 0%, rgba(216,25,47,0.1) 100%); box-shadow: var(--shadow-md); transform: translateY(-2px); }\n  .menu-boton:active { transform: translateY(0); box-shadow: var(--shadow-inset); }",
    ],
    [
        "  .dash-tarjeta { background: var(--panel); border: 1px solid rgba(155,157,159,0.25); padding: 20px; }",
        "  .dash-tarjeta { background: linear-gradient(165deg, var(--panel) 0%, var(--panel-2) 100%); border: 1px solid rgba(155,157,159,0.25); border-radius: var(--radius); padding: 20px; box-shadow: var(--shadow-sm); }",
    ],
    [
        "  .empresa-card {\n    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;\n    background: var(--panel-2); border: 1px solid rgba(198,142,63,0.2);\n    padding: 14px 16px; margin-bottom: 12px;\n  }",
        "  .empresa-card {\n    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;\n    background: linear-gradient(165deg, var(--panel-2) 0%, #26272A 100%); border: 1px solid rgba(198,142,63,0.2);\n    border-radius: var(--radius);\n    padding: 14px 16px; margin-bottom: 12px;\n    box-shadow: var(--shadow-sm);\n  }",
    ],
    [
        "  .filtros {\n    display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end;\n    background: var(--panel); border: 1px solid rgba(155,157,159,0.2);\n    padding: 14px 16px; margin-bottom: 18px;\n  }",
        "  .filtros {\n    display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end;\n    background: linear-gradient(180deg, var(--panel) 0%, var(--panel-2) 100%); border: 1px solid rgba(155,157,159,0.2);\n    border-radius: var(--radius);\n    padding: 14px 16px; margin-bottom: 18px;\n    box-shadow: var(--shadow-sm);\n  }",
    ],
]

ARCHIVOS["frontend/kiosko_turnos.html"] = [
    [
        "  #btnTomar { width:100%; padding:28px; font-size:22px; font-weight:700; border-radius:14px; border:none; background:#B01426; color:#fff; cursor:pointer; }\n  #btnTomar:active { transform: scale(0.98); }\n  #btnTomar:disabled { opacity:0.5; }\n  #botonesCategorias { display:none; grid-template-columns: 1fr 1fr; gap:14px; margin-bottom:14px; }\n  .btnCategoria { padding:26px 10px; font-size:17px; font-weight:700; border-radius:14px; border:none; background:#D8192F; color:#fff; cursor:pointer; }\n  .btnCategoria:active { transform: scale(0.98); }\n  .btnCategoria:disabled { opacity:0.5; }\n  #resultado { display:none; }\n  #resultado .numero { font-size:96px; font-weight:800; margin:16px 0; }\n  #resultado .nota { font-size:14px; color:#9B9D9F; margin-bottom:28px; }\n  #btnOtro { padding:14px 24px; font-size:14px; border-radius:10px; border:1px solid rgba(155,157,159,0.35); background:transparent; color:#EDEDED; cursor:pointer; }",
        "  #btnTomar {\n    width:100%; padding:28px; font-size:22px; font-weight:700; border-radius:16px; border:1px solid #7A0D1A;\n    background:linear-gradient(180deg, #E3213B 0%, #B01426 55%, #7A0D1A 100%); color:#fff; cursor:pointer;\n    box-shadow: 0 8px 22px rgba(176,20,38,0.45), inset 0 1px 0 rgba(255,255,255,0.15);\n    transition: transform 0.1s ease, box-shadow 0.1s ease, filter 0.15s ease;\n  }\n  #btnTomar:hover { filter:brightness(1.06); box-shadow: 0 12px 30px rgba(176,20,38,0.55), inset 0 1px 0 rgba(255,255,255,0.15); }\n  #btnTomar:active { transform: scale(0.98) translateY(1px); box-shadow: inset 0 3px 8px rgba(0,0,0,0.45); }\n  #btnTomar:disabled { opacity:0.5; box-shadow:none; transform:none; }\n  #botonesCategorias { display:none; grid-template-columns: 1fr 1fr; gap:14px; margin-bottom:14px; }\n  .btnCategoria {\n    padding:26px 10px; font-size:17px; font-weight:700; border-radius:16px; border:1px solid #8C0F1F;\n    background:linear-gradient(180deg, #EE2C46 0%, #D8192F 55%, #8C0F1F 100%); color:#fff; cursor:pointer;\n    box-shadow: 0 6px 18px rgba(216,25,47,0.4), inset 0 1px 0 rgba(255,255,255,0.15);\n    transition: transform 0.1s ease, box-shadow 0.1s ease, filter 0.15s ease;\n  }\n  .btnCategoria:hover { filter:brightness(1.06); box-shadow: 0 10px 24px rgba(216,25,47,0.5), inset 0 1px 0 rgba(255,255,255,0.15); }\n  .btnCategoria:active { transform: scale(0.98) translateY(1px); box-shadow: inset 0 3px 8px rgba(0,0,0,0.45); }\n  .btnCategoria:disabled { opacity:0.5; box-shadow:none; transform:none; }\n  #resultado { display:none; }\n  #resultado .numero { font-size:96px; font-weight:800; margin:16px 0; text-shadow: 0 3px 10px rgba(0,0,0,0.5); }\n  #resultado .nota { font-size:14px; color:#9B9D9F; margin-bottom:28px; }\n  #btnOtro {\n    padding:14px 24px; font-size:14px; border-radius:12px; border:1px solid rgba(155,157,159,0.35);\n    background:linear-gradient(180deg, #1F2022 0%, #161719 100%); color:#EDEDED; cursor:pointer;\n    box-shadow: 0 3px 10px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.06);\n    transition: transform 0.1s ease, box-shadow 0.1s ease;\n  }\n  #btnOtro:hover { box-shadow: 0 6px 16px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.06); }\n  #btnOtro:active { transform: translateY(1px); box-shadow: inset 0 2px 6px rgba(0,0,0,0.4); }",
    ],
]

ARCHIVOS["frontend/pantalla_turnos.html"] = [
    [
        "  #panelInferior { flex:0 0 auto; display:flex; align-items:center; justify-content:space-between; gap:24px; padding:18px 32px; background:#141516; border-top:2px solid #D8192F; flex-wrap:wrap; }\n  #sucursalNombre { font-size:16px; color:#9B9D9F; text-transform:uppercase; letter-spacing:0.05em; }\n  #turnoActualBox { text-align:center; }\n  #turnoActualLabel { font-size:13px; color:#9B9D9F; text-transform:uppercase; letter-spacing:0.08em; }\n  #turnoActualNumero { font-size:88px; font-weight:800; line-height:1; color:#fff; }\n  #turnoActualVentanilla { font-size:26px; color:#D8192F; font-weight:700; margin-top:2px; }\n  #historial { display:flex; gap:20px; }\n  #historial .item { text-align:center; opacity:0.55; }",
        "  #panelInferior {\n    flex:0 0 auto; display:flex; align-items:center; justify-content:space-between; gap:24px; padding:18px 32px;\n    background:linear-gradient(180deg, #1A1B1D 0%, #141516 100%); border-top:2px solid #D8192F; flex-wrap:wrap;\n    box-shadow: 0 -10px 28px rgba(0,0,0,0.5);\n  }\n  #sucursalNombre { font-size:16px; color:#9B9D9F; text-transform:uppercase; letter-spacing:0.05em; }\n  #turnoActualBox { text-align:center; }\n  #turnoActualLabel { font-size:13px; color:#9B9D9F; text-transform:uppercase; letter-spacing:0.08em; }\n  #turnoActualNumero { font-size:88px; font-weight:800; line-height:1; color:#fff; text-shadow: 0 3px 10px rgba(0,0,0,0.6); }\n  #turnoActualVentanilla { font-size:26px; color:#D8192F; font-weight:700; margin-top:2px; }\n  #historial { display:flex; gap:14px; }\n  #historial .item {\n    text-align:center; opacity:0.7; background:rgba(255,255,255,0.04); border-radius:8px; padding:6px 14px;\n    box-shadow: inset 0 1px 3px rgba(0,0,0,0.35), 0 1px 0 rgba(255,255,255,0.04);\n  }",
    ],
]

ARCHIVOS["frontend/gantt.html"] = [
    [
        "  .toolbar-actions{margin-left:auto;display:flex;gap:8px;align-items:center;}\n  .btn{\n    border:1px solid var(--border);background:var(--panel);padding:7px 13px;border-radius:6px;\n    cursor:pointer;font-size:13px;font-weight:600;color:var(--text);\n  }\n  .btn:hover{border-color:var(--border-strong);}\n  .btn-primary{background:var(--accent);border-color:var(--accent);color:#fff;}\n  .btn-primary:hover{filter:brightness(1.05);}",
        "  .toolbar-actions{margin-left:auto;display:flex;gap:8px;align-items:center;}\n  .btn{\n    border:1px solid var(--border);background:linear-gradient(180deg,#FFFFFF 0%,#F1F2F5 100%);padding:7px 13px;border-radius:6px;\n    cursor:pointer;font-size:13px;font-weight:600;color:var(--text);\n    box-shadow:0 1px 2px rgba(16,24,40,0.06),inset 0 1px 0 rgba(255,255,255,0.6);\n    transition:transform 0.1s ease,box-shadow 0.1s ease,border-color 0.15s ease;\n  }\n  .btn:hover{border-color:var(--border-strong);box-shadow:0 4px 10px rgba(16,24,40,0.1),inset 0 1px 0 rgba(255,255,255,0.6);transform:translateY(-1px);}\n  .btn:active{transform:translateY(1px);box-shadow:inset 0 2px 4px rgba(16,24,40,0.12);}\n  .btn-primary{background:linear-gradient(180deg,#4A6AE0 0%,var(--accent) 55%,#2A45B0 100%);border-color:#2A45B0;color:#fff;box-shadow:0 3px 10px rgba(52,87,213,0.35),inset 0 1px 0 rgba(255,255,255,0.2);}\n  .btn-primary:hover{filter:brightness(1.05);box-shadow:0 6px 16px rgba(52,87,213,0.45),inset 0 1px 0 rgba(255,255,255,0.2);}\n  .btn-primary:active{filter:brightness(0.97);box-shadow:inset 0 2px 6px rgba(0,0,0,0.25);}",
    ],
    [
        "  .nav-btn{\n    border:1px solid var(--border);background:var(--panel);width:30px;height:30px;border-radius:6px;\n    cursor:pointer;font-size:14px;color:var(--text);display:flex;align-items:center;justify-content:center;\n  }\n  .nav-btn:hover{border-color:var(--border-strong);}\n  .nav-today{border:1px solid var(--border);background:var(--panel);padding:0 12px;height:30px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;}",
        "  .nav-btn{\n    border:1px solid var(--border);background:linear-gradient(180deg,#FFFFFF 0%,#F1F2F5 100%);width:30px;height:30px;border-radius:6px;\n    cursor:pointer;font-size:14px;color:var(--text);display:flex;align-items:center;justify-content:center;\n    box-shadow:0 1px 2px rgba(16,24,40,0.06),inset 0 1px 0 rgba(255,255,255,0.6);\n    transition:transform 0.1s ease,box-shadow 0.1s ease,border-color 0.15s ease;\n  }\n  .nav-btn:hover{border-color:var(--border-strong);box-shadow:0 4px 10px rgba(16,24,40,0.1);transform:translateY(-1px);}\n  .nav-btn:active{transform:translateY(1px);box-shadow:inset 0 2px 4px rgba(16,24,40,0.12);}\n  .nav-today{\n    border:1px solid var(--border);background:linear-gradient(180deg,#FFFFFF 0%,#F1F2F5 100%);padding:0 12px;height:30px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;\n    box-shadow:0 1px 2px rgba(16,24,40,0.06),inset 0 1px 0 rgba(255,255,255,0.6);\n    transition:transform 0.1s ease,box-shadow 0.1s ease;\n  }\n  .nav-today:hover{box-shadow:0 4px 10px rgba(16,24,40,0.1);transform:translateY(-1px);}\n  .nav-today:active{transform:translateY(1px);box-shadow:inset 0 2px 4px rgba(16,24,40,0.12);}",
    ],
    [
        "  .complete-btn{\n    align-self:center;justify-self:start;border:1px solid var(--border-strong);background:var(--panel);\n    padding:5px 12px;border-radius:14px;font-size:11.5px;font-weight:700;cursor:pointer;color:var(--text-muted);\n    width:max-content;white-space:nowrap;\n  }\n  .complete-btn.is-complete{background:var(--success-soft);border-color:var(--success);color:var(--success);}",
        "  .complete-btn{\n    align-self:center;justify-self:start;border:1px solid var(--border-strong);background:linear-gradient(180deg,#FFFFFF 0%,#F1F2F5 100%);\n    padding:5px 12px;border-radius:14px;font-size:11.5px;font-weight:700;cursor:pointer;color:var(--text-muted);\n    width:max-content;white-space:nowrap;\n    box-shadow:0 1px 3px rgba(16,24,40,0.08);\n    transition:transform 0.1s ease,box-shadow 0.1s ease;\n  }\n  .complete-btn:hover{box-shadow:0 3px 8px rgba(16,24,40,0.12);transform:translateY(-1px);}\n  .complete-btn.is-complete{background:linear-gradient(180deg,#E4F8ED 0%,var(--success-soft) 100%);border-color:var(--success);color:var(--success);}",
    ],
    [
        "  #modal{background:var(--panel);border-radius:10px;width:min(520px,92vw);max-height:88vh;overflow:auto;box-shadow:0 20px 60px rgba(0,0,0,.3);}",
        "  #modal{background:linear-gradient(165deg,#FFFFFF 0%,#F7F8FA 100%);border-radius:12px;width:min(520px,92vw);max-height:88vh;overflow:auto;box-shadow:0 24px 70px rgba(0,0,0,.35);}",
    ],
]

ARCHIVOS["frontend/cotizador_costos.html"] = [
    [
        "  .download-btn{\n    width:100%; margin-top:24px; padding:13px; border:none; border-radius:8px;\n    background:var(--rojo); color:#fff; font-family:var(--font-body); font-weight:700; font-size:0.92rem;\n    cursor:pointer; letter-spacing:0.01em;\n  }\n  .download-btn:hover{ background:var(--rojo-oscuro); }\n  .download-btn:disabled{ opacity:0.5; cursor:wait; }",
        "  .download-btn{\n    width:100%; margin-top:24px; padding:13px; border:1px solid var(--rojo-oscuro); border-radius:8px;\n    background:linear-gradient(180deg, #ED3A50 0%, var(--rojo) 55%, var(--rojo-oscuro) 100%); color:#fff; font-family:var(--font-body); font-weight:700; font-size:0.92rem;\n    cursor:pointer; letter-spacing:0.01em;\n    box-shadow: 0 4px 14px rgba(216,25,47,0.35), inset 0 1px 0 rgba(255,255,255,0.2);\n    transition: transform 0.1s ease, box-shadow 0.1s ease, filter 0.15s ease;\n  }\n  .download-btn:hover{ filter:brightness(1.05); box-shadow: 0 8px 20px rgba(216,25,47,0.45), inset 0 1px 0 rgba(255,255,255,0.2); transform: translateY(-1px); }\n  .download-btn:active{ transform: translateY(1px); box-shadow: inset 0 2px 6px rgba(0,0,0,0.3); }\n  .download-btn:disabled{ opacity:0.5; cursor:wait; box-shadow:none; transform:none; }",
    ],
    [
        "  .modebar{ display:flex; gap:6px; background:var(--papel); border:1px solid var(--linea); border-radius:8px; padding:3px; }\n  .modebar button{\n    border:none; background:transparent; padding:7px 14px; font-family:var(--font-body);\n    font-size:0.82rem; font-weight:600; color:var(--gris-1); border-radius:6px; cursor:pointer;\n  }\n  .modebar button.on{ background:var(--rojo); color:#fff; }",
        "  .modebar{ display:flex; gap:6px; background:var(--papel); border:1px solid var(--linea); border-radius:8px; padding:3px; box-shadow: inset 0 1px 3px rgba(0,0,0,0.08); }\n  .modebar button{\n    border:none; background:transparent; padding:7px 14px; font-family:var(--font-body);\n    font-size:0.82rem; font-weight:600; color:var(--gris-1); border-radius:6px; cursor:pointer;\n    transition: background 0.15s ease, box-shadow 0.15s ease, color 0.15s ease;\n  }\n  .modebar button.on{ background:linear-gradient(180deg, #ED3A50 0%, var(--rojo) 100%); color:#fff; box-shadow: 0 2px 6px rgba(216,25,47,0.4), inset 0 1px 0 rgba(255,255,255,0.2); }",
    ],
    [
        "  .module-card{\n    border:1px solid var(--linea-fuerte); border-radius:10px; padding:14px; margin-bottom:12px;\n    background:var(--panel);\n  }",
        "  .module-card{\n    border:1px solid var(--linea-fuerte); border-radius:10px; padding:14px; margin-bottom:12px;\n    background:var(--panel);\n    box-shadow: 0 1px 4px rgba(0,0,0,0.06);\n    transition: box-shadow 0.15s ease;\n  }\n  .module-card:hover{ box-shadow: 0 4px 14px rgba(0,0,0,0.1); }",
    ],
    [
        "  .slider{ position:absolute; inset:0; background:var(--linea-fuerte); border-radius:20px; cursor:pointer; transition:.15s; }\n  .slider:before{ content:\"\"; position:absolute; width:15px; height:15px; left:3px; top:3px; background:#fff; border-radius:50%; transition:.15s; }",
        "  .slider{ position:absolute; inset:0; background:var(--linea-fuerte); border-radius:20px; cursor:pointer; transition:.15s; box-shadow: inset 0 1px 3px rgba(0,0,0,0.15); }\n  .slider:before{ content:\"\"; position:absolute; width:15px; height:15px; left:3px; top:3px; background:#fff; border-radius:50%; transition:.15s; box-shadow: 0 1px 3px rgba(0,0,0,0.3); }",
    ],
]

ARCHIVOS["frontend/seguimiento.html"] = [
    [
        "  #estadoTexto {\n    display: inline-block; font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em;\n    padding: 4px 10px; border-radius: 12px; background: rgba(216,25,47,0.15); color: #FF6B7A;\n  }",
        "  #estadoTexto {\n    display: inline-block; font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em;\n    padding: 4px 10px; border-radius: 12px; background: rgba(216,25,47,0.15); color: #FF6B7A;\n    box-shadow: inset 0 1px 2px rgba(0,0,0,0.25), 0 1px 0 rgba(255,255,255,0.04);\n  }\n  header { box-shadow: 0 4px 14px rgba(0,0,0,0.35); position: relative; z-index: 2; }",
    ],
]



def leer(ruta):
    with open(ruta, 'r', encoding='utf-8') as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def aplicar_reemplazos(ruta):
    try:
        contenido = leer(ruta)
    except FileNotFoundError:
        print("[" + ruta + "] NO ENCONTRADO -- asegurate de correr este script desde la raiz del repo (junto a backend/ y frontend/).")
        return False
    cambios = 0
    hubo_error = False
    for viejo, nuevo in ARCHIVOS[ruta]:
        if viejo in contenido:
            contenido = contenido.replace(viejo, nuevo, 1)
            cambios += 1
        elif nuevo in contenido:
            cambios += 1  # ya aplicado antes
        else:
            print("[" + ruta + "] No se encontro un bloque esperado. El archivo pudo haber cambiado desde la ultima vez.")
            hubo_error = True
    escribir(ruta, contenido)
    print("[" + ruta + "] " + str(cambios) + "/" + str(len(ARCHIVOS[ruta])) + " cambio(s) aplicado(s).")
    return not hubo_error


def main():
    ok = True
    for ruta in ARCHIVOS:
        ok = aplicar_reemplazos(ruta) and ok

    if not ok:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    archivos_git = list(ARCHIVOS.keys())
    print("   git add " + " ".join(archivos_git))
    print('   git commit -m "Apariencia: botones y paneles con sombra/degradado (efecto 3D) en toda la app"')
    print("   git push")


if __name__ == "__main__":
    main()
