import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from scipy import stats

# --- 1. DATA PRE-PROCESSING ENGINE ---
def load_and_prepare_data(csv_path):
    """
    Cleans the data and focuses on Set, Rarity, and Age (Generalization).
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Missing {csv_path}. Please run your scraper first.")

    df = pd.read_csv(csv_path)
    
    # Clean Prices and Dates
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
    df['Days Since Print'] = pd.to_numeric(df['Days Since Print'], errors='coerce')
    
    # Remove rows with missing critical data
    df = df.dropna(subset=['Price', 'Days Since Print', 'Rarity', 'Card Code'])

    # OUTLIER REMOVAL: Remove extreme price anomalies (Z-Score > 3)
    df = df[np.abs(stats.zscore(df['Price'])) < 3].copy()

    # FEATURE ENGINEERING: Extract Set Prefix (e.g., 'LOB' or 'STOR')
    # Refined regex to handle different card code formats found in your data
    df['Set_Prefix'] = df['Card Code'].str.extract(r'([A-Z]{3,4})')
    
    # CATEGORICAL ENCODING: We EXCLUDE 'Card Name' to prevent overfitting
    # This forces the model to learn via Rarity and Set Prefix
    df_encoded = pd.get_dummies(df, columns=['Rarity', 'Set_Prefix'], drop_first=True)
    
    # Define Target (y) and Features (X)
    # We drop metadata that isn't a numerical feature
    y = df_encoded['Price']
    X = df_encoded.drop(columns=['Price', 'Card Name', 'Card Code', 'Availability'])
    
    return train_test_split(X, y, test_size=0.2, random_state=42), X.columns, df

# --- 2. MULTI-MODEL COMPARISON ---
def evaluate_models(X_train, X_test, y_train, y_test):
    algorithms = {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42),
        "Gradient Boosting": GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, random_state=42)
    }
    
    performance = {}
    fitted_models = {}
    
    print(f"\n{'Algorithm':<20} | {'MAE':<10} | {'R2 Score':<10}")
    print("-" * 45)
    
    for name, model in algorithms.items():
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        
        mae = mean_absolute_error(y_test, preds)
        r2 = r2_score(y_test, preds)
        
        performance[name] = preds
        fitted_models[name] = model
        print(f"{name:<20} | ${mae:<9.2f} | {r2:<10.4f}")
    
    return performance, fitted_models

# --- 3. PERFORMANCE VISUALIZATION ---
def plot_results(y_test, performance):
    plt.figure(figsize=(10, 6))
    plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'k--', lw=2, label="Perfect Fit")
    
    for name, preds in performance.items():
        plt.scatter(y_test, preds, label=name, alpha=0.5)
    
    plt.title("Card Price Prediction (Generalization Mode)")
    plt.xlabel("Actual Price ($)")
    plt.ylabel("Predicted Price ($)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()

# --- 4. EXECUTION ---
if __name__ == "__main__":
    CSV_FILE = "card_data_final.csv"
    
    try:
        # Step 1: Prep Data (X_columns will be much smaller now)
        (X_train, X_test, y_train, y_test), features, original_df = load_and_prepare_data(CSV_FILE)
        print(f"Model Cleaned. Feature Count Reduced to: {len(features)}")
        
        # Step 2: Run Comparison
        results, models = evaluate_models(X_train, X_test, y_train, y_test)
        
        # Step 3: Diagnostic - See which specific cards are in the test set
        test_indices = X_test.index
        # Use .loc to match the shuffled indices back to the original labels
        test_comparison = original_df.loc[test_indices].copy()
        
        # Add the predictions
        test_comparison['Predicted'] = results['Gradient Boosting']
        
        print("\n--- Sample of Predictions (True Market Logic) ---")
        # Now we can safely see the names without an Index Error
        print(test_comparison[['Card Name', 'Card Code', 'Rarity', 'Price', 'Predicted']].head(15))
        # Step 4: Visualize
        plot_results(y_test, results)
        
    except Exception as e:
        print(f"Execution Error: {e}")