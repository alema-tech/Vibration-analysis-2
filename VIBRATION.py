# Import necessary libraries
import streamlit as st
import numpy as np
import pandas as pd
import pywt
import plotly.graph_objs as go
from scipy.signal import butter, filtfilt
from scipy.stats import kurtosis
import websocket
import json
import time

# Set Streamlit page configuration
st.set_page_config(
    page_title="Real-Time Vibration Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Function to set up a WebSocket connection to NodeMCU
def fetch_data_ws(websocket_url):
    """Fetches real-time JSON data from NodeMCU via WebSocket."""
    ws = websocket.create_connection(websocket_url)
    real_time_data_stream = []
    try:
        while True:
            result = ws.recv()
            data = json.loads(result)
            real_time_data_stream.append(data)
            if len(real_time_data_stream) >= 100:  # Limit the buffer to 100 samples
                real_time_data_stream.pop(0)
            yield real_time_data_stream
    except websocket.WebSocketException as websocket_error:
        st.error(f"WebSocket error: {websocket_error}")
    finally:
        ws.close()

# Data processing function
def process_data(data, lowcut, highcut, wavelet_type, decomposition_level, fs=1000):
    """Processes accelerometer data by filtering and wavelet transformation."""
    df = pd.DataFrame(data)

    # Check if the required columns are present
    if not all(col in df.columns for col in ["Time", "X", "Y", "Z"]):
        st.error("Data format is incorrect. Required columns: Time, X, Y, Z")
        return None

    timestamp, x, y, z = df["Time"].values, df["X"].values, df["Y"].values, df["Z"].values

    x_filtered_signal = combined_filter(x, lowcut, highcut, fs)
    y_filtered_signal = combined_filter(y, lowcut, highcut, fs)
    z_filtered_signal = combined_filter(z, lowcut, highcut, fs)

    # Scientific statistics
    stats = {
        'X': {"RMS": np.sqrt(np.mean(x_filtered_signal ** 2)), "Kurtosis": kurtosis(x_filtered_signal)},
        'Y': {"RMS": np.sqrt(np.mean(y_filtered_signal ** 2)), "Kurtosis": kurtosis(y_filtered_signal)},
        'Z': {"RMS": np.sqrt(np.mean(z_filtered_signal ** 2)), "Kurtosis": kurtosis(z_filtered_signal)},
    }
    st.write("### Scientific Metrics (RMS and Kurtosis)")
    st.json(stats)

    return timestamp, x_filtered_signal, y_filtered_signal, z_filtered_signal

# Filter function
def combined_filter(data, lowcut, highcut, fs, order=5):
    """Applies low-pass and high-pass Butterworth filters to the data."""
    b_low, a_low = butter(order, lowcut / (0.5 * fs), btype='low')
    low_passed = filtfilt(b_low, a_low, data)
    b_high, a_high = butter(order, highcut / (0.5 * fs), btype='high')
    return filtfilt(b_high, a_high, low_passed)

# Plotting function for wavelet analysis
def plot_dwt_analysis(timestamp, signal, title, wavelet_type, decomposition_level, graph_type="3D"):
    """Plots Discrete Wavelet Transform (DWT) analysis results in 2D or 3D with Plotly."""
    coeffs = pywt.wavedec(signal, wavelet_type, level=decomposition_level)
    levels = len(coeffs) - 1
    time_indices = [np.linspace(0, len(signal), len(c)) for c in coeffs]

    fig = go.Figure()
    if graph_type == "3D":
        for level in range(1, levels + 1):
            t = time_indices[level]
            amplitude = np.abs(coeffs[level])
            fig.add_trace(go.Scatter3d(
                x=t, y=[level] * len(t), z=amplitude,
                mode='lines', name=f'Level {level}',
                line=dict(width=2)
            ))
        fig.update_layout(
            title=f'{title} - Time vs Level vs Amplitude',
            scene=dict(
                xaxis_title="Time (s)",
                yaxis_title="Decomposition Level",
                zaxis_title="Amplitude"
            )
        )
    else:
        for level in range(1, levels + 1):
            t = time_indices[level]
            amplitude = np.abs(coeffs[level])
            fig.add_trace(go.Scatter(
                x=t, y=amplitude,
                mode='lines', name=f'Level {level}'
            ))
        fig.update_layout(
            title=f'{title} - Time vs Amplitude',
            xaxis_title="Time (s)",
            yaxis_title="Amplitude"
        )

    st.plotly_chart(fig)

# Sidebar configuration
st.sidebar.title("Vibration Analysis Configuration")
ws_url_input = st.sidebar.text_input("WebSocket URL", "ws://192.168.1.1:80")
lowcut = st.sidebar.number_input("Low Cutoff Frequency (Hz)", min_value=0.1, value=0.5, step=0.1)
highcut = st.sidebar.number_input("High Cutoff Frequency (Hz)", min_value=0.1, value=20.0, step=0.1)
wavelet_type = st.sidebar.selectbox("Wavelet Type", pywt.wavelist(), index=0)
decomposition_level = st.sidebar.number_input("Decomposition Level", min_value=1, value=3, step=1)
graph_type = st.sidebar.radio("Graph Type", ("3D", "2D"))

# Real-time data fetching and processing
if st.sidebar.button("Start Real-Time Analysis"):
    st.info("Connecting to WebSocket and analyzing data. Please wait...")
    try:
        for real_time_data in fetch_data_ws(ws_url_input):
            results = process_data(real_time_data, lowcut, highcut, wavelet_type, decomposition_level)
            if results is not None and isinstance(results, tuple) and len(results) == 4:
                timestamp, x_filtered_signal, y_filtered_signal, z_filtered_signal = results
                st.success("Data successfully fetched and processed.")

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write("### X-Axis Vibration Analysis")
                    plot_dwt_analysis(timestamp, x_filtered_signal, "X-Axis Vibration", wavelet_type, decomposition_level, graph_type)
                with col2:
                    st.write("### Y-Axis Vibration Analysis")
                    plot_dwt_analysis(timestamp, y_filtered_signal, "Y-Axis Vibration", wavelet_type, decomposition_level, graph_type)
                with col3:
                    st.write("### Z-Axis Vibration Analysis")
                    plot_dwt_analysis(timestamp, z_filtered_signal, "Z-Axis Vibration", wavelet_type, decomposition_level, graph_type)

            else:
                st.warning("No valid data received for unpacking. Please verify the data format and source.")

            time.sleep(0.1)  # Adjust delay as needed
    except Exception as e:
        st.error(f"Error in real-time analysis: {e}")
else:
    st.warning("Press 'Start Real-Time Analysis' to begin data acquisition.")
