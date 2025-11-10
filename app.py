import streamlit as st
import re
import plotly.graph_objects as go
import numpy as np

st.set_page_config(page_title="Foundation Beam Analysis", layout="wide")

st.title("Foundation Beam Analysis Viewer")
st.markdown("Upload your foundation analysis file to visualize ground stress and loads")

# File uploader
uploaded_file = st.file_uploader("Choose a .txt file", type=['txt'])

if uploaded_file is not None:
    # Read file with fallback encoding
    def read_uploaded_file(file):
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'windows-1252']
        
        for encoding in encodings:
            try:
                file.seek(0)
                content = file.read().decode(encoding)
                lines = content.split('\n')
                return lines
            except UnicodeDecodeError:
                continue
        
        # Last resort
        try:
            file.seek(0)
            content = file.read().decode('utf-8', errors='ignore')
            lines = content.split('\n')
            return lines
        except Exception as e:
            st.error(f"Could not read file: {e}")
            return []

    lines = read_uploaded_file(uploaded_file)
    
    if lines:
        stramienlijnen = {}
        balken = []
        ground_stress_data = {}
        load_cases = {}
        
        # === PARSE STRAMIENLIJNEN ===
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
                    x1 = float(match.group(2))
                    y1 = float(match.group(3))
                    x2 = float(match.group(4))
                    y2 = float(match.group(5))
                    stramienlijnen[naam] = [(x1, y1), (x2, y2)]
        
        # === PARSE BALKEN ===
        in_balken = False
        for line in lines:
            if "BALKEN" in line and "vervolg" not in line.lower():
                in_balken = True
                continue
            if "BALKEN vervolg" in line or "DOORSNEDESECTOREN" in line:
                break
            if in_balken and line.strip():
                match = re.match(r"\s*\d+\s+\S+\s+(\S+)\s+(\S+)", line)
                if match:
                    begin = match.group(1)
                    eind = match.group(2)
                    balken.append((begin, eind))
        
        # === HELPER FUNCTIONS ===
        def get_beam_coord(code):
            lijn_naam, pos_str = code.split(';')
            i = int(pos_str)
            
            if lijn_naam not in stramienlijnen:
                raise ValueError(f"Stramienlijn {lijn_naam} niet gevonden")
            
            p1, p2 = stramienlijnen[lijn_naam]
            x = p1[0] + (i - 1) * (p2[0] - p1[0]) / 3
            y = p1[1] + (i - 1) * (p2[1] - p1[1]) / 3
            return (x, y)
        
        def get_beam_length(beam_num):
            in_sections = False
            for line in lines:
                if "DOORSNEDESECTOREN" in line:
                    in_sections = True
                    continue
                if in_sections and line.strip():
                    match = re.match(rf"Balk\s+{beam_num}:\d+\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", line)
                    if match:
                        return float(match.group(3))
            return 0
        
        def get_coord_3d(code):
            lijn_naam, pos_str = code.split(';')
            i = int(pos_str)
            
            if lijn_naam not in stramienlijnen:
                raise ValueError(f"Stramienlijn {lijn_naam} niet gevonden")
            
            p1, p2 = stramienlijnen[lijn_naam]
            x = p1[0] + (i - 1) * (p2[0] - p1[0]) / 3
            y = p1[1] + (i - 1) * (p2[1] - p1[1]) / 3
            z = 0.0
            
            return (x, y, z)
        
        def get_beam_3d_coords(beam_num, position):
            if beam_num > len(balken):
                return None
            
            beam_start, beam_end = balken[beam_num - 1]
            start_coord = get_beam_coord(beam_start)
            end_coord = get_beam_coord(beam_end)
            
            beam_length = get_beam_length(beam_num)
            if beam_length <= 0:
                return None
            
            ratio = position / beam_length
            x = start_coord[0] + ratio * (end_coord[0] - start_coord[0])
            y = start_coord[1] + ratio * (end_coord[1] - start_coord[1])
            
            return (x, y, 0.0)
        
        # === PARSE LOAD CASES ===
        def parse_load_cases():
            in_loads_section = False
            current_bg = None
            current_beam = None
            
            for line in lines:
                bg_match = re.match(r"VELDBELASTINGEN\s+B\.G:(\d+)", line)
                if bg_match:
                    current_bg = int(bg_match.group(1))
                    if current_bg not in load_cases:
                        load_cases[current_bg] = {}
                    in_loads_section = True
                    continue
                
                if in_loads_section and ("BELASTINGCOMBINATIES" in line or "REACTIES" in line):
                    in_loads_section = False
                    continue
                
                if in_loads_section and line.strip():
                    beam_match = re.match(r"Balk\s+(\d+):", line)
                    if beam_match:
                        current_beam = int(beam_match.group(1))
                        if current_beam not in load_cases[current_bg]:
                            load_cases[current_bg][current_beam] = []
                    
                    q_match = re.match(r"Balk\s+\d+:\d+\s+\d+\s+1:q-last\s+([-\d.]+)\s+([-\d.]+)\s+([\d.]+)\s+([\d.]+)", line)
                    if q_match and current_beam:
                        q1 = float(q_match.group(1))
                        q2 = float(q_match.group(2))
                        distance = float(q_match.group(3))
                        length = float(q_match.group(4))
                        load_cases[current_bg][current_beam].append({
                            'type': 'distributed',
                            'q1': q1,
                            'q2': q2,
                            'start': distance,
                            'length': length
                        })
                    
                    p_match = re.match(r"Balk\s+\d+:\d+\s+\d+\s+8:Puntlast\s+([-\d.]+)\s+([\d.]+)", line)
                    if p_match and current_beam:
                        force = float(p_match.group(1))
                        position = float(p_match.group(2))
                        load_cases[current_bg][current_beam].append({
                            'type': 'point',
                            'force': force,
                            'position': position
                        })
        
        parse_load_cases()
        
        # === PARSE GROUND STRESS ===
        def parse_ground_stress():
            in_displacement_section = False
            
            for i, line in enumerate(lines):
                if "TUSSENPUNTEN VERPLAATSINGEN" in line and "Fundamentele combinatie" in line:
                    in_displacement_section = True
                    continue
                    
                if in_displacement_section and ("REACTIES" in line or "BELASTINGCOMBINATIES" in line):
                    break
                    
                if in_displacement_section and line.strip():
                    match = re.match(r"\s*(\d+)\s+(\d+)\s+([\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([\d.]+)", line)
                    if match:
                        beam_num = int(match.group(1))
                        position = float(match.group(3))
                        ground_stress = float(match.group(8))
                        
                        if beam_num <= len(balken):
                            beam_start, beam_end = balken[beam_num - 1]
                            
                            try:
                                start_coord = get_beam_coord(beam_start)
                                end_coord = get_beam_coord(beam_end)
                                
                                beam_length = get_beam_length(beam_num)
                                if beam_length > 0:
                                    ratio = position / beam_length
                                    
                                    x = start_coord[0] + ratio * (end_coord[0] - start_coord[0])
                                    y = start_coord[1] + ratio * (end_coord[1] - start_coord[1])
                                    
                                    coord_key = f"Beam{beam_num}_Pos{position:.3f}"
                                    ground_stress_data[coord_key] = {
                                        'x': x, 'y': y, 'z': ground_stress,
                                        'beam': beam_num, 'position': position,
                                        'stress': ground_stress
                                    }
                            except:
                                continue
        
        parse_ground_stress()
        
        # === VISUALIZATION FUNCTIONS ===
        def create_ground_stress_plot():
            fig = go.Figure()
            
            beam_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57', '#FF9FF3', '#54A0FF', '#5F27CD', '#00D2D3']
            
            for i, (b_start, b_end) in enumerate(balken):
                try:
                    x0, y0, z0 = get_coord_3d(b_start)
                    x1, y1, z1 = get_coord_3d(b_end)
                    
                    fig.add_trace(go.Scatter3d(
                        x=[x0, x1],
                        y=[y0, y1],
                        z=[z0, z1],
                        mode='lines',
                        name=f"Beam {i+1} Structure",
                        line=dict(width=2, color='rgba(100,100,100,0.4)'),
                        showlegend=True,
                        hoverinfo='skip'
                    ))
                except Exception as e:
                    pass
            
            if ground_stress_data:
                beams_data = {}
                for key, data in ground_stress_data.items():
                    beam_num = data['beam']
                    if beam_num not in beams_data:
                        beams_data[beam_num] = {'x': [], 'y': [], 'z': [], 'stress': [], 'pos': []}
                    beams_data[beam_num]['x'].append(data['x'])
                    beams_data[beam_num]['y'].append(data['y'])
                    beams_data[beam_num]['z'].append(data['z'])
                    beams_data[beam_num]['stress'].append(data['stress'])
                    beams_data[beam_num]['pos'].append(data['position'])
                
                all_z_values = []
                for data in beams_data.values():
                    all_z_values.extend(data['z'])
                z_min, z_max = min(all_z_values), max(all_z_values)
                
                for beam_num, data in beams_data.items():
                    sorted_indices = sorted(range(len(data['pos'])), key=lambda i: data['pos'][i])
                    x_sorted = [data['x'][i] for i in sorted_indices]
                    y_sorted = [data['y'][i] for i in sorted_indices]
                    z_sorted = [data['z'][i] for i in sorted_indices]
                    stress_sorted = [data['stress'][i] for i in sorted_indices]
                    pos_sorted = [data['pos'][i] for i in sorted_indices]
                    
                    n_points = len(x_sorted)
                    vertices_x = x_sorted + x_sorted
                    vertices_y = y_sorted + y_sorted
                    vertices_z = z_sorted + [0] * n_points
                    
                    faces = []
                    for i in range(n_points - 1):
                        faces.append([i + n_points, i, i + n_points + 1])
                        faces.append([i, i + 1, i + n_points + 1])
                    
                    fig.add_trace(go.Mesh3d(
                        x=vertices_x,
                        y=vertices_y,
                        z=vertices_z,
                        i=[face[0] for face in faces],
                        j=[face[1] for face in faces], 
                        k=[face[2] for face in faces],
                        intensity=z_sorted + [0] * n_points,
                        colorscale='Viridis',
                        cmin=z_min,
                        cmax=z_max,
                        name=f"Beam {beam_num} Stress Surface",
                        showscale=True if beam_num == 1 else False,
                        colorbar=dict(
                            title=dict(text="Ground Stress<br>(kN/m²)", font=dict(size=12)),
                            x=1.02,
                            thickness=15,
                            len=0.7
                        ),
                        opacity=0.85,
                        showlegend=True,
                        hovertemplate=f'<b>Beam {beam_num}</b><br>' +
                                     'Ground Stress: %{z:.1f} kN/m²<br>' +
                                     'X: %{x:.1f}m, Y: %{y:.1f}m<extra></extra>'
                    ))
                    
                    fig.add_trace(go.Scatter3d(
                        x=x_sorted,
                        y=y_sorted,
                        z=z_sorted,
                        mode='lines',
                        name=f"Beam {beam_num} Peak Line",
                        line=dict(width=3, color='rgba(0,0,0,0.6)'),
                        showlegend=True,
                        hovertemplate=f'<b>Beam {beam_num} Peak</b><br>' +
                                     'Position: %{customdata[0]:.2f}m<br>' +
                                     'Ground Stress: %{customdata[1]:.1f} kN/m²<br>' +
                                     'X: %{x:.1f}m, Y: %{y:.1f}m<extra></extra>',
                        customdata=list(zip(pos_sorted, stress_sorted))
                    ))
            
            unique_points = set()
            for b_start, b_end in balken:
                unique_points.add(b_start)
                unique_points.add(b_end)
            
            node_x, node_y, node_z, node_labels = [], [], [], []
            for point in sorted(unique_points):
                try:
                    x, y, z = get_coord_3d(point)
                    node_x.append(x)
                    node_y.append(y) 
                    node_z.append(z)
                    node_labels.append(point)
                except Exception as e:
                    pass
            
            if node_x:
                fig.add_trace(go.Scatter3d(
                    x=node_x,
                    y=node_y,
                    z=node_z,
                    mode='markers+text',
                    name='Beam Endpoints',
                    marker=dict(size=8, color='black', symbol='circle'),
                    text=node_labels,
                    textposition="top center",
                    textfont=dict(size=10),
                    hovertemplate='<b>Node: %{text}</b><br>' +
                                 'X: %{x:.2f}m<br>' +
                                 'Y: %{y:.2f}m<extra></extra>'
                ))
            
            fig.update_layout(
                title=dict(
                    text="Ground Stress Distribution",
                    x=0.5,
                    font=dict(size=20, color='black')
                ),
                scene=dict(
                    xaxis=dict(title="X (m)", showgrid=False, showline=False, zeroline=False, showticklabels=True, backgroundcolor='rgba(0,0,0,0)', gridcolor='rgba(0,0,0,0)'),
                    yaxis=dict(title="Y (m)", showgrid=False, showline=False, zeroline=False, showticklabels=True, backgroundcolor='rgba(0,0,0,0)', gridcolor='rgba(0,0,0,0)'),
                    zaxis=dict(title="Ground Stress (kN/m²)", showgrid=False, showline=False, zeroline=False, showticklabels=True, backgroundcolor='rgba(0,0,0,0)', gridcolor='rgba(0,0,0,0)'),
                    bgcolor='rgba(0,0,0,0)',
                    aspectmode='manual',
                    aspectratio=dict(x=1, y=1, z=0.8),
                    camera=dict(eye=dict(x=1.3, y=1.3, z=1.5))
                ),
                showlegend=False,
                margin=dict(l=0, r=0, t=60, b=0),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                autosize=True,
                height=700
            )
            
            return fig
        
        def create_loads_plot(bg_number):
            if bg_number not in load_cases:
                return None
            
            fig = go.Figure()
            beam_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57', '#FF9FF3', '#54A0FF', '#5F27CD', '#00D2D3']
            
            for i, (b_start, b_end) in enumerate(balken):
                try:
                    x0, y0, z0 = get_coord_3d(b_start)
                    x1, y1, z1 = get_coord_3d(b_end)
                    
                    color = beam_colors[i % len(beam_colors)]
                    
                    fig.add_trace(go.Scatter3d(
                        x=[x0, x1],
                        y=[y0, y1],
                        z=[z0, z1],
                        mode='lines',
                        name=f"Beam {i+1}",
                        line=dict(width=6, color=color),
                        showlegend=False,
                        hovertemplate=f'<b>Beam {i+1}</b><br>X: %{{x:.2f}}m<br>Y: %{{y:.2f}}m<extra></extra>'
                    ))
                except Exception as e:
                    pass
            
            arrow_scale = 0.05
            
            for beam_num, loads in load_cases[bg_number].items():
                if beam_num > len(balken):
                    continue
                
                beam_length = get_beam_length(beam_num)
                color = beam_colors[(beam_num-1) % len(beam_colors)]
                
                for load in loads:
                    if load['type'] == 'point':
                        coords = get_beam_3d_coords(beam_num, load['position'])
                        if coords:
                            x, y, z = coords
                            force_magnitude = abs(load['force'])
                            arrow_height = force_magnitude * arrow_scale
                            
                            fig.add_trace(go.Scatter3d(
                                x=[x, x],
                                y=[y, y],
                                z=[arrow_height, 0],
                                mode='lines',
                                line=dict(width=8, color='red'),
                                showlegend=False,
                                hovertemplate=f'<b>Point Load</b><br>Beam {beam_num}<br>' +
                                             f'Force: {load["force"]:.1f} kN<br>' +
                                             f'Position: {load["position"]:.2f}m<extra></extra>'
                            ))
                            
                            fig.add_trace(go.Cone(
                                x=[x],
                                y=[y],
                                z=[0],
                                u=[0],
                                v=[0],
                                w=[-1],
                                sizemode='absolute',
                                sizeref=arrow_height * 0.3,
                                colorscale=[[0, 'red'], [1, 'red']],
                                showscale=False,
                                showlegend=False,
                                hovertemplate=f'<b>Point Load</b><br>Beam {beam_num}<br>' +
                                             f'Force: {load["force"]:.1f} kN<extra></extra>'
                            ))
                            
                            fig.add_trace(go.Scatter3d(
                                x=[x],
                                y=[y],
                                z=[arrow_height],
                                mode='text',
                                text=[f"{load['force']:.1f} kN"],
                                textposition="top center",
                                textfont=dict(size=12, color='red', family='Arial Black'),
                                showlegend=False,
                                hoverinfo='skip'
                            ))
                    
                    elif load['type'] == 'distributed':
                        start_pos = load['start']
                        end_pos = start_pos + load['length']
                        
                        n_arrows = max(3, int(load['length'] / 0.5))
                        positions = np.linspace(start_pos, end_pos, n_arrows)
                        
                        for i, pos in enumerate(positions):
                            coords = get_beam_3d_coords(beam_num, pos)
                            if coords:
                                x, y, z = coords
                                
                                ratio = (pos - start_pos) / load['length'] if load['length'] > 0 else 0
                                q_local = abs(load['q1']) + ratio * (abs(load['q2']) - abs(load['q1']))
                                arrow_height = q_local * arrow_scale * 2
                                
                                fig.add_trace(go.Scatter3d(
                                    x=[x, x],
                                    y=[y, y],
                                    z=[arrow_height, 0],
                                    mode='lines',
                                    line=dict(width=4, color='orange'),
                                    showlegend=False,
                                    hovertemplate=f'<b>Distributed Load</b><br>Beam {beam_num}<br>' +
                                                 f'q: {q_local:.1f} kN/m<br>' +
                                                 f'Position: {pos:.2f}m<extra></extra>'
                                ))
                                
                                fig.add_trace(go.Cone(
                                    x=[x],
                                    y=[y],
                                    z=[0],
                                    u=[0],
                                    v=[0],
                                    w=[-1],
                                    sizemode='absolute',
                                    sizeref=arrow_height * 0.3,
                                    colorscale=[[0, 'orange'], [1, 'orange']],
                                    showscale=False,
                                    showlegend=False,
                                    hovertemplate=f'<b>Distributed Load</b><br>Beam {beam_num}<br>' +
                                                 f'q: {q_local:.1f} kN/m<extra></extra>'
                                ))
                                
                                if i == 0 or i == len(positions) - 1:
                                    fig.add_trace(go.Scatter3d(
                                        x=[x],
                                        y=[y],
                                        z=[arrow_height],
                                        mode='text',
                                        text=[f"{q_local:.1f} kN/m"],
                                        textposition="top center",
                                        textfont=dict(size=10, color='orange', family='Arial Black'),
                                        showlegend=False,
                                        hoverinfo='skip'
                                    ))
            
            unique_points = set()
            for b_start, b_end in balken:
                unique_points.add(b_start)
                unique_points.add(b_end)
            
            node_x, node_y, node_z, node_labels = [], [], [], []
            for point in sorted(unique_points):
                try:
                    x, y, z = get_coord_3d(point)
                    node_x.append(x)
                    node_y.append(y) 
                    node_z.append(z)
                    node_labels.append(point)
                except Exception as e:
                    pass
            
            if node_x:
                fig.add_trace(go.Scatter3d(
                    x=node_x,
                    y=node_y,
                    z=node_z,
                    mode='markers+text',
                    marker=dict(size=8, color='black', symbol='circle'),
                    text=node_labels,
                    textposition="top center",
                    textfont=dict(size=10),
                    showlegend=False,
                    hovertemplate='<b>Node: %{text}</b><br>X: %{x:.2f}m<br>Y: %{y:.2f}m<extra></extra>'
                ))
            
            load_case_name = "Permanent" if bg_number == 1 else "Variable"
            fig.update_layout(
                title=dict(
                    text=f"Load Case B.G:{bg_number} - {load_case_name}",
                    x=0.5,
                    font=dict(size=20, color='black')
                ),
                scene=dict(
                    xaxis=dict(title="X (m)", showgrid=True, gridcolor='rgba(200,200,200,0.3)', showline=True, zeroline=False, showticklabels=True),
                    yaxis=dict(title="Y (m)", showgrid=True, gridcolor='rgba(200,200,200,0.3)', showline=True, zeroline=False, showticklabels=True),
                    zaxis=dict(title="Load (kN or kN/m)", showgrid=True, gridcolor='rgba(200,200,200,0.3)', showline=True, zeroline=False, showticklabels=True),
                    bgcolor='rgba(240,240,240,1)',
                    aspectmode='manual',
                    aspectratio=dict(x=1, y=1, z=0.6),
                    camera=dict(eye=dict(x=1.5, y=1.5, z=1.2))
                ),
                showlegend=False,
                margin=dict(l=0, r=0, t=60, b=0),
                paper_bgcolor='white',
                autosize=True,
                height=700
            )
            
            return fig
        
        # === STREAMLIT UI ===
        st.success(f"✅ File loaded successfully!")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Grid Lines", len(stramienlijnen))
        with col2:
            st.metric("Beams", len(balken))
        with col3:
            st.metric("Load Cases", len(load_cases))
        
        st.markdown("---")
        
        # Tabs for different views
        tabs = st.tabs(["Ground Stress"] + [f"Load Case B.G:{bg}" for bg in sorted(load_cases.keys())])
        
        with tabs[0]:
            st.subheader("Ground Stress Distribution")
            if ground_stress_data:
                fig_stress = create_ground_stress_plot()
                st.plotly_chart(fig_stress, use_container_width=True)
            else:
                st.warning("No ground stress data found in the file.")
        
        for idx, bg_num in enumerate(sorted(load_cases.keys())):
            with tabs[idx + 1]:
                load_case_name = "Permanent" if bg_num == 1 else "Variable"
                st.subheader(f"Load Case B.G:{bg_num} - {load_case_name}")
                
                # Show summary statistics
                total_point_loads = sum(1 for beam_loads in load_cases[bg_num].values() 
                                       for load in beam_loads if load['type'] == 'point')
                total_distributed = sum(1 for beam_loads in load_cases[bg_num].values() 
                                       for load in beam_loads if load['type'] == 'distributed')
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Point Loads", total_point_loads)
                with col2:
                    st.metric("Distributed Loads", total_distributed)
                
                fig_loads = create_loads_plot(bg_num)
                if fig_loads:
                    st.plotly_chart(fig_loads, use_container_width=True)
                else:
                    st.warning(f"No load data found for B.G:{bg_num}")

else:
    st.info("👆 Please upload a foundation analysis file to begin")
    
    st.markdown("""
    ### Expected File Format
    The application expects a text file containing:
    - **STRAMIENLIJNEN
""")

