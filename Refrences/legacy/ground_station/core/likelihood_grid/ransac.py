import numpy as np
from scipy.optimize import least_squares
import random

def rssi_to_dist(rssi, A, n):
    """Convert RSSI to distance using Log-Distance Path Loss Model."""
    return 10**((A - rssi) / (10.0 * n))

def dist_to_rssi(dist, A, n):
    """Convert distance to RSSI using Log-Distance Path Loss Model."""
    return A - 10 * n * np.log10(dist + 1e-6)

def trilateration_error(target, coords, dists):
    """Residual function for trilateration optimization."""
    # target: [x, y]
    # coords: [[x1, y1], [x2, y2], ...]
    # dists: [d1, d2, ...]
    d_calc = np.sqrt(np.sum((coords - target)**2, axis=1))
    return d_calc - dists

class RANSACLocalization:
    """
    Random Sample Consensus for Emitter Localization.
    Robustly estimates target location by identifying and ignoring NLoS/multipath outliers.
    """
    def __init__(self, iterations=100, inlier_thresh_dbm=10.0, min_samples=3):
        self.iterations = iterations
        self.inlier_thresh_dbm = inlier_thresh_dbm
        self.min_samples = min_samples

    def fit(self, coords, rssis, params):
        """
        Robustly estimate the emitter location.
        
        Args:
            coords: (N, 2) numpy array of local [x, y] coordinates of the receiver.
            rssis: (N,) numpy array of RSSI measurements in dBm.
            params: Dictionary containing 'A' (RSSI at 1m) and 'n' (Path Loss Exponent).
            
        Returns:
            best_point: [x, y] of the best estimate, or None if failed.
            best_inliers: List of indices of inlier measurements.
        """
        A = params.get('A', -40.0)
        n = params.get('n', 2.5)
        
        dists = rssi_to_dist(rssis, A, n)
        
        best_point = None
        best_inliers = []
        max_inliers = 0
        
        num_points = len(coords)
        if num_points < self.min_samples:
            return None, []

        # Ensure random reproducibility if needed, but usually we want it dynamic
        for _ in range(self.iterations):
            # 1. Select random samples
            indices = random.sample(range(num_points), self.min_samples)
            sample_coords = coords[indices]
            sample_dists = dists[indices]
            
            # 2. Fit model (Trilateration) using non-linear least squares
            # Initial guess: mean of sample positions
            initial_guess = np.mean(sample_coords, axis=0)
            res = least_squares(trilateration_error, initial_guess, args=(sample_coords, sample_dists), 
                                xtol=1e-3, ftol=1e-3, max_nfev=100)
            
            if not res.success:
                continue
            
            candidate_point = res.x
            
            # 3. Evaluate inliers
            # Distance from candidate point to all receiver positions
            all_d_calc = np.sqrt(np.sum((coords - candidate_point)**2, axis=1))
            # Predicted RSSI from candidate point
            predicted_rssis = dist_to_rssi(all_d_calc, A, n)
            
            # Absolute error in dBm
            errors = np.abs(rssis - predicted_rssis)
            inliers = np.where(errors < self.inlier_thresh_dbm)[0]
            
            if len(inliers) > max_inliers:
                max_inliers = len(inliers)
                best_inliers = inliers
                best_point = candidate_point
                
                # If we have a very good consensus, we can stop early
                if max_inliers > 0.8 * num_points:
                    break
                    
        # 4. Refine estimate using all inliers
        if best_point is not None and len(best_inliers) >= self.min_samples:
            res = least_squares(trilateration_error, best_point, args=(coords[best_inliers], dists[best_inliers]),
                                xtol=1e-4, ftol=1e-4)
            if res.success:
                best_point = res.x
                
        if isinstance(best_inliers, list):
            return best_point, best_inliers
        return best_point, best_inliers.tolist()
