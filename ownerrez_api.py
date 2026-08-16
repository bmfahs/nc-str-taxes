"""
OwnerRez API Client for NC Tax Reporter

Fetches booking data directly from OwnerRez API, eliminating the need for
manual CSV exports. Since OwnerRez syncs with Airbnb (via Transaction Sync)
and VRBO, all bookings are available through a single API.

Setup:
1. Log into OwnerRez
2. Go to Settings > Advanced Tools > Developer/API Settings
3. Create a Personal Access Token
4. Add credentials to config.py

API Documentation: https://www.ownerrez.com/support/articles/api-overview
"""

import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, date
from typing import Optional
import json


class OwnerRezAPI:
    """Client for OwnerRez REST API"""
    
    # API endpoints
    BASE_URL_V1 = "https://app.ownerrez.com/api"
    BASE_URL_V2 = "https://api.ownerrez.com/v2"
    
    def __init__(self, email: str, token: str, property_id: Optional[str] = None):
        """
        Initialize OwnerRez API client.
        
        Args:
            email: OwnerRez account email
            token: Personal Access Token (starts with pt_)
            property_id: Optional property ID to filter bookings
        """
        self.email = email
        self.token = token
        self.property_id = property_id
        self.auth = HTTPBasicAuth(email, self.token)
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "NC-Tax-Reporter/1.0"
        }
    
    def _request(self, method: str, endpoint: str, version: int = 2, **kwargs) -> dict:
        """Make authenticated API request."""
        base_url = self.BASE_URL_V2 if version == 2 else self.BASE_URL_V1
        url = f"{base_url}/{endpoint}"
        
        response = requests.request(
            method,
            url,
            auth=self.auth,
            headers=self.headers,
            **kwargs
        )
        
        if response.status_code == 401:
            raise AuthenticationError("Invalid credentials. Check your email and API token.")
        elif response.status_code == 403:
            raise AuthenticationError("Access forbidden. Ensure your token has the required permissions.")
        elif response.status_code == 404:
            raise APIError(f"Endpoint not found: {endpoint}")
        elif response.status_code >= 400:
            raise APIError(f"API error {response.status_code}: {response.text}")
        
        return response.json()
    
    def get_properties(self) -> list:
        """Get list of all properties."""
        result = self._request("GET", "properties")
        return result.get("items", [])
    
    def get_bookings(self, 
                     arrive_from: Optional[date] = None,
                     arrive_to: Optional[date] = None,
                     since_utc: Optional[datetime] = None,
                     include_canceled: bool = False) -> list:
        """
        Get bookings within date range.
        
        Args:
            arrive_from: Filter by arrival date >= this date
            arrive_to: Filter by arrival date <= this date
            since_utc: Only return bookings modified since this datetime
            include_canceled: Whether to include canceled bookings
            
        Returns:
            List of booking objects
        """
        params = {}
        
        if arrive_from:
            params["arrive_from"] = arrive_from.isoformat()
        if arrive_to:
            params["arrive_to"] = arrive_to.isoformat()
        if since_utc:
            params["since_utc"] = since_utc.isoformat()
        if self.property_id:
            params["property_ids"] = self.property_id
        if not include_canceled:
            params["statuses"] = "confirmed,closed"  # Exclude canceled
        params["limit"] = 100  # Fetch up to 100 per page to minimize requests
            
        all_items = []
        endpoint = "bookings"
        
        while endpoint:
            result = self._request("GET", endpoint, params=params)
            items = result.get("items", [])
            all_items.extend(items)
            
            next_url = result.get("next_page_url")
            if next_url:
                # next_page_url comes back as e.g. /v2/bookings?property_ids=...&cursor=...
                # Remove the /v2/ prefix since _request adds BASE_URL_V2
                if next_url.startswith("/v2/"):
                    endpoint = next_url[4:]
                else:
                    endpoint = next_url
                # Params are already included in next_url
                params = None
            else:
                endpoint = None
                
        return all_items
    
    def get_booking_detail(self, booking_id: str) -> dict:
        """Get detailed information for a specific booking."""
        return self._request("GET", f"bookings/{booking_id}")
    
    def get_bookings_for_month(self, year: int, month: int) -> list:
        """
        Get all bookings where arrival falls within the specified month.
        
        This matches the tax reporting requirement of reporting based on
        check-in date, not checkout or booking date.
        
        Args:
            year: Year (e.g., 2025)
            month: Month (1-12)
            
        Returns:
            List of booking objects with financial details
        """
        # Calculate month boundaries
        from calendar import monthrange
        first_day = date(year, month, 1)
        last_day = date(year, month, monthrange(year, month)[1])
        
        # Fetch bookings
        bookings = self.get_bookings(
            arrive_from=first_day,
            arrive_to=last_day,
            include_canceled=False
        )
        
        # Since v2 API fetches all bookings (arrive_from unsupported), we must filter locally
        month_bookings = []
        for b in bookings:
            arrive_date = parse_date(b.get("arrival") or b.get("arrive"))
            if arrive_date and arrive_date.year == year and arrive_date.month == month:
                month_bookings.append(b)
        
        # Enrich with details if needed
        enriched = []
        for booking in month_bookings:
            # Basic booking info should include what we need
            # but we can fetch details if financial info is missing
            if not booking.get("charges") and not booking.get("total"):
                try:
                    detail = self.get_booking_detail(booking["id"])
                    booking.update(detail)
                except APIError:
                    pass  # Use basic info if detail fetch fails
            enriched.append(booking)
        
        return enriched


