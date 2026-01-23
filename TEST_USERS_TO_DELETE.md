# Test Users Created by Agent

Based on the database query, these users appear to be test accounts created by an agent or for testing purposes:

## Obvious Test Users (should be deleted):
1. **test** (`test@example.com`) - Created: 2026-01-18 22:56:45
2. **devtest** (`devtest@example.com`) - Created: 2026-01-18 22:50:56
3. **dev** (`dev@example.com`) - Created: 2026-01-18 17:07:25

## Example Users (likely test data):
4. **jane** (`jane@example.com`) - Created: 2026-01-18 17:07:12
5. **john** (`john@example.com`) - Created: 2026-01-18 17:07:12

## Wallet Test Users (debug/test wallets):
6. **wallet_0x3174...62d6** (no email) - Created: 2026-01-19 18:00:35
7. **wallet_0xfina...l123** (no email) - Created: 2026-01-19 17:58:26
8. **wallet_0xdebu...g123** (no email) - Created: 2026-01-19 17:57:35
9. **wallet_0x1234...6789** (no email) - Created: 2026-01-19 17:56:13
10. **wallet_0x9876...3210** (no email) - Created: 2026-01-18 22:57:15

## Real Users (DO NOT DELETE):
- **admin** (`admin@metalayer.org`) - Admin account
- **daveed** (`daveed@bridgit.io`) - Your admin account
- **shiftshapr** (`shiftshapr@example.com`) - Editor role
- **wallet_0x1cA1...a26C** (`daveroom@gmail.com`) - Your Web3Auth account (Daveed Benjamin)
- **dave** (`dave@bridgit.io`) - Recent account, might be real

## SQL Commands to Delete Test Users:

```sql
-- Delete obvious test users
DELETE FROM user WHERE username IN ('test', 'devtest', 'dev', 'jane', 'john');

-- Delete wallet test users
DELETE FROM user WHERE username LIKE 'wallet_%' AND email IS NULL OR email = '';

-- Specific wallet deletions
DELETE FROM user WHERE username IN (
    'wallet_0x3174...62d6',
    'wallet_0xfina...l123',
    'wallet_0xdebu...g123',
    'wallet_0x1234...6789',
    'wallet_0x9876...3210'
);
```

## To Delete via Admin UI:
Once the delete buttons are working, click the trash icon next to each test user in the admin dashboard at `/admin/users/`.
