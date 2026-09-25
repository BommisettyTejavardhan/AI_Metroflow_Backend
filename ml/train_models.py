import os
import json
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, IsolationForest
from sklearn.metrics import mean_absolute_error, mean_squared_error, accuracy_score, confusion_matrix
import joblib

def main():
    print("Starting ML Model Training Pipeline...")
    os.makedirs("ml/models", exist_ok=True)
    
    # ----------------------------------------------------
    # 1. LOAD DATASETS
    # ----------------------------------------------------
    metro_csv_path = "datasets/delhi_metro_updated.csv"
    delay_csv_path = "datasets/public_transport_delays.csv"
    
    if not os.path.exists(metro_csv_path) or not os.path.exists(delay_csv_path):
        print("Error: Required datasets are missing in datasets/ folder.")
        return

    print("Loading datasets...")
    df_metro = pd.read_csv(metro_csv_path)
    df_delay = pd.read_csv(delay_csv_path)
    
    # Clean strings in metro dataset
    df_metro['From_Station'] = df_metro['From_Station'].str.strip()
    df_metro['To_Station'] = df_metro['To_Station'].str.strip()
    df_metro['Remarks'] = df_metro['Remarks'].str.strip().fillna('normal')
    df_metro['Ticket_Type'] = df_metro['Ticket_Type'].str.strip().fillna('Unknown')
    
    # ----------------------------------------------------
    # 2. TRAIN PASSENGER DEMAND MODEL (REGRESSION)
    # ----------------------------------------------------
    print("Preprocessing Passenger Demand dataset...")
    # Convert date
    df_metro['Date'] = pd.to_datetime(df_metro['Date'])
    df_metro['DayOfWeek'] = df_metro['Date'].dt.dayofweek
    df_metro['Month'] = df_metro['Date'].dt.month
    df_metro['IsWeekend'] = df_metro['DayOfWeek'].apply(lambda x: 1 if x >= 5 else 0)
    
    # Label encode stations and remarks
    stations = sorted(list(set(df_metro['From_Station'].unique()) | set(df_metro['To_Station'].unique())))
    station_map = {station: i for i, station in enumerate(stations)}
    
    remarks = sorted(df_metro['Remarks'].unique())
    remarks_map = {rem: i for i, rem in enumerate(remarks)}
    
    df_metro['From_Station_Code'] = df_metro['From_Station'].map(station_map)
    df_metro['To_Station_Code'] = df_metro['To_Station'].map(station_map)
    df_metro['Remarks_Code'] = df_metro['Remarks'].map(remarks_map)
    
    # Drop rows with NaN in critical features
    df_metro = df_metro.dropna(subset=['From_Station_Code', 'To_Station_Code', 'Passengers', 'Distance_km'])
    
    demand_features = ['From_Station_Code', 'To_Station_Code', 'Distance_km', 'DayOfWeek', 'Month', 'IsWeekend', 'Remarks_Code']
    X_demand = df_metro[demand_features]
    y_demand = df_metro['Passengers']
    
    # We downsample if the dataset is too huge to train quickly, but 150k is small enough for Random Forest if we limit estimators
    print(f"Demand dataset shape: {X_demand.shape}. Splitting dataset...")
    X_train_dem, X_test_dem, y_train_dem, y_test_dem = train_test_split(X_demand, y_demand, test_size=0.2, random_state=42)
    
    print("Training Passenger Demand Model (RandomForestRegressor)...")
    demand_model = RandomForestRegressor(n_estimators=50, max_depth=12, random_state=42, n_jobs=-1)
    demand_model.fit(X_train_dem, y_train_dem)
    
    y_pred_dem = demand_model.predict(X_test_dem)
    dem_mae = mean_absolute_error(y_test_dem, y_pred_dem)
    dem_rmse = np.sqrt(mean_squared_error(y_test_dem, y_pred_dem))
    print(f"Demand Model Evaluation -> MAE: {dem_mae:.4f}, RMSE: {dem_rmse:.4f}")
    
    # Feature importance
    dem_importances = demand_model.feature_importances_
    dem_feat_imp = {feat: float(imp) for feat, imp in zip(demand_features, dem_importances)}
    
    # Save demand model & encoder maps
    joblib.dump(demand_model, "ml/models/demand_model.pkl")
    
    # ----------------------------------------------------
    # 2.5 TRAIN ANOMALY DETECTION MODEL (ISOLATION FOREST)
    # ----------------------------------------------------
    print("Training Anomaly Detection Model (Isolation Forest)...")
    
    # We use all features including passengers for anomaly detection
    anomaly_features = ['From_Station_Code', 'To_Station_Code', 'Distance_km', 'DayOfWeek', 'Month', 'IsWeekend', 'Remarks_Code', 'Passengers']
    X_anomaly = df_metro[anomaly_features]
    
    # Contamination defines the proportion of outliers in the data set (5%)
    anomaly_model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42, n_jobs=-1)
    anomaly_model.fit(X_anomaly)
    
    # Calculate anomaly scores for metrics (-1 is anomaly, 1 is normal)
    # decision_function returns average anomaly score, lower is more abnormal
    scores = anomaly_model.decision_function(X_anomaly)
    mean_score = float(np.mean(scores))
    std_score = float(np.std(scores))
    
    print(f"Anomaly Model Trained. Mean Score: {mean_score:.4f}")
    
    joblib.dump(anomaly_model, "ml/models/anomaly_model.pkl")
    
    # ----------------------------------------------------
    # 3. TRAIN DELAY CLASSIFIER & REGRESSOR
    # ----------------------------------------------------
    print("Preprocessing Delay dataset...")
    # Filter metro or use all (the dataset contains different transit types, filtering for Metro is best)
    df_metro_delay = df_delay[df_delay['transport_type'] == 'Metro'].copy()
    if len(df_metro_delay) < 100:
        # Fallback to whole dataset if metro data is too scarce
        df_metro_delay = df_delay.copy()
        
    # Categorical features mapping
    weather_list = sorted(df_metro_delay['weather_condition'].fillna('Clear').unique())
    weather_map = {w: i for i, w in enumerate(weather_list)}
    
    event_list = sorted(df_metro_delay['event_type'].fillna('None').unique())
    event_map = {e: i for i, e in enumerate(event_list)}
    
    df_metro_delay['weather_code'] = df_metro_delay['weather_condition'].fillna('Clear').map(weather_map)
    df_metro_delay['event_code'] = df_metro_delay['event_type'].fillna('None').map(event_map)
    
    delay_features = [
        'temperature_C', 'humidity_percent', 'wind_speed_kmh', 
        'precipitation_mm', 'traffic_congestion_index', 'holiday', 
        'peak_hour', 'weekday', 'weather_code', 'event_code'
    ]
    
    # Target 1: delayed (0/1 classification)
    # Target 2: actual_arrival_delay_min (regression)
    X_delay = df_metro_delay[delay_features].fillna(0)
    y_delay_class = df_metro_delay['delayed'].fillna(0).astype(int)
    y_delay_reg = df_metro_delay['actual_arrival_delay_min'].fillna(0)
    
    print(f"Delay dataset shape: {X_delay.shape}. Splitting dataset...")
    X_train_del, X_test_del, y_train_del_c, y_test_del_c = train_test_split(X_delay, y_delay_class, test_size=0.2, random_state=42)
    _, _, y_train_del_r, y_test_del_r = train_test_split(X_delay, y_delay_reg, test_size=0.2, random_state=42)
    
    print("Training Delay Classifier (RandomForestClassifier)...")
    delay_classifier = RandomForestClassifier(n_estimators=50, max_depth=10, random_state=42, n_jobs=-1)
    delay_classifier.fit(X_train_del, y_train_del_c)
    
    y_pred_del_c = delay_classifier.predict(X_test_del)
    del_acc = accuracy_score(y_test_del_c, y_pred_del_c)
    del_cm = confusion_matrix(y_test_del_c, y_pred_del_c).tolist()
    print(f"Delay Classifier Accuracy: {del_acc:.4f}")
    
    print("Training Delay Regressor (RandomForestRegressor)...")
    delay_regressor = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42, n_jobs=-1)
    delay_regressor.fit(X_train_del, y_train_del_r)
    
    y_pred_del_r = delay_regressor.predict(X_test_del)
    del_mae = mean_absolute_error(y_test_del_r, y_pred_del_r)
    del_rmse = np.sqrt(mean_squared_error(y_test_del_r, y_pred_del_r))
    print(f"Delay Regressor MAE: {del_mae:.4f}, RMSE: {del_rmse:.4f}")
    
    # Delay feature importances
    del_importances = delay_classifier.feature_importances_
    del_feat_imp = {feat: float(imp) for feat, imp in zip(delay_features, del_importances)}
    
    # Save delay models
    joblib.dump(delay_classifier, "ml/models/delay_classifier.pkl")
    joblib.dump(delay_regressor, "ml/models/delay_regressor.pkl")
    
    # ----------------------------------------------------
    # 4. SAVE ENCODERS AND METRICS TO JSON
    # ----------------------------------------------------
    metrics_payload = {
        "demand_model": {
            "mae": float(dem_mae),
            "rmse": float(dem_rmse),
            "feature_importance": dem_feat_imp
        },
        "anomaly_model": {
            "contamination": 0.05,
            "mean_decision_score": mean_score,
            "std_decision_score": std_score
        },
        "delay_model": {
            "accuracy": float(del_acc),
            "confusion_matrix": del_cm,
            "mae": float(del_mae),
            "rmse": float(del_rmse),
            "feature_importance": del_feat_imp
        },
        "mappings": {
            "stations": station_map,
            "remarks": remarks_map,
            "weather": weather_map,
            "events": event_map
        }
    }
    
    with open("ml/models/metrics.json", "w") as f:
        json.dump(metrics_payload, f, indent=4)
        
    print("ML Pipeline completed successfully. Serialized models and metrics saved in ml/models/")

if __name__ == "__main__":
    main()
