
import numpy as np
import math

class LikelihoodGrid:
    def __init__(self, origin_lat, origin_lon, width_m, height_m, resolution_m=1.0):
        self.origin_lat = origin_lat
        self.origin_lon = origin_lon
        self.width_m = width_m
        self.height_m = height_m
        self.resolution_m = resolution_m
        
        # Earth radius for conversions
        self.R = 6371000.0

        # Grid dimensions
        self.nx = int(np.ceil(width_m / resolution_m))
        self.ny = int(np.ceil(height_m / resolution_m))
        
        # Initialize Grid with zeros for accumulation
        self.grid_score = np.zeros((self.ny, self.nx))
        
        # Create coordinate grids for vectorized updates
        xs = np.linspace(0, (self.nx - 1) * resolution_m, self.nx)
        ys = np.linspace(0, (self.ny - 1) * resolution_m, self.ny)
        self.grid_x, self.grid_y = np.meshgrid(xs, ys)
        

    def latlon_to_xy(self, lat, lon):
        """Convert lat/lon to local x/y meters relative to origin."""
        dlat = np.radians(lat - self.origin_lat)
        dlon = np.radians(lon - self.origin_lon)
        lat0 = np.radians(self.origin_lat)
        
        x = dlon * self.R * np.cos(lat0)
        y = dlat * self.R
        return x, y
        
    def xy_to_latlon(self, x, y):
        """Convert local x/y meters to lat/lon."""
        lat0 = np.radians(self.origin_lat)
        dlat = y / self.R
        dlon = x / (self.R * np.cos(lat0))
        
        lat = self.origin_lat + np.degrees(dlat)
        lon = self.origin_lon + np.degrees(dlon)
        return lat, lon

    def update(self, meas_x, meas_y, rssi, params, weight=1.0):
        """
        Update grid using Gaussian Ring Accumulator.
        Score = exp(-(d_cell - d_exp)^2 / (2 * sigma^2))
        """
        n = params.get('n', 2.5)
        A = params.get('A', -40.0)
        sigma = params.get('sigma', 6.0)
        
        # 1. Calculate Expected Distance (Inverse Path Loss)
        # RSSI = A - 10n*log10(d) => log10(d) = (A - RSSI) / 10n
        d_exp = 10**((A - rssi) / (10.0 * n))
        
        # Dynamic Sigma: Uncertainty increases with distance
        # sigma_final = sigma * (1 + alpha * d_exp)
        alpha = params.get('alpha', 0.05) # Default 5% increase per meter if not specified? 
        # Actually user plan said: "sigma_dyn = sigma * (1 + alpha * d_exp)"
        # Let's default alpha to 0 for backward compat unless explicitly requested, 
        # but the prompt implies we *should* use it. Let's start with 0 unless passed.
        # Wait, the user asked to "Ensure grids are initialized...". 
        # Let's stick to the prompt: params.get('alpha', 0.0) to be safe, but I will enable it in the view.
        
        sigma_dyn = sigma
        if alpha > 0:
            sigma_dyn = sigma * (1.0 + alpha * d_exp)
        
        # 2. Distance from measurement to all cell centers
        dist_sq = (self.grid_x - meas_x)**2 + (self.grid_y - meas_y)**2
        d_cell = np.sqrt(dist_sq)
        
        # 3. Gaussian Score
        # Using a ring of probability around the measurement
        ring_score = np.exp(-((d_cell - d_exp)**2) / (2 * sigma_dyn**2))
        
        # 4. Accumulate
        self.grid_score += ring_score * weight

    def get_most_likely_point(self):
        """Find the (lat, lon) center of the cell with highest accumulated score."""
        flat_idx = np.argmax(self.grid_score)
        idx = np.unravel_index(flat_idx, self.grid_score.shape)
        y_idx, x_idx = idx
        
        x = x_idx * self.resolution_m
        y = y_idx * self.resolution_m
        
        return self.xy_to_latlon(x, y)

    def detect_peaks(self, max_peaks=5, min_dist_m=10.0):
        """
        Detect multiple local maxima (peaks) in the grid.
        Returns a list of dicts: [{'lat', 'lon', 'score', 'confidence'}]
        """
        from scipy.ndimage import maximum_filter, label
        
        # 1. Local maxima filter
        neighborhood_size = int(np.ceil(min_dist_m / self.resolution_m))
        data_max = maximum_filter(self.grid_score, size=neighborhood_size)
        maxima = (self.grid_score == data_max) & (self.grid_score > 0)
        
        # 2. Get coordinates and values of peaks
        y_coords, x_coords = np.where(maxima)
        scores = self.grid_score[y_coords, x_coords]
        
        peaks = []
        for y, x, score in zip(y_coords, x_coords, scores):
            lat, lon = self.xy_to_latlon(x * self.resolution_m, y * self.resolution_m)
            peaks.append({
                'lat': lat,
                'lon': lon,
                'score': float(score),
                'x_idx': x,
                'y_idx': y
            })
            
        # 3. Sort by score descending
        peaks = sorted(peaks, key=lambda p: p['score'], reverse=True)
        peaks = peaks[:max_peaks]

        if not peaks:
            return []

        # 4. Global Likelihood Analysis (Emitter Count Detection)
        # Intensity ratio between peaks
        max_score = peaks[0]['score']
        for p in peaks:
            p['confidence'] = p['score'] / max_score if max_score > 0 else 0
            
        return peaks

    def get_probability_map(self):
        """Return the accumulated score map."""
        return self.grid_score

    def get_grid_lines_latlon(self):
        """
        Return a list of polylines (list of [lat, lon] pairs) representing the grid mesh.
        Used for visualization.
        """
        lines = []
        
        # Vertical lines (constant x)
        ys = np.linspace(0, (self.ny - 1) * self.resolution_m, self.ny)
        y_min, y_max = ys[0], ys[-1]
        
        for i in range(self.nx + 1): # +1 to close the box
            x = i * self.resolution_m
            # Start and end of vertical line
            lat_start, lon_start = self.xy_to_latlon(x, y_min)
            lat_end, lon_end = self.xy_to_latlon(x, y_max)
            lines.append([[lat_start, lon_start], [lat_end, lon_end]])
            
        # Horizontal lines (constant y)
        xs = np.linspace(0, (self.nx - 1) * self.resolution_m, self.nx)
        x_min, x_max = xs[0], xs[-1]
        
        for j in range(self.ny + 1):
            y = j * self.resolution_m
            lat_start, lon_start = self.xy_to_latlon(x_min, y)
            lat_end, lon_end = self.xy_to_latlon(x_max, y)
            lines.append([[lat_start, lon_start], [lat_end, lon_end]])
            
        return lines
