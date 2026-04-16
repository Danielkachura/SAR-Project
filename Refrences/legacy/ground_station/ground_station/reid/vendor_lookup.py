"""
Vendor lookup from MAC address OUI (Organizationally Unique Identifier).
Maps MAC address prefixes to manufacturer names like Wireshark does.
"""
import pandas as pd


class VendorLookup:
    """Lookup vendor names from MAC addresses using OUI database."""
    
    def __init__(self):
        self._parser = None
        self._initialized = False
        
    def _ensure_initialized(self):
        """Lazy initialization of manuf parser."""
        if self._initialized:
            return
        
        try:
            import manuf
            self._parser = manuf.MacParser(update=False)  # Don't auto-update
            self._initialized = True
        except ImportError:
            print("Warning: 'manuf' library not installed. Vendor lookup disabled.")
            print("Install with: pip install manuf")
            self._initialized = True
        except Exception as e:
            print(f"Warning: Could not initialize vendor lookup: {e}")
            self._initialized = True
    
    def lookup(self, mac_address):
        """
        Get vendor name for a MAC address.
        
        Args:
            mac_address: MAC address string (any format: aa:bb:cc:dd:ee:ff, aa-bb-cc, etc)
            
        Returns:
            Vendor name string or None if not found
        """
        if not mac_address or pd.isna(mac_address):
            return None
        
        self._ensure_initialized()
        
        if self._parser is None:
            return None
        
        try:
            # manuf library handles various MAC formats
            result = self._parser.get_all(str(mac_address))
            if result and result.manuf:
                return result.manuf
        except Exception:
            pass
        
        return None
    
    def lookup_series(self, mac_series):
        """
        Lookup vendor names for a pandas Series of MAC addresses.
        
        Args:
            mac_series: pandas Series of MAC addresses
            
        Returns:
            pandas Series of vendor names
        """
        if mac_series is None or mac_series.empty:
            return pd.Series(dtype=str)
        
        return mac_series.apply(self.lookup)


# Global singleton instance
_vendor_lookup = VendorLookup()


def get_vendor(mac_address):
    """Get vendor name for a single MAC address."""
    return _vendor_lookup.lookup(mac_address)


def get_vendor_series(mac_series):
    """Get vendor names for a pandas Series of MAC addresses."""
    return _vendor_lookup.lookup_series(mac_series)
