# Deposits and Withdrawals

## Crypto deposits
1. Go to Wallet → Deposit and select the asset.
2. Choose the correct network (e.g., BTC, ERC-20, BEP-20, TRC-20). Sending an
   asset on the wrong network can result in permanent loss.
3. Copy the deposit address (and memo/tag if shown — required for XRP, XLM,
   TON and several others; omitting the memo will delay or lose the deposit).
4. Deposits credit after the required network confirmations (e.g., 1 for BTC
   arrival display, 2 for full credit; 12 for ETH and ERC-20 tokens).

## Deposit not arrived
- Verify the transaction on a block explorer using the TxID.
- Confirm the network and memo/tag used match the deposit instructions.
- If the transaction is confirmed on-chain but not credited after 2 hours,
  submit a deposit inquiry with the TxID. Wrong-network self-service recovery
  is available for some pairs and carries a recovery fee.

## Fiat deposits
Supported channels vary by region: bank transfer (SEPA, SWIFT, FPS), debit or
credit card, and regulated third-party providers. Card deposits carry a fee of
roughly 1.8–2.0% depending on region. Bank transfer fees vary by channel and
currency; many SEPA transfers are free.

## Crypto withdrawals
1. Go to Wallet → Withdraw, select asset and network.
2. Paste the destination address; double-check the first and last 6 characters.
3. Withdrawals require passing 2FA and, for new withdrawal addresses, a
   24-hour address-allowlist hold if allowlisting is enabled.
4. Network fees are dynamic and displayed before confirmation.

## Withdrawal suspended or on hold
Withdrawals may be temporarily suspended for: recent password reset (24-hour
hold), recent device or 2FA change (24–48 hours), ongoing risk review, or
wallet maintenance on a specific network. Holds triggered by security changes
cannot be lifted early — this protects the account if credentials were stolen.

## Minimums and limits
Each asset has a minimum withdrawal amount and per-transaction cap shown on
the withdrawal page. Daily limits are set by verification level.
