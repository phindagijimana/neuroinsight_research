# Licensing and Billing Operations Playbook (Phase 5)

This playbook defines day-2 operations for paid desktop licensing.

## Licensing Model Inputs

- signed license token (payload + signature)
- token expiry and optional grace policy
- plan tier and feature entitlements
- organization and seat constraints

## Operational Lifecycle

1. **Issue**
   - Generate signed token from licensing service
   - Deliver securely to customer account/contact
2. **Activate**
   - Customer imports token in desktop control center
   - Desktop validates schema, signature, and expiry
3. **Renew**
   - Issue new token before expiry
   - communicate renewal window and fallback behavior
4. **Revoke**
   - mark license as revoked in licensing backend
   - provide replacement token if needed

## Billing Touchpoints

- trial conversion date
- renewal reminders (30/14/7 days)
- payment-failure follow-up
- grace window start/end notifications

## Support Scenarios

- invalid token format: provide corrected token package
- signature mismatch: verify public key chain and token source
- expired token: issue renewal token or apply grace policy
- entitlement mismatch: reissue token with corrected features

## Audit and Compliance

- keep issuance/revocation audit logs
- maintain token templates and signing key rotation records
- verify least-privilege access for signing operations
