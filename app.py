import streamlit as st
import re
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(layout="wide", page_title="Spanningen en Structuur met Belastingen")
st.title("Vergelijking Spanningen, Structuur en Belastingen")

uploaded_file = st.file_uploader("Upload fundering_nieuwV3.txt", type=["txt"])

if uploaded_file is not None:

    # ===========================
    # Bestand lezen met fallback
    # ===========================
    def read_file_with_fallback_encoding(file):
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'windows-1252']
        for enc in encodings:
            try:
                lines = file.getvalue().decode(enc).splitlines()
                st.success(f"Bestand gelezen met encoding: {enc}")
                return lines
            except UnicodeDecodeError:
                continue
        lines = file.getvalue().decode('utf-8', errors='ignore').splitlines()
        return lines

    lines = read_file_with_fallback_encoding(uploaded_file)

    # ===========================
    # STRAMIENLIJNEN PARSEN
    # ===========================
    stramienlijnen = {}
    in_stramien = False
    for line in lines:
        if "STRAMIENLIJNEN" in line:
            in_stramien = True
            continue
        if "BALKEN" in line:
            break
        if in_stramien:
            match = re.match(r"\s*\d+\s+(\S+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", line)
            if match:
                naam = match.group(1)
                x1, y1, x2, y2 = map(float, match.groups()[1:])
                stramienlijnen[naam] = [(x1, y1), (x2, y2)]

    # ===========================
    # BALKEN PARSEN
    # ===========================
    balken = []
    in_balken = False
    for line in lines:
        if "BALKEN" in line and "vervolg" not in line:
            in_balken = True
            continue
        if "BALKEN vervolg" in line or "DOORSNEDESECTOREN" in line:
            break
        if in_balken and line.strip():
            match = re.match(r"\s*\d+\s+\S+\s+(\S+)\s+(\S+)", line)
            if match:
                balken.append((match.group(1), match.group(2)))

    # ===========================
    # Functies voor coördinaten
    # ===========================
    def get_beam_coord(code):
        lijn_naam, pos_str = code.split(';')
        i = int(pos_str)
        p1, p2 = stramienlijnen[lijn_naam]
        x = p1[0] + (i - 1) * (p2[0] - p1[0]) / 3
        y = p1[1] + (i - 1) * (p2[1] - p1[1]) / 3
        return (x, y)

    def get_coord_3d(code):
        x, y = get_beam_coord(code)
        return (x, y, 0)

    # ===========================
    # GROUND STRESS PARSEN
    # ===========================
    ground_stress_data = {}

    def parse_ground_stress():
        in_disp = False
        for line in lines:
            if "TUSSENPUNTEN VERPLAATSINGEN" in line and "Fundamentele combinatie" in line:
                in_disp = True
                continue
            if in_disp and ("REACTIES" in line or "BELASTINGCOMBINATIES" in line):
                break
            match = re.match(r"\s*(\d+)\s+(\d+)\s+([\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([\d.]+)", line)
            if match:
                beam_num = int(match.group(1))
                position = float(match.group(3))
                ground_stress = float(match.group(8))
                if beam_num <= len(balken):
                    b_start, b_end = balken[beam_num - 1]
                    x1, y1 = get_beam_coord(b_start)
                    x2, y2 = get_beam_coord(b_end)
                    ratio = position / 10
                    x = x1 + ratio * (x2 - x1)
                    y = y1 + ratio * (y2 - y1)
                    ground_stress_data[f"Beam{beam_num}_{position}"] = {'x': x, 'y': y, 'z': ground_stress, 'beam': beam_num}

    parse_ground_stress()

    # ===========================
    # LOAD CASES PARSEN
    # ===========================
    load_cases = {}
    current_bg = None
    in_loads = False
    for line in lines:
        if line.startswith("VELDBELASTINGEN"):
            m = re.match(r"VELDBELASTINGEN\s+B\.G:(\d+)", line)
            if m:
                current_bg = f"BG{m.group(1)}"
                load_cases[current_bg] = []
                in_loads = True
            continue
        if in_loads and line.strip() == "":
            in_loads = False
            current_bg = None
        if in_loads and current_bg:
            m = re.match(r"Balk (\d+:\d+)\s+\d+\s+\S+\s+([-\d.]+)\s+([-\d.]*)\s+([-\d.]+)\s+([-\d.]+)", line)
            if m:
                balk_code = m.group(1)
                q = float(m.group(2))
                afstand = float(m.group(4))
                lengte = float(m.group(5))
                load_cases[current_bg].append({'balk': balk_code, 'q': q, 'afstand': afstand, 'lengte': lengte})

    selected_bg = st.selectbox("Selecteer Load Case (B.G.)", list(load_cases.keys()))

    # ===========================
    # 3D PLOT OPSTELLEN
    # ===========================
    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "scene"}, {"type": "scene"}]],
        subplot_titles=("Ground Stress", "Structuur & Loads")
    )

    # --- Ground Stress ---
    beam_colors = ['#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57', '#FF9FF3', '#54A0FF', '#5F27CD', '#00D2D3']
    beams_data = {}
    for d in ground_stress_data.values():
        b = d['beam']
        if b not in beams_data:
            beams_data[b] = {'x': [], 'y': [], 'z': []}
        beams_data[b]['x'].append(d['x'])
        beams_data[b]['y'].append(d['y'])
        beams_data[b]['z'].append(d['z'])
    for beam_num, data in beams_data.items():
        color = beam_colors[(beam_num - 1) % len(beam_colors)]
        fig.add_trace(go.Scatter3d(
            x=data['x'], y=data['y'], z=data['z'],
            mode='lines+markers',
            name=f"Beam {beam_num} Stress",
            line=dict(width=6, color=color),
            marker=dict(size=3, color=color),
            showlegend=True
        ), row=1, col=1)

    # --- Structuurplot ---
    for i, (b_start, b_end) in enumerate(balken):
        x0, y0, z0 = get_coord_3d(b_start)
        x1, y1, z1 = get_coord_3d(b_end)
        fig.add_trace(go.Scatter3d(
            x=[x0, x1], y=[y0, y1], z=[z0, z1],
            mode='lines',
            name=f"Balk {i+1}",
            line=dict(width=4, color='steelblue'),
            showlegend=True
        ), row=1, col=2)

    # --- Belastingen tekenen (q-lasten & puntlasten) ---
    scaling = 0.05
    for ld in load_cases[selected_bg]:
        balk_idx = int(ld['balk'].split(':')[0]) - 1
        b_start, b_end = balken[balk_idx]
        x0, y0 = get_beam_coord(b_start)
        x1, y1 = get_beam_coord(b_end)

        last_start = ld['afstand']
        last_end = last_start + ld['lengte'] if ld['lengte'] != 0 else last_start + 0.01

        # 20 punten over de last
        n_points = 20
        x_vals = [x0 + ((last_start + i*(last_end-last_start)/n_points)/ld['lengte']) * (x1-x0) for i in range(n_points+1)]
        y_vals = [y0 + ((last_start + i*(last_end-last_start)/n_points)/ld['lengte']) * (y1-y0) for i in range(n_points+1)]
        z_vals = [-ld['q']*scaling]*len(x_vals)

        fig.add_trace(go.Scatter3d(
            x=x_vals, y=y_vals, z=z_vals,
            mode='lines',
            line=dict(color='red', width=6),
            name=f"Load {ld['balk']}",
            showlegend=False
        ), row=1, col=2)

    # ===========================
    # Layout
    # ===========================
    shared_camera = dict(eye=dict(x=1.4, y=1.4, z=1.2))
    fig.update_layout(
        height=700, width=1400,
        scene=dict(
            xaxis=dict(title="X (m)"),
            yaxis=dict(title="Y (m)"),
            zaxis=dict(title="Stress (kN/m²)"),
            camera=shared_camera
        ),
        scene2=dict(
            xaxis=dict(title="X (m)"),
            yaxis=dict(title="Y (m)"),
            zaxis=dict(title="Z (m)"),
            camera=shared_camera
        ),
        legend=dict(
            x=0.45, y=1.0,
            bgcolor='rgba(255,255,255,0.7)',
            bordercolor='rgba(0,0,0,0.2)', borderwidth=1
        )
    )

    st.plotly_chart(fig, use_container_width=True)
