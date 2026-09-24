# Fare Almanac

A single-page flight fare explorer. Open `index.html` in a browser; there is no build step.

- **Route fares:** compare every airline on a route (domestic or international). You get a 12-month fare calendar, the cheapest month, the cheapest departure weekday, a price-by-airline chart, and a "when to book" curve for any date.
- **Explore destinations:** rank all ~95 destinations from your home airport by lowest fare and cents per mile.
- Each date links to Google Flights, Kayak and Skyscanner for live prices.

## About the prices

Prices are **modeled estimates**, not live quotes. Live fare APIs (Amadeus, Duffel, Skyscanner) need API keys and a server, and they block direct calls from a web page. The model combines:

- great-circle distance and regional price levels
- each airline's price tier (legacy, low-cost, ultra-low-cost, long-haul budget) and its hub network, which decides nonstop vs. connecting
- seasonal demand by destination, US holidays, Lunar New Year and Golden Week
- day-of-week pricing and a booking-lead-time curve, assuming you book today
- optional checked-bag fees
