# API Trading

## Creating an API key
1. Go to Profile → API Management and create a key. Complete 2FA.
2. Choose permissions: read-only, spot trading, futures trading, or withdrawal
   (withdrawal permission also requires IP allowlisting).
3. Restrict the key to trusted IPs. Unrestricted keys that allow trading are
   automatically deleted after 90 days of inactivity for safety.

## Rate limits
- REST: request weight limit of 6,000 per minute per IP on spot; order
  placement limited to 100 orders per 10 seconds per account.
- WebSocket: 300 connections per attempt limit per 5 minutes per IP.
- Exceeding limits returns HTTP 429; repeated violations trigger an IP ban
  from 2 minutes up to 3 days (HTTP 418).

## Common errors
- `-1021 Timestamp out of recvWindow`: sync your server clock via NTP.
- `-2010 Insufficient balance`: order value exceeds free balance; check open
  orders locking funds.
- `-1013 Filter failure LOT_SIZE`: quantity violates the symbol's step size;
  fetch exchangeInfo for filters.
- `401 Unauthorized`: signature mismatch — verify the query string is signed
  with HMAC SHA256 using the secret key and parameters are in request order.

## Key security
Never share the secret key; it is shown once at creation. If leaked, delete
the key immediately — deleting takes effect instantly and cancels nothing on
open orders. Support cannot retrieve a lost secret key; create a new one.

## Testnet
A public testnet with free funds is available for both spot and futures for
development. Testnet order books are thin and prices diverge from production.