class AuthenticationError(Exception):
    """Raised when API authentication fails."""
    pass


class APIError(Exception):
    """Raised when API returns an error."""
    pass


def parse_ownerrez_bookings(bookings: list) -> list:
    """
    Parse OwnerRez API booking data into our standard format.
    
    Args:
        bookings: List of booking objects from OwnerRez API
        
    Returns:
        List of standardized booking dicts matching CSV parser output
    """
    parsed = []
    
    for booking in bookings:
        # Skip blocks and canceled bookings
        if booking.get('type') == 'block' or booking.get('status') == 'canceled':
            continue
            
        # Determine source from the booking
        source = determine_source(booking)
        
        # Extract financial information
        # OwnerRez stores amounts in different fields depending on source
        total = extract_total(booking)
        occupancy_taxes, host_collected = extract_occupancy_tax_info(booking)
        
        parsed.append({
            "confirmation": booking.get("confirmation_code") or booking.get("id", ""),
            "arrive": parse_date(booking.get("arrival") or booking.get("arrive")),
            "depart": parse_date(booking.get("departure") or booking.get("depart")),
            "total": total,
            "source": source,
            "occupancy_tax": occupancy_taxes,
            "host_collected_tax": host_collected,
            "property": booking.get("property", {}).get("name", ""),
            "guest_name": f"{booking.get('guest', {}).get('first_name', '')} {booking.get('guest', {}).get('last_name', '')}".strip(),
            "raw_data": booking  # Keep original for debugging
        })
    
    return parsed


def determine_source(booking: dict) -> str:
    """Determine booking source (Airbnb, VRBO, Direct, etc.)"""
    # Check various fields where source might be stored
    source = booking.get("source", "")
    channel = booking.get("channel", "")
    listing_site = booking.get("listing_site", "")
    
    # Normalize source name
    source_str = (source or channel or listing_site or "").upper()
    
    if "AIRBNB" in source_str:
        return "Airbnb"
    elif "VRBO" in source_str or "HOMEAWAY" in source_str:
        return "VRBO"
    elif "BOOKING" in source_str:
        return "Booking.com"
    elif source_str in ("", "DIRECT", "WEBSITE", "PHONE", "EMAIL"):
        return "Direct"
    else:
        return source or "Direct"


