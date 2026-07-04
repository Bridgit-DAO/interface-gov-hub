# Custodial BTC Provenance Signing

Gov Hub exposes one internal Canopi signing endpoint:

`POST /api/internal/custodial-btc/sign-provenance`

Auth uses the existing Canopi internal shared secret: `Authorization: Bearer $GOV_HUB_API_KEY`.

## Trust Model

Gov Hub provisions BIP86 Taproot custodial wallets and stores encrypted per-user leaf keys in `custodial_wallet`. The signing endpoint resolves a user by `govhubUserId`/`userId`, `web3authVerifierId`, or email, decrypts the user's stored key inside Gov Hub, verifies the key derives the stored and expected Taproot address, and returns a signature over Canopi's canonical provenance digest.

Private keys, WIFs, xprvs, seeds, and mnemonics never leave Gov Hub and must never be logged.

## Signature Method

The endpoint returns `method: btc_taproot_bip340_schnorr_sha256_digest`.

This is a BIP340 Schnorr signature over the 32-byte SHA-256 digest of Canopi's canonical provenance message. It is not a BIP322 Bitcoin message signature, and it is not Bitcoin transaction signing or broadcasting.

Canopi may send both `canonical` and `digest`; Gov Hub rejects the request if they do not match. `address` is treated as the expected Taproot address and protects against signing with the wrong user wallet.

`signedAt` is the time Gov Hub signed. `historicalRecordedAt`, when present, is copied from Canopi and represents the original record time for backfills or historical attestations.
