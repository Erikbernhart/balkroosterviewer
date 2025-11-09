import streamlit as st
import re
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(layout="wide", page_title="Spanningen en Structuur")

st.title("Vergelijking Spanningen en Structuur")

# === Bestand uploaden ===
uploaded_file = st.file_uploader("Upload fundering_nieuwV3.txt", type=["txt"])

if uploaded_file is not None:
    # === Bestand inlezen met fallback encoding ===
    def read_file_with_fallback_encoding(file):
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'windows-1252']
        for encoding in encodings:
            try:
                lines = file.getvalue().decode(encoding).splitlines()
                st.success(f"Bestand gelezen met encoding: {encoding}")
                return lines
            except UnicodeDecodeError:
                continue
        # fallback
        lines = file.getvalue().decode('utf-8', errors='ignore').splitlines()
        return lines

    lines = read_file_with_fallback_encoding(uploaded_file)

    # === Data containers ===
    stramienlijnen = {}
    balken = []
    ground_stress_data = {}

    # === STRAMIENLIJNEN PARSEN ===
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

    # === BALKEN PARSEN ===
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

    # === Functies voor coördinaten ===
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

    # === Ground stress parser ===
    def parse_ground_stress():
        in_displacement_section = False
        for i, line in enumerate(lines):
            if "TUSSENPUNTEN VERPLAATSINGEN" in line and "Fundamentele combinatie" in line:
                in_displacement_section = True
                continue
            if in_displacement_section and ("REACTIES" in line or "BELASTINGCOMBINATIES" in line):
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
                    ratio = position / 10  # vereenvoudigd
                    x = x1 + ratio * (x2 - x1)
                    y = y1 + ratio * (y2 - y1)
                    ground_stress_data[f"Beam{beam_num}_{position}"] = {'x': x, 'y': y, 'z': ground_stress, 'beam': beam_num}

    parse_ground_stress()

    # === 3D PLOT: Ground Stress ===
    fig_stress = go.Figure()
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
        fig_stress.add_trace(go.Scatter3d(
            x=data['x'], y=data['y'], z=data['z'],
            mode='lines+markers',
            name=f"Beam {beam_num} Stress",
            line=dict(width=6, color=color),
            marker=dict(size=3, color=color),
            hovertemplate='Beam %{text}<br>Stress: %{z:.1f} kN/m²<extra></extra>'
        ))

    # === 3D STRUCTUURPLOT ===
    fig_structure = go.Figure()
    for i, (b_start, b_end) in enumerate(balken):
        x0, y0, z0 = get_coord_3d(b_start)
        x1, y1, z1 = get_coord_3d(b_end)
        fig_structure.add_trace(go.Scatter3d(
            x=[x0, x1], y=[y0, y1], z=[z0, z1],
            mode='lines',
            name=f"Balk {i+1}",
            line=dict(width=4, color='steelblue'),
            hovertemplate=f"<b>Balk {i+1}</b><br>{b_start} → {b_end}<extra></extra>"
        ))

    points = set(sum(balken, ()))
    node_x, node_y, node_z, node_labels = [], [], [], []
    for p in sorted(points):
        x, y, z = get_coord_3d(p)
        node_x.append(x)
        node_y.append(y)
        node_z.append(z)
        node_labels.append(p)
    fig_structure.add_trace(go.Scatter3d(
        x=node_x, y=node_y, z=node_z,
        mode='markers+text',
        name="Knopen",
        marker=dict(size=6, color='darkred'),
        text=node_labels,
        textposition="top center",
        textfont=dict(size=10),
    ))

    # === COMBINEER DE TWEE PLOTS NAAST ELKAAR ===
    fig_combined = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "scene"}, {"type": "scene"}]],
        subplot_titles=("Ground Stress", "Structuurmodel")
    )

    for trace in fig_stress.data:
        trace.showlegend = True
        fig_combined.add_trace(trace, row=1, col=1)

    for trace in fig_structure.data:
        trace.showlegend = True
        fig_combined.add_trace(trace, row=1, col=2)

    shared_camera = dict(eye=dict(x=1.4, y=1.4, z=1.2))
    fig_combined.update_layout(
        height=700, width=1400,
        title_text="Vergelijking Spanningen en Structuur",
        scene=dict(
            xaxis=dict(title="X (m)", showgrid=False, zeroline=False, showline=False),
            yaxis=dict(title="Y (m)", showgrid=False, zeroline=False, showline=False),
            zaxis=dict(title="Ground Stress (kN/m²)", showgrid=False, zeroline=False, showline=False),
            bgcolor='rgba(0,0,0,0)',
            camera=shared_camera
        ),
        scene2=dict(
            xaxis=dict(title="X (m)", showgrid=False, zeroline=False, showline=False),
            yaxis=dict(title="Y (m)", showgrid=False, zeroline=False, showline=False),
            zaxis=dict(title="Z (m)", showgrid=False, zeroline=False, showline=False),
            bgcolor='rgba(0,0,0,0)',
            camera=shared_camera
        ),
        legend=dict(
            x=0.45, y=1.0,
            bgcolor='rgba(255,255,255,0.7)',
            bordercolor='rgba(0,0,0,0.2)', borderwidth=1
        )
    )

    # === Toon in Streamlit ===
    st.plotly_chart(fig_combined, use_container_width=True)