def extract_total(booking: dict) -> float:
    """Extract total booking amount (excluding taxes)."""
    # Prefer summing from charges directly to exclude taxes accurately
    charges = booking.get("charges", [])
    if charges:
        non_tax_total = 0.0
        for c in charges:
            # Exclude tax charges
            if str(c.get("type", "")).lower() == "tax":
                continue
            
            # Additional check: sometimes taxes might be placed as a surcharge
            c_desc = f"{c.get('name', '')} {c.get('description', '')}".lower()
            if "tax" in c_desc and ("occupancy" in c_desc or "sales" in c_desc or "lodging" in c_desc or "county" in c_desc):
                continue
                
            non_tax_total += parse_amount(c.get("amount", 0))
        
        if non_tax_total > 0:
            return non_tax_total

    # Try rent_total first as it generally doesn't include taxes
    if booking.get("rent_total"):
        return parse_amount(booking["rent_total"])
        
    # Try financial summary which separates rent and surcharges from taxes
    financial = booking.get("financial", {})
    if financial and ("rent" in financial or "surcharge" in financial):
        return parse_amount(financial.get("rent", 0)) + parse_amount(financial.get("surcharge", 0))

    # Fallback to total and subtract known taxes
    for field in ["total", "total_amount", "grand_total"]:
        if field in booking and booking[field]:
            total_val = parse_amount(booking[field])
            # Try to subtract occupancy tax if we have it
            for tax_field in ["occupancy_tax", "lodging_tax", "hotel_tax"]:
                if tax_field in booking and booking[tax_field]:
                    total_val -= parse_amount(booking[tax_field])
            return total_val
    
    return 0.0


def extract_occupancy_tax_info(booking: dict) -> tuple[float, bool]:
    """Extract occupancy tax amount and whether host collected it."""
    # Look in charges for tax items
    charges = booking.get("charges", [])
    tax_total = 0.0
    host_collected = False
    
    for charge in charges:
        charge_type = f"{charge.get('type', '')} {charge.get('name', '')} {charge.get('description', '')}".lower()
        if "tax" in charge_type and "occupancy" in charge_type:
            tax_total += parse_amount(charge.get("amount", 0))
            if not charge.get("is_channel_managed", True):
                host_collected = True
        elif "lodging tax" in charge_type:
            tax_total += parse_amount(charge.get("amount", 0))
            if not charge.get("is_channel_managed", True):
                host_collected = True
                
    if tax_total > 0:
        return tax_total, host_collected
        
    # Try direct field as fallback
    for field in ["occupancy_tax", "lodging_tax", "hotel_tax"]:
        if field in booking and booking[field]:
            return parse_amount(booking[field]), False
            
    return 0.0, False


def parse_amount(value) -> float:
    """Parse monetary amount from various formats."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Remove currency symbols and commas
        cleaned = value.replace("$", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    if isinstance(value, dict):
        # Handle {"amount": 100, "currency": "USD"} format
        return parse_amount(value.get("amount", 0))
    return 0.0


def parse_date(value) -> Optional[date]:
    """Parse date from various formats."""
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        # Try common formats
        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"]:
            try:
                return datetime.strptime(value[:10] if "T" in value else value, fmt.split("T")[0]).date()
            except ValueError:
                continue
    return None


def test_connection(email: str, token: str) -> tuple[bool, str]:
    """
    Test API connection and credentials.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        api = OwnerRezAPI(email, token)
        properties = api.get_properties()
        return True, f"Connected successfully. Found {len(properties)} properties."
    except AuthenticationError as e:
        return False, f"Authentication failed: {e}"
    except APIError as e:
        return False, f"API error: {e}"
    except requests.RequestException as e:
        return False, f"Connection error: {e}"


if __name__ == "__main__":
    # Quick test
    import sys
    if len(sys.argv) >= 3:
        email = sys.argv[1]
        token = sys.argv[2]
        success, msg = test_connection(email, token)
        print(msg)
        
        if success and len(sys.argv) >= 5:
            year = int(sys.argv[3])
            month = int(sys.argv[4])
            api = OwnerRezAPI(email, token)
            bookings = api.get_bookings_for_month(year, month)
            parsed = parse_ownerrez_bookings(bookings)
            print(f"\nFound {len(parsed)} bookings for {month}/{year}:")
            for b in parsed:
                print(f"  {b['confirmation']}: {b['source']} - ${b['total']:.2f}")
    else:
        print("Usage: python ownerrez_api.py <email> <token> [year] [month]")
