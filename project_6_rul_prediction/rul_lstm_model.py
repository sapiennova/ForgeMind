import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense

# Load dataset
df = pd.read_csv("dataset/FD001.csv", sep=' ', header=None)
df.dropna(axis=1, inplace=True)

# Preprocessing
scaler = MinMaxScaler()
scaled_data = scaler.fit_transform(df.iloc[:, 5:])

# Create sequences
def create_sequences(data, window_size=30):
    X, y = [], []
    for i in range(len(data) - window_size):
        X.append(data[i:i+window_size])
        y.append(data[i+window_size, 0])  # Assume RUL is first column
    return np.array(X), np.array(y)

X, y = create_sequences(scaled_data)

# Model
model = Sequential()
model.add(LSTM(64, return_sequences=True, input_shape=(X.shape[1], X.shape[2])))
model.add(LSTM(32))
model.add(Dense(1))
model.compile(loss='mse', optimizer='adam')
model.fit(X, y, epochs=10, batch_size=64, validation_split=0.2)
