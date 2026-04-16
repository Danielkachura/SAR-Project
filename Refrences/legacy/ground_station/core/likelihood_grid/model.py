
import numpy as np

def path_loss_model(d, A, n):
    """
    Expected RSSI at distance d.
    r(d) = A - 10 * n * log10(d)
    """
    # Avoid log(0)
    d_safe = np.maximum(d, 0.1) 
    return A - 10 * n * np.log10(d_safe)

def calibrate(rssi_vals, dists):
    """
    Fit path loss model to data.
    Model: RSSI = A - 10 * n * log10(d)
    
    We fit: y = m * x + c
    Where:
      y = RSSI
      x = log10(d)
      m = -10 * n
      c = A
    
    Returns dictionary with n, A, sigma.
    """
    rssi_vals = np.array(rssi_vals)
    dists = np.array(dists)
    
    # Filter valid data: positive distances and finite RSSI
    mask = (dists > 0.1) & np.isfinite(rssi_vals)
    rssi_clean = rssi_vals[mask]
    dists_clean = dists[mask]
    
    # Default fallback if not enough data
    if len(rssi_clean) < 3:
        return {"n": 2.5, "A": -40.0, "sigma": 6.0}

    log_d = np.log10(dists_clean)
    
    # Linear regression using numpy
    # polyfit returns [slope, intercept] for degree 1
    slope, intercept = np.polyfit(log_d, rssi_clean, 1)
    
    # Derive model parameters
    # slope = -10 * n  => n = -slope / 10
    n = -slope / 10.0
    A = intercept
    
    # Calculate noise (sigma)
    predicted = A - 10 * n * log_d
    residuals = rssi_clean - predicted
    sigma = np.std(residuals)
    
    return {
        "n": float(n),
        "A": float(A),
        "sigma": float(sigma)
    }
